from datetime import datetime, timedelta

from core.candle import Candle, OHLCSeries


class CandleSeriesBuilder:
    """Fluent builder for synthetic OHLCSeries fixtures.

    Candles are auto-timestamped one hour apart in emission order — tests
    care about OHLC shape and relative position, not wall-clock time.
    """

    def __init__(self, instrument: str = "EURUSD", timeframe: str = "1H"):
        self._instrument = instrument
        self._timeframe = timeframe
        self._candles: list[Candle] = []

    def candle(
        self, open: float, high: float, low: float, close: float
    ) -> "CandleSeriesBuilder":
        index = len(self._candles)
        self._candles.append(
            Candle(
                timestamp=datetime(2026, 1, 1) + timedelta(hours=index),
                open=open,
                high=high,
                low=low,
                close=close,
            )
        )
        return self

    def build(self) -> OHLCSeries:
        return OHLCSeries(
            candles=tuple(self._candles),
            instrument=self._instrument,
            timeframe=self._timeframe,
        )


def bearish_purge_setup() -> OHLCSeries:
    """Charter-2 [00:05:28]-[00:06:04]: a swing high forms, then a later
    candle purges it (wicks above, taking the resting liquidity) before the
    market reverses down.

    Index 1 is the swing high (strictly higher than index 0 and index 2 on
    the high side) — flaggable as soon as index 2 exists, i.e. BEFORE the
    purge candle at index 3 appears (REQ-06.1). Index 3 is the purge
    candle: its wick sweeps above index 1's high. Full engulf/retest
    mechanics are Model-1's concern (S-004) — this fixture only needs to
    carry the Swing-relevant shape for S-000.
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1005, low=1.0985, close=1.0995)
        .candle(open=1.0995, high=1.1020, low=1.0990, close=1.1005)
        .candle(open=1.1005, high=1.1010, low=1.0980, close=1.0990)
        .candle(open=1.0990, high=1.1030, low=1.0970, close=1.0975)
        .build()
    )
