"""Matched control-group construction (Unit C): is the post-SL behavior
measured in `behavior/post_stop_metrics.py` actually different from how
price behaves at an ordinary, comparable moment that never involved one of
this model's stop-losses?

Design (every decision below uses ONLY information available at or before
the control's own reference instant -- never a future trajectory):

- A control event borrows its (instrument, origin_model, direction,
  risk_price, target_distance) from exactly one real SL event it is matched
  to. All are pre-event-decided by construction (they describe the real
  event's own setup, not anything about the control point's future). The
  control's OWN identity is only its timestamp.
- **Phase-3 fix**: the control timestamp is drawn from the SAME stratum
  (instrument x PERIOD_BUCKET) as the real event, filtered to a comparable
  **NY wall-clock hour-of-day** (`NY_HOUR_TOLERANCE_HOURS = 1.0`, a fixed,
  pre-declared window -- see `common/ny_time.py`), THEN nearest-ATR-matched
  among that hour-filtered pool. Phase 2's `_candidate_pool` never applied
  the hour filter at all -- `session_label` (the real event's ORIGIN MODEL,
  1AM/9AM) was copied onto the control but never used to restrict which
  timestamps were eligible, so a 9AM-model stop could be compared against a
  control drawn from any hour of the day. `origin_model` (which signal
  produced the trade) and `actual_stop_time_ny` (when the stop itself
  executed, which can be hours after the model's own feeder-candle instant)
  are now tracked as separate fields precisely because they are not the
  same thing.
- Candidates within EXCLUSION_BUFFER of ANY real SL event of the same
  instrument are dropped first, to limit the same market episode
  contributing to both groups.
- Controls are measured with the EXACT SAME
  `behavior.post_stop_metrics.compute_post_stop_behavior` function used for
  real events (by wrapping each control in a minimal synthetic
  `EventRecord`), so the two populations are computed identically.

PERIOD_BUCKETS are predeclared (unchanged from Phase 2), before any Phase-3
comparison ran, as four roughly equal calendar spans covering the dataset's
known range (2015-2026).

Match quality is tiered and NEVER silently relaxed: `MATCHED` (a fresh,
not-yet-used candidate within the NY-hour window and all other criteria),
`MATCHED_WITH_REPLACEMENT` (every fresh candidate in that specific
stratum+hour-window was already used by an earlier real event, so an
already-used one is reused), or `UNMATCHED` (zero candidates -- fresh or
reused -- satisfy the NY-hour window + exclusion + stratum criteria at all;
the real event is reported, not silently dropped or given a worse match).

Determinism: every random draw goes through one `random.Random(seed)`
instance threaded explicitly through every call -- never the global
`random` module -- so a fixed seed always reproduces the same control set.
"""
from __future__ import annotations

import bisect
import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from core.candle import OHLCSeries

from behavior.post_stop_metrics import compute_atr_at_event
from common.ny_time import circular_hour_distance, ny_hour_of_day, ny_hours_of_day_bulk
from common.series_index import timestamps_for
from schema.events import (
    EventRecord,
    ExitReasonBasis,
    FeaturesAtStop,
    FeaturesPreEntry,
    Identification,
    Outcome,
    OriginalOperation,
)

EXCLUSION_BUFFER = timedelta(hours=4)
MIN_LOOKBACK_FOR_ATR = timedelta(hours=4)  # ATR_PERIOD(14) M15 bars ~= 3.5h; keep a safety margin
CANDIDATE_POOL_SIZE = 400  # per stratum x hour-window, before ATR nearest-matching
DEFAULT_SEED = 20261124  # the date this control design was first registered, not tuned post-hoc
NY_HOUR_TOLERANCE_HOURS = 1.0  # fixed, pre-declared matching window -- see module docstring
QUARTER_HOUR_STEPS = 96  # 24h x 4 quarters-per-hour, for the hour-bucket index

PERIOD_BUCKETS: tuple[tuple[str, int, int], ...] = (
    ("2015-2017", 2015, 2017),
    ("2018-2020", 2018, 2020),
    ("2021-2023", 2021, 2023),
    ("2024-2026", 2024, 2026),
)


class MatchTier(str, Enum):
    MATCHED = "matched"
    MATCHED_WITH_REPLACEMENT = "matched_with_replacement"
    UNMATCHED = "unmatched"


@dataclass(frozen=True)
class ControlEvent:
    control_id: str
    matched_event_id: str
    instrument: str
    origin_model: str  # the matched real event's generating model (1am/9am) -- NOT a time
    direction: str
    period_bucket: str
    control_ts: datetime
    risk_price: float
    target_distance: float  # abs(entry_price - exit_price) of the matched real event; may differ from risk_price under a gap fill
    atr_at_control: float | None
    atr_at_matched_event: float | None
    actual_stop_time_ny: float  # matched real event's NY hour-of-day
    control_reference_time_ny: float  # this control's own NY hour-of-day
    match_tier: MatchTier


@dataclass(frozen=True)
class UnmatchedEvent:
    event_id: str
    instrument: str
    period_bucket: str | None
    reason: str


@dataclass
class ControlSamplingResult:
    controls: list[ControlEvent]
    unmatched: list[UnmatchedEvent]


def period_bucket(ts: datetime) -> str | None:
    for label, start_year, end_year in PERIOD_BUCKETS:
        if start_year <= ts.year <= end_year:
            return label
    return None


def _real_event_timestamps_by_instrument(records: list[EventRecord]) -> dict[str, list[datetime]]:
    by_instrument: dict[str, list[datetime]] = {}
    for record in records:
        ts = record.operation.exit_ts
        if ts is None:
            continue
        by_instrument.setdefault(record.identification.instrument, []).append(ts)
    for timestamps in by_instrument.values():
        timestamps.sort()
    return by_instrument


def _is_excluded(ts: datetime, sorted_real_timestamps: list[datetime], buffer: timedelta) -> bool:
    idx = bisect.bisect_left(sorted_real_timestamps, ts)
    for neighbor_idx in (idx - 1, idx):
        if 0 <= neighbor_idx < len(sorted_real_timestamps):
            if abs(sorted_real_timestamps[neighbor_idx] - ts) < buffer:
                return True
    return False


def _quarter_hour_bucket(ny_hour: float) -> int:
    return int(round(ny_hour * 4)) % QUARTER_HOUR_STEPS


def _build_hour_buckets(
    series: OHLCSeries,
    bucket: tuple[str, int, int],
    excluded_timestamps: list[datetime],
    rng: random.Random,
    pool_size: int,
) -> dict[int, list[int]]:
    """All non-excluded candidate indices in `bucket`'s date range, grouped
    by their NY-local quarter-hour-of-day, each bucket shuffled (seeded) and
    capped at `pool_size`. Built once per stratum; every real event matched
    to that stratum then only pays an O(1) dict lookup per nearby
    quarter-hour key instead of re-scanning the whole range.

    The per-bucket cap and shuffle matter for two reasons: (1) without a cap,
    a 1-hour NY window over a multi-year bucket can still hold thousands of
    raw candidates, defeating `pool_size`'s purpose of bounding the matching
    cost and making true exhaustion (MATCHED_WITH_REPLACEMENT/UNMATCHED)
    unreachable in practice; (2) without a seeded shuffle, candidates within
    a bucket are kept in scan order, so an exact ATR tie (common on
    synthetic/flat data, and not impossible on real data either) would
    always resolve to the same index regardless of `seed` -- shuffling
    first makes `min(..., key=...)`'s tie-break seed-dependent too."""
    _, start_year, end_year = bucket
    start_ts = datetime(start_year, 1, 1)
    end_ts = datetime(end_year + 1, 1, 1)
    timestamps = timestamps_for(series)
    lo = bisect.bisect_left(timestamps, start_ts + MIN_LOOKBACK_FOR_ATR)
    hi = bisect.bisect_right(timestamps, end_ts)
    if hi <= lo:
        return {}

    candidate_indices = [
        idx for idx in range(lo, hi)
        if not _is_excluded(series.candles[idx].timestamp, excluded_timestamps, EXCLUSION_BUFFER)
    ]
    if not candidate_indices:
        return {}
    candidate_ts = [series.candles[idx].timestamp for idx in candidate_indices]
    ny_hours = ny_hours_of_day_bulk(candidate_ts)

    raw_buckets: dict[int, list[int]] = defaultdict(list)
    for idx, hour in zip(candidate_indices, ny_hours):
        raw_buckets[_quarter_hour_bucket(hour)].append(idx)

    buckets: dict[int, list[int]] = {}
    for key, indices in raw_buckets.items():
        rng.shuffle(indices)
        buckets[key] = indices[:pool_size]
    return buckets


def _gather_near_hour(hour_buckets: dict[int, list[int]], target_ny_hour: float) -> list[int]:
    target_key = _quarter_hour_bucket(target_ny_hour)
    tolerance_steps = int(round(NY_HOUR_TOLERANCE_HOURS * 4))
    gathered: list[int] = []
    for offset in range(-tolerance_steps, tolerance_steps + 1):
        gathered.extend(hour_buckets.get((target_key + offset) % QUARTER_HOUR_STEPS, []))
    return gathered


def sample_controls(
    records: list[EventRecord],
    series_by_instrument: dict[str, OHLCSeries],
    seed: int = DEFAULT_SEED,
    pool_size: int = CANDIDATE_POOL_SIZE,
) -> ControlSamplingResult:
    rng = random.Random(seed)
    real_timestamps_by_instrument = _real_event_timestamps_by_instrument(records)

    hour_bucket_cache: dict[tuple[str, str], dict[int, list[int]]] = {}
    # ATR for every candidate in a stratum is computed once and reused
    # across every real event matched to that stratum (Phase-2 perf fix,
    # preserved here).
    atr_cache: dict[tuple[str, str], dict[int, float | None]] = {}
    used_indices: dict[tuple[str, str], set[int]] = {}
    controls: list[ControlEvent] = []
    unmatched: list[UnmatchedEvent] = []

    for record in records:
        op = record.operation
        event_id = record.identification.event_id
        instrument = record.identification.instrument

        if op.exit_ts is None or op.risk_price in (None, 0.0):
            unmatched.append(UnmatchedEvent(event_id, instrument, None, "censored_or_invalid_risk"))
            continue

        bucket_label = period_bucket(op.exit_ts)
        if bucket_label is None:
            unmatched.append(UnmatchedEvent(event_id, instrument, None, "no_period_bucket"))
            continue
        bucket = next(b for b in PERIOD_BUCKETS if b[0] == bucket_label)
        series = series_by_instrument[instrument]

        cache_key = (instrument, bucket_label)
        if cache_key not in hour_bucket_cache:
            excluded = real_timestamps_by_instrument.get(instrument, [])
            hour_bucket_cache[cache_key] = _build_hour_buckets(series, bucket, excluded, rng, pool_size)
        hour_buckets = hour_bucket_cache[cache_key]

        actual_stop_time_ny = ny_hour_of_day(op.exit_ts)
        near_hour_indices = _gather_near_hour(hour_buckets, actual_stop_time_ny)
        if not near_hour_indices:
            unmatched.append(UnmatchedEvent(event_id, instrument, bucket_label, "no_candidates_in_ny_hour_window"))
            continue

        if cache_key not in atr_cache:
            atr_cache[cache_key] = {}
        atr_by_idx = atr_cache[cache_key]
        for idx in near_hour_indices:
            if idx not in atr_by_idx:
                atr_by_idx[idx] = compute_atr_at_event(series, series.candles[idx].timestamp)

        used = used_indices.setdefault(cache_key, set())
        fresh = [i for i in near_hour_indices if i not in used]
        if fresh:
            match_tier = MatchTier.MATCHED
            candidate_set = fresh
        else:
            match_tier = MatchTier.MATCHED_WITH_REPLACEMENT
            candidate_set = near_hour_indices

        atr_at_event = compute_atr_at_event(series, op.exit_ts)
        if atr_at_event is None:
            chosen_idx = rng.choice(candidate_set)
        else:
            def _atr_distance(idx: int) -> float:
                atr = atr_by_idx.get(idx)
                return float("inf") if atr is None else abs(atr - atr_at_event)

            chosen_idx = min(candidate_set, key=_atr_distance)

        used.add(chosen_idx)
        control_ts = series.candles[chosen_idx].timestamp
        atr_at_control = atr_by_idx.get(chosen_idx)
        target_distance = abs(op.entry_price - op.exit_price)

        controls.append(
            ControlEvent(
                control_id=f"control:{event_id}",
                matched_event_id=event_id,
                instrument=instrument,
                origin_model=record.identification.session_label,
                direction=record.identification.original_direction,
                period_bucket=bucket_label,
                control_ts=control_ts,
                risk_price=op.risk_price,
                target_distance=target_distance,
                atr_at_control=atr_at_control,
                atr_at_matched_event=atr_at_event,
                actual_stop_time_ny=actual_stop_time_ny,
                control_reference_time_ny=ny_hour_of_day(control_ts),
                match_tier=match_tier,
            )
        )
    return ControlSamplingResult(controls=controls, unmatched=unmatched)


def audit_match_quality(records_by_id: dict[str, EventRecord], controls: list[ControlEvent]) -> dict:
    """Deliverable C: do matched controls actually share the agreed
    characteristics (NY hour, volatility, risk distance, instrument, period,
    direction) with their real event, or only nominally?"""
    hour_diffs, atr_diffs, distance_ratios = [], [], []
    by_tier: dict[str, int] = defaultdict(int)
    by_instrument_mismatch = 0
    by_period_mismatch = 0
    by_direction_mismatch = 0

    for control in controls:
        by_tier[control.match_tier.value] += 1
        hour_diffs.append(
            circular_hour_distance(control.actual_stop_time_ny, control.control_reference_time_ny)
        )
        if control.atr_at_control is not None and control.atr_at_matched_event is not None:
            atr_diffs.append(abs(control.atr_at_control - control.atr_at_matched_event))
        matched = records_by_id.get(control.matched_event_id)
        if matched is None:
            continue
        if matched.identification.instrument != control.instrument:
            by_instrument_mismatch += 1
        if period_bucket(matched.operation.exit_ts) != control.period_bucket:
            by_period_mismatch += 1
        if matched.identification.original_direction != control.direction:
            by_direction_mismatch += 1

    n = len(controls)
    return {
        "n_controls": n,
        "by_match_tier": dict(by_tier),
        "ny_hour_diff_hours": {
            "mean": sum(hour_diffs) / len(hour_diffs) if hour_diffs else None,
            "max": max(hour_diffs) if hour_diffs else None,
            "within_tolerance_pct": (
                sum(1 for d in hour_diffs if d <= NY_HOUR_TOLERANCE_HOURS + 1e-9) / len(hour_diffs)
                if hour_diffs else None
            ),
        },
        "atr_abs_diff_mean": sum(atr_diffs) / len(atr_diffs) if atr_diffs else None,
        "instrument_mismatches": by_instrument_mismatch,
        "period_bucket_mismatches": by_period_mismatch,
        "direction_mismatches": by_direction_mismatch,
    }


def control_to_event_record(control: ControlEvent, series: OHLCSeries) -> EventRecord:
    """Wrap a ControlEvent in a minimal synthetic EventRecord so
    `behavior.post_stop_metrics.compute_post_stop_behavior` can measure it
    with the exact same code path used for real SL events. Uses
    `risk_price` (not `target_distance`) for the synthetic entry/stop/target
    construction, matching Phase 2's own convention so the general Atlas
    re-run stays comparable; the recovery-specific analysis
    (`behavior/recovery_analysis.py`) builds its own `target_distance`-based
    synthetic record instead, since that endpoint's whole point is the
    distance actually traveled to the real entry price, not the nominal
    risk.

    Phase-3.1 fix: the reference price is the reference bar's OWN OPEN, not
    its close. `control.control_ts` is that bar's open timestamp (the same
    convention `exit_ts` uses for a real SL event); using its close here
    would attribute a price not actually known until
    `control_ts + M15_DURATION` to an event timestamped at `control_ts` --
    exactly the Defect-B-shaped leak this module's own docstring warns
    about elsewhere, just not yet applied to this one spot. A real event's
    own `exit_price` is NEVER its exit bar's close either (see
    `detector/backtest/simulate.py::_resolve_level_exit` -- it is the
    pre-known stop/target level, or that bar's own OPEN under a gap): using
    this bar's open keeps the control causally equivalent to a real event,
    and needs no change to `compute_post_stop_behavior`'s existing
    `_bisect_after` boundary, which already starts post-event measurement
    at the NEXT bar for both groups identically."""
    timestamps = timestamps_for(series)
    idx = bisect.bisect_left(timestamps, control.control_ts)
    open_at_control = series.candles[idx].open
    bullish = control.direction == "bullish"
    entry_price = (
        open_at_control + control.risk_price if bullish else open_at_control - control.risk_price
    )
    take_profit = (
        entry_price + 2 * control.risk_price if bullish else entry_price - 2 * control.risk_price
    )

    identification = Identification(
        event_id=control.control_id, source_path="control:sampled", source_version="v3",
        instrument=control.instrument, session_label=control.origin_model,
        config_id="control", original_direction=control.direction,
    )
    operation = OriginalOperation(
        entry_price=entry_price, stop_loss=open_at_control, take_profit=take_profit,
        risk_price=control.risk_price, activation_ts=None, order_placed_ts=None,
        entry_ts=control.control_ts - timedelta(hours=1), exit_ts=control.control_ts,
        exit_price=open_at_control, outcome=Outcome.LOSS, r_multiple=-1.0,
        exit_reason=None, exit_reason_basis=ExitReasonBasis.UNKNOWN,
        ambiguous_bar=False, gap_filled=False, has_partial_exit=False,
    )
    features_pre_entry = FeaturesPreEntry(
        feeder_ref_available_ts=None, activation_instant_ts=None, model1_available_ts=None,
        order_placed_ts=None, time_from_activation_to_order_s=None,
        planned_risk_price=control.risk_price, planned_reward_price=2 * control.risk_price, planned_rr=2.0,
    )
    features_at_stop = FeaturesAtStop(
        exit_ts=control.control_ts, exit_price=open_at_control, outcome=Outcome.LOSS, r_multiple=-1.0,
        speed_to_stop_s=None, ambiguous_bar=False, gap_filled=False,
    )
    return EventRecord(identification, operation, features_pre_entry, features_at_stop)
