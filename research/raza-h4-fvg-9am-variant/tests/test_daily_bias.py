from datetime import date, timedelta

from conftest import flat_bucket, override

from raza_h4fvg.daily_bias import daily_bias_for_session

M15_COUNT_24H = 96


def _two_day_series(session_date, yesterday_overrides=None, today_overrides=None, base=1.1000):
    """Builds yesterday's (17:00 NY, session_date-3) and today's (17:00
    NY, session_date-2) 96-bar daily buckets back-to-back, contiguous."""
    from raza_h4fvg.daily_bias import _daily_open_utc
    yesterday_open = _daily_open_utc(session_date - timedelta(days=3))
    today_open = _daily_open_utc(session_date - timedelta(days=2))
    assert today_open - yesterday_open == timedelta(hours=24)

    yesterday = flat_bucket(yesterday_open, M15_COUNT_24H, base=base, flat_delta=0.0005)
    today = flat_bucket(today_open, M15_COUNT_24H, base=base, flat_delta=0.0005)
    for idx, kwargs in (yesterday_overrides or {}).items():
        override(yesterday, idx, **kwargs)
    for idx, kwargs in (today_overrides or {}).items():
        override(today, idx, **kwargs)
    return tuple(yesterday + today)


def test_low_sweep_and_inside_close_gives_bullish_bias():
    session_date = date(2024, 6, 10)
    candles = _two_day_series(
        session_date,
        yesterday_overrides={0: dict(open=1.10, high=1.1010, low=1.0990, close=1.10)},
        today_overrides={
            50: dict(open=1.0995, high=1.1005, low=1.0970, close=1.0995),  # the sweep (low)
            95: dict(open=1.0995, high=1.1000, low=1.0990, close=1.0995),  # the bucket's own last bar sets the final close
        },
    )
    timestamps = [c.timestamp for c in candles]
    result = daily_bias_for_session(timestamps, candles, session_date)
    assert result.bias == "bullish"
    assert result.reason == "OK"


def test_high_sweep_and_inside_close_gives_bearish_bias():
    session_date = date(2024, 6, 10)
    candles = _two_day_series(
        session_date,
        yesterday_overrides={0: dict(open=1.10, high=1.1010, low=1.0990, close=1.10)},
        today_overrides={
            50: dict(open=1.1005, high=1.1030, low=1.0995, close=1.1005),  # the sweep (high)
            95: dict(open=1.1005, high=1.1008, low=1.1000, close=1.1005),  # the bucket's own last bar sets the final close
        },
    )
    timestamps = [c.timestamp for c in candles]
    result = daily_bias_for_session(timestamps, candles, session_date)
    assert result.bias == "bearish"
    assert result.reason == "OK"


def test_double_sweep_gives_no_bias():
    session_date = date(2024, 6, 10)
    candles = _two_day_series(
        session_date,
        yesterday_overrides={0: dict(open=1.10, high=1.1010, low=1.0990, close=1.10)},
        today_overrides={
            50: dict(open=1.0995, high=1.1030, low=1.0970, close=1.0995),  # both sides swept
            95: dict(open=1.0995, high=1.1000, low=1.0990, close=1.0995),
        },
    )
    timestamps = [c.timestamp for c in candles]
    result = daily_bias_for_session(timestamps, candles, session_date)
    assert result.bias is None
    assert result.reason == "DOUBLE_SWEEP"


def test_close_outside_range_gives_no_bias():
    session_date = date(2024, 6, 10)
    candles = _two_day_series(
        session_date,
        yesterday_overrides={0: dict(open=1.10, high=1.1010, low=1.0990, close=1.10)},
        today_overrides={
            50: dict(open=1.0995, high=1.1005, low=1.0960, close=1.0965),
            95: dict(open=1.0965, high=1.0970, low=1.0960, close=1.0965),  # the bucket's own LAST bar sets the final close
        },
    )
    timestamps = [c.timestamp for c in candles]
    result = daily_bias_for_session(timestamps, candles, session_date)
    assert result.bias is None
    assert result.reason == "NOT_INSIDE"


def test_missing_daily_data_is_reported_not_silently_dropped():
    session_date = date(2024, 6, 10)
    from raza_h4fvg.daily_bias import _daily_open_utc
    today_open = _daily_open_utc(session_date - timedelta(days=2))
    today = flat_bucket(today_open, M15_COUNT_24H)
    timestamps = [c.timestamp for c in today]  # yesterday's bucket is entirely absent
    result = daily_bias_for_session(timestamps, tuple(today), session_date)
    assert result.bias is None
    assert result.reason == "MISSING_DATA"
