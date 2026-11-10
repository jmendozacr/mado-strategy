from datetime import datetime

from fixtures.synthetic import (
    model1_body_tiebreak_aligned_color_bullish_setup,
    model1_body_tiebreak_aligned_color_setup,
    model1_body_tiebreak_big_body_setup,
    model1_body_tiebreak_small_body_setup,
    model1_confirmed_setup,
    model1_delayed_confirmation_after_retest_setup,
    model1_delayed_engulf_charter2_setup,
    model1_dual_purge_and_fvg_fill_charter2_setup,
    model1_invalidated_setup,
    model1_pending_setup,
    model1_pre_confirmation_breach_setup,
    model1_purge_engulf_charter2_setup,
    model1_wick_priority_setup,
)

from core.candle import Candle, OHLCSeries
from core.config import Model1Config
from core.results import DetectionStatus
from entries.model1 import detect_model1_signals
from primitives.crt_range import CRTRange


def _find(signals, anchor_index, direction, confirmation_type="purge_engulf"):
    return next(
        s
        for s in signals
        if s.anchor_index == anchor_index
        and s.direction == direction
        and s.confirmation_type == confirmation_type
    )


# --- Anchor detection: wick-vs-body entry selection (REQ-20), isolated from
# the post-anchor CONFIRMED/INVALIDATED/PENDING outcome ---


def test_close_beyond_wick_extreme_uses_wick_regardless_of_body_size():
    """REQ-20.1: confirming close clears the anchor's WICK extreme ->
    entry_type=wick, entry_price=the retest-side body boundary (REQ-47.2's
    formula, mirrored here — real-trade evidence showed the swept extreme
    itself is never where a Model-1 wick entry actually fills),
    regardless of the anchor's body_ratio.
    """
    series = model1_wick_priority_setup()

    signal = _find(detect_model1_signals(series), anchor_index=1, direction="bearish")

    assert signal.entry_type == "wick"
    assert signal.entry_price == 1.1010


def test_middle_zone_close_with_big_body_tiebreaks_to_body():
    """REQ-20, charter-2 [00:11:18]: confirming close clears the anchor's
    BODY extreme but not its WICK extreme (middle zone); anchor's
    body_ratio (0.767) >= body_ratio_tiebreak (0.6) -> tiebreak favors
    Body, entry_price = anchor's body extreme.
    """
    series = model1_body_tiebreak_big_body_setup()

    signal = _find(detect_model1_signals(series), anchor_index=1, direction="bearish")

    assert signal.entry_type == "body"
    assert signal.entry_price == 1.1005


def test_middle_zone_close_with_small_body_tiebreaks_to_wick():
    """REQ-20, charter-2 [00:12:02]: same middle-zone close condition, but
    anchor's body_ratio (0.044) < body_ratio_tiebreak (0.6) -> tiebreak
    favors Wick, entry_price = the retest-side body boundary.
    """
    series = model1_body_tiebreak_small_body_setup()

    signal = _find(detect_model1_signals(series), anchor_index=1, direction="bearish")

    assert signal.entry_type == "wick"
    assert signal.entry_price == 1.1015


def test_middle_zone_close_with_anchor_color_aligned_to_direction_uses_anchor_open_bearish():
    """REQ-20 regression, charter-2 [00:11:04]-[00:11:18]: "Body" and
    "Open" are synonyms in the source methodology — Body entry is always
    anchor.open, with no color/direction-dependent min/max logic. Here the
    anchor's color matches the trade direction (bearish anchor, bearish
    trade), placing anchor.open on the body's HIGH side, but the entry
    price is still anchor.open.
    """
    series = model1_body_tiebreak_aligned_color_setup()

    signal = _find(detect_model1_signals(series), anchor_index=1, direction="bearish")

    assert signal.entry_type == "body"
    assert signal.entry_price == 1.1038


def test_middle_zone_close_with_anchor_color_aligned_to_direction_uses_anchor_open_bullish():
    """REQ-20 regression, bullish mirror: anchor's color matches the trade
    direction (bullish anchor, bullish trade), placing anchor.open on the
    body's LOW side — entry price is still anchor.open.
    """
    series = model1_body_tiebreak_aligned_color_bullish_setup()

    signal = _find(detect_model1_signals(series), anchor_index=1, direction="bullish")

    assert signal.entry_type == "body"
    assert signal.entry_price == 1.0962


def test_body_ratio_tiebreak_is_read_from_config_not_hardcoded():
    """REQ-25: a lower configured body_ratio_tiebreak flips the small-body
    fixture's tiebreak outcome from Wick (default 0.6) to Body (threshold
    lowered below its 0.044 ratio) — proves the threshold is read from
    config, not hardcoded.
    """
    series = model1_body_tiebreak_small_body_setup()

    default_signal = _find(detect_model1_signals(series), anchor_index=1, direction="bearish")
    lenient_signal = _find(
        detect_model1_signals(series, config=Model1Config(body_ratio_tiebreak=0.01)),
        anchor_index=1,
        direction="bearish",
    )

    assert default_signal.entry_type == "wick"
    assert lenient_signal.entry_type == "body"


# --- Post-anchor state transitions (REQ-21): CONFIRMED / INVALIDATED / PENDING ---


def test_retest_and_same_candle_close_beyond_own_open_confirms():
    """REQ-21: retest occurs and the retest candle itself closes beyond its
    own open in the trade direction (no minimum threshold) -> CONFIRMED.
    """
    series = model1_confirmed_setup()

    signal = _find(detect_model1_signals(series), anchor_index=1, direction="bearish")

    assert signal.status == DetectionStatus.CONFIRMED
    assert signal.retest_index == 3
    assert signal.entry_type == "wick"
    assert signal.entry_price == 1.1010


def test_close_beyond_protected_extreme_before_retest_invalidates():
    """REQ-18/REQ-21: a close beyond the anchor's protected extreme (zero
    tolerance) before any retest is found -> INVALIDATED, retest_index
    stays None.
    """
    series = model1_invalidated_setup()

    signal = _find(detect_model1_signals(series), anchor_index=1, direction="bearish")

    assert signal.status == DetectionStatus.INVALIDATED
    assert signal.retest_index is None


def test_pre_confirmation_breach_invalidates_immediately_instead_of_dropping_the_signal():
    """REQ-18: any close beyond the anchor's protected extreme BEFORE
    confirmation invalidates immediately — must still emit a
    Model1Signal(status=INVALIDATED), not silently drop the anchor
    (previously indistinguishable from "no purge ever happened here").
    """
    series = model1_pre_confirmation_breach_setup()

    signal = _find(detect_model1_signals(series), anchor_index=1, direction="bearish")

    assert signal.status == DetectionStatus.INVALIDATED
    assert signal.retest_index is None
    assert signal.entry_type == "wick"
    assert signal.entry_price == 1.1010


def test_no_retest_by_series_end_is_pending_not_dropped():
    """REQ-21.1, grounded charter-2 [00:08:29]-[00:08:57]: confirmed anchor,
    series ends before any retest -> PENDING, never dropped.
    """
    series = model1_pending_setup()

    signal = _find(detect_model1_signals(series), anchor_index=1, direction="bearish")

    assert signal.status == DetectionStatus.PENDING
    assert signal.retest_index is None


def test_max_retest_lookback_is_read_from_config_not_hardcoded():
    """REQ-25: a max_retest_lookback of 0 leaves no room to find a retest
    after confirmation, forcing PENDING even where the default (20) finds
    the eventual retest/CONFIRMED outcome — proves the window is read from
    config, not hardcoded.
    """
    series = model1_confirmed_setup()

    default_signal = _find(detect_model1_signals(series), anchor_index=1, direction="bearish")
    strict_signal = _find(
        detect_model1_signals(series, config=Model1Config(max_retest_lookback=1)),
        anchor_index=1,
        direction="bearish",
    )

    assert default_signal.status == DetectionStatus.CONFIRMED
    assert strict_signal.status == DetectionStatus.PENDING


# --- Charter-2 grounded behavior-matching examples ---


def test_purge_engulf_matches_charter2_example1():
    """REQ-17.1, grounded charter-2 [00:05:28]-[00:06:04]: purge High,
    immediate engulf close, retest, expansion -> CONFIRMED sell setup.
    """
    series = model1_purge_engulf_charter2_setup()

    signal = _find(detect_model1_signals(series), anchor_index=1, direction="bearish")

    assert signal.purge_target == 1.1020
    assert signal.entry_type == "wick"
    assert signal.entry_price == 1.1010
    assert signal.retest_index == 3
    assert signal.status == DetectionStatus.CONFIRMED


def test_delayed_engulf_matches_charter2_example2():
    """REQ-18.1, grounded charter-2 [00:06:35]-[00:07:02]: purge Low, the
    engulfing close takes a couple of delayed candles (no intervening
    breach) -> anchor stays valid, confirms on close, then CONFIRMED.
    """
    series = model1_delayed_engulf_charter2_setup()

    signal = _find(detect_model1_signals(series), anchor_index=1, direction="bullish")

    assert signal.purge_target == 1.0980
    assert signal.entry_type == "wick"
    assert signal.entry_price == 1.0990
    assert signal.retest_index == 4
    assert signal.status == DetectionStatus.CONFIRMED


def test_dual_purge_and_fvg_fill_matches_charter2_example3():
    """REQ-19.1, grounded charter-2 [00:07:27]-[00:07:56]: one candle both
    purges a CRT Low AND fills an FVG -> two independent Model1Signal
    entries at the same anchor, one per confirmation_type, both CONFIRMED.
    """
    series = model1_dual_purge_and_fvg_fill_charter2_setup()
    signals = detect_model1_signals(series)

    purge_signal = _find(signals, anchor_index=4, direction="bullish", confirmation_type="purge_engulf")
    fvg_signal = _find(signals, anchor_index=4, direction="bullish", confirmation_type="fvg_fill")

    assert purge_signal.purge_target == 1.1012
    assert fvg_signal.purge_target == 1.1010
    for signal in (purge_signal, fvg_signal):
        assert signal.entry_type == "wick"
        assert signal.entry_price == 1.1030
        assert signal.retest_index == 6
        assert signal.status == DetectionStatus.CONFIRMED


# --- signal_id / confirmation_index (REQ-41.1, REQ-43.1) ---


def _series_with_shared_purge_candle() -> OHLCSeries:
    """3 candles, one bearish purge candle (index 2) whose high breaches
    two DIFFERENT hand-built CRTRanges' `high` (1.1010 and 1.1005) — both
    ranges report the SAME anchor_index/direction/confirmation_type, only
    `origin_index` (the range's own `start_index`) differs. Candle 3 closes
    beyond the anchor's protected extreme (1.1050) before any confirmation
    -> pre-confirmation INVALIDATED for both, which still computes
    signal_id (REQ-41's id is set regardless of terminal status).
    """
    candles = (
        Candle(timestamp=datetime(2026, 1, 1, 12, 0, 0), open=1.0995, high=1.1010, low=1.0985, close=1.1000),
        Candle(timestamp=datetime(2026, 1, 1, 13, 0, 0), open=1.0990, high=1.1005, low=1.0980, close=1.0995),
        Candle(timestamp=datetime(2026, 1, 1, 14, 0, 0), open=1.1020, high=1.1050, low=1.1010, close=1.1030),
        Candle(timestamp=datetime(2026, 1, 1, 15, 0, 0), open=1.1040, high=1.1060, low=1.1035, close=1.1055),
    )
    return OHLCSeries(candles=candles, instrument="EURUSD", timeframe="1H")


def test_signal_id_distinguishes_signals_sharing_an_anchor_from_different_crt_ranges():
    """REQ-41.1: two signals sharing the same anchor_index/direction but
    originating from different CRTRanges (different `start_index`) get
    distinct signal_id values."""
    series = _series_with_shared_purge_candle()
    range_a = CRTRange(
        model="2-candle", high=1.1010, low=1.0985, start_index=0, end_index=2,
        resolution="true_break", resolved_at_index=3,
    )
    range_b = CRTRange(
        model="2-candle", high=1.1005, low=1.0980, start_index=1, end_index=2,
        resolution="true_break", resolved_at_index=3,
    )

    signals = detect_model1_signals(series, crt_ranges=[range_a, range_b], fvgs=[])

    signal_a = _find(signals, anchor_index=2, direction="bearish")
    signal_b = next(
        s for s in signals
        if s.anchor_index == 2 and s.direction == "bearish" and s.origin_index == 1
    )

    assert signal_a.origin_index == 0
    assert signal_a.status == DetectionStatus.INVALIDATED
    assert signal_a.signal_id != signal_b.signal_id
    assert signal_a.signal_id == "0-2-bearish-purge_engulf-wick"
    assert signal_b.signal_id == "1-2-bearish-purge_engulf-wick"


def test_confirmation_index_is_the_confirming_candle_not_the_retest_candle():
    """REQ-43.1: confirmation lands 6 candles after the retest touch ->
    confirmation_index equals the confirming candle's own index (9),
    distinct from retest_index (3)."""
    series = model1_delayed_confirmation_after_retest_setup()

    signal = _find(detect_model1_signals(series), anchor_index=1, direction="bearish")

    assert signal.status == DetectionStatus.CONFIRMED
    assert signal.retest_index == 3
    assert signal.confirmation_index == 9
