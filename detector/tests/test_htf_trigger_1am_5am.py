"""odd/tasks/htf-turtle-soup-trigger.md T7+T8 (S8, S9): the 1AM and 5AM
feeder-candle models, generalizing T1-T3's own trigger-geometry and
confirmation-window tests to `MODEL_1AM`/`MODEL_5AM`.
"""

from datetime import datetime, timedelta

from causal.htf_trigger import (
    MODEL_1AM,
    MODEL_5AM,
    confirmation_window_utc,
    find_turtle_soup_triggers,
)
from core.candle import Candle
from core.key_level import KeyLevel

_DAY = datetime(2026, 1, 5)


def _candle(hour, o, h, l, c, day=_DAY):
    return Candle(timestamp=day + timedelta(hours=hour), open=o, high=h, low=l, close=c)


def _htf_candle(ts):
    return Candle(timestamp=ts, open=1.1, high=1.1, low=1.1, close=1.1)


# --- 1AM model: previous candle = 00:00 UTC ("9PM range"), trigger = 04:00 UTC ---


def test_1am_trigger_is_array_adjacent_to_0000_utc():
    """S8: the "9PM range" candle (00:00 UTC) and the "1AM" candle (04:00
    UTC) are array-adjacent on the existing fixed-UTC grid -- verified
    against real UTC-offset arithmetic before building (see the module's
    own docstring), not assumed to generalize from the 9am model."""
    zone = KeyLevel(kind="fvg", top=1.1040, bottom=1.1030, origin_index=0, expiry_index=None)
    candles = (
        _candle(0, 1.1000, 1.1020, 1.0980, 1.1010),  # 00:00 UTC -- "9PM range"
        _candle(4, 1.1010, 1.1035, 1.1000, 1.1005),  # 04:00 UTC -- "1AM", sweeps high, closes back inside
    )
    triggers = find_turtle_soup_triggers(candles, [zone], MODEL_1AM)
    assert len(triggers) == 1
    assert triggers[0].candle_index == 1
    assert triggers[0].direction == "bearish"


def test_1am_wrong_utc_hour_is_never_considered():
    """Same shape, but at 08:00 UTC (the 5AM model's own trigger hour) --
    must never fire as a 1AM trigger."""
    zone = KeyLevel(kind="fvg", top=1.1040, bottom=1.1030, origin_index=0, expiry_index=None)
    candles = (
        _candle(4, 1.1000, 1.1020, 1.0980, 1.1010, day=_DAY),
        _candle(8, 1.1010, 1.1035, 1.1000, 1.1005, day=_DAY),
    )
    assert find_turtle_soup_triggers(candles, [zone], MODEL_1AM) == []


def test_1am_window_edt_is_0600_to_0800_utc():
    """July -- EDT (UTC-4): 02:00 NY = 06:00 UTC, 04:00 NY = 08:00 UTC."""
    trigger = _htf_candle(datetime(2026, 7, 6, 4, 0))
    start, end = confirmation_window_utc(trigger, MODEL_1AM)
    assert start == datetime(2026, 7, 6, 6, 0)
    assert end == datetime(2026, 7, 6, 8, 0)


def test_1am_window_est_is_0700_to_0900_utc():
    """January -- EST (UTC-5): 02:00 NY = 07:00 UTC, 04:00 NY = 09:00 UTC --
    straddles past the trigger candle's own [04:00,08:00) UTC window, which
    is fine: the LTF window mapping uses absolute UTC timestamps, not H4
    candle boundaries."""
    trigger = _htf_candle(datetime(2026, 1, 6, 4, 0))
    start, end = confirmation_window_utc(trigger, MODEL_1AM)
    assert start == datetime(2026, 1, 6, 7, 0)
    assert end == datetime(2026, 1, 6, 9, 0)


# --- 5AM model: previous candle = 04:00 UTC ("1AM range"), trigger = 08:00 UTC ---


def test_5am_trigger_is_array_adjacent_to_0400_utc():
    zone = KeyLevel(kind="fvg", top=1.1040, bottom=1.1030, origin_index=0, expiry_index=None)
    candles = (
        _candle(4, 1.1000, 1.1020, 1.0980, 1.1010),  # 04:00 UTC -- "1AM range"
        _candle(8, 1.1010, 1.1035, 1.1000, 1.1005),  # 08:00 UTC -- "5AM", sweeps high, closes back inside
    )
    triggers = find_turtle_soup_triggers(candles, [zone], MODEL_5AM)
    assert len(triggers) == 1
    assert triggers[0].candle_index == 1
    assert triggers[0].direction == "bearish"


def test_5am_wrong_utc_hour_is_never_considered():
    zone = KeyLevel(kind="fvg", top=1.1040, bottom=1.1030, origin_index=0, expiry_index=None)
    candles = (
        _candle(0, 1.1000, 1.1020, 1.0980, 1.1010, day=_DAY),
        _candle(4, 1.1010, 1.1035, 1.1000, 1.1005, day=_DAY),
    )
    assert find_turtle_soup_triggers(candles, [zone], MODEL_5AM) == []


def test_5am_window_edt_is_1000_to_1230_utc():
    """July -- EDT (UTC-4): 06:00 NY = 10:00 UTC, 08:30 NY = 12:30 UTC."""
    trigger = _htf_candle(datetime(2026, 7, 6, 8, 0))
    start, end = confirmation_window_utc(trigger, MODEL_5AM)
    assert start == datetime(2026, 7, 6, 10, 0)
    assert end == datetime(2026, 7, 6, 12, 30)


def test_5am_window_est_is_1100_to_1330_utc():
    """January -- EST (UTC-5): 06:00 NY = 11:00 UTC, 08:30 NY = 13:30 UTC."""
    trigger = _htf_candle(datetime(2026, 1, 6, 8, 0))
    start, end = confirmation_window_utc(trigger, MODEL_5AM)
    assert start == datetime(2026, 1, 6, 11, 0)
    assert end == datetime(2026, 1, 6, 13, 30)
