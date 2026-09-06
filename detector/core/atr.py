"""Pure ATR (Average True Range) arithmetic over a Candle series -- no
CRT/ICT domain semantics, shared downward by `primitives.fvg` (gap-size
normalization) and `backtest.levels` (stop-loss buffer normalization),
both legal per ADR-01's layering (both sit above `core`).
"""

from core.candle import Candle

ATR_PERIOD = 14


def true_range(candles: tuple[Candle, ...], index: int) -> float:
    candle = candles[index]
    if index == 0:
        return candle.high - candle.low
    prev_close = candles[index - 1].close
    return max(
        candle.high - candle.low,
        abs(candle.high - prev_close),
        abs(candle.low - prev_close),
    )


def atr(candles: tuple[Candle, ...], index: int, period: int = ATR_PERIOD) -> float:
    start = max(0, index - period + 1)
    true_ranges = [true_range(candles, j) for j in range(start, index + 1)]
    return sum(true_ranges) / len(true_ranges)
