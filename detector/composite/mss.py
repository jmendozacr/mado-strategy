from dataclasses import dataclass
from typing import Literal

from core.candle import Candle, OHLCSeries
from core.config import MSSConfig
from primitives.swing import SwingPoint, detect_swings


@dataclass(frozen=True)
class MSSEvent:
    index: int
    direction: Literal["bullish", "bearish"]
    broken_swing: SwingPoint


def detect_mss_events(
    series: OHLCSeries, config: MSSConfig = MSSConfig()
) -> list[MSSEvent]:
    candles = series.candles
    swings = detect_swings(series)
    events = []

    for broken_swing in swings:
        opposite_kind = "low" if broken_swing.kind == "high" else "high"
        opposite_swing = _most_recent_before(swings, broken_swing.index, opposite_kind)
        if opposite_swing is None:
            continue

        distance = abs(broken_swing.price - opposite_swing.price)
        if distance <= 0:
            continue

        break_index = _find_decisive_break(
            candles, broken_swing, distance, config.decisive_close_ratio
        )
        if break_index is None:
            continue

        direction: Literal["bullish", "bearish"] = (
            "bullish" if broken_swing.kind == "high" else "bearish"
        )
        events.append(
            MSSEvent(index=break_index, direction=direction, broken_swing=broken_swing)
        )

    return events


def _most_recent_before(
    swings: list[SwingPoint], index: int, kind: Literal["high", "low"]
) -> SwingPoint | None:
    candidates = [s for s in swings if s.kind == kind and s.index < index]
    if not candidates:
        return None
    return max(candidates, key=lambda s: s.index)


def _find_decisive_break(
    candles: tuple[Candle, ...],
    broken_swing: SwingPoint,
    distance: float,
    decisive_close_ratio: float,
) -> int | None:
    threshold = distance * decisive_close_ratio
    for j in range(broken_swing.index + 1, len(candles)):
        close = candles[j].close
        if broken_swing.kind == "high" and close >= broken_swing.price + threshold:
            return j
        if broken_swing.kind == "low" and close <= broken_swing.price - threshold:
            return j
    return None
