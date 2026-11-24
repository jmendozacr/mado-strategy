"""Deliverables B/C/D: Post-Stop-Loss Behavior Atlas, Matched Control
Comparison, and stratified breakdowns -- descriptive and comparative only
("Esta fase es exclusivamente descriptiva y comparativa"). No strategy
design, no entry optimization, no model training happens here.

Scope of the eligible population: CONFIRMED_STOP + STOP_AFTER_PARTIAL events
(`eligibility/stop_eligibility.py`). AMBIGUOUS_STOP events run through the
exact same pipeline but are reported separately, as a sensitivity check
only -- never pooled into the main Atlas numbers.

Stratification is one-way only (by instrument, by session/model, by
direction, by period bucket -- each alone), plus the pooled-overall result.
Deliberately NOT a full cross-product grid: the brief explicitly asked this
phase to avoid combinatorial subgroup search.

MIN_HEADLINE_N = 30 is declared here, before any stratum's actual sample
size was inspected: a group below this is still reported in full (n, point
estimate, CI), but flagged `small_sample=True` rather than treated as solid
evidence, per "no presentes porcentajes como evidencia solida" for small
groups.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Callable

LAB_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = LAB_ROOT.parent.parent
for _path in (LAB_ROOT, REPO_ROOT / "detector"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from behavior.post_stop_metrics import PHASE2_HORIZONS, compute_post_stop_behavior  # noqa: E402
from control.sampling import control_to_event_record, period_bucket, sample_controls  # noqa: E402
from eligibility.stop_eligibility import StopEligibility, classify_all  # noqa: E402
from extract.from_causal_lookahead_audit import extract  # noqa: E402
from extract.post_stop_trajectory import load_m15_series  # noqa: E402
from schema.events import EventRecord, Outcome  # noqa: E402
from stats.bootstrap import block_bootstrap_ci, block_bootstrap_paired_diff_ci, block_key, median, quantiles

MIN_HEADLINE_N = 30
INSTRUMENTS = ("EURUSD", "USDCAD", "AUDUSD")


def split_by_eligibility(records: list[EventRecord]) -> dict[str, list[EventRecord]]:
    results = classify_all(records)
    eligible, ambiguous = [], []
    for record in records:
        result = results.get(record.identification.event_id)
        if result is None:  # a win -- out of this taxonomy entirely
            continue
        if result.category in (StopEligibility.CONFIRMED_STOP, StopEligibility.STOP_AFTER_PARTIAL):
            eligible.append(record)
        elif result.category is StopEligibility.AMBIGUOUS_STOP:
            ambiguous.append(record)
        # OPEN_CENSORED events are neither -- they have no exit to measure a trajectory from.
    return {"eligible": eligible, "ambiguous": ambiguous}


def compute_behaviors(records: list[EventRecord], series_by_instrument: dict) -> dict[str, list]:
    behaviors: dict[str, list] = {}
    for record in records:
        series = series_by_instrument[record.identification.instrument]
        try:
            behaviors[record.identification.event_id] = compute_post_stop_behavior(record, series)
        except ValueError:
            continue  # censored (missing exit_ts/exit_price) -- excluded from trajectory measurement
    return behaviors


def _at_horizon(behaviors: list, horizon_label: str):
    return next(b for b in behaviors if b.horizon_label == horizon_label)


def _resolved_indicator(behavior, target_label: str) -> float | None:
    """1.0 if this behavior's first move was `target_label`; 0.0 if the
    first move resolved to something else OR the full horizon was observed
    with no threshold ever crossed (a confirmed absence); None if the
    horizon was censored before any threshold could have been crossed --
    excluded from the statistic entirely, never counted as a 0."""
    if behavior.first_move_direction == target_label:
        return 1.0
    if behavior.first_move_direction is not None or behavior.censored is False:
        return 0.0
    return None


def _proportion(values: list[float]) -> float:
    return sum(values) / len(values) if values else float("nan")


def _bootstrap_metric(
    records: list[EventRecord], behaviors_by_id: dict, horizon_label: str,
    value_fn: Callable, statistic: Callable = median,
) -> dict:
    values_with_blocks = []
    for record in records:
        behaviors = behaviors_by_id.get(record.identification.event_id)
        if behaviors is None:
            continue
        behavior = _at_horizon(behaviors, horizon_label)
        value = value_fn(behavior)
        if value is None:
            continue
        values_with_blocks.append((value, block_key(record.identification.instrument, record.operation.exit_ts)))
    result = block_bootstrap_ci(values_with_blocks, statistic=statistic)
    result["small_sample"] = result["n"] < MIN_HEADLINE_N
    return result


def summarize_group(records: list[EventRecord], behaviors_by_id: dict, horizon_label: str) -> dict:
    n = len(records)
    mae_r = _bootstrap_metric(records, behaviors_by_id, horizon_label, lambda b: b.mae_r)
    mfe_r = _bootstrap_metric(records, behaviors_by_id, horizon_label, lambda b: b.mfe_r)
    directional_return_r = _bootstrap_metric(
        records, behaviors_by_id, horizon_label, lambda b: b.directional_return_r
    )
    p_continuation = _bootstrap_metric(
        records, behaviors_by_id, horizon_label,
        lambda b: _resolved_indicator(b, "continuation"), statistic=_proportion,
    )
    p_reversal = _bootstrap_metric(
        records, behaviors_by_id, horizon_label,
        lambda b: _resolved_indicator(b, "reversal"), statistic=_proportion,
    )
    p_recovered = _bootstrap_metric(
        records, behaviors_by_id, horizon_label,
        lambda b: 1.0 if b.recovered_to_entry_price else 0.0, statistic=_proportion,
    )
    n_censored = sum(
        1 for r in records
        if r.identification.event_id in behaviors_by_id
        and _at_horizon(behaviors_by_id[r.identification.event_id], horizon_label).censored
    )
    n_weekend_gap = sum(
        1 for r in records
        if r.identification.event_id in behaviors_by_id
        and _at_horizon(behaviors_by_id[r.identification.event_id], horizon_label).weekend_gap_spanned
    )
    return {
        "n": n,
        "mae_r_median": mae_r,
        "mfe_r_median": mfe_r,
        "directional_return_r_median": directional_return_r,
        "p_continuation": p_continuation,
        "p_reversal": p_reversal,
        "p_recovered_to_entry": p_recovered,
        "pct_censored": n_censored / n if n else None,
        "pct_weekend_gap_spanned": n_weekend_gap / n if n else None,
    }


def compare_to_controls(
    records: list[EventRecord], behaviors_by_id: dict,
    control_records_by_matched_id: dict[str, EventRecord], control_behaviors_by_id: dict,
    horizon_label: str,
) -> dict:
    mae_pairs, continuation_pairs = [], []
    for record in records:
        event_id = record.identification.event_id
        control_record = control_records_by_matched_id.get(event_id)
        if control_record is None:
            continue
        sl_behaviors = behaviors_by_id.get(event_id)
        control_behaviors = control_behaviors_by_id.get(control_record.identification.event_id)
        if sl_behaviors is None or control_behaviors is None:
            continue
        sl_b = _at_horizon(sl_behaviors, horizon_label)
        control_b = _at_horizon(control_behaviors, horizon_label)
        block = block_key(record.identification.instrument, record.operation.exit_ts)
        if sl_b.mae_r is not None and control_b.mae_r is not None:
            mae_pairs.append((sl_b.mae_r, control_b.mae_r, block))

        sl_flag = _resolved_indicator(sl_b, "continuation")
        control_flag = _resolved_indicator(control_b, "continuation")
        if sl_flag is not None and control_flag is not None:
            continuation_pairs.append((sl_flag, control_flag, block))

    mae_diff = block_bootstrap_paired_diff_ci(mae_pairs, statistic=median)
    mae_diff["small_sample"] = mae_diff["n"] < MIN_HEADLINE_N
    cont_diff = block_bootstrap_paired_diff_ci(continuation_pairs, statistic=_proportion)
    cont_diff["small_sample"] = cont_diff["n"] < MIN_HEADLINE_N
    return {"mae_r_median_diff_sl_minus_control": mae_diff, "p_continuation_diff_sl_minus_control": cont_diff}


def run_atlas() -> dict:
    records = extract(REPO_ROOT)
    split = split_by_eligibility(records)
    eligible, ambiguous = split["eligible"], split["ambiguous"]

    series_by_instrument = {instrument: load_m15_series(instrument, _data_dir()) for instrument in INSTRUMENTS}

    eligible_behaviors = compute_behaviors(eligible, series_by_instrument)
    ambiguous_behaviors = compute_behaviors(ambiguous, series_by_instrument)

    controls = sample_controls(eligible, series_by_instrument)
    control_records = [control_to_event_record(c, series_by_instrument[c.instrument]) for c in controls]
    control_records_by_matched_id = {c.matched_event_id: cr for c, cr in zip(controls, control_records)}
    control_behaviors = compute_behaviors(control_records, series_by_instrument)

    one_way_groupers = {
        "instrument": lambda r: r.identification.instrument,
        "session_label": lambda r: r.identification.session_label,
        "original_direction": lambda r: r.identification.original_direction,
        "period_bucket": lambda r: period_bucket(r.operation.exit_ts),
    }

    atlas: dict = {"overall": {}, "by_dimension": {}, "control_comparison": {}, "ambiguous_sensitivity": {}}
    for horizon_label, _ in PHASE2_HORIZONS:
        atlas["overall"][horizon_label] = summarize_group(eligible, eligible_behaviors, horizon_label)
        atlas["control_comparison"][horizon_label] = compare_to_controls(
            eligible, eligible_behaviors, control_records_by_matched_id, control_behaviors, horizon_label
        )
        atlas["ambiguous_sensitivity"][horizon_label] = summarize_group(
            ambiguous, ambiguous_behaviors, horizon_label
        )
        for dim_name, key_fn in one_way_groupers.items():
            groups: dict[str, list[EventRecord]] = {}
            for record in eligible:
                groups.setdefault(key_fn(record), []).append(record)
            atlas["by_dimension"].setdefault(dim_name, {})[horizon_label] = {
                group_value: summarize_group(group_records, eligible_behaviors, horizon_label)
                for group_value, group_records in groups.items()
            }

    return {
        "atlas": atlas,
        "n_eligible": len(eligible),
        "n_ambiguous": len(ambiguous),
        "n_controls": len(controls),
    }


def _data_dir():
    import config
    return config.resolve_data_dir()


def main() -> dict:
    result = run_atlas()
    artifacts_dir = LAB_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    (artifacts_dir / "phase2_atlas.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"n_eligible={result['n_eligible']} n_ambiguous={result['n_ambiguous']} n_controls={result['n_controls']}")
    return result


if __name__ == "__main__":
    main()
