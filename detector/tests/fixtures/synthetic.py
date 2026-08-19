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


def bearish_fvg_fill_setup() -> OHLCSeries:
    """Charter-2 [00:13:19] DXY daily: "El mercado llenó un FVG, cerró por
    debajo de la vela de rebalanceo, retesteó dicha vela y se expandió a la
    baja" — a bearish Fair Value Gap forms (candle-1's low sits above
    candle-3's high), price later trades back up to fully fill it (retest),
    then expands down.

    Index 0-2 form the gap (bearish: candle[2].high < candle[0].low).
    Index 3 is filler. Index 4 trades back up to fill the gap (its high
    reaches candle[0].low, the gap's top/far edge).
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.1050, high=1.1055, low=1.1040, close=1.1045)  # 0 — gap top = low 1.1040
        .candle(open=1.1030, high=1.1035, low=1.1005, close=1.1020)  # 1 — middle candle (low kept above candle 3's high to avoid an overlapping i=1 gap)
        .candle(open=1.1010, high=1.1015, low=1.0995, close=1.1000)  # 2 — gap bottom = high 1.1015
        .candle(open=1.1000, high=1.1010, low=1.0990, close=1.0995)  # 3 — filler, still below gap
        .candle(open=1.1005, high=1.1042, low=1.1000, close=1.1038)  # 4 — retest, high reaches gap top (1.1040) -> filled
        .build()
    )


def bullish_fvg_partial_fill_setup() -> OHLCSeries:
    """Charter-3 [00:14:47]-[00:15:23]: a 4H bullish FVG identified as a
    support zone; "el mercado sube sin rellenar completamente el FVG" — price
    rises without fully filling the gap below it.

    Index 0-2 form the gap (bullish: candle[2].low > candle[0].high).
    Index 3 dips into the gap's near edge (top) but never reaches the far
    edge (bottom) — REQ-10.1's partial re-entry, stays "open".
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.0980, high=1.0985, low=1.0970, close=1.0975)  # 0 — gap bottom = high 1.0985
        .candle(open=1.0995, high=1.1005, low=1.0990, close=1.1000)  # 1 — middle candle
        .candle(open=1.1010, high=1.1020, low=1.1005, close=1.1015)  # 2 — gap top = low 1.1005
        .candle(open=1.1000, high=1.1008, low=1.0990, close=1.0993)  # 3 — dips to gap top (1.0985<1.0990<=1.1005) but not gap bottom (1.0985)
        .build()
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
