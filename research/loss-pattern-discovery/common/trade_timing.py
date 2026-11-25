"""Shared entry/exit bar-index and duration helpers (Phase 5).

Reusable for ANY executed trade (win, loss, or confirmed-stop loss) --
unlike `behavior.pre_stop_trajectory`, which is deliberately scoped to
confirmed-stop losses only. Pure index/timing arithmetic, no price logic,
so it introduces no new causal assumption beyond what Phase 1-4 already
established and tested: `entry_ts`/`exit_ts` are M15 bar OPEN timestamps on
the same grid as the instrument's own M15 series, located via exact
`bisect_left` match (never an approximate wall-clock diff, so a weekend gap
between entry and exit never inflates or deflates a bar-count duration).
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass

from core.candle import OHLCSeries

from common.series_index import timestamps_for
from schema.events import EventRecord


@dataclass(frozen=True)
class TradeTiming:
    event_id: str
    entry_index: int | None
    exit_index: int | None
    duration_bars: int | None  # exit_index - entry_index; None if either timestamp is missing (open/censored)
    duration_s: float | None
    same_or_next_bar: bool | None  # duration_bars in {0, 1}; None if duration_bars is None


def compute_trade_timing(record: EventRecord, series: OHLCSeries) -> TradeTiming:
    op = record.operation
    event_id = record.identification.event_id
    if op.entry_ts is None or op.exit_ts is None:
        return TradeTiming(event_id, None, None, None, None, None)

    timestamps = timestamps_for(series)
    entry_index = bisect.bisect_left(timestamps, op.entry_ts)
    exit_index = bisect.bisect_left(timestamps, op.exit_ts)
    duration_bars = exit_index - entry_index
    duration_s = (op.exit_ts - op.entry_ts).total_seconds()
    return TradeTiming(
        event_id=event_id, entry_index=entry_index, exit_index=exit_index,
        duration_bars=duration_bars, duration_s=duration_s,
        same_or_next_bar=duration_bars <= 1,
    )
