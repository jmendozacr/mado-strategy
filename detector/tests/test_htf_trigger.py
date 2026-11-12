"""odd/tasks/htf-turtle-soup-trigger.md T1+T2: the 9:00/NY HTF Turtle Soup
trigger, scoped to the fixed-UTC H4 grid's 12:00 UTC candle only, gated on a
credited Key Level touch on that same candle (S1, S2).
"""

from datetime import datetime, timedelta

from causal.htf_trigger import find_9am_turtle_soup_triggers
from core.candle import Candle
from core.key_level import KeyLevel

_DAY = datetime(2026, 1, 5)  # a Monday, arbitrary

# Zone that the bearish fixture's purge wick (1.1035) lands inside, with an
# origin well before any trigger candle.
_ZONE = KeyLevel(kind="fvg", top=1.1040, bottom=1.1030, origin_index=0, expiry_index=None)


def _candle(hour, o, h, l, c, day=_DAY):
    return Candle(timestamp=day + timedelta(hours=hour), open=o, high=h, low=l, close=c)


def test_bearish_trigger_on_same_candle_wick_beyond_and_close_back():
    """08:00 UTC candle defines the range; 12:00 UTC candle wicks above its
    high (1.1035 > 1.1020, landing inside `_ZONE` [1.1030, 1.1040]) and
    closes back inside it (1.1005 <= 1.1020) -- a same-candle Turtle Soup
    with a credited Key Level touch -> bearish trigger at the 12:00 candle."""
    candles = (
        _candle(8, 1.1000, 1.1020, 1.0980, 1.1010),  # 08:00 UTC -- the "previous" candle
        _candle(12, 1.1010, 1.1035, 1.1000, 1.1005),  # 12:00 UTC -- sweeps high, closes back inside
    )
    triggers = find_9am_turtle_soup_triggers(candles, [_ZONE])
    assert len(triggers) == 1
    assert triggers[0].candle_index == 1
    assert triggers[0].direction == "bearish"
    assert triggers[0].key_level == _ZONE
    assert triggers[0].key_level_reaction == "reject_close_inside"


def test_bullish_trigger_on_same_candle_wick_beyond_and_close_back():
    zone = KeyLevel(kind="fvg", top=1.0970, bottom=1.0960, origin_index=0, expiry_index=None)
    candles = (
        _candle(8, 1.1000, 1.1020, 1.0980, 1.1010),
        _candle(12, 1.1005, 1.1015, 1.0960, 1.0990),  # sweeps low (1.0960 < 1.0980, inside zone), closes back inside (1.0990 >= 1.0980)
    )
    triggers = find_9am_turtle_soup_triggers(candles, [zone])
    assert len(triggers) == 1
    assert triggers[0].candle_index == 1
    assert triggers[0].direction == "bullish"
    assert triggers[0].key_level == zone


def test_no_credited_key_level_means_no_trigger():
    """Same Turtle Soup geometry as the bearish fixture, but with no
    registered Key Level at all -- S1's key-level touch is part of the
    trigger condition, not optional."""
    candles = (
        _candle(8, 1.1000, 1.1020, 1.0980, 1.1010),
        _candle(12, 1.1010, 1.1035, 1.1000, 1.1005),
    )
    assert find_9am_turtle_soup_triggers(candles, []) == []


def test_key_level_registered_but_not_touched_means_no_trigger():
    """A real Key Level exists, but far from where this purge wick reaches
    -- geometry alone is not enough."""
    far_zone = KeyLevel(kind="fvg", top=1.2000, bottom=1.1990, origin_index=0, expiry_index=None)
    candles = (
        _candle(8, 1.1000, 1.1020, 1.0980, 1.1010),
        _candle(12, 1.1010, 1.1035, 1.1000, 1.1005),
    )
    assert find_9am_turtle_soup_triggers(candles, [far_zone]) == []


def test_continuation_close_beyond_range_does_not_trigger():
    """The 12:00 candle sweeps the high but CLOSES beyond it too (1.1030 >
    1.1020) -- a continuation, not a rejection. No trigger, regardless of
    any registered Key Level."""
    candles = (
        _candle(8, 1.1000, 1.1020, 1.0980, 1.1010),
        _candle(12, 1.1010, 1.1035, 1.1005, 1.1030),
    )
    assert find_9am_turtle_soup_triggers(candles, [_ZONE]) == []


def test_no_wick_breach_does_not_trigger():
    candles = (
        _candle(8, 1.1000, 1.1020, 1.0980, 1.1010),
        _candle(12, 1.1005, 1.1015, 1.0990, 1.1000),  # stays fully inside the previous candle's range
    )
    assert find_9am_turtle_soup_triggers(candles, [_ZONE]) == []


def test_wrong_utc_hour_is_never_considered():
    """Same shape as the bearish-trigger fixture, but at 16:00 UTC instead
    of 12:00 -- must never trigger, since this isn't the 9am-NY-containing
    candle at all."""
    candles = (
        _candle(12, 1.1000, 1.1020, 1.0980, 1.1010),
        _candle(16, 1.1010, 1.1035, 1.1000, 1.1005),
    )
    assert find_9am_turtle_soup_triggers(candles, [_ZONE]) == []


def test_outside_bar_can_trigger_both_directions():
    """A candle that sweeps BOTH the previous high and low, closing back
    inside on both sides, is ambiguous by construction -- both triggers are
    reported (mirrors this project's existing outside-bar handling in
    composite.order_flow), no tie-break picked here. Each direction needs
    its own credited zone to actually fire."""
    bearish_zone = KeyLevel(kind="fvg", top=1.1040, bottom=1.1030, origin_index=0, expiry_index=None)
    bullish_zone = KeyLevel(kind="fvg", top=1.0970, bottom=1.0960, origin_index=0, expiry_index=None)
    candles = (
        _candle(8, 1.1000, 1.1020, 1.0980, 1.1010),
        _candle(12, 1.1000, 1.1035, 1.0960, 1.1000),  # sweeps both sides, closes back inside both
    )
    triggers = find_9am_turtle_soup_triggers(candles, [bearish_zone, bullish_zone])
    directions = {t.direction for t in triggers}
    assert directions == {"bearish", "bullish"}


def test_multiple_days_each_checked_independently():
    day2 = _DAY + timedelta(days=1)
    candles = (
        _candle(8, 1.1000, 1.1020, 1.0980, 1.1010),
        _candle(12, 1.1010, 1.1035, 1.1000, 1.1005, day=_DAY),  # day 1: bearish trigger
        _candle(8, 1.0990, 1.1000, 1.0960, 1.0980, day=day2),
        _candle(12, 1.0975, 1.0995, 1.0965, 1.0985, day=day2),  # day 2: stays fully inside, no trigger
    )
    triggers = find_9am_turtle_soup_triggers(candles, [_ZONE])
    assert len(triggers) == 1
    assert triggers[0].candle_index == 1
