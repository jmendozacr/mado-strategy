"""Deliverable D: Recovery-to-Entry Analysis -- Phase 3's primary investigation.

H1: after a confirmed Stop Loss, price recovers the original entry level
with a frequency different from comparable market moments, controlling for
NY hour, volatility, and target distance.
H0: post-SL recovery shows no relevant difference from comparable controls.

Primary endpoint (pre-registered -- this entire module was written, and this
docstring fixed, BEFORE it was run against real data for the first time):

    P(recovery within 24 calendar hours | confirmed SL)
    vs.
    P(recovery within 24 calendar hours | matched control)

at a **95% CI** (not this lab's usual 90%, for this one endpoint per
explicit instruction), block bootstrap (instrument x ISO week), paired
against the matched control. "Relevant difference" is pre-declared here as
the 95% CI excluding zero AND the absolute point difference being at least
5 percentage points -- a modest, round, conservative bar chosen before
looking at any Phase-3 result, distinguishing "measurably nonzero" from
"an interesting magnitude" (deliberately not the same bar as "profitable").

The control's synthetic target is placed at `target_distance` -- the
matched real event's own ACTUAL distance from its executed exit price to
its entry price -- never assumed to be exactly 1R, since a gap fill can
make the two differ (`control/sampling.py::ControlEvent.target_distance`).

**This is NOT genuine out-of-sample validation.** The 75.4%/85.4%
(Phase 2) and corrected 1d/3d recovery figures were already observed before
this hypothesis was registered. Results here are classified as replication
/ exploratory evidence within a previously-examined 2015-2026 dataset, per
`docs/04-methodology-safeguards.md` -- never described with OOS-validation
language.
"""
from __future__ import annotations

import bisect
import datetime as dt
from dataclasses import dataclass

from core.candle import OHLCSeries

from behavior.post_stop_metrics import PHASE2_HORIZONS, compute_post_stop_behavior
from common.series_index import timestamps_for
from control.sampling import ControlEvent, period_bucket
from schema.events import (
    EventRecord,
    ExitReasonBasis,
    FeaturesAtStop,
    FeaturesPreEntry,
    Identification,
    Outcome,
    OriginalOperation,
)
from stats.bootstrap import block_bootstrap_paired_diff_ci, block_key

PRIMARY_HORIZON_LABEL = "1d"
PRIMARY_CI_LEVEL = 0.95
RELEVANT_DIFFERENCE_PP = 0.05  # 5 percentage points -- pre-declared, see module docstring


def recovery_control_to_event_record(control: ControlEvent, series: OHLCSeries) -> EventRecord:
    """Like `control.sampling.control_to_event_record`, but the synthetic
    'entry_price' (the level whose recovery we measure) sits `target_distance`
    away from the control's reference price -- not `risk_price` -- because
    this endpoint is specifically about the distance actually traveled to
    the real entry price, which a gap fill can make differ from the nominal
    risk."""
    timestamps = timestamps_for(series)
    idx = bisect.bisect_left(timestamps, control.control_ts)
    close_at_control = series.candles[idx].close
    bullish = control.direction == "bullish"
    entry_price = (
        close_at_control + control.target_distance if bullish else close_at_control - control.target_distance
    )
    take_profit = (
        entry_price + 2 * control.target_distance if bullish else entry_price - 2 * control.target_distance
    )

    identification = Identification(
        event_id=f"recovery:{control.control_id}", source_path="control:sampled", source_version="v2",
        instrument=control.instrument, session_label=control.origin_model,
        config_id="control", original_direction=control.direction,
    )
    operation = OriginalOperation(
        entry_price=entry_price, stop_loss=close_at_control, take_profit=take_profit,
        risk_price=control.target_distance, activation_ts=None, order_placed_ts=None,
        entry_ts=control.control_ts - dt.timedelta(hours=1), exit_ts=control.control_ts,
        exit_price=close_at_control, outcome=Outcome.LOSS, r_multiple=-1.0,
        exit_reason=None, exit_reason_basis=ExitReasonBasis.UNKNOWN,
        ambiguous_bar=False, gap_filled=False, has_partial_exit=False,
    )
    features_pre_entry = FeaturesPreEntry(
        feeder_ref_available_ts=None, activation_instant_ts=None, model1_available_ts=None,
        order_placed_ts=None, time_from_activation_to_order_s=None,
        planned_risk_price=control.target_distance, planned_reward_price=2 * control.target_distance,
        planned_rr=2.0,
    )
    features_at_stop = FeaturesAtStop(
        exit_ts=control.control_ts, exit_price=close_at_control, outcome=Outcome.LOSS, r_multiple=-1.0,
        speed_to_stop_s=None, ambiguous_bar=False, gap_filled=False,
    )
    return EventRecord(identification, operation, features_pre_entry, features_at_stop)


def _recovery_flag(behavior) -> float | None:
    if behavior.recovered_to_entry_price:
        return 1.0
    if behavior.censored:
        return None
    return 0.0


def _at_horizon(behaviors: list, horizon_label: str):
    return next(b for b in behaviors if b.horizon_label == horizon_label)


@dataclass
class RecoveryAnalysisResult:
    primary_endpoint: dict  # P(recovery_1d | SL) vs control, 95% CI
    secondary_by_horizon: dict  # descriptive only, 1h/4h/1d/3d
    time_to_recovery_quantiles_s: dict
    target_distance_in_atr_quantiles: dict
    cumulative_incidence: dict  # proportion recovered by each horizon (not independent draws across horizons -- same events)
    n_never_recovered_by_3d: int
    n_censored_by_3d: int
    gap_effect: dict  # recovery rate split by weekend/unexpected gap exposure
    by_instrument: dict
    by_origin_model: dict


def analyze_recovery(
    eligible: list[EventRecord],
    eligible_behaviors: dict[str, list],
    controls: list[ControlEvent],
    series_by_instrument: dict[str, OHLCSeries],
) -> RecoveryAnalysisResult:
    recovery_control_records = {
        c.matched_event_id: recovery_control_to_event_record(c, series_by_instrument[c.instrument])
        for c in controls
    }
    recovery_control_behaviors = {
        event_id: compute_post_stop_behavior(record, series_by_instrument[record.identification.instrument])
        for event_id, record in recovery_control_records.items()
    }

    def _paired_at(horizon_label: str) -> list[tuple[float, float, tuple]]:
        pairs = []
        for record in eligible:
            event_id = record.identification.event_id
            control_record = recovery_control_records.get(event_id)
            if control_record is None:
                continue
            sl_behaviors = eligible_behaviors.get(event_id)
            control_behaviors = recovery_control_behaviors.get(event_id)
            if sl_behaviors is None or control_behaviors is None:
                continue
            sl_flag = _recovery_flag(_at_horizon(sl_behaviors, horizon_label))
            control_flag = _recovery_flag(_at_horizon(control_behaviors, horizon_label))
            if sl_flag is None or control_flag is None:
                continue
            block = block_key(record.identification.instrument, record.operation.exit_ts)
            pairs.append((sl_flag, control_flag, block))
        return pairs

    proportion = lambda xs: sum(xs) / len(xs) if xs else float("nan")  # noqa: E731

    primary_pairs = _paired_at(PRIMARY_HORIZON_LABEL)
    primary = block_bootstrap_paired_diff_ci(primary_pairs, statistic=proportion, ci=PRIMARY_CI_LEVEL)
    primary["relevant_difference"] = (
        primary["ci_low"] is not None
        and (primary["ci_low"] > 0 or primary["ci_high"] < 0)
        and abs(primary["point_estimate"]) >= RELEVANT_DIFFERENCE_PP
    )

    secondary_by_horizon = {}
    cumulative_incidence = {}
    for label, _ in PHASE2_HORIZONS:
        pairs = _paired_at(label)
        diff = block_bootstrap_paired_diff_ci(pairs, statistic=proportion)
        secondary_by_horizon[label] = diff
        recovered_flags = [p[0] for p in pairs]
        cumulative_incidence[label] = proportion(recovered_flags) if recovered_flags else None

    time_to_recovery = [
        _at_horizon(eligible_behaviors[r.identification.event_id], "3d").time_to_entry_recovery_s
        for r in eligible
        if r.identification.event_id in eligible_behaviors
        and _at_horizon(eligible_behaviors[r.identification.event_id], "3d").recovered_to_entry_price
    ]
    time_to_recovery_quantiles_s = _quantiles(time_to_recovery)

    distance_in_atr = [
        c.target_distance / c.atr_at_matched_event
        for c in controls
        if c.atr_at_matched_event
    ]
    target_distance_in_atr_quantiles = _quantiles(distance_in_atr)

    behaviors_3d = [
        _at_horizon(eligible_behaviors[r.identification.event_id], "3d")
        for r in eligible if r.identification.event_id in eligible_behaviors
    ]
    n_never_recovered_by_3d = sum(1 for b in behaviors_3d if not b.recovered_to_entry_price and not b.censored)
    n_censored_by_3d = sum(1 for b in behaviors_3d if b.censored)

    gap_effect = {
        "weekend_gap_spanned": proportion([1.0 if b.recovered_to_entry_price else 0.0 for b in behaviors_3d if b.weekend_gap_spanned]),
        "no_weekend_gap": proportion([1.0 if b.recovered_to_entry_price else 0.0 for b in behaviors_3d if not b.weekend_gap_spanned]),
        "unexpected_gap_spanned": proportion([1.0 if b.recovered_to_entry_price else 0.0 for b in behaviors_3d if b.unexpected_gap_spanned]),
        "no_unexpected_gap": proportion([1.0 if b.recovered_to_entry_price else 0.0 for b in behaviors_3d if not b.unexpected_gap_spanned]),
    }

    by_instrument = _one_way(eligible, eligible_behaviors, lambda r: r.identification.instrument)
    by_origin_model = _one_way(eligible, eligible_behaviors, lambda r: r.identification.session_label)

    return RecoveryAnalysisResult(
        primary_endpoint=primary,
        secondary_by_horizon=secondary_by_horizon,
        time_to_recovery_quantiles_s=time_to_recovery_quantiles_s,
        target_distance_in_atr_quantiles=target_distance_in_atr_quantiles,
        cumulative_incidence=cumulative_incidence,
        n_never_recovered_by_3d=n_never_recovered_by_3d,
        n_censored_by_3d=n_censored_by_3d,
        gap_effect=gap_effect,
        by_instrument=by_instrument,
        by_origin_model=by_origin_model,
    )


def _quantiles(values: list[float], qs=(0.1, 0.25, 0.5, 0.75, 0.9)) -> dict:
    if not values:
        return {q: None for q in qs}
    ordered = sorted(values)
    n = len(ordered)
    return {q: ordered[min(int(q * n), n - 1)] for q in qs}


def _one_way(records, behaviors_by_id, key_fn) -> dict:
    groups: dict[str, list] = {}
    for record in records:
        groups.setdefault(key_fn(record), []).append(record)
    result = {}
    for group_value, group_records in groups.items():
        flags = [
            1.0 if _at_horizon(behaviors_by_id[r.identification.event_id], "1d").recovered_to_entry_price else 0.0
            for r in group_records
            if r.identification.event_id in behaviors_by_id
            and not _at_horizon(behaviors_by_id[r.identification.event_id], "1d").censored
        ]
        result[group_value] = {
            "n": len(flags),
            "p_recovery_1d": sum(flags) / len(flags) if flags else None,
        }
    return result
