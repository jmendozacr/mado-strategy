"""Displacement event detection — RESEARCH TOOLING, not a production Key
Level or signal source.

Frozen 2026-09-06, alongside `research.order_block`. Promotes, byte-for-byte
in behavior, the ">=1x ATR14 body sum over <=3 candles" displacement test
every prior ablation this session reproduced by hand, in prose, plus a
"most recent displacement at-or-before a cutoff" lookup mirroring
`research.order_block.is_active`'s right-closed boundary convention.

Leaf package rules identical to `research.order_block`: may import downward
from `core`/`primitives`, must never be imported by any production layer
(`entries`, `alignment`, `backtest`, `viz`, `cli`) — see `.importlinter`'s
`no-research-in-production` contract.
"""

from dataclasses import dataclass
from typing import Literal

from core.atr import atr
from core.candle import OHLCSeries

DISPLACEMENT_VERSION = "daily_displacement_v1"

_DISPLACEMENT_MULTIPLIER = 1.0
_MAX_DISPLACEMENT_CANDLES = 3

Direction = Literal["bullish", "bearish"]


@dataclass(frozen=True)
class DisplacementEvent:
    index: int
    direction: Direction


def detect_displacements(daily: OHLCSeries) -> list[DisplacementEvent]:
    """Body-sum-over-a-<=3-candle-window >= ATR14 test, exactly as used
    across every prior ablation this session. No config parameter — the
    thresholds above are frozen constants, not tunables, same rationale as
    `research.order_block.detect_order_blocks`."""
    candles = daily.candles
    events: list[DisplacementEvent] = []

    for i in range(2, len(candles)):
        window = [j for j in range(i - _MAX_DISPLACEMENT_CANDLES + 1, i + 1) if j >= 0]
        body = sum(abs(candles[j].close - candles[j].open) for j in window)
        if body < atr(candles, i) * _DISPLACEMENT_MULTIPLIER:
            continue
        net = sum(candles[j].close - candles[j].open for j in window)
        events.append(DisplacementEvent(index=i, direction="bullish" if net > 0 else "bearish"))

    return events


def most_recent_before(events: list[DisplacementEvent], cutoff_index: int) -> DisplacementEvent | None:
    """Most recent (highest `index`) event with `index <= cutoff_index` —
    right-closed at cutoff, the same boundary convention as
    `research.order_block.is_active` (chosen here for consistency across
    this session's reconciliation tooling, not because displacement events
    carry any expiry of their own to justify it independently). `None` when
    no event qualifies."""
    qualifying = [e for e in events if e.index <= cutoff_index]
    if not qualifying:
        return None
    return max(qualifying, key=lambda e: e.index)
