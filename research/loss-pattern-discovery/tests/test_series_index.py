import datetime as dt

from core.candle import Candle, OHLCSeries

from common import series_index
from common.series_index import timestamps_for


def _series(n: int, start: dt.datetime) -> OHLCSeries:
    candles = tuple(
        Candle(start + dt.timedelta(minutes=15 * i), open=1.1, high=1.1, low=1.1, close=1.1)
        for i in range(n)
    )
    return OHLCSeries(candles=candles, instrument="X", timeframe="M15")


def test_timestamps_for_matches_series_candles():
    start = dt.datetime(2026, 1, 1)
    series = _series(5, start)
    assert timestamps_for(series) == [start + dt.timedelta(minutes=15 * i) for i in range(5)]


def test_stale_cache_entry_at_a_colliding_id_is_detected_and_recomputed():
    # Directly reproduce the exact bug class this module guards against: a
    # cache entry left over at some id, now describing a DIFFERENT, shorter
    # series than the one that currently happens to share that id (as can
    # genuinely occur when CPython reuses a freed tuple's id).
    start = dt.datetime(2026, 1, 1)
    real_series = _series(3, start)
    fake_key = id(real_series.candles)
    stale_fingerprint = (1, start - dt.timedelta(days=1), start - dt.timedelta(days=1))
    series_index._cache[fake_key] = (*stale_fingerprint, [start - dt.timedelta(days=1)])

    result = timestamps_for(real_series)
    assert result == [start + dt.timedelta(minutes=15 * i) for i in range(3)]


def test_repeated_calls_are_consistent():
    start = dt.datetime(2026, 1, 1)
    series = _series(10, start)
    first = timestamps_for(series)
    second = timestamps_for(series)
    assert first == second
