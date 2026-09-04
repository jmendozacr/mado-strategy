from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class OHLCSeries:
    candles: tuple[Candle, ...]
    instrument: str
    timeframe: str

    def up_to(self, index: int) -> "OHLCSeries":
        return OHLCSeries(
            candles=self.candles[:index],
            instrument=self.instrument,
            timeframe=self.timeframe,
        )


def first_overlap_index(candles: tuple[Candle, ...], start: int, top: float, bottom: float) -> int | None:
    """First candle index from `start` onward whose range overlaps
    `[bottom, top]` (wick or body, boundary-inclusive)."""
    for i in range(start, len(candles)):
        candle = candles[i]
        if candle.high >= bottom and candle.low <= top:
            return i
    return None
