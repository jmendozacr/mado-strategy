"""Post-Stop-Loss trajectory reconstruction: joins raw M15 bars after an
event's own `exit_ts` to measure what price actually did afterward.

This is a building block for Research Line B (see
docs/01-objectives-and-hypotheses.md). It measures price behavior; it does
not define or evaluate any new hypothetical strategy. Any later hypothetical
post-SL entry must still satisfy the causal constraint that it may never
trigger before its own entry condition is observable -- evaluating that
belongs to a later research unit, not to this module.

MFE/MAE convention: both are measured relative to the ORIGINAL trade's
direction, exactly as if the original trade were still open past its own
exit. For a bullish original trade, MAE keeps growing if price keeps falling
(continuing the move that caused the SL); MFE grows if price reverses back
up. This is NOT the P&L of a new post-SL trade -- it only characterizes what
price did, in the original direction's frame. MFE/MAE accumulate across
increasing horizons (the 1d figure already includes everything seen by 4h).
"""
from __future__ import annotations

import bisect
from datetime import datetime, timedelta
from pathlib import Path

from core.candle import OHLCSeries
from ingestion.loader import load_mt5_csv

from schema.events import EventRecord, PostStopOutcome

DEFAULT_HORIZONS: tuple[tuple[str, timedelta], ...] = (
    ("4h", timedelta(hours=4)),
    ("1d", timedelta(days=1)),
    ("3d", timedelta(days=3)),
)


def _m15_path_for(pair: str, data_dir: Path) -> Path:
    matches = sorted(data_dir.glob(f"{pair}_M15_*.csv"))
    if not matches:
        raise FileNotFoundError(f"no M15 file found for {pair!r} under {data_dir}")
    if len(matches) > 1:
        raise FileNotFoundError(
            f"multiple M15 files found for {pair!r} under {data_dir}: {matches} "
            "-- disambiguate, do not guess which one is current"
        )
    return matches[0]


def load_m15_series(pair: str, data_dir: Path) -> OHLCSeries:
    path = _m15_path_for(pair, data_dir)
    return load_mt5_csv(str(path), pair)


def _bisect_after(candles: tuple, ts: datetime) -> int:
    timestamps = [c.timestamp for c in candles]
    return bisect.bisect_right(timestamps, ts)


def compute_post_stop_outcomes(
    record: EventRecord,
    series: OHLCSeries,
    horizons: tuple[tuple[str, timedelta], ...] = DEFAULT_HORIZONS,
) -> list[PostStopOutcome]:
    exit_ts = record.operation.exit_ts
    exit_price = record.operation.exit_price
    if exit_ts is None:
        raise ValueError(
            f"{record.identification.event_id}: exit_ts is missing, cannot "
            "reconstruct a post-stop trajectory"
        )

    bullish = record.identification.original_direction == "bullish"
    start_index = _bisect_after(series.candles, exit_ts)

    if start_index >= len(series.candles):
        # No bars at all after exit_ts in this data file -- fully censored.
        return [
            PostStopOutcome(
                horizon_label=label,
                horizon_ts=exit_ts + delta,
                mfe_price=None,
                mae_price=None,
                mfe_r=None,
                mae_r=None,
                price_at_horizon=None,
                bars_available=0,
                censored=True,
            )
            for label, delta in horizons
        ]

    risk_price = record.operation.risk_price
    outcomes: list[PostStopOutcome] = []
    best_favorable = 0.0
    worst_adverse = 0.0
    last_close = exit_price
    bars_seen = 0
    idx = start_index
    last_bar_ts = series.candles[-1].timestamp

    for label, delta in horizons:
        horizon_ts = exit_ts + delta
        while idx < len(series.candles) and series.candles[idx].timestamp <= horizon_ts:
            candle = series.candles[idx]
            if bullish:
                favorable_excursion = candle.high - exit_price
                adverse_excursion = exit_price - candle.low
            else:
                favorable_excursion = exit_price - candle.low
                adverse_excursion = candle.high - exit_price
            best_favorable = max(best_favorable, favorable_excursion)
            worst_adverse = max(worst_adverse, adverse_excursion)
            last_close = candle.close
            bars_seen += 1
            idx += 1
        censored = last_bar_ts < horizon_ts
        outcomes.append(
            PostStopOutcome(
                horizon_label=label,
                horizon_ts=horizon_ts,
                mfe_price=best_favorable,
                mae_price=worst_adverse,
                mfe_r=(best_favorable / risk_price) if risk_price else None,
                mae_r=(worst_adverse / risk_price) if risk_price else None,
                price_at_horizon=last_close,
                bars_available=bars_seen,
                censored=censored,
            )
        )
    return outcomes
