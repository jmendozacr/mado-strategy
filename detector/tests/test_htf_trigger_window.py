"""odd/tasks/htf-turtle-soup-trigger.md T3: the 09:00-10:30 NY-local
confirmation window (S4, 9:00/NY model only), DST-aware, mapped to UTC and
then to LTF candle indices.
"""

from datetime import datetime, timedelta

from causal.htf_trigger import confirmation_window_utc, ltf_window_indices
from core.candle import Candle


def _htf_candle(ts):
    return Candle(timestamp=ts, open=1.1, high=1.1, low=1.1, close=1.1)


def test_window_in_edt_is_1300_to_1430_utc():
    """July -- EDT (UTC-4): 09:00 NY = 13:00 UTC, 10:30 NY = 14:30 UTC."""
    trigger = _htf_candle(datetime(2026, 7, 6, 12, 0))  # the 12:00 UTC trigger candle itself
    start, end = confirmation_window_utc(trigger)
    assert start == datetime(2026, 7, 6, 13, 0)
    assert end == datetime(2026, 7, 6, 14, 30)


def test_window_in_est_is_1400_to_1530_utc():
    """January -- EST (UTC-5): 09:00 NY = 14:00 UTC, 10:30 NY = 15:30 UTC."""
    trigger = _htf_candle(datetime(2026, 1, 6, 12, 0))
    start, end = confirmation_window_utc(trigger)
    assert start == datetime(2026, 1, 6, 14, 0)
    assert end == datetime(2026, 1, 6, 15, 30)


def test_ltf_window_indices_finds_the_right_range():
    start_utc = datetime(2026, 7, 6, 13, 0)
    end_utc = datetime(2026, 7, 6, 14, 30)
    ltf_candles = tuple(
        _htf_candle(datetime(2026, 7, 6, 12, 45) + timedelta(minutes=15 * i)) for i in range(10)
    )
    # timestamps: 12:45, 13:00, 13:15, ..., 15:00 -- window [13:00,14:30) is
    # half-open (excludes 14:30 itself), so it covers indices 1..6 (13:00..14:15)
    result = ltf_window_indices(ltf_candles, start_utc, end_utc)
    assert result == (1, 6)


def test_ltf_window_indices_returns_none_when_nothing_falls_inside():
    start_utc = datetime(2026, 7, 6, 13, 0)
    end_utc = datetime(2026, 7, 6, 14, 30)
    ltf_candles = (_htf_candle(datetime(2026, 7, 6, 10, 0)), _htf_candle(datetime(2026, 7, 6, 20, 0)))
    assert ltf_window_indices(ltf_candles, start_utc, end_utc) is None
