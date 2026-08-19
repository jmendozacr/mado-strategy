from fixtures.synthetic import (
    model1_body_tiebreak_big_body_setup,
    model1_body_tiebreak_small_body_setup,
    model1_confirmed_setup,
    model1_delayed_engulf_charter2_setup,
    model1_dual_purge_and_fvg_fill_charter2_setup,
    model1_invalidated_setup,
    model1_pending_setup,
    model1_purge_engulf_charter2_setup,
    model1_wick_priority_setup,
)

from core.config import Model1Config
from core.results import DetectionStatus
from entries.model1 import detect_model1_signals


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
    entry_type=wick, entry_price=anchor's wick extreme (the swept side),
    regardless of the anchor's body_ratio.
    """
    series = model1_wick_priority_setup()

    signal = _find(detect_model1_signals(series), anchor_index=1, direction="bearish")

    assert signal.entry_type == "wick"
    assert signal.entry_price == 1.1035


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
    favors Wick, entry_price = anchor's wick extreme.
    """
    series = model1_body_tiebreak_small_body_setup()

    signal = _find(detect_model1_signals(series), anchor_index=1, direction="bearish")

    assert signal.entry_type == "wick"
    assert signal.entry_price == 1.1040


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
    assert signal.entry_price == 1.1035


def test_close_beyond_protected_extreme_before_retest_invalidates():
    """REQ-18/REQ-21: a close beyond the anchor's protected extreme (zero
    tolerance) before any retest is found -> INVALIDATED, retest_index
    stays None.
    """
    series = model1_invalidated_setup()

    signal = _find(detect_model1_signals(series), anchor_index=1, direction="bearish")

    assert signal.status == DetectionStatus.INVALIDATED
    assert signal.retest_index is None


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
    assert signal.entry_price == 1.1035
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
    assert signal.entry_price == 1.0960
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
        assert signal.entry_price == 1.1005
        assert signal.retest_index == 6
        assert signal.status == DetectionStatus.CONFIRMED
