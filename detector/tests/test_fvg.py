from fixtures.synthetic import (
    CandleSeriesBuilder,
    bearish_fvg_fill_setup,
    bullish_fvg_partial_fill_setup,
)

from core.config import FVGConfig
from primitives.fvg import detect_fvgs


def test_detects_bearish_fvg_and_marks_filled_after_retest():
    """REQ-08.1 + REQ-10, grounded charter-2 [00:13:19] DXY daily: a bearish
    FVG forms, then the market retests and fully fills it before expanding
    down. top/bottom must match candle-1's low / candle-3's high.
    """
    series = bearish_fvg_fill_setup()

    fvgs = detect_fvgs(series)

    assert len(fvgs) == 1
    fvg = fvgs[0]
    assert fvg.start_index == 0
    assert fvg.end_index == 2
    assert fvg.direction == "bearish"
    assert fvg.top == series.candles[0].low
    assert fvg.bottom == series.candles[2].high
    assert fvg.fill_status == "filled"


def test_bullish_gap_top_bottom_match_candle_one_and_three_extremes():
    """REQ-08.1: bullish FVG = candle[i+2].low > candle[i].high; top/bottom
    are those extremes. No further candles after formation -> stays open.
    """
    series = (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1010, low=1.0995, close=1.1005)  # 0
        .candle(open=1.1015, high=1.1030, low=1.1010, close=1.1025)  # 1
        .candle(open=1.1040, high=1.1050, low=1.1035, close=1.1045)  # 2 — low(1.1035) > candle0.high(1.1010)
        .build()
    )

    fvgs = detect_fvgs(series)

    assert len(fvgs) == 1
    fvg = fvgs[0]
    assert fvg.start_index == 0
    assert fvg.end_index == 2
    assert fvg.direction == "bullish"
    assert fvg.top == series.candles[2].low
    assert fvg.bottom == series.candles[0].high
    assert fvg.fill_status == "open"


def test_partial_reentry_leaves_gap_open():
    """REQ-10.1, grounded charter-3 [00:14:47]-[00:15:23]: price dips back
    into the gap but never reaches its far edge -> stays open, not filled.
    """
    series = bullish_fvg_partial_fill_setup()

    fvgs = detect_fvgs(series)

    assert len(fvgs) == 1
    assert fvgs[0].fill_status == "open"


def test_gap_narrower_than_default_min_size_is_excluded():
    """REQ-09.1: gap width below FVGConfig.min_size_atr (default 0.1) x
    ATR(14) at formation is not flagged at all.
    """
    series = (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1010, low=1.1000, close=1.1000)  # 0 — TR=0.0010
        .candle(open=1.1000, high=1.1010, low=1.1000, close=1.1000)  # 1 — TR=0.0010
        .candle(open=1.1010, high=1.1012, low=1.10105, close=1.1011)  # 2 — tiny gap (low 1.10105 > candle0.high 1.1010)
        .build()
    )

    fvgs = detect_fvgs(series)

    assert fvgs == []


def test_custom_min_size_atr_config_lowers_exclusion_threshold():
    """REQ-25: min_size_atr is sourced from config, not hardcoded — a
    smaller configured multiplier admits the same gap REQ-09.1 excluded by
    default.
    """
    series = (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1010, low=1.1000, close=1.1000)  # 0 — TR=0.0010
        .candle(open=1.1000, high=1.1010, low=1.1000, close=1.1000)  # 1 — TR=0.0010
        .candle(open=1.1010, high=1.1012, low=1.10105, close=1.1011)  # 2 — tiny gap (low 1.10105 > candle0.high 1.1010)
        .build()
    )

    fvgs = detect_fvgs(series, config=FVGConfig(min_size_atr=0.01))

    assert len(fvgs) == 1
