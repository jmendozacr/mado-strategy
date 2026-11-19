"""Tests for the D1/D2/D3 causal anchor-source mechanism
(causal_anchor_v2.py). Design: design-causal-anchor-source.md
("Cierre de diseño -- ronda 3"), corrected per the review of commit
86a1e58 (off-by-one in the "still not swept" condition; gap-safe
timestamp-based age; independent High/Low sides). Nothing under
detector/ or scanner/ is touched.
"""
from datetime import datetime, timedelta

import pytest

from core.candle import Candle
from core.config import Model1Config
from core.results import DetectionStatus

import causal_anchor_v2 as ca
import causal_intrabar as ci


def _m15(ohlc, start=datetime(2026, 1, 1, 0, 0), step=timedelta(minutes=15)):
    """ohlc: list of (open, high, low, close) tuples, one per candle."""
    return tuple(
        Candle(timestamp=start + step * i, open=o, high=h, low=l, close=c)
        for i, (o, h, l, c) in enumerate(ohlc)
    )


# A wide, never-breached filler candle -- used to pad synthetic series
# without it ever accidentally becoming a competing anchor candidate.
_FAR = (100.0, 100000.0, -100000.0, 100.0)


# ---------------------------------------------------------------------------
# find_first_valid_anchor: the corrected breach condition (design S19
# review, commit 86a1e58's fix) -- tests 12-14 of the design's S7.
# ---------------------------------------------------------------------------

def test_bearish_breach_basic():
    """Origin candle 0 (high=100). Candle 1 doesn't break it. Candle 2
    breaks it (high=101 > 100). Expected: anchor=(0, 2)."""
    candles = _m15([
        (100.0, 100.0, 95.0, 99.0),   # 0: origin, high=100
        (99.0, 99.5, 98.0, 99.0),     # 1: does not break
        (99.0, 101.0, 98.0, 100.5),   # 2: breaks (high=101 > 100)
    ])
    result = ca.find_first_valid_anchor(candles, 0, 2, "bearish")
    assert result == (0, 2)


def test_bullish_breach_basic():
    """Mirror of the bearish case, on the low side."""
    candles = _m15([
        (100.0, 105.0, 95.0, 99.0),   # 0: origin, low=95
        (99.0, 100.0, 96.0, 99.0),    # 1: does not break
        (99.0, 100.0, 94.0, 98.0),    # 2: breaks (low=94 < 95)
    ])
    result = ca.find_first_valid_anchor(candles, 0, 2, "bullish")
    assert result == (0, 2)


def test_touch_without_exceeding_is_not_a_breach():
    """candle.high == level.high (touches, does not exceed) must NOT
    count as a breach -- `is_broken_by` uses strict `>`/`<`."""
    candles = _m15([
        (100.0, 100.0, 95.0, 99.0),   # 0: origin, high=100
        (99.0, 100.0, 98.0, 99.5),    # 1: touches exactly 100, does not exceed
    ])
    assert ca.find_first_valid_anchor(candles, 0, 1, "bearish") is None


def test_off_by_one_fix_candle_already_broken_before_j_is_excluded():
    """The exact bug the user's review of commit 86a1e58 caught: a
    level already broken by a candle BEFORE j must not be re-offered as
    a candidate at a later j, even if j itself would also exceed it.
    Origin candle 0 (high=100). Candle 1 already breaks it (high=105).
    Candle 2 would ALSO exceed level.high, but candle 0 is no longer
    "open" by then -- candle 1 is the one and only valid anchor for
    origin 0, and nothing should match origin 0 again at j=2."""
    candles = _m15([
        (100.0, 100.0, 95.0, 99.0),    # 0: origin, high=100
        (99.0, 105.0, 98.0, 103.0),    # 1: FIRST breach of origin 0's high
        (103.0, 108.0, 102.0, 107.0),  # 2: would also exceed 100, but origin 0 already consumed at j=1
    ])
    result = ca.find_first_valid_anchor(candles, 0, 2, "bearish")
    assert result == (0, 1), "origin 0 must anchor at j=1 (the FIRST breach), not be reusable at j=2"


def test_independent_high_low_sides():
    """Origin candle 0 has high=100, low=95. Candle 1 breaks the HIGH
    side (high=105) but NOT the low side (low=96, above 95). A later
    BULLISH (low-side) search must still find origin 0 as a valid
    candidate when its low eventually gets broken -- breaking one side
    must never disqualify the other."""
    candles = _m15([
        (100.0, 100.0, 95.0, 99.0),   # 0: origin, high=100, low=95
        (99.0, 105.0, 96.0, 103.0),   # 1: breaks HIGH side only (low=96 > 95, untouched)
        (103.0, 104.0, 94.0, 95.5),   # 2: NOW breaks the LOW side (low=94 < 95)
    ])
    # Bearish (high-side) search: origin 0 anchors at j=1, as expected.
    assert ca.find_first_valid_anchor(candles, 0, 2, "bearish") == (0, 1)
    # Bullish (low-side) search over the SAME candles: origin 0's low side
    # was never touched before j=2, so it must still be a valid candidate.
    assert ca.find_first_valid_anchor(candles, 0, 2, "bullish") == (0, 2)


def test_level_expires_by_timestamp_not_bar_count_across_a_gap():
    """Origin candle 0 at 00:00 (available_at 00:15). A data gap skips
    straight to 05:00 for candle 1 (available_at 05:15) -- only ONE bar
    index apart, but 5 real hours later, past the 4h age window. Must
    be treated as expired (gap-safe: timestamp-based, never bar-count)."""
    candles = (
        Candle(timestamp=datetime(2026, 1, 1, 0, 0), open=100.0, high=100.0, low=95.0, close=99.0),
        Candle(timestamp=datetime(2026, 1, 1, 5, 0), open=99.0, high=106.0, low=98.0, close=104.0),
    )
    # candle 1 breaks candle 0's high (106 > 100), but only after the level expired.
    assert ca.find_first_valid_anchor(candles, 0, 1, "bearish") is None


def test_level_still_valid_at_exactly_four_hours():
    """Boundary: available_at(j) - available_at(i) == 4h exactly must
    NOT be expired (strict `>` in the expiry check, per the design).
    Padding candles must stay strictly INSIDE the origin's [low,high]
    (95,100) so they never break it prematurely -- unlike `_FAR`, which
    is only safe as a never-broken filler, not as a non-breaking one."""
    narrow_padding = (98.0, 99.0, 96.0, 98.0)
    ohlc = [narrow_padding] * 17
    ohlc[0] = (100.0, 100.0, 95.0, 99.0)   # origin, high=100
    ohlc[16] = (99.0, 105.0, 98.0, 103.0)  # breaches at exactly +4h (available_at)
    candles = _m15(ohlc)
    assert ca.find_first_valid_anchor(candles, 0, 16, "bearish") == (0, 16)


def test_level_expired_just_past_four_hours():
    """4h15min later (one M15 bar past the exact-4h boundary above),
    via a direct gap in the timestamps rather than padding with bars
    (padding with same-level filler bars would itself create other,
    still-unexpired candidates by the time the breach bar arrives --
    a real effect of the design, not a bug; isolating origin 0 cleanly
    needs a sparse two-candle series instead)."""
    candles = (
        Candle(timestamp=datetime(2026, 1, 1, 0, 0), open=100.0, high=100.0, low=95.0, close=99.0),
        Candle(timestamp=datetime(2026, 1, 1, 4, 15), open=99.0, high=105.0, low=98.0, close=103.0),
    )
    assert ca.find_first_valid_anchor(candles, 0, 1, "bearish") is None


def test_never_resolving_level_is_still_eligible():
    """The old mechanism required a range to classify as true/false
    break within max_lookback to exist at all. The new mechanism has no
    such notion -- a level that is swept via a plain wick breach is
    eligible regardless of what a retrospective true/false-break
    classification would have said (this function never computes one)."""
    candles = _m15([
        (100.0, 100.0, 95.0, 99.0),   # 0: origin
        (99.0, 101.0, 98.0, 99.5),    # 1: wick pokes beyond (101 > 100) but closes back inside -- a
                                        #    "false_break"-shaped candle under the OLD classification,
                                        #    yet still a valid anchor here on the wick breach alone.
    ])
    assert ca.find_first_valid_anchor(candles, 0, 1, "bearish") == (0, 1)


def test_causal_invariance_same_past_different_futures():
    """Two histories share candles 0-2 exactly; they diverge at index 3
    onward. The anchor decision restricted to [0,2] must be identical
    regardless of what happens at index 3+."""
    shared = [
        (100.0, 100.0, 95.0, 99.0),   # 0: origin, high=100
        (99.0, 99.5, 98.0, 99.0),     # 1: no breach
        (99.0, 101.0, 98.0, 100.5),   # 2: breaches -- anchor=(0,2)
    ]
    history_a = _m15(shared + [(100.5, 102.0, 99.0, 101.0)])      # diverges: continues up
    history_b = _m15(shared + [(100.5, 100.6, 90.0, 91.0)])        # diverges: reverses hard
    result_a = ca.find_first_valid_anchor(history_a, 0, 2, "bearish")
    result_b = ca.find_first_valid_anchor(history_b, 0, 2, "bearish")
    assert result_a == result_b == (0, 2)


# ---------------------------------------------------------------------------
# confirm_in_ltf_window_v2: end-to-end with the real _track_anchor
# (engulf/retest/confirmation/retry-on-invalidation, reused UNMODIFIED)
# ---------------------------------------------------------------------------

def test_confirm_in_ltf_window_v2_full_bullish_sequence_confirms():
    candles = _m15([
        _FAR,                              # 0: filler, never breached
        _FAR,                              # 1: filler, never breached
        (97.0, 100.0, 95.0, 98.0),         # 2: origin, low=95
        (100.0, 102.0, 90.0, 99.0),         # 3: anchor -- purges low (90 < 95), body [99,100]
        (101.0, 106.0, 100.0, 105.0),       # 4: engulf -- closes (105) beyond body_high (100)
        (103.0, 104.0, 99.5, 102.5),         # 5: retest -- wick overlaps [99,100], retest_open=103;
                                               #    close(102.5) < open(103) so it does NOT self-confirm
        (103.0, 105.0, 102.0, 104.0),        # 6: closes (104) beyond retest_open (103) -- CONFIRMED
        _FAR, _FAR, _FAR,
    ])
    config = Model1Config()
    signal = ca.confirm_in_ltf_window_v2(candles, (0, 9), "bullish", config)
    assert signal is not None
    assert signal.status == DetectionStatus.CONFIRMED
    assert signal.origin_index == 2
    assert signal.anchor_index == 3
    assert signal.confirmation_index == 6


def test_confirm_in_ltf_window_v2_retry_on_invalidation():
    """First anchor attempt (index 2) gets invalidated at index 3
    (closes beyond the protected extreme before confirming);
    `_track_anchor`'s own retry loop (reused unmodified) picks up index
    3 itself as the new `current_anchor` (exactly the old mechanism's
    behavior: `current_anchor = result.confirmation_index`) and
    continues from there using candle 3's OWN body/protected_extreme."""
    candles = _m15([
        _FAR,
        (97.0, 100.0, 95.0, 98.0),           # 1: origin, low=95
        (100.0, 101.0, 90.0, 99.0),           # 2: first anchor -- purges low (90<95), body [99,100],
                                                #    protected_extreme=90 (this candle's own low)
        (99.0, 99.5, 80.0, 81.0),             # 3: invalidates attempt #1 (close=81 < 90) -- becomes
                                                #    the retry's new anchor; its own body is [81,99],
                                                #    protected_extreme=80 (its own low)
        (85.0, 102.0, 84.0, 101.0),            # 4: confirms retry #2 (close=101 > body_high=99)
        (98.0, 100.0, 95.0, 97.0),              # 5: retest -- wick overlaps [81,99]; close(97) < open(98)
                                                #    so it does NOT self-confirm; retest_open=98
        (96.0, 101.0, 95.0, 99.0),               # 6: closes (99) beyond retest_open (98) -- CONFIRMED
        _FAR, _FAR, _FAR,
    ])
    config = Model1Config()
    signal = ca.confirm_in_ltf_window_v2(candles, (0, 9), "bullish", config)
    assert signal is not None
    assert signal.status == DetectionStatus.CONFIRMED
    assert signal.origin_index == 1, "origin_index must be preserved through the retry"
    assert signal.anchor_index == 3, "anchor_index must be reassigned to the retry's own anchor"
    assert signal.confirmation_index == 6


# ---------------------------------------------------------------------------
# Window-boundary helpers (design S19 S0/S1 -- old vs. new 9AM windows)
# ---------------------------------------------------------------------------

def test_old_window_fns_matches_confirmation_window_utc():
    from causal.htf_trigger import MODEL_9AM, confirmation_window_utc
    from types import SimpleNamespace

    window_open_ts = datetime(2026, 3, 10, 13, 0)  # some 9AM-NY-equivalent UTC open
    expected = confirmation_window_utc(SimpleNamespace(timestamp=window_open_ts), MODEL_9AM)
    start_fn, end_fn = ca.old_window_fns(MODEL_9AM)
    assert (start_fn(window_open_ts), end_fn(window_open_ts)) == expected


def test_new_9am_window_fns_boundaries():
    window_open_ts = datetime(2026, 3, 10, 13, 0)  # 09:00 NY equivalent
    start_fn, end_fn = ca.new_9am_window_fns()
    assert start_fn(window_open_ts) == window_open_ts
    assert end_fn(window_open_ts) == window_open_ts + timedelta(hours=4)


@pytest.mark.parametrize("model_name,windows_9am,expected_hours", [
    ("9am", "new", 2),
    ("9am", "old", 4),
    ("1am", "new", 4),   # 1AM is never widened, regardless of windows_9am
    ("1am", "old", 4),
])
def test_activation_window_close_ts(model_name, windows_9am, expected_hours):
    window_open_ts = datetime(2026, 3, 10, 13, 0)
    result = ca.activation_window_close_ts(window_open_ts, model_name, windows_9am)
    assert result == window_open_ts + timedelta(hours=expected_hours)
