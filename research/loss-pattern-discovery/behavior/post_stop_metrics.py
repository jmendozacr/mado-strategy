"""Richer post-stop-loss behavior metrics for the Atlas.

Builds on `extract/post_stop_trajectory.py`'s bar-slicing (reused, not
duplicated) to compute: raw max/min, MFE/MAE in price/R/ATR, directional
return, continuation-vs-reversal first-move ordering, recovery to the
original entry price, and gap/censoring classification.

Causality (Phase 3 fixes three defects found by direct code review of the
Phase-2 version -- see docs/13-phase3-corrections-report.md for the full
root-cause writeup):

- **Defect A (fixed)**: `raw_max_price`/`raw_min_price` used to be seeded
  from the first post-exit candle UNCONDITIONALLY, before checking whether
  that candle even belonged to the horizon being measured -- a weekend-gap
  candle landing just past a short horizon's own boundary could leak its
  high/low into that horizon's result. They now start `None` and are only
  set from a candle that is actually included in the window below.
- **Defect B (fixed)**: a candle's `timestamp` is its OPEN instant (MT5
  convention, already relied on by this repo's own causal-lookahead-audit
  fixes); its high/low/close are not fully known until it CLOSES, at
  `timestamp + M15_DURATION`. The old inclusion test was
  `candle.timestamp <= horizon_ts`, which could use a candle's own
  not-yet-closed OHLC up to ~15 minutes before it was actually knowable.
  The test is now `candle.timestamp + M15_DURATION <= horizon_ts` --
  a candle only counts toward a horizon once it has fully closed by that
  horizon's boundary. The same fix is applied to `compute_atr_at_event`'s
  pre-event lookback, which had the identical leak on the exit bar itself.
- **Defect C (fixed)**: `censored` now means ONLY "the dataset itself ran
  out before this horizon's boundary" (`idx` reached the end of `series`
  AND the last bar actually used closed before `horizon_ts`) -- never a
  legitimate weekend/holiday closure, which is fully observed (we know
  nothing moved, because nothing could trade) and never flagged censored.
  `weekend_gap_spanned` and `unexpected_gap_spanned` are reported
  separately and are informational, not censoring.

MFE/MAE convention: measured relative to the ORIGINAL trade's direction
(MAE = continuation of the move that caused the SL; MFE = reversal back
toward the original direction), in price, in R (of the original risk), and
in ATR (14-bar M15 ATR, causal). They accumulate across increasing
horizons.

Pre-registered thresholds (fixed before any result was inspected):

- CONTINUATION_REVERSAL_THRESHOLD_R = 0.25R.
- ATR_PERIOD = 14 M15 bars, simple (non-Wilder) average true range.
- GAP_TOLERANCE_MINUTES = 20 -- any gap longer than this between
  consecutive available bars is classified via `classify_gap` as either an
  ordinary weekend/holiday closure or an unexpected gap.
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass
from datetime import datetime, timedelta

from core.candle import OHLCSeries

from common.series_index import timestamps_for
from extract.post_stop_trajectory import load_m15_series  # noqa: F401 -- re-exported for callers
from schema.events import EventRecord

CONTINUATION_REVERSAL_THRESHOLD_R = 0.25
ATR_PERIOD = 14
GAP_TOLERANCE_MINUTES = 20
M15_DURATION = timedelta(minutes=15)

# Phase 2's own horizon set (1h/4h/1d/3d) -- intentionally NOT the same
# tuple as extract/post_stop_trajectory.py's Phase-1 DEFAULT_HORIZONS
# (4h/1d/3d), which stays frozen/unchanged so Phase-1's own tests keep
# passing untouched.
PHASE2_HORIZONS: tuple[tuple[str, timedelta], ...] = (
    ("1h", timedelta(hours=1)),
    ("4h", timedelta(hours=4)),
    ("1d", timedelta(days=1)),
    ("3d", timedelta(days=3)),
)


def classify_gap(prev_ts: datetime, candle_ts: datetime) -> str:
    """"none" | "weekend_closure" | "unexpected_gap". A gap is a
    weekend/holiday closure only if it starts on a Friday and lasts between
    40 and 60 hours (FX's ordinary Friday-evening-to-Sunday-evening
    closure, in UTC/broker time); any other gap longer than
    GAP_TOLERANCE_MINUTES is "unexpected" -- a simple, pre-declared
    heuristic, not a full holiday calendar, so a genuine holiday closure
    that doesn't match this exact pattern is conservatively flagged
    unexpected rather than silently absorbed."""
    gap = candle_ts - prev_ts
    if gap <= M15_DURATION + timedelta(minutes=GAP_TOLERANCE_MINUTES):
        return "none"
    if prev_ts.weekday() == 4 and timedelta(hours=40) <= gap <= timedelta(hours=60):
        return "weekend_closure"
    return "unexpected_gap"


@dataclass
class PostStopBehavior:
    event_id: str
    horizon_label: str
    horizon_ts: datetime
    first_actionable_ts: datetime
    bars_available: int
    censored: bool  # true data exhaustion only -- see module docstring, Defect C
    weekend_gap_spanned: bool
    unexpected_gap_spanned: bool

    raw_max_price: float | None
    raw_min_price: float | None
    price_at_horizon: float | None
    directional_return_price: float | None  # relative to the ORIGINAL trade direction
    directional_return_r: float | None

    mfe_price: float | None
    mae_price: float | None
    mfe_r: float | None
    mae_r: float | None
    atr_at_event: float | None
    mfe_atr: float | None
    mae_atr: float | None

    first_move_direction: str | None  # "continuation" | "reversal" | None
    first_move_ts: datetime | None
    continuation_before_first_reversal_r: float | None

    recovered_to_entry_price: bool
    time_to_entry_recovery_s: float | None
    # Section-5 executable-entry distinction: contact vs. causal confirmation
    # vs. first actionable instant are tracked separately so a later,
    # dedicated re-entry analysis never conflates "price touched the level"
    # with "a new order could have filled there".
    recovery_touch_bar_open: datetime | None  # the touch candle's own open time (A: historical contact)
    recovery_confirmed_at: datetime | None  # touch_bar_open + M15_DURATION (B: causally confirmed)
    recovery_first_actionable_at: datetime | None  # earliest a new order could react (C) -- == recovery_confirmed_at at M15 granularity
    recovery_gap: bool  # the touch candle's own OPEN was already past entry_price -- a gap through the level, not a clean touch
    recovery_reference_price: float | None  # the level that was recovered to (entry_price), only once confirmed


def compute_atr_at_event(series: OHLCSeries, event_ts: datetime, period: int = ATR_PERIOD) -> float | None:
    """Simple ATR over the `period` M15 bars fully closed strictly before
    `event_ts` -- exclusively pre-event information. Phase-3 fix: the
    upper bound used to be `bisect_right(timestamps, event_ts)`, which
    could include the bar AT event_ts itself -- using that bar's `close`
    even though, per Defect B, it is not actually known until
    `event_ts + M15_DURATION`. The bound is now `event_ts - M15_DURATION`,
    i.e. only bars that have themselves fully closed by `event_ts`."""
    timestamps = timestamps_for(series)
    end_index = bisect.bisect_right(timestamps, event_ts - M15_DURATION)
    start_index = end_index - period
    if start_index < 1:  # need a previous close for every true-range term
        return None
    true_ranges = []
    for i in range(start_index, end_index):
        candle = series.candles[i]
        prev_close = series.candles[i - 1].close
        true_range = max(
            candle.high - candle.low,
            abs(candle.high - prev_close),
            abs(candle.low - prev_close),
        )
        true_ranges.append(true_range)
    if not true_ranges:
        return None
    return sum(true_ranges) / len(true_ranges)


def _bisect_after(series: OHLCSeries, ts: datetime) -> int:
    return bisect.bisect_right(timestamps_for(series), ts)


def _empty_behavior(event_id: str, exit_ts: datetime, first_actionable_ts: datetime,
                     atr_at_event: float | None, horizons) -> list[PostStopBehavior]:
    return [
        PostStopBehavior(
            event_id=event_id, horizon_label=label, horizon_ts=exit_ts + delta,
            first_actionable_ts=first_actionable_ts, bars_available=0, censored=True,
            weekend_gap_spanned=False, unexpected_gap_spanned=False,
            raw_max_price=None, raw_min_price=None, price_at_horizon=None,
            directional_return_price=None, directional_return_r=None,
            mfe_price=None, mae_price=None, mfe_r=None, mae_r=None,
            atr_at_event=atr_at_event, mfe_atr=None, mae_atr=None,
            first_move_direction=None, first_move_ts=None,
            continuation_before_first_reversal_r=None,
            recovered_to_entry_price=False, time_to_entry_recovery_s=None,
            recovery_touch_bar_open=None, recovery_confirmed_at=None,
            recovery_first_actionable_at=None, recovery_gap=False, recovery_reference_price=None,
        )
        for label, delta in horizons
    ]


def compute_post_stop_behavior(
    record: EventRecord,
    series: OHLCSeries,
    horizons: tuple[tuple[str, timedelta], ...] = PHASE2_HORIZONS,
) -> list[PostStopBehavior]:
    op = record.operation
    exit_ts = op.exit_ts
    exit_price = op.exit_price
    if exit_ts is None or exit_price is None:
        raise ValueError(
            f"{record.identification.event_id}: exit_ts/exit_price missing -- "
            "cannot reconstruct post-stop behavior for a censored (open) event"
        )

    bullish = record.identification.original_direction == "bullish"
    risk_price = op.risk_price if op.risk_price else None
    atr_at_event = compute_atr_at_event(series, exit_ts)
    first_actionable_ts = exit_ts + M15_DURATION
    entry_price = op.entry_price
    event_id = record.identification.event_id

    start_index = _bisect_after(series, exit_ts)
    if start_index >= len(series.candles):
        return _empty_behavior(event_id, exit_ts, first_actionable_ts, atr_at_event, horizons)

    last_bar_availability = series.candles[-1].timestamp + M15_DURATION

    best_favorable = 0.0
    worst_adverse = 0.0
    raw_max: float | None = None
    raw_min: float | None = None
    weekend_gap_spanned = False
    unexpected_gap_spanned = False
    first_move_direction: str | None = None
    first_move_ts: datetime | None = None
    continuation_before_first_reversal_r: float | None = None
    recovered_to_entry_price = False
    time_to_entry_recovery_s: float | None = None
    recovery_touch_bar_open: datetime | None = None
    recovery_confirmed_at: datetime | None = None
    recovery_gap = False
    last_close = exit_price
    last_known_ts = exit_ts
    bars_seen = 0
    idx = start_index
    prev_ts = exit_ts

    outcomes: list[PostStopBehavior] = []
    for label, delta in horizons:
        horizon_ts = exit_ts + delta
        while idx < len(series.candles) and (series.candles[idx].timestamp + M15_DURATION) <= horizon_ts:
            candle = series.candles[idx]
            gap_kind = classify_gap(prev_ts, candle.timestamp)
            if gap_kind == "weekend_closure":
                weekend_gap_spanned = True
            elif gap_kind == "unexpected_gap":
                unexpected_gap_spanned = True
            prev_ts = candle.timestamp

            if raw_max is None:
                raw_max, raw_min = candle.high, candle.low
            else:
                raw_max = max(raw_max, candle.high)
                raw_min = min(raw_min, candle.low)

            if bullish:
                favorable_excursion = candle.high - exit_price
                adverse_excursion = exit_price - candle.low
                touched_entry = candle.high >= entry_price
                gapped_through_entry = candle.open >= entry_price
            else:
                favorable_excursion = exit_price - candle.low
                adverse_excursion = candle.high - exit_price
                touched_entry = candle.low <= entry_price
                gapped_through_entry = candle.open <= entry_price

            best_favorable = max(best_favorable, favorable_excursion)
            worst_adverse = max(worst_adverse, adverse_excursion)

            if not recovered_to_entry_price and touched_entry:
                recovered_to_entry_price = True
                recovery_touch_bar_open = candle.timestamp
                recovery_confirmed_at = candle.timestamp + M15_DURATION
                recovery_gap = gapped_through_entry
                time_to_entry_recovery_s = (recovery_confirmed_at - exit_ts).total_seconds()

            if first_move_direction is None and risk_price:
                # Continuation (adverse) checked first: an unresolvable
                # same-bar tie on both thresholds resolves pessimistically,
                # mirroring this project's existing SL-wins-ties convention
                # rather than overstating reversal evidence.
                if worst_adverse / risk_price >= CONTINUATION_REVERSAL_THRESHOLD_R:
                    first_move_direction = "continuation"
                    first_move_ts = candle.timestamp
                elif best_favorable / risk_price >= CONTINUATION_REVERSAL_THRESHOLD_R:
                    first_move_direction = "reversal"
                    first_move_ts = candle.timestamp
                    continuation_before_first_reversal_r = worst_adverse / risk_price

            last_close = candle.close
            last_known_ts = candle.timestamp + M15_DURATION
            bars_seen += 1
            idx += 1

        # True data exhaustion only (Defect C): we ran out of the SERIES
        # itself before reaching horizon_ts. A legitimate weekend/holiday
        # gap that merely straddles horizon_ts, with more real data later
        # in the file, is fully observed -- idx has not reached the end.
        censored = (idx >= len(series.candles)) and (last_known_ts < horizon_ts)

        directional_return_price = (last_close - exit_price) if bullish else (exit_price - last_close)
        outcomes.append(
            PostStopBehavior(
                event_id=event_id,
                horizon_label=label,
                horizon_ts=horizon_ts,
                first_actionable_ts=first_actionable_ts,
                bars_available=bars_seen,
                censored=censored,
                weekend_gap_spanned=weekend_gap_spanned,
                unexpected_gap_spanned=unexpected_gap_spanned,
                raw_max_price=raw_max,
                raw_min_price=raw_min,
                price_at_horizon=last_close,
                directional_return_price=directional_return_price,
                directional_return_r=(directional_return_price / risk_price) if risk_price else None,
                mfe_price=best_favorable,
                mae_price=worst_adverse,
                mfe_r=(best_favorable / risk_price) if risk_price else None,
                mae_r=(worst_adverse / risk_price) if risk_price else None,
                atr_at_event=atr_at_event,
                mfe_atr=(best_favorable / atr_at_event) if atr_at_event else None,
                mae_atr=(worst_adverse / atr_at_event) if atr_at_event else None,
                first_move_direction=first_move_direction,
                first_move_ts=first_move_ts,
                continuation_before_first_reversal_r=continuation_before_first_reversal_r,
                recovered_to_entry_price=recovered_to_entry_price,
                time_to_entry_recovery_s=time_to_entry_recovery_s,
                recovery_touch_bar_open=recovery_touch_bar_open,
                recovery_confirmed_at=recovery_confirmed_at,
                recovery_first_actionable_at=recovery_confirmed_at,
                recovery_gap=recovery_gap,
                recovery_reference_price=entry_price if recovered_to_entry_price else None,
            )
        )
    return outcomes
