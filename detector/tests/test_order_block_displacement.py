from datetime import datetime, timedelta

from composite.displacement import confirm_displacement
from core.candle import Candle


def _candle(i, o, c, h=None, l=None):
    return Candle(
        timestamp=datetime(2026, 1, 1) + timedelta(hours=4 * i),
        open=o, close=c,
        high=h if h is not None else max(o, c),
        low=l if l is not None else min(o, c),
    )


def _flat_atr_series(n, base=1.10, body=0.0010):
    """n candles with a small, constant body -- ATR settles near `body`
    once warmed up, giving a predictable threshold for the displacement
    tests below."""
    candles = []
    price = base
    for i in range(n):
        candles.append(_candle(i, price, price + body, h=price + body + 0.0005, l=price - 0.0005))
        price += body
    return tuple(candles)


class TestConfirmDisplacement:
    def test_single_large_bullish_candle_confirms_at_its_own_index(self) -> None:
        candles = list(_flat_atr_series(20))
        break_index = 20
        # ATR14 here is ~0.0010; one huge bullish candle alone clears it.
        candles.append(_candle(break_index, 1.1200, 1.1300, h=1.1310, l=1.1190))
        result = confirm_displacement(tuple(candles), break_index=break_index, direction="bullish")
        assert result == break_index

    def test_accumulates_across_candles_up_to_the_max_window(self) -> None:
        candles = list(_flat_atr_series(20))
        break_index = 20
        # Three modest bullish candles that only clear ATR once summed.
        candles.append(_candle(break_index, 1.1200, 1.1206))
        candles.append(_candle(break_index + 1, 1.1206, 1.1212))
        candles.append(_candle(break_index + 2, 1.1212, 1.1260))
        result = confirm_displacement(tuple(candles), break_index=break_index, direction="bullish")
        assert result == break_index + 2

    def test_never_confirms_beyond_the_max_window(self) -> None:
        candles = list(_flat_atr_series(20))
        break_index = 20
        for offset in range(5):
            candles.append(_candle(break_index + offset, 1.1200 + offset * 0.0001, 1.1201 + offset * 0.0001))
        result = confirm_displacement(tuple(candles), break_index=break_index, direction="bullish", max_candles=3)
        assert result is None

    def test_none_when_body_sum_never_reaches_the_atr_threshold(self) -> None:
        candles = list(_flat_atr_series(20))
        break_index = 20
        candles.append(_candle(break_index, 1.1200, 1.1201))
        result = confirm_displacement(tuple(candles), break_index=break_index, direction="bullish")
        assert result is None

    def test_wrong_direction_net_move_does_not_confirm(self) -> None:
        """A big bearish candle must not confirm a requested bullish
        displacement, even though its body magnitude clears ATR."""
        candles = list(_flat_atr_series(20))
        break_index = 20
        candles.append(_candle(break_index, 1.1300, 1.1200, h=1.1310, l=1.1190))
        result = confirm_displacement(tuple(candles), break_index=break_index, direction="bullish")
        assert result is None

    def test_bearish_direction_symmetric(self) -> None:
        candles = list(_flat_atr_series(20))
        break_index = 20
        candles.append(_candle(break_index, 1.1300, 1.1200, h=1.1310, l=1.1190))
        result = confirm_displacement(tuple(candles), break_index=break_index, direction="bearish")
        assert result == break_index

    def test_none_when_break_index_is_the_series_end(self) -> None:
        candles = _flat_atr_series(20)
        result = confirm_displacement(candles, break_index=len(candles) - 1, direction="bullish")
        assert result is None
