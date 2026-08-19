from fixtures.synthetic import (
    bearish_mss_setup,
    bullish_mss_setup,
    mss_no_prior_opposite_swing_setup,
    mss_ratio_undershoot_setup,
    mss_uses_most_recent_opposite_swing_setup,
)

from core.config import MSSConfig
from composite.mss import detect_mss_events


def test_bullish_mss_flagged_when_close_decisively_beats_swing_high():
    """REQ-15.1, grounded charter-3 [00:10:32]: a swing low forms, then a
    swing high forms after it (prior opposite-extreme rejection satisfied),
    then a later candle CLOSES beyond the swing high by at least the
    decisive_close_ratio (default 0.25) of the swing-to-opposite-extreme
    distance -> bullish MSS flagged at the break candle.
    """
    series = bullish_mss_setup()

    events = detect_mss_events(series)

    assert len(events) == 1
    event = events[0]
    assert event.index == 5
    assert event.direction == "bullish"
    assert event.broken_swing.index == 3
    assert event.broken_swing.kind == "high"


def test_bearish_mss_mirrors_bullish_logic():
    """Mirror of the bullish case: swing high then swing low, then a close
    beyond the swing low by the decisive ratio -> bearish MSS. Forces the
    bearish branch to generalise rather than being hardcoded from the
    bullish-only implementation.
    """
    series = bearish_mss_setup()

    events = detect_mss_events(series)

    assert len(events) == 1
    event = events[0]
    assert event.index == 5
    assert event.direction == "bearish"
    assert event.broken_swing.index == 3
    assert event.broken_swing.kind == "low"


def test_close_beating_swing_but_under_decisive_ratio_is_not_mss():
    """Triangulates the ratio-weighted threshold: a close that beats the
    swing high price but falls short of decisive_close_ratio * distance
    must NOT be flagged — distinguishes the ratio computation from a plain
    "close beyond swing price" check.
    """
    series = mss_ratio_undershoot_setup()

    events = detect_mss_events(series)

    assert events == []


def test_break_with_no_prior_opposite_swing_excludes_mss():
    """REQ-16.1: a swing high with no opposite-kind swing ever recorded
    before it (a plain one-directional run) is excluded, no matter how
    decisively a later close clears it.
    """
    series = mss_no_prior_opposite_swing_setup()

    events = detect_mss_events(series)

    assert events == []


def test_pairs_broken_swing_with_the_most_recent_opposite_swing_before_it():
    """Triangulates "most recent ... formed BEFORE it" (design.md 4.4)
    against a nearest-by-index-distance implementation that ignores
    before/after order — an opposite-kind swing formed AFTER the broken
    swing must never be used for the distance computation, even when it is
    numerically closer in index than the correct (earlier) one.
    """
    series = mss_uses_most_recent_opposite_swing_setup()

    events = detect_mss_events(series)

    assert events == []


def test_decisive_close_ratio_is_read_from_config_not_hardcoded():
    """REQ-25: a higher configured decisive_close_ratio excludes an MSS the
    default (0.25) would have allowed.
    """
    series = mss_ratio_undershoot_setup()

    default_events = detect_mss_events(series)
    strict_events = detect_mss_events(series, config=MSSConfig(decisive_close_ratio=0.5))

    assert default_events == []
    assert strict_events == []

    lenient_events = detect_mss_events(series, config=MSSConfig(decisive_close_ratio=0.05))
    assert len(lenient_events) == 1
