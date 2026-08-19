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


def three_candle_crt_setup() -> OHLCSeries:
    """Charter-1 [00:16:11] Example 2: Vela1 establishes the range. Vela2
    purges the CRT High (wick beyond, close back inside) reacting to a
    Rejection Block. Vela3 expands directly to the CRT Low (close beyond
    the opposite extreme) -> 3-candle model, true_break resolution.
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1020, low=1.0980, close=1.1010)  # 0 — range: H=1.1020 L=1.0980
        .candle(open=1.1010, high=1.1035, low=1.1000, close=1.1005)  # 1 — pokes High, closes back inside
        .candle(open=1.1000, high=1.1005, low=1.0950, close=1.0960)  # 2 — closes below Low -> true_break
        .build()
    )


def two_candle_crt_setup() -> OHLCSeries:
    """Charter-1 [00:16:53] Example 3: Vela1 establishes the range. Vela2
    sweeps the CRT High AND, within that same candle, falls hard to close
    beyond the CRT Low -> 2-candle model, true_break resolution.
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1020, low=1.0980, close=1.1010)  # 0 — range: H=1.1020 L=1.0980
        .candle(open=1.1015, high=1.1035, low=1.0950, close=1.0960)  # 1 — pokes High AND closes below Low
        .build()
    )


def multi_inside_crt_setup() -> OHLCSeries:
    """Charter-1 [00:18:12] Example 5: Vela1 establishes the range. Candles
    2-3 stay fully trapped inside [Low, High] (no wick or close breach).
    Candle 4 finally purges the CRT High (wick beyond, close back inside).
    Candle 5 expands to close beyond the CRT Low -> multi-inside model.
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1020, low=1.0980, close=1.1010)  # 0 — range: H=1.1020 L=1.0980
        .candle(open=1.1005, high=1.1015, low=1.0990, close=1.1000)  # 1 — trapped
        .candle(open=1.1000, high=1.1012, low=1.0985, close=1.1005)  # 2 — trapped
        .candle(open=1.1010, high=1.1035, low=1.1000, close=1.1005)  # 3 — finally pokes High, closes inside
        .candle(open=1.1000, high=1.1005, low=1.0950, close=1.0960)  # 4 — closes below Low -> true_break
        .build()
    )


def multi_outside_crt_setup() -> OHLCSeries:
    """Charter-1 [00:11:06] Outside Bar CRT: Vela1 establishes the range.
    Vela2 purges the CRT High (wick beyond, close back inside) — same
    shape as the 3-candle model's Vela2. Unlike 3-candle, expansion does
    NOT complete at Vela3 — candle 2 stays inside without even reaching
    the range midpoint; only candle 3 finally closes beyond the CRT Low
    -> multi-outside (expansion took multiple subsequent candles).
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1020, low=1.0980, close=1.1010)  # 0 — range: H=1.1020 L=1.0980, mid=1.1000
        .candle(open=1.1010, high=1.1035, low=1.1000, close=1.1005)  # 1 — pokes High, closes back inside
        .candle(open=1.1005, high=1.1015, low=1.0995, close=1.1008)  # 2 — stays inside, above midpoint
        .candle(open=1.1000, high=1.1005, low=1.0950, close=1.0960)  # 3 — finally closes below Low
        .build()
    )


def crt_range_false_break_setup() -> OHLCSeries:
    """Charter-1 [00:06:48]/[00:07:03] "Ruptura Falsa / Turtle Soup": Vela2
    pokes the CRT Low (wick beyond, close back inside). Candle 2's close
    reverses back through the range reaching at least the midpoint
    ((High+Low)/2 = 1.1000) without fully breaking the opposite (High)
    extreme -> false_break resolution.
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1020, low=1.0980, close=1.1010)  # 0 — range: H=1.1020 L=1.0980, mid=1.1000
        .candle(open=1.0990, high=1.1010, low=1.0960, close=1.0995)  # 1 — pokes Low, closes back inside
        .candle(open=1.0995, high=1.1008, low=1.0990, close=1.1005)  # 2 — close reaches midpoint (>= 1.1000)
        .build()
    )


def crt_range_never_resolves_setup() -> OHLCSeries:
    """Price stays fully within [Low, High] for the whole lookback window
    (`max_lookback=2` in the test's config) -> REQ-14: never resolves,
    not emitted at all.
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1020, low=1.0980, close=1.1010)  # 0 — range: H=1.1020 L=1.0980
        .candle(open=1.1005, high=1.1015, low=1.0990, close=1.1000)  # 1 — inside
        .candle(open=1.1000, high=1.1010, low=1.0985, close=1.1005)  # 2 — inside
        .build()
    )


def crt_range_resolves_on_last_candle_setup() -> OHLCSeries:
    """Price stays inside for one candle, then resolves exactly on the
    candle at `i + max_lookback` (`max_lookback=2` in the test's config) —
    the last candle the lookback window allows.
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1020, low=1.0980, close=1.1010)  # 0 — range: H=1.1020 L=1.0980
        .candle(open=1.1005, high=1.1015, low=1.0990, close=1.1000)  # 1 — inside
        .candle(open=1.1000, high=1.1005, low=1.0950, close=1.0960)  # 2 — offset=2=max_lookback, true_break
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
