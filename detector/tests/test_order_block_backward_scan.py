from datetime import datetime, timedelta

from composite.order_block_scan import scan_for_anchor
from core.candle import Candle


def _candle(i, o, c):
    return Candle(
        timestamp=datetime(2026, 1, 1) + timedelta(hours=4 * i),
        open=o, high=max(o, c) + 0.0001, low=min(o, c) - 0.0001, close=c,
    )


class TestScanForAnchor:
    def test_bullish_displacement_anchors_on_the_nearest_bearish_candle(self) -> None:
        candles = (
            _candle(0, 1.10, 1.11),   # bullish -- further away, not the anchor
            _candle(1, 1.12, 1.11),   # bearish -- the nearest opposite candle
            _candle(2, 1.1205, 1.1300),  # break/displacement candle itself
        )
        result = scan_for_anchor(candles, displacement_start=2, direction="bullish", lookback=20)
        assert result == 1

    def test_bearish_displacement_anchors_on_the_nearest_bullish_candle(self) -> None:
        candles = (
            _candle(0, 1.11, 1.10),
            _candle(1, 1.10, 1.1150),
            _candle(2, 1.1145, 1.1000),
        )
        result = scan_for_anchor(candles, displacement_start=2, direction="bearish", lookback=20)
        assert result == 1

    def test_stops_at_the_nearest_match_not_a_further_one(self) -> None:
        candles = (
            _candle(0, 1.14, 1.15),  # bullish, further
            _candle(1, 1.13, 1.12),  # bearish, further
            _candle(2, 1.12, 1.125), # bullish, nearer but not opposite
            _candle(3, 1.125, 1.12), # bearish, nearest -- this one wins
            _candle(4, 1.12, 1.13),
        )
        result = scan_for_anchor(candles, displacement_start=4, direction="bullish", lookback=20)
        assert result == 3

    def test_none_when_no_opposite_candle_within_lookback(self) -> None:
        candles = tuple(_candle(i, 1.10 + i * 0.001, 1.101 + i * 0.001) for i in range(5))
        result = scan_for_anchor(candles, displacement_start=4, direction="bullish", lookback=20)
        assert result is None

    def test_respects_the_lookback_cap(self) -> None:
        candles = [_candle(i, 1.10 + i * 0.001, 1.101 + i * 0.001) for i in range(25)]
        candles[0] = _candle(0, 1.12, 1.10)  # bearish, but 24 candles before displacement_start
        result = scan_for_anchor(tuple(candles), displacement_start=24, direction="bullish", lookback=20)
        assert result is None

    def test_within_the_lookback_cap_it_is_found(self) -> None:
        candles = [_candle(i, 1.10 + i * 0.001, 1.101 + i * 0.001) for i in range(25)]
        candles[5] = _candle(5, 1.12, 1.10)  # bearish, 19 candles before index 24 -- inside the cap
        result = scan_for_anchor(tuple(candles), displacement_start=24, direction="bullish", lookback=20)
        assert result == 5

    def test_doji_zero_body_candle_is_neither_direction_and_never_anchors(self) -> None:
        candles = (
            _candle(0, 1.10, 1.09),  # bearish -- real anchor
            _candle(1, 1.11, 1.11),  # doji, zero body
            _candle(2, 1.1105, 1.1200),
        )
        result = scan_for_anchor(candles, displacement_start=2, direction="bullish", lookback=20)
        assert result == 0
