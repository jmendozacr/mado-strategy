"""Matched control-group construction (Unit C): is the post-SL behavior
measured in `behavior/post_stop_metrics.py` actually different from how
price behaves at an ordinary, comparable moment that never involved one of
this model's stop-losses?

Design (every decision below uses ONLY information available at or before
the control's own reference instant -- never a future trajectory):

- A control event borrows its (instrument, session, direction, risk_price)
  from exactly one real SL event it is matched to. Those four fields are all
  pre-event-decided by construction (they describe the real event's own
  setup, not anything about the control point's future). The control's OWN
  identity is only its timestamp.
- The control timestamp is drawn from the SAME stratum (instrument, session,
  direction, PERIOD_BUCKET -- see below) as the real event, from a random
  candidate pool of that instrument's M15 bars, nearest-ATR-matched (ATR
  computed causally, strictly from bars at/before the candidate instant --
  reuses `behavior.post_stop_metrics.compute_atr_at_event`) against the real
  event's own ATR at its stop.
- Candidates within EXCLUSION_BUFFER of ANY real SL event of the same
  instrument are dropped first, to limit the same market episode
  contributing to both groups.
- Controls are measured with the EXACT SAME
  `behavior.post_stop_metrics.compute_post_stop_behavior` function used for
  real events (by wrapping each control in a minimal synthetic
  `EventRecord`), so the two populations are computed identically and are
  directly comparable -- no separate, possibly-inconsistent implementation.

PERIOD_BUCKETS are predeclared here, before any comparison in this phase was
run, as four roughly equal calendar spans covering the dataset's known range
(2015-2026) -- not chosen to maximize or hide any difference.

Determinism: every random draw goes through one `random.Random(seed)`
instance threaded explicitly through every call -- never the global
`random` module -- so a fixed seed always reproduces the same control set.
"""
from __future__ import annotations

import bisect
import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from core.candle import OHLCSeries

from behavior.post_stop_metrics import compute_atr_at_event
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
CANDIDATE_POOL_SIZE = 400  # per stratum, before ATR nearest-matching
DEFAULT_SEED = 20261124  # the date this control design was registered, not tuned post-hoc

PERIOD_BUCKETS: tuple[tuple[str, int, int], ...] = (
    ("2015-2017", 2015, 2017),
    ("2018-2020", 2018, 2020),
    ("2021-2023", 2021, 2023),
    ("2024-2026", 2024, 2026),
)


@dataclass(frozen=True)
class ControlEvent:
    control_id: str
    matched_event_id: str
    instrument: str
    session_label: str
    direction: str
    period_bucket: str
    control_ts: datetime
    risk_price: float
    atr_at_control: float | None
    atr_at_matched_event: float | None


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


def _candidate_pool(
    series: OHLCSeries,
    bucket: tuple[str, int, int],
    excluded_timestamps: list[datetime],
    rng: random.Random,
    pool_size: int,
) -> list[int]:
    label, start_year, end_year = bucket
    start_ts = datetime(start_year, 1, 1)
    end_ts = datetime(end_year + 1, 1, 1)
    timestamps = timestamps_for(series)
    lo = bisect.bisect_left(timestamps, start_ts + MIN_LOOKBACK_FOR_ATR)
    hi = bisect.bisect_right(timestamps, end_ts)
    if hi <= lo:
        return []
    all_indices = list(range(lo, hi))
    rng.shuffle(all_indices)
    pool: list[int] = []
    for idx in all_indices:
        if len(pool) >= pool_size:
            break
        if not _is_excluded(series.candles[idx].timestamp, excluded_timestamps, EXCLUSION_BUFFER):
            pool.append(idx)
    return pool


def sample_controls(
    records: list[EventRecord],
    series_by_instrument: dict[str, OHLCSeries],
    seed: int = DEFAULT_SEED,
    pool_size: int = CANDIDATE_POOL_SIZE,
) -> list[ControlEvent]:
    rng = random.Random(seed)
    real_timestamps_by_instrument = _real_event_timestamps_by_instrument(records)

    pool_cache: dict[tuple[str, str], list[int]] = {}
    # Each pool candidate's own ATR is computed ONCE per stratum and reused
    # across every real event matched to that stratum (hundreds of real
    # events can share a stratum) -- recomputing it per-event would be
    # O(events_in_stratum * pool_size) redundant ATR calls at Phase-2 scale.
    pool_atr_cache: dict[tuple[str, str], dict[int, float | None]] = {}
    used_indices: dict[str, set[int]] = {}
    controls: list[ControlEvent] = []

    for record in records:
        op = record.operation
        if op.exit_ts is None or op.risk_price in (None, 0.0):
            continue  # censored or invalid-risk events are not matchable

        instrument = record.identification.instrument
        bucket_label = period_bucket(op.exit_ts)
        if bucket_label is None:
            continue
        bucket = next(b for b in PERIOD_BUCKETS if b[0] == bucket_label)
        series = series_by_instrument[instrument]

        atr_at_event = compute_atr_at_event(series, op.exit_ts)

        cache_key = (instrument, bucket_label)
        if cache_key not in pool_cache:
            excluded = real_timestamps_by_instrument.get(instrument, [])
            pool = _candidate_pool(series, bucket, excluded, rng, pool_size)
            pool_cache[cache_key] = pool
            pool_atr_cache[cache_key] = {
                idx: compute_atr_at_event(series, series.candles[idx].timestamp) for idx in pool
            }
        pool = pool_cache[cache_key]
        atr_by_idx = pool_atr_cache[cache_key]
        used = used_indices.setdefault(cache_key, set())
        available = [i for i in pool if i not in used]
        if not available:
            available = pool  # pool exhausted for this stratum -- fall back to sampling with replacement

        if atr_at_event is None or not available:
            if not available:
                continue
            chosen_idx = rng.choice(available)
        else:
            def _atr_distance(idx: int) -> float:
                atr = atr_by_idx.get(idx)
                return float("inf") if atr is None else abs(atr - atr_at_event)

            chosen_idx = min(available, key=_atr_distance)

        used.add(chosen_idx)
        control_ts = series.candles[chosen_idx].timestamp
        atr_at_control = compute_atr_at_event(series, control_ts)

        controls.append(
            ControlEvent(
                control_id=f"control:{record.identification.event_id}",
                matched_event_id=record.identification.event_id,
                instrument=instrument,
                session_label=record.identification.session_label,
                direction=record.identification.original_direction,
                period_bucket=bucket_label,
                control_ts=control_ts,
                risk_price=op.risk_price,
                atr_at_control=atr_at_control,
                atr_at_matched_event=atr_at_event,
            )
        )
    return controls


def control_to_event_record(control: ControlEvent, series: OHLCSeries) -> EventRecord:
    """Wrap a ControlEvent in a minimal synthetic EventRecord so
    `behavior.post_stop_metrics.compute_post_stop_behavior` can measure it
    with the exact same code path used for real SL events."""
    timestamps = timestamps_for(series)
    idx = bisect.bisect_left(timestamps, control.control_ts)
    close_at_control = series.candles[idx].close
    bullish = control.direction == "bullish"
    entry_price = (
        close_at_control + control.risk_price if bullish else close_at_control - control.risk_price
    )
    take_profit = (
        entry_price + 2 * control.risk_price if bullish else entry_price - 2 * control.risk_price
    )

    identification = Identification(
        event_id=control.control_id, source_path="control:sampled", source_version="v1",
        instrument=control.instrument, session_label=control.session_label,
        config_id="control", original_direction=control.direction,
    )
    operation = OriginalOperation(
        entry_price=entry_price, stop_loss=close_at_control, take_profit=take_profit,
        risk_price=control.risk_price, activation_ts=None, order_placed_ts=None,
        entry_ts=control.control_ts - timedelta(hours=1), exit_ts=control.control_ts,
        exit_price=close_at_control, outcome=Outcome.LOSS, r_multiple=-1.0,
        exit_reason=None, exit_reason_basis=ExitReasonBasis.UNKNOWN,
        ambiguous_bar=False, gap_filled=False, has_partial_exit=False,
    )
    features_pre_entry = FeaturesPreEntry(
        feeder_ref_available_ts=None, activation_instant_ts=None, model1_available_ts=None,
        order_placed_ts=None, time_from_activation_to_order_s=None,
        planned_risk_price=control.risk_price, planned_reward_price=2 * control.risk_price, planned_rr=2.0,
    )
    features_at_stop = FeaturesAtStop(
        exit_ts=control.control_ts, exit_price=close_at_control, outcome=Outcome.LOSS, r_multiple=-1.0,
        speed_to_stop_s=None, ambiguous_bar=False, gap_filled=False,
    )
    return EventRecord(identification, operation, features_pre_entry, features_at_stop)
