"""Richer post-stop-loss behavior metrics for Phase 2's Atlas.

Builds on `extract/post_stop_trajectory.py`'s bar-slicing (reused, not
duplicated) to compute the full Phase-2 metric set: raw max/min, MFE/MAE in
price/R/ATR, directional return, continuation-vs-reversal first-move
ordering, recovery to the original entry price, and weekend-gap detection.

Causality: the measurement baseline is each event's own `exit_price` (the
ACTUAL executed price, already gap-adjusted where relevant -- see
`eligibility/stop_eligibility.py`), and the first bar considered is strictly
AFTER `exit_ts` -- the exit bar's own M15 range is never used retrospectively
(reuses `extract/post_stop_trajectory.py`'s existing `bisect_right`
boundary). `first_actionable_ts` makes that boundary explicit for any later
hypothetical re-entry rule: `exit_ts` plus one M15 duration, i.e. the first
instant at which the exit bar itself is fully closed and known.

Pre-registered thresholds (fixed BEFORE any result was inspected, per
docs/04-methodology-safeguards.md's "hypotheses are registered before being
evaluated on reserved data" rule):

- CONTINUATION_REVERSAL_THRESHOLD_R = 0.25R -- the first-move label only
  fires once price has moved a quarter of the original risk in one
  direction; chosen as large enough to exceed typical FX spread/noise at
  this risk scale, small enough to catch early moves.
- ATR_PERIOD = 14 M15 bars, simple (non-Wilder-smoothed) average true range,
  computed strictly from bars at or before `exit_ts` -- never leaking
  post-event bars into the event's own volatility estimate.
- WEEKEND_GAP_MINUTES = 20 -- any gap between consecutive available M15 bars
  longer than this (more than one missing bar) is flagged, not silently
  absorbed into the time-to-X calculations.
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from core.candle import OHLCSeries

from common.series_index import timestamps_for
from extract.post_stop_trajectory import load_m15_series  # noqa: F401 -- re-exported for callers
from schema.events import EventRecord

CONTINUATION_REVERSAL_THRESHOLD_R = 0.25
ATR_PERIOD = 14
WEEKEND_GAP_MINUTES = 20
M15_DURATION = timedelta(minutes=15)

# Phase 2's own horizon set (1h/4h/1d/3d), per the user's explicit spec --
# intentionally NOT the same tuple as extract/post_stop_trajectory.py's
# Phase-1 DEFAULT_HORIZONS (4h/1d/3d), which stays frozen/unchanged so
# Phase-1's own tests keep passing untouched.
PHASE2_HORIZONS: tuple[tuple[str, timedelta], ...] = (
    ("1h", timedelta(hours=1)),
    ("4h", timedelta(hours=4)),
    ("1d", timedelta(days=1)),
    ("3d", timedelta(days=3)),
)


@dataclass
class PostStopBehavior:
    event_id: str
    horizon_label: str
    horizon_ts: datetime
    first_actionable_ts: datetime
    bars_available: int
    censored: bool
    weekend_gap_spanned: bool

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


def compute_atr_at_event(series: OHLCSeries, event_ts: datetime, period: int = ATR_PERIOD) -> float | None:
    """Simple ATR over the `period` M15 bars at or before `event_ts` --
    exclusively pre-event information, never leaking the future."""
    timestamps = timestamps_for(series)
    end_index = bisect.bisect_right(timestamps, event_ts)  # exclusive upper bound, bars <= event_ts
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

    start_index = _bisect_after(series, exit_ts)
    event_id = record.identification.event_id

    if start_index >= len(series.candles):
        return [
            PostStopBehavior(
                event_id=event_id, horizon_label=label, horizon_ts=exit_ts + delta,
                first_actionable_ts=first_actionable_ts, bars_available=0, censored=True,
                weekend_gap_spanned=False,
                raw_max_price=None, raw_min_price=None, price_at_horizon=None,
                directional_return_price=None, directional_return_r=None,
                mfe_price=None, mae_price=None, mfe_r=None, mae_r=None,
                atr_at_event=atr_at_event, mfe_atr=None, mae_atr=None,
                first_move_direction=None, first_move_ts=None,
                continuation_before_first_reversal_r=None,
                recovered_to_entry_price=False, time_to_entry_recovery_s=None,
            )
            for label, delta in horizons
        ]

    best_favorable = 0.0
    worst_adverse = 0.0
    raw_max = series.candles[start_index].high
    raw_min = series.candles[start_index].low
    weekend_gap_spanned = False
    first_move_direction: str | None = None
    first_move_ts: datetime | None = None
    continuation_before_first_reversal_r: float | None = None
    recovered_to_entry_price = False
    time_to_entry_recovery_s: float | None = None
    last_close = exit_price
    bars_seen = 0
    idx = start_index
    prev_ts = exit_ts
    last_bar_ts = series.candles[-1].timestamp

    outcomes: list[PostStopBehavior] = []
    for label, delta in horizons:
        horizon_ts = exit_ts + delta
        while idx < len(series.candles) and series.candles[idx].timestamp <= horizon_ts:
            candle = series.candles[idx]
            if (candle.timestamp - prev_ts) > (M15_DURATION + timedelta(minutes=WEEKEND_GAP_MINUTES)):
                weekend_gap_spanned = True
            prev_ts = candle.timestamp

            raw_max = max(raw_max, candle.high)
            raw_min = min(raw_min, candle.low)
            if bullish:
                favorable_excursion = candle.high - exit_price
                adverse_excursion = exit_price - candle.low
                touched_entry = candle.high >= entry_price
            else:
                favorable_excursion = exit_price - candle.low
                adverse_excursion = candle.high - exit_price
                touched_entry = candle.low <= entry_price

            best_favorable = max(best_favorable, favorable_excursion)
            worst_adverse = max(worst_adverse, adverse_excursion)

            if not recovered_to_entry_price and touched_entry:
                recovered_to_entry_price = True
                time_to_entry_recovery_s = (candle.timestamp - exit_ts).total_seconds()

            if first_move_direction is None and risk_price:
                # Continuation (the adverse/SL-extending side) is checked
                # FIRST: if a single bar's range crosses both thresholds at
                # once (unresolvable intrabar order, same class of ambiguity
                # as eligibility's `ambiguous_bar`), the tie resolves against
                # the more "interesting" finding (a tradeable reversal),
                # mirroring this project's existing pessimistic convention
                # (detector's own SL-wins-ties rule; Phase 1's MFE/MAE
                # "conservative call") rather than overstating reversal
                # evidence.
                if worst_adverse / risk_price >= CONTINUATION_REVERSAL_THRESHOLD_R:
                    first_move_direction = "continuation"  # extending the move that caused the SL
                    first_move_ts = candle.timestamp
                elif best_favorable / risk_price >= CONTINUATION_REVERSAL_THRESHOLD_R:
                    first_move_direction = "reversal"  # back toward the original direction
                    first_move_ts = candle.timestamp
                    continuation_before_first_reversal_r = worst_adverse / risk_price

            last_close = candle.close
            bars_seen += 1
            idx += 1

        censored = last_bar_ts < horizon_ts
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
            )
        )
    return outcomes
