from datetime import datetime, timedelta

from composite.significant_swing import detect_significant_swings
from core.candle import Candle, OHLCSeries


def _candle(i, o, c, h=None, l=None):
    return Candle(
        timestamp=datetime(2026, 1, 1) + timedelta(hours=4 * i),
        open=o, close=c,
        high=h if h is not None else max(o, c) + 0.0001,
        low=l if l is not None else min(o, c) - 0.0001,
    )


def _flat(n, base=1.10, body=0.0005):
    candles = []
    price = base
    for i in range(n):
        candles.append(_candle(i, price, price + body))
        price += body
    return candles


def _series(candles) -> OHLCSeries:
    return OHLCSeries(candles=tuple(candles), instrument="EURUSDm", timeframe="H4")


class TestDetectSignificantSwings:
    def test_a_real_swing_high_with_bearish_displacement_survives(self) -> None:
        candles = _flat(20)  # indices 0..19, warms up ATR
        candles.append(_candle(20, 1.1100, 1.1105, h=1.1120, l=1.1095))  # 20: the swing high candle
        candles.append(_candle(21, 1.1095, 1.1050, h=1.1098, l=1.1045))  # 21: real bearish displacement
        series = _series(candles)

        swings = detect_significant_swings(series)

        assert any(s.index == 20 and s.kind == "high" for s in swings)

    def test_a_minor_wiggle_high_with_no_real_displacement_is_filtered_out(self) -> None:
        candles = _flat(20)
        candles.append(_candle(20, 1.1100, 1.1105, h=1.1120, l=1.1095))  # 20: raw fractal high
        candles.append(_candle(21, 1.1095, 1.1098, h=1.1099, l=1.1094))  # 21: tiny move, no displacement
        candles.append(_candle(22, 1.1098, 1.1100, h=1.1101, l=1.1096))  # 22: still nothing
        candles.append(_candle(23, 1.1100, 1.1102, h=1.1103, l=1.1098))  # 23: still flat
        series = _series(candles)

        swings = detect_significant_swings(series)

        assert not any(s.index == 20 and s.kind == "high" for s in swings)

    def test_a_real_swing_low_with_bullish_displacement_survives(self) -> None:
        candles = _flat(20)
        candles.append(_candle(20, 1.1000, 1.0995, h=1.1005, l=1.0980))  # 20: the swing low candle
        candles.append(_candle(21, 1.0995, 1.1050, h=1.1055, l=1.0993))  # 21: real bullish displacement
        series = _series(candles)

        swings = detect_significant_swings(series)

        assert any(s.index == 20 and s.kind == "low" for s in swings)

    def test_the_swing_candles_own_body_does_not_count_as_displacement(self) -> None:
        """Displacement must be measured AFTER the swing forms, not
        including its own formation candle: a swing candle whose WICK sets
        the fractal high but whose own CLOSE already carries a large
        bearish body, followed by nothing but flat candles, must NOT
        count as "real displacement" -- that would credit the swing
        candle's own noise as follow-through."""
        candles = _flat(20)
        # wick high=1.1120 sets the fractal high; the candle's own body
        # is already a big bearish move (1.1100 -> 1.1050) -- but nothing
        # actually continues after it.
        candles.append(_candle(20, 1.1100, 1.1050, h=1.1120, l=1.1045))
        candles.append(_candle(21, 1.1050, 1.1052, h=1.1055, l=1.1048))
        candles.append(_candle(22, 1.1052, 1.1053, h=1.1056, l=1.1050))
        candles.append(_candle(23, 1.1053, 1.1054, h=1.1057, l=1.1051))
        series = _series(candles)

        swings = detect_significant_swings(series)

        assert not any(s.index == 20 and s.kind == "high" for s in swings)

    def test_raw_swing_count_bounds_the_significant_count(self) -> None:
        """Never produces MORE swings than the raw fractal -- this is a
        filter, not a different detector."""
        from primitives.swing import detect_swings

        candles = _flat(20)
        candles.append(_candle(20, 1.1100, 1.1105, h=1.1120, l=1.1095))
        candles.append(_candle(21, 1.1095, 1.1050, h=1.1098, l=1.1045))
        series = _series(candles)

        assert len(detect_significant_swings(series)) <= len(detect_swings(series))
