from datetime import datetime, timedelta

from core.candle import Candle
from core.candle import OHLCSeries
from experimental.order_block_anchor_variant import daily_key_levels, extreme_anchor


def _candle(i, o, h, l, c):
    return Candle(timestamp=datetime(2026, 1, 1) + timedelta(hours=i), open=o, high=h, low=l, close=c)


def test_bullish_picks_the_lowest_low_in_the_span_not_the_nearest_candle():
    """swing_index=0, break_index=4 -> span is [1, 2, 3]. Index 2 has the
    deepest low (1.0940) even though it is NOT the candle nearest the
    break (index 3) -- the current production rule (nearest opposite
    color) would never consider index 2 over index 3 on proximity alone."""
    candles = (
        _candle(0, 1.1000, 1.1010, 1.0990, 1.1005),  # 0 — swing low marker
        _candle(1, 1.0995, 1.1000, 1.0960, 1.0998),  # 1 — low=1.0960
        _candle(2, 1.0990, 1.0995, 1.0940, 1.0992),  # 2 — low=1.0940, the deepest
        _candle(3, 1.0992, 1.1000, 1.0950, 1.0998),  # 3 — low=1.0950, nearest to the break
        _candle(4, 1.1000, 1.1050, 1.0995, 1.1045),  # 4 — break candle
    )
    assert extreme_anchor(candles, swing_index=0, break_index=4, direction="bullish") == 2


def test_bearish_picks_the_highest_high_in_the_span():
    candles = (
        _candle(0, 1.1000, 1.1010, 1.0990, 1.1005),  # 0 — swing high marker
        _candle(1, 1.1005, 1.1040, 1.1000, 1.1010),  # 1 — high=1.1040
        _candle(2, 1.1010, 1.1060, 1.1005, 1.1015),  # 2 — high=1.1060, the highest
        _candle(3, 1.1008, 1.1030, 1.1000, 1.1010),  # 3 — high=1.1030, nearest to the break
        _candle(4, 1.1000, 1.1005, 1.0950, 1.0960),  # 4 — break candle
    )
    assert extreme_anchor(candles, swing_index=0, break_index=4, direction="bearish") == 2


def test_falls_back_to_the_candle_before_the_break_when_the_span_is_empty():
    """The break happens on the very next candle after the swing -- no
    candle exists strictly between them -- mirrors smartmoneyconcepts'
    own default-index behavior rather than raising or returning None."""
    candles = (
        _candle(0, 1.1000, 1.1010, 1.0990, 1.1005),  # 0 — swing marker
        _candle(1, 1.1000, 1.1050, 1.0995, 1.1045),  # 1 — break, immediately after the swing
    )
    assert extreme_anchor(candles, swing_index=0, break_index=1, direction="bullish") == 0


def test_daily_key_levels_dispatches_to_the_requested_anchor_rule(monkeypatch):
    """Sanity check the WIRING, not either anchor rule's own domain logic
    (covered above / by the production detector's own suite): `extreme`
    picks `detect_order_blocks_extreme_anchor`, not
    `composite.ict_order_block.detect_order_blocks`."""
    import experimental.order_block_anchor_variant as module

    calls = []
    monkeypatch.setattr(module, "detect_order_blocks", lambda series: calls.append("today") or [])
    monkeypatch.setattr(
        module, "detect_order_blocks_extreme_anchor", lambda series: calls.append("extreme") or [],
    )

    series = OHLCSeries(candles=(), instrument="EURUSDm", timeframe="Daily")
    module.daily_key_levels(series, extreme=False)
    assert calls == ["today"]

    module.daily_key_levels(series, extreme=True)
    assert calls == ["today", "extreme"]
