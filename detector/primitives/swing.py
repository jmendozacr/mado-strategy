from dataclasses import dataclass
from typing import Literal

from core.candle import OHLCSeries
from core.config import SwingConfig


@dataclass(frozen=True)
class SwingPoint:
    index: int
    price: float
    kind: Literal["high", "low"]


TrendLabel = Literal["HH", "HL", "LH", "LL"]


@dataclass(frozen=True)
class ClassifiedSwing:
    """One swing against the most recent PRIOR swing of the SAME kind --
    `label` is `None` for the first swing of each kind, since there is
    nothing yet to compare it against (not a negative classification).
    `HH`/`LL` require a STRICTLY higher/lower price than the predecessor;
    an equal price is `LH`/`HL` (no new extreme was made)."""

    swing: SwingPoint
    label: TrendLabel | None


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


def classify_trend(swings: list[SwingPoint]) -> list[ClassifiedSwing]:
    """Market Structure classification (HH/HL/LH/LL), Market-Structure step
    of the order-block-redefinition chain (`odd/tasks/
    detector-order-block-redefinition.md` S2/T1). Highs and lows track
    independently -- a low never compares against a prior high. `swings`
    must already be index-ascending (as `detect_swings` returns them)."""
    last_high: SwingPoint | None = None
    last_low: SwingPoint | None = None
    result = []

    for swing in swings:
        if swing.kind == "high":
            label = None if last_high is None else ("HH" if swing.price > last_high.price else "LH")
            last_high = swing
        else:
            label = None if last_low is None else ("LL" if swing.price < last_low.price else "HL")
            last_low = swing
        result.append(ClassifiedSwing(swing=swing, label=label))

    return result
