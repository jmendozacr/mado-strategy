"""Backward scan for the Order Block anchor candle, the last step of the
order-block-redefinition chain (`odd/tasks/detector-order-block-redefinition.md`
S2/S5/T3): from where displacement starts, walk backward for the nearest
candle whose BODY COLOR is opposite the displacement's own direction (the
classic ICT definition -- a bullish OB is the last BEARISH-bodied candle
before a bullish move).
"""
from __future__ import annotations

from typing import Literal

from core.candle import Candle

Direction = Literal["bullish", "bearish"]


def scan_for_anchor(
    candles: tuple[Candle, ...],
    displacement_start: int,
    direction: Direction,
    lookback: int,
) -> int | None:
    """Nearest (highest-index) candle strictly before `displacement_start`
    whose body is opposite-colored to `direction`, within `lookback`
    candles -- `None` if none qualifies. A zero-body (doji) candle is
    neither color and never anchors."""
    floor = max(0, displacement_start - lookback)
    for index in range(displacement_start - 1, floor - 1, -1):
        candle = candles[index]
        if direction == "bullish" and candle.close < candle.open:
            return index
        if direction == "bearish" and candle.close > candle.open:
            return index
    return None
