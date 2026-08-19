from dataclasses import dataclass
from typing import Literal

from core.candle import Candle, OHLCSeries
from core.config import FVGConfig

_ATR_PERIOD = 14


@dataclass(frozen=True)
class FVG:
    start_index: int
    end_index: int
    top: float
    bottom: float
    direction: Literal["bullish", "bearish"]
    fill_status: Literal["open", "filled"]


def detect_fvgs(series: OHLCSeries, config: FVGConfig = FVGConfig()) -> list[FVG]:
    candles = series.candles
    fvgs = []
    for i in range(len(candles) - 2):
        formed = _formed_gap(candles[i], candles[i + 2])
        if formed is None:
            continue
        direction, top, bottom = formed
        if (top - bottom) < config.min_size_atr * _atr(candles, i + 2):
            continue
        fvgs.append(
            FVG(
                start_index=i,
                end_index=i + 2,
                top=top,
                bottom=bottom,
                direction=direction,
                fill_status=_fill_status(candles[i + 3 :], direction, top, bottom),
            )
        )
    return fvgs


def _formed_gap(
    candle1: Candle, candle3: Candle
) -> tuple[Literal["bullish", "bearish"], float, float] | None:
    if candle3.low > candle1.high:
        return "bullish", candle3.low, candle1.high
    if candle3.high < candle1.low:
        return "bearish", candle1.low, candle3.high
    return None


def _fill_status(
    subsequent: tuple[Candle, ...],
    direction: Literal["bullish", "bearish"],
    top: float,
    bottom: float,
) -> Literal["open", "filled"]:
    if direction == "bullish":
        reached_far_edge = any(c.low <= bottom for c in subsequent)
    else:
        reached_far_edge = any(c.high >= top for c in subsequent)
    return "filled" if reached_far_edge else "open"


def _true_range(candles: tuple[Candle, ...], index: int) -> float:
    candle = candles[index]
    if index == 0:
        return candle.high - candle.low
    prev_close = candles[index - 1].close
    return max(
        candle.high - candle.low,
        abs(candle.high - prev_close),
        abs(candle.low - prev_close),
    )


def _atr(candles: tuple[Candle, ...], index: int) -> float:
    start = max(0, index - _ATR_PERIOD + 1)
    true_ranges = [_true_range(candles, j) for j in range(start, index + 1)]
    return sum(true_ranges) / len(true_ranges)
