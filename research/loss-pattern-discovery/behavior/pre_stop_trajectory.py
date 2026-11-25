"""Pre-SL trajectory reconstruction (Phase 4, Layer B): what happened from
entry to a CONFIRMED Stop Loss -- for `eligibility.stop_eligibility`'s
`CONFIRMED_STOP`/`STOP_AFTER_PARTIAL` events only.

Causality: the entry bar and the exit (SL) bar each have an unknown
intrabar order relative to the trade's own fill/stop instant -- using
either bar's own high/low as "pre-SL favorable/adverse movement" would
silently assume an intrabar sequence M15 cannot resolve (the same class of
ambiguity `ambiguous_bar` already names for SL-vs-TP ties, applied here to
entry-vs-SL instead). The PRIMARY reconstruction therefore only uses bars
STRICTLY BETWEEN the entry bar and the exit bar (both excluded). If there
are zero such bars (the SL fires on the entry bar itself, or on the very
next bar), the path is marked `AMBIGUOUS`/`INSUFFICIENT` and the primary
MFE/MAE are `None` -- never fabricated as 0. Two separate, clearly-labeled
sensitivity variants (`mfe_including_entry_bar_r`, `mfe_including_exit_bar_r`)
report the alternative without letting it contaminate the primary number.
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass
from datetime import datetime

from core.candle import OHLCSeries

from behavior.post_stop_metrics import CONTINUATION_REVERSAL_THRESHOLD_R
from common.series_index import timestamps_for
from schema.events import EventRecord


class PathIntegrity:
    RECONSTRUCTIBLE = "reconstructible"
    AMBIGUOUS = "ambiguous"  # exactly one bar between entry and exit is unusable, but duration > 1 bar
    INSUFFICIENT = "insufficient"  # entry and exit are the same or adjacent bar -- no observable path at all


@dataclass
class PreStopTrajectory:
    event_id: str
    integrity: str
    n_observable_bars: int
    duration_bars: int
    duration_s: float | None
    time_activation_to_exit_s: float | None

    mfe_pre_sl_price: float | None
    mfe_pre_sl_r: float | None
    mfe_pre_sl_atr: float | None
    mae_pre_sl_price: float | None
    mae_pre_sl_atr: float | None

    had_material_favorable_excursion: bool | None  # None unless integrity == RECONSTRUCTIBLE
    retracement_from_best_favorable_price: float | None
    pct_bars_closed_favorable: float | None
    pct_bars_closed_adverse: float | None
    avg_adverse_speed_price_per_bar: float | None

    # Sensitivity-only alternates -- never the primary number, always reported separately.
    mfe_including_entry_bar_r: float | None
    mfe_including_exit_bar_r: float | None


def _window_mfe_mae(series: OHLCSeries, start_idx: int, end_idx_exclusive: int, entry_price: float, bullish: bool):
    if start_idx >= end_idx_exclusive or start_idx < 0:
        return None, None
    best_favorable = 0.0
    worst_adverse = 0.0
    for candle in series.candles[start_idx:end_idx_exclusive]:
        if bullish:
            favorable = candle.high - entry_price
            adverse = entry_price - candle.low
        else:
            favorable = entry_price - candle.low
            adverse = candle.high - entry_price
        best_favorable = max(best_favorable, favorable)
        worst_adverse = max(worst_adverse, adverse)
    return best_favorable, worst_adverse


def compute_pre_stop_trajectory(
    record: EventRecord, series: OHLCSeries, atr_at_entry: float | None = None
) -> PreStopTrajectory:
    op = record.operation
    event_id = record.identification.event_id
    entry_ts, exit_ts = op.entry_ts, op.exit_ts

    if entry_ts is None or exit_ts is None:
        return PreStopTrajectory(
            event_id, PathIntegrity.INSUFFICIENT, 0, 0, None, None,
            None, None, None, None, None, None, None, None, None, None, None, None,
        )

    timestamps = timestamps_for(series)
    entry_index = bisect.bisect_left(timestamps, entry_ts)
    exit_index = bisect.bisect_left(timestamps, exit_ts)
    duration_bars = exit_index - entry_index
    duration_s = (exit_ts - entry_ts).total_seconds()

    pre = record.features_pre_entry
    time_activation_to_exit_s = (
        (exit_ts - pre.activation_instant_ts).total_seconds() if pre.activation_instant_ts else None
    )

    bullish = record.identification.original_direction == "bullish"
    risk_price = op.risk_price if op.risk_price else None

    # Sensitivity-only variants, computed regardless of primary integrity.
    mfe_entry_incl, _ = _window_mfe_mae(series, entry_index, exit_index, op.entry_price, bullish)
    mfe_exit_incl, _ = _window_mfe_mae(series, entry_index + 1, exit_index + 1, op.entry_price, bullish)
    mfe_including_entry_bar_r = (mfe_entry_incl / risk_price) if (mfe_entry_incl is not None and risk_price) else None
    mfe_including_exit_bar_r = (mfe_exit_incl / risk_price) if (mfe_exit_incl is not None and risk_price) else None

    middle_start, middle_end = entry_index + 1, exit_index
    n_observable = max(0, middle_end - middle_start)

    if n_observable <= 0:
        # n_observable == duration_bars - 1 by construction, so this branch
        # is always duration_bars <= 1: duration_bars == 0 means entry and
        # exit are the SAME bar (immediate failure, no structure at all --
        # INSUFFICIENT); duration_bars == 1 means they are ADJACENT bars
        # (entry and exit are at least distinguishable, but still zero
        # observable middle bars -- AMBIGUOUS, not as empty as the same-bar case).
        integrity = PathIntegrity.INSUFFICIENT if duration_bars <= 0 else PathIntegrity.AMBIGUOUS
        return PreStopTrajectory(
            event_id, integrity, 0, duration_bars, duration_s, time_activation_to_exit_s,
            None, None, None, None, None, None, None, None, None, None,
            mfe_including_entry_bar_r, mfe_including_exit_bar_r,
        )

    window = series.candles[middle_start:middle_end]
    best_favorable, worst_adverse = _window_mfe_mae(series, middle_start, middle_end, op.entry_price, bullish)
    best_favorable_price = op.entry_price
    running_best = 0.0
    n_favorable_close = n_adverse_close = 0
    for candle in window:
        favorable = (candle.high - op.entry_price) if bullish else (op.entry_price - candle.low)
        if favorable > running_best:
            running_best = favorable
            best_favorable_price = candle.high if bullish else candle.low
        bar_closed_up = candle.close > candle.open
        bar_closed_down = candle.close < candle.open
        bar_closed_favorable = bar_closed_up if bullish else bar_closed_down
        bar_closed_adverse = bar_closed_down if bullish else bar_closed_up
        if bar_closed_favorable:
            n_favorable_close += 1
        elif bar_closed_adverse:
            n_adverse_close += 1

    had_material = (
        (best_favorable / risk_price) >= CONTINUATION_REVERSAL_THRESHOLD_R if risk_price else None
    )
    retracement = abs(
        (best_favorable_price - op.exit_price) if bullish else (op.exit_price - best_favorable_price)
    )

    return PreStopTrajectory(
        event_id=event_id,
        integrity=PathIntegrity.RECONSTRUCTIBLE,
        n_observable_bars=n_observable,
        duration_bars=duration_bars,
        duration_s=duration_s,
        time_activation_to_exit_s=time_activation_to_exit_s,
        mfe_pre_sl_price=best_favorable,
        mfe_pre_sl_r=(best_favorable / risk_price) if risk_price else None,
        mfe_pre_sl_atr=(best_favorable / atr_at_entry) if atr_at_entry else None,
        mae_pre_sl_price=worst_adverse,
        mae_pre_sl_atr=(worst_adverse / atr_at_entry) if atr_at_entry else None,
        had_material_favorable_excursion=had_material,
        retracement_from_best_favorable_price=retracement,
        pct_bars_closed_favorable=n_favorable_close / len(window),
        pct_bars_closed_adverse=n_adverse_close / len(window),
        avg_adverse_speed_price_per_bar=(worst_adverse / len(window)) if window else None,
        mfe_including_entry_bar_r=mfe_including_entry_bar_r,
        mfe_including_exit_bar_r=mfe_including_exit_bar_r,
    )
