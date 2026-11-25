"""Pre-entry feature extraction (Phase 4, Layer A).

Every feature here is computed using ONLY bars fully closed strictly before
`OriginalOperation.entry_ts` -- the exact same causal boundary
`behavior.post_stop_metrics.compute_atr_at_event` already uses (reused
directly, called at `entry_ts` instead of `exit_ts`), and the same boundary
`schema.events.FeaturesPreEntry` documents for this event's OWN pre-entry
fields. Applies to EVERY event (win, loss, open) with the SAME methodology,
because Phase 4's winner-vs-loser comparison requires it -- `outcome` is
carried on the output purely for later stratification, never used to
choose how a feature is computed.

Feature audit (name, formula, source, availability, unit, missing-value
treatment, causality test) is documented in full in
`docs/23-pre-entry-feature-audit.md`; this module is the implementation.
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass
from datetime import datetime, timedelta

from core.candle import OHLCSeries

from behavior.post_stop_metrics import ATR_PERIOD, compute_atr_at_event
from common.ny_time import to_ny
from common.series_index import timestamps_for
from schema.events import EventRecord

RECENT_RANGE_LOOKBACK = ATR_PERIOD  # reuses the same pre-registered 14-bar window as the ATR itself
M15_DURATION = timedelta(minutes=15)

_SYMBOL_CONFIG = None  # lazily imported -- see _trading_cost_price


def _trading_cost_price(instrument: str) -> float | None:
    """Read-only reuse of the SAME per-symbol round-trip cost config the
    production scanner and the causal-lookahead-audit's own corrected
    pipeline already use (confirmed in Phase 2/3's own source inventory) --
    never re-estimated or hardcoded independently here."""
    global _SYMBOL_CONFIG
    if _SYMBOL_CONFIG is None:
        from experimental.htf_trigger_1am_9am_backtest import SYMBOL_CONFIG

        _SYMBOL_CONFIG = SYMBOL_CONFIG
    config = _SYMBOL_CONFIG.get(instrument)
    return config.trading_cost_price if config is not None else None


@dataclass
class PreEntryFeatures:
    event_id: str
    instrument: str
    origin_model: str
    direction: str
    outcome: str  # carried for stratified comparison ONLY -- never used to choose how a feature is computed
    entry_ts: datetime | None

    # B. Volatility (known strictly before entry_ts)
    atr_m15_at_entry: float | None
    recent_range_price: float | None
    recent_range_atr: float | None

    # C. Trade geometry
    risk_price: float
    reward_price: float
    risk_atr: float | None
    planned_rr: float | None
    cost_to_risk_ratio: float | None

    # D. Temporal context
    ny_hour_at_entry: float | None
    day_of_week_ny: int | None  # Monday=0 .. Sunday=6, NY-local calendar date
    time_activation_to_entry_s: float | None

    # E. Directional context (generic price action only -- no CRT/Key-Level assumption)
    prior_m15_return: float | None
    position_in_recent_range: float | None  # 0 = at the recent low, 1 = at the recent high
    prior_move_direction: int | None  # +1 up, -1 down, 0 flat, over the lookback window
    distance_to_recent_high_atr: float | None
    distance_to_recent_low_atr: float | None

    missing_reasons: tuple[str, ...]


def compute_pre_entry_features(record: EventRecord, series: OHLCSeries) -> PreEntryFeatures:
    op = record.operation
    entry_ts = op.entry_ts
    missing: list[str] = []

    if entry_ts is None:
        missing.append("entry_ts_missing")
        atr = None
    else:
        atr = compute_atr_at_event(series, entry_ts, period=ATR_PERIOD)
        if atr is None:
            missing.append("atr_m15_at_entry_insufficient_history")

    recent_range_price = None
    prior_m15_return = None
    position_in_recent_range = None
    prior_move_direction = None
    distance_to_recent_high_atr = None
    distance_to_recent_low_atr = None
    ny_hour_at_entry = None
    day_of_week_ny = None

    if entry_ts is not None:
        ny_hour_at_entry = to_ny(entry_ts).hour + to_ny(entry_ts).minute / 60.0
        day_of_week_ny = to_ny(entry_ts).weekday()

        timestamps = timestamps_for(series)
        # Same causal boundary as compute_atr_at_event: bars fully closed
        # strictly before entry_ts -- the entry bar's own (possibly
        # pre-fill) range is never part of this window.
        end_index = bisect.bisect_right(timestamps, entry_ts - M15_DURATION)
        start_index = end_index - RECENT_RANGE_LOOKBACK
        if start_index >= 1 and end_index > start_index:
            window = series.candles[start_index:end_index]
            recent_high = max(c.high for c in window)
            recent_low = min(c.low for c in window)
            recent_range_price = recent_high - recent_low
            last_closed = series.candles[end_index - 1]
            first_of_window = series.candles[start_index]
            if recent_range_price > 0:
                position_in_recent_range = (last_closed.close - recent_low) / recent_range_price
            if last_closed.open:
                prior_m15_return = (last_closed.close - last_closed.open) / last_closed.open
            direction_delta = last_closed.close - first_of_window.close
            prior_move_direction = 1 if direction_delta > 0 else (-1 if direction_delta < 0 else 0)
            if atr:
                distance_to_recent_high_atr = (recent_high - op.entry_price) / atr
                distance_to_recent_low_atr = (op.entry_price - recent_low) / atr
        else:
            missing.append("recent_range_insufficient_history")

    recent_range_atr = (recent_range_price / atr) if (recent_range_price is not None and atr) else None
    risk_atr = (op.risk_price / atr) if (atr and op.risk_price) else None
    cost = _trading_cost_price(record.identification.instrument)
    cost_to_risk_ratio = (cost / op.risk_price) if (cost is not None and op.risk_price) else None

    pre = record.features_pre_entry
    time_activation_to_entry_s = (
        (entry_ts - pre.activation_instant_ts).total_seconds()
        if entry_ts and pre.activation_instant_ts
        else None
    )

    return PreEntryFeatures(
        event_id=record.identification.event_id,
        instrument=record.identification.instrument,
        origin_model=record.identification.session_label,
        direction=record.identification.original_direction,
        outcome=op.outcome.value,
        entry_ts=entry_ts,
        atr_m15_at_entry=atr,
        recent_range_price=recent_range_price,
        recent_range_atr=recent_range_atr,
        risk_price=op.risk_price,
        reward_price=pre.planned_reward_price,
        risk_atr=risk_atr,
        planned_rr=pre.planned_rr,
        cost_to_risk_ratio=cost_to_risk_ratio,
        ny_hour_at_entry=ny_hour_at_entry,
        day_of_week_ny=day_of_week_ny,
        time_activation_to_entry_s=time_activation_to_entry_s,
        prior_m15_return=prior_m15_return,
        position_in_recent_range=position_in_recent_range,
        prior_move_direction=prior_move_direction,
        distance_to_recent_high_atr=distance_to_recent_high_atr,
        distance_to_recent_low_atr=distance_to_recent_low_atr,
        missing_reasons=tuple(missing),
    )
