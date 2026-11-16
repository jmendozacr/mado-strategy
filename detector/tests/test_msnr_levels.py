from fixtures.synthetic import CandleSeriesBuilder

from core.config import MSNRConfig
from primitives.msnr_levels import detect_msnr_levels, to_key_levels


def test_bullish_then_bearish_candle_forms_a_shape_resistance_at_bullish_close():
    """MSNR A-shape (resistance): a bullish candle followed by a bearish
    one -- the level sits at the CLOSE of the bullish candle, not either
    candle's wick."""
    series = (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1020, low=1.0995, close=1.1015)  # 0 -- bullish
        .candle(open=1.1010, high=1.1012, low=1.0980, close=1.0990)  # 1 -- bearish
        .build()
    )

    levels = detect_msnr_levels(series)

    assert len(levels) == 1
    level = levels[0]
    assert level.kind == "a_shape"
    assert level.index == 0
    assert level.price == series.candles[0].close


def test_bearish_then_bullish_candle_forms_v_shape_support_at_bearish_close():
    """MSNR V-shape (support): a bearish candle followed by a bullish one
    -- the level sits at the CLOSE of the bearish candle."""
    series = (
        CandleSeriesBuilder()
        .candle(open=1.1015, high=1.1020, low=1.0990, close=1.0995)  # 0 -- bearish
        .candle(open=1.1000, high=1.1030, low=1.0998, close=1.1025)  # 1 -- bullish
        .build()
    )

    levels = detect_msnr_levels(series)

    assert len(levels) == 1
    level = levels[0]
    assert level.kind == "v_shape"
    assert level.index == 0
    assert level.price == series.candles[0].close


def test_two_candles_same_direction_form_no_level():
    """Neither shape requires a single candle to reverse the OTHER's
    direction -- two same-direction candles (or a doji breaking either
    streak) must not register a pivot."""
    series = (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1020, low=1.0995, close=1.1015)  # 0 -- bullish
        .candle(open=1.1015, high=1.1035, low=1.1010, close=1.1030)  # 1 -- bullish
        .build()
    )

    levels = detect_msnr_levels(series)

    assert levels == []


def test_doji_candle_breaks_the_pivot_pattern():
    """A doji (close == open) is neither bullish nor bearish -- it must
    not satisfy either half of the A-shape/V-shape pair."""
    series = (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1020, low=1.0995, close=1.1015)  # 0 -- bullish
        .candle(open=1.1010, high=1.1020, low=1.1000, close=1.1010)  # 1 -- doji
        .build()
    )

    levels = detect_msnr_levels(series)

    assert levels == []


def test_to_key_levels_buffers_the_close_price_by_atr():
    """MSNR levels are a single close PRICE, not a wick-to-wick zone --
    `KeyLevel` needs a nonzero [bottom, top] width or a real wick could
    never land inside it (alignment.htf_ltf's qualifying check is an
    inclusive range, not an exact-equality test). Buffered symmetrically
    around the close by `MSNRConfig.zone_atr_multiple` * ATR, the same
    ATR-relative-not-raw-constant convention as every other config in
    this module (REQ-31 precedent, BacktestConfig.sl_buffer_atr_multiple).
    """
    series = (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1020, low=1.0995, close=1.1015)  # 0 -- bullish
        .candle(open=1.1010, high=1.1012, low=1.0980, close=1.0990)  # 1 -- bearish
        .build()
    )
    levels = detect_msnr_levels(series)

    key_levels = to_key_levels(levels, series.candles, MSNRConfig(zone_atr_multiple=0.1))

    assert len(key_levels) == 1
    key_level = key_levels[0]
    assert key_level.kind == "msnr"
    assert key_level.origin_index == 0
    assert key_level.bottom < series.candles[0].close < key_level.top
