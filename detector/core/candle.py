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
