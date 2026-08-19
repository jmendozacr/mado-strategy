from fixtures.synthetic import CandleSeriesBuilder, bearish_purge_setup

from primitives.swing import detect_swings


def test_detects_fractal_swing_high():
    series = (
        CandleSeriesBuilder()
        .candle(open=1.0, high=1.0005, low=0.9995, close=1.0)  # index 0
        .candle(open=1.0, high=1.0020, low=0.9995, close=1.0)  # index 1 — swing high
        .candle(open=1.0, high=1.0010, low=0.9995, close=1.0)  # index 2
        .build()
    )

    swings = detect_swings(series)

    assert len(swings) == 1
    assert swings[0].index == 1
    assert swings[0].price == 1.0020
    assert swings[0].kind == "high"


def test_detects_fractal_swing_low():
    series = (
        CandleSeriesBuilder()
        .candle(open=1.0, high=1.0005, low=1.0000, close=1.0)  # index 0
        .candle(open=1.0, high=1.0005, low=0.9980, close=1.0)  # index 1 — swing low
        .candle(open=1.0, high=1.0005, low=0.9990, close=1.0)  # index 2
        .build()
    )

    swings = detect_swings(series)

    assert len(swings) == 1
    assert swings[0].index == 1
    assert swings[0].price == 0.9980
    assert swings[0].kind == "low"


def test_tied_highs_are_not_swings():
    series = (
        CandleSeriesBuilder()
        .candle(open=1.0, high=1.0005, low=0.9995, close=1.0)  # index 0
        .candle(open=1.0, high=1.0020, low=0.9995, close=1.0)  # index 1 — tied high
        .candle(open=1.0, high=1.0020, low=0.9995, close=1.0)  # index 2 — tied high
        .candle(open=1.0, high=1.0005, low=0.9995, close=1.0)  # index 3
        .build()
    )

    swings = detect_swings(series)

    assert swings == []


def test_pre_purge_high_flagged_before_purge_candle_appears():
    """REQ-06.1, grounded charter-2 [00:05:28]: the swing high at index 1
    must already be detectable from the series truncated right before the
    purge candle (index 3) appears — the detector never needs to see the
    purge to have flagged what it purges.
    """
    full_series = bearish_purge_setup()
    pre_purge_series = full_series.up_to(3)  # candles 0, 1, 2 only

    swings = detect_swings(pre_purge_series)

    assert len(swings) == 1
    assert swings[0].index == 1
    assert swings[0].kind == "high"
    assert swings[0].price == full_series.candles[1].high


def test_series_shorter_than_three_candles_returns_no_swings():
    series = (
        CandleSeriesBuilder()
        .candle(open=1.0, high=1.0005, low=0.9995, close=1.0)
        .candle(open=1.0, high=1.0020, low=0.9995, close=1.0)
        .build()
    )

    swings = detect_swings(series)

    assert swings == []
