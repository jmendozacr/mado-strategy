from fixtures.synthetic import CandleSeriesBuilder

from core.config import MSNRConfig
from primitives.msnr_levels import detect_msnr_levels, to_key_levels, to_key_levels_with_sbr_rbs


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


def test_rbs_a_shape_closed_above_flips_to_a_support_segment():
    """RBS (Resistance Becomes Support): once price CLOSES above an
    A-shape level, that level's resistance segment ends (expiry_index =
    the break candle) and a new segment starts there, now defending the
    SAME price as support, open-ended until its own next break."""
    series = (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1020, low=1.0995, close=1.1015)  # 0 -- bullish, pivot forms here
        .candle(open=1.1010, high=1.1012, low=1.0980, close=1.0990)  # 1 -- bearish, confirms a_shape at 1.1015
        .candle(open=1.0995, high=1.1025, low=1.0990, close=1.1020)  # 2 -- closes ABOVE 1.1015: RBS break
        .candle(open=1.1020, high=1.1030, low=1.1015, close=1.1025)  # 3 -- no further break
        .build()
    )
    levels = [lvl for lvl in detect_msnr_levels(series) if lvl.index == 0]

    key_levels = to_key_levels_with_sbr_rbs(levels, series.candles, MSNRConfig(zone_atr_multiple=0.1))

    assert len(key_levels) == 2
    first, second = key_levels
    assert first.origin_index == 0
    assert first.expiry_index == 2
    assert second.origin_index == 2
    assert second.expiry_index is None
    # same price line throughout the flip -- buffer width may differ per
    # segment (ATR is resampled fresh at each new origin), but the
    # midpoint price being defended never moves
    assert (first.top + first.bottom) / 2 == (second.top + second.bottom) / 2


def test_sbr_v_shape_chains_through_multiple_flips():
    """SBR then RBS again: a V-shape (support) level closed below flips
    to resistance (SBR); once THAT segment is itself closed above, it
    flips back to support (RBS) -- three chained segments total."""
    series = (
        CandleSeriesBuilder()
        .candle(open=1.1015, high=1.1020, low=1.0990, close=1.0995)  # 0 -- bearish, pivot forms here
        .candle(open=1.1000, high=1.1030, low=1.0998, close=1.1025)  # 1 -- bullish, confirms v_shape at 1.0995
        .candle(open=1.1000, high=1.1005, low=1.0980, close=1.0990)  # 2 -- closes BELOW 1.0995: SBR break
        .candle(open=1.0990, high=1.1010, low=1.0985, close=1.1000)  # 3 -- closes ABOVE 1.0995 again: RBS break
        .candle(open=1.1000, high=1.1010, low=1.0995, close=1.1005)  # 4 -- no further break
        .build()
    )
    levels = [lvl for lvl in detect_msnr_levels(series) if lvl.index == 0]

    key_levels = to_key_levels_with_sbr_rbs(levels, series.candles, MSNRConfig(zone_atr_multiple=0.1))

    assert len(key_levels) == 3
    origins = [kl.origin_index for kl in key_levels]
    expiries = [kl.expiry_index for kl in key_levels]
    assert origins == [0, 2, 3]
    assert expiries == [2, 3, None]


def test_level_never_broken_stays_a_single_open_ended_segment():
    series = (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1020, low=1.0995, close=1.1015)  # 0 -- bullish, pivot forms here
        .candle(open=1.1010, high=1.1012, low=1.0980, close=1.0990)  # 1 -- bearish, confirms a_shape
        .candle(open=1.0995, high=1.1010, low=1.0990, close=1.1000)  # 2 -- closes below 1.1015, no break
        .build()
    )
    levels = [lvl for lvl in detect_msnr_levels(series) if lvl.index == 0]

    key_levels = to_key_levels_with_sbr_rbs(levels, series.candles, MSNRConfig(zone_atr_multiple=0.1))

    assert len(key_levels) == 1
    assert key_levels[0].origin_index == 0
    assert key_levels[0].expiry_index is None
