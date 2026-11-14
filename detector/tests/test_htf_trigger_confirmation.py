"""odd/tasks/htf-turtle-soup-trigger.md T4: LTF Model-1 confirmation
cascaded from an HTF trigger, bounded by the trigger's own confirmation
window (not an HTF true_break check -- the HTF event already resolved
once, as the trigger itself).
"""

from datetime import datetime, timedelta

from causal.htf_trigger import confirm_in_ltf_window
from core.candle import Candle
from core.config import Model1Config
from core.results import DetectionStatus
from primitives.crt_range import CRTRange

_BASE = datetime(2026, 1, 1, 13, 0)  # arbitrary, inside the 09:00-10:30 NY confirmation window in spirit


def _candle(o, h, l, c, i):
    return Candle(timestamp=_BASE + timedelta(minutes=15 * i), open=o, high=h, low=l, close=c)


def test_clean_confirmation_inside_the_window():
    candles = (
        _candle(1.1000, 1.1020, 1.0980, 1.1010, 0),  # 0 -- range
        _candle(1.1010, 1.1035, 1.1000, 1.1015, 1),  # 1 -- anchor, purges High
        _candle(1.1000, 1.1005, 1.0950, 1.0960, 2),  # 2 -- confirms
        _candle(1.0960, 1.1012, 1.0955, 1.0965, 3),  # 3 -- retest
        _candle(1.0965, 1.0968, 1.0900, 1.0910, 4),  # 4 -- expansion -> confirms
    )
    ltf_range = CRTRange(
        model="2-candle", high=1.1020, low=1.0980,
        start_index=0, end_index=1, resolution="false_break", resolved_at_index=1,
    )
    result = confirm_in_ltf_window(candles, [ltf_range], window=(1, 4), direction="bearish", config=Model1Config())
    assert result is not None
    assert result.anchor_index == 1
    assert result.retest_index == 3
    assert result.status == DetectionStatus.CONFIRMED


def test_retry_inside_the_window_still_confirms():
    candles = (
        _candle(1.1000, 1.1020, 1.0980, 1.1010, 0),  # 0 -- range
        _candle(1.1010, 1.1025, 1.1005, 1.1015, 1),  # 1 -- anchor1, purges High(1.1025)
        _candle(1.1015, 1.1035, 1.1010, 1.1030, 2),  # 2 -- breaches anchor1.high -> INVALIDATED; becomes anchor2
        _candle(1.1010, 1.1012, 1.0950, 1.0960, 3),  # 3 -- anchor2 confirms
        _candle(1.0965, 1.1020, 1.0955, 1.0970, 4),  # 4 -- retest
        _candle(1.0900, 1.0905, 1.0700, 1.0800, 5),  # 5 -- confirms (strictly after retest)
    )
    ltf_range = CRTRange(
        model="2-candle", high=1.1020, low=1.0980,
        start_index=0, end_index=1, resolution="false_break", resolved_at_index=1,
    )
    result = confirm_in_ltf_window(candles, [ltf_range], window=(1, 5), direction="bearish", config=Model1Config())
    assert result is not None
    assert result.anchor_index == 2  # re-anchored to the breaching candle
    assert result.retest_index == 4
    assert result.status == DetectionStatus.CONFIRMED


def test_chain_running_past_the_window_is_unconfirmed_not_an_error():
    """Same fixture as the retry test, but the window ends right where the
    retry's own invalidation lands -- there is no room left to re-anchor,
    so this must report unconfirmed (`None`), never raise and never report
    a false CONFIRMED/PENDING using data outside the window."""
    candles = (
        _candle(1.1000, 1.1020, 1.0980, 1.1010, 0),
        _candle(1.1010, 1.1025, 1.1005, 1.1015, 1),
        _candle(1.1015, 1.1035, 1.1010, 1.1030, 2),  # breaches anchor1 right at the window's edge
        _candle(1.1010, 1.1012, 1.0950, 1.0960, 3),  # exists in the series but OUTSIDE the window
    )
    ltf_range = CRTRange(
        model="2-candle", high=1.1020, low=1.0980,
        start_index=0, end_index=1, resolution="false_break", resolved_at_index=1,
    )
    result = confirm_in_ltf_window(candles, [ltf_range], window=(1, 2), direction="bearish", config=Model1Config())
    assert result is None


def test_no_candidate_in_window_or_direction_returns_none():
    candles = (
        _candle(1.1000, 1.1020, 1.0980, 1.1010, 0),
        _candle(1.1010, 1.1035, 1.1000, 1.1015, 1),
        _candle(1.1000, 1.1005, 1.0950, 1.0960, 2),
        _candle(1.0960, 1.1012, 1.0955, 1.0965, 3),
        _candle(1.0965, 1.0968, 1.0900, 1.0910, 4),
    )
    ltf_range = CRTRange(
        model="2-candle", high=1.1020, low=1.0980,
        start_index=0, end_index=1, resolution="false_break", resolved_at_index=1,
    )
    # Real bearish anchor exists at index 1, but we ask for bullish -- no candidate.
    assert confirm_in_ltf_window(candles, [ltf_range], window=(1, 4), direction="bullish", config=Model1Config()) is None
    # Real bearish anchor exists at index 1, but the window starts after it.
    assert confirm_in_ltf_window(candles, [ltf_range], window=(2, 4), direction="bearish", config=Model1Config()) is None


def test_earliest_anchor_across_competing_ranges_wins():
    """Two independent LTF ranges both produce a bearish anchor inside the
    window; the earlier one must be the one tracked, mirroring R-strict's
    own earliest-wins tie-break rule (never the later, "better-looking" one)."""
    candles = (
        _candle(1.1000, 1.1020, 1.0980, 1.1010, 0),  # 0 -- range A
        _candle(1.1010, 1.1025, 1.1005, 1.1015, 1),  # 1 -- range A's anchor, purges High(1.1020)
        _candle(1.1000, 1.1005, 1.0950, 1.0960, 2),  # 2 -- confirms range A's anchor
        _candle(1.0960, 1.1012, 1.0955, 1.0965, 3),  # 3 -- retest
        _candle(1.0965, 1.0968, 1.0900, 1.0910, 4),  # 4 -- expansion -> confirms
    )
    range_a = CRTRange(
        model="2-candle", high=1.1020, low=1.0980,
        start_index=0, end_index=1, resolution="false_break", resolved_at_index=1,
    )
    # Range B is a genuine second candidate -- its own anchor is index 2
    # (candle2's high 1.1005 breaches range B's own high 1.1000), strictly
    # LATER than range A's anchor (index 1). If "latest wins" were used
    # instead of "earliest wins," this test would pick range B and track
    # from anchor_index=2 instead.
    range_b = CRTRange(
        model="2-candle", high=1.1000, low=1.0990,
        start_index=1, end_index=2, resolution="false_break", resolved_at_index=2,
    )
    result = confirm_in_ltf_window(
        candles, [range_b, range_a], window=(1, 4), direction="bearish", config=Model1Config(),
    )
    assert result is not None
    assert result.anchor_index == 1
    assert result.status == DetectionStatus.CONFIRMED
