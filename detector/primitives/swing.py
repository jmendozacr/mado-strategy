from dataclasses import dataclass
from typing import Literal

from core.candle import OHLCSeries
from core.config import SwingConfig


@dataclass(frozen=True)
class SwingPoint:
    index: int
    price: float
    kind: Literal["high", "low"]


def detect_swings(
    series: OHLCSeries, config: SwingConfig = SwingConfig()
) -> list[SwingPoint]:
    candles = series.candles
    swings = []
    for i in range(1, len(candles) - 1):
        if candles[i].high > candles[i - 1].high and candles[i].high > candles[i + 1].high:
            swings.append(SwingPoint(index=i, price=candles[i].high, kind="high"))
        if candles[i].low < candles[i - 1].low and candles[i].low < candles[i + 1].low:
            swings.append(SwingPoint(index=i, price=candles[i].low, kind="low"))
    return swings
