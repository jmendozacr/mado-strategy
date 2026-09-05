"""Candle-by-candle trade lifecycle simulation (REQ-30, 33, 34, 35, 36, 37,
38, 40, 44, 47, 50) — unit tests directly constructing AlignedSignal
populations so each scenario's entry/stop/target/fill mechanics are fully
controlled.
"""

import random
from datetime import datetime

from fixtures.synthetic import CandleSeriesBuilder

from alignment.htf_ltf import AlignedSignal
from core.config import BacktestConfig, DetectorConfig
from core.key_level import KeyLevel
from core.results import DetectionStatus
from entries.model1 import Model1Signal
from primitives.crt_range import CRTRange

from backtest.simulate import simulate

_HTF_CONTEXT = CRTRange(
    model="2-candle", high=1.1050, low=1.0950, start_index=0, end_index=1,
    resolution="true_break", resolved_at_index=1,
)

# Confluence is irrelevant to most of this file's fill/exit/bucket-mechanics
# tests, and was implicitly satisfied before AlignedSignal.key_level
# existed — this default preserves that authored intent (design §8.1).
# Confluence-specific tests pass key_level=None explicitly.
_KEY_LEVEL = KeyLevel(kind="fvg", top=1.1050, bottom=1.0950, origin_index=0, expiry_index=None)


def _signal(
    anchor_index, direction, entry_type, retest_index,
    status=DetectionStatus.CONFIRMED, confirmation_type="purge_engulf", origin_index=0,
):
    return Model1Signal(
        anchor_index=anchor_index, direction=direction, purge_target=0.0,
        confirmation_type=confirmation_type, entry_type=entry_type, entry_price=0.0,
        retest_index=retest_index, status=status,
        confirmation_index=retest_index if retest_index is not None else anchor_index,
        origin_index=origin_index,
    )


def _aligned(signal, htf_context=_HTF_CONTEXT, aligned="aligned", key_level=_KEY_LEVEL):
    return AlignedSignal(ltf_signal=signal, htf_context=htf_context, aligned=aligned, key_level=key_level)


def _base_bullish_series() -> CandleSeriesBuilder:
    """anchor@0 (protected_extreme=low=1.0990), body-type entry=anchor.open
    (1.1000), retest@2 doesn't touch, fills@4 (low=1.0995<=1.1000)."""
    return (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1010, low=1.0990, close=1.1005)  # 0 — anchor
        .candle(open=1.1005, high=1.1010, low=1.1000, close=1.1005)  # 1 — filler
        .candle(open=1.1002, high=1.1008, low=1.1001, close=1.1004)  # 2 — retest, no touch
        .candle(open=1.1003, high=1.1006, low=1.1001, close=1.1002)  # 3 — no touch
        .candle(open=1.1020, high=1.1025, low=1.0995, close=1.1010)  # 4 — fills (low<=1.1000); open far more favorable (REQ-47.5)
        .candle(open=1.1000, high=1.1010, low=1.0995, close=1.1002)  # 5 — SL/TP untouched
    )


def test_confirmed_signal_fills_and_resolves_open():
    """REQ-30.1/37.1/38.1/44.1/47.5/50.2: a CONFIRMED body-type candidate
    becomes a trade via the unified fill window starting at retest_index
    (not confirmation_index+1); the fill candle's more-favorable open is
    never used as the entry price; TP is read straight from htf_context;
    neither SL nor TP touches by series end -> open."""
    series = _base_bullish_series().build()
    signal = _signal(anchor_index=0, direction="bullish", entry_type="body", retest_index=2)
    trades, report = simulate([_aligned(signal)], series, DetectorConfig())

    assert report.signals_considered == 1
    assert report.trades_opened == 1
    trade = trades[0]
    assert trade.entry_index == 4  # fill searched forward from retest_index=2, not confirmation_index
    assert trade.entry_price == 1.1000  # candidate's computed entry, never the fill candle's open
    assert trade.take_profit == _HTF_CONTEXT.high
    assert trade.outcome == "open"
    assert trade.exit_index is None
    assert trade.exit_price is None
    assert trade.r_multiple is None
    assert trade.ambiguous_bar is False
    assert trade.gap_filled is False


def test_invalidated_and_pending_with_retest_use_the_same_fill_mechanism():
    """REQ-37.2: INVALIDATED+retest and PENDING+retest candidates are
    simulated through the exact same fill mechanism as CONFIRMED — no
    candidate-type branch."""
    series = _base_bullish_series().build()
    invalidated = _signal(
        anchor_index=0, direction="bullish", entry_type="body", retest_index=2,
        status=DetectionStatus.INVALIDATED, origin_index=1,
    )
    pending = _signal(
        anchor_index=0, direction="bullish", entry_type="body", retest_index=2,
        status=DetectionStatus.PENDING, origin_index=2,
    )

    trades_i, report_i = simulate([_aligned(invalidated)], series, DetectorConfig())
    trades_p, report_p = simulate([_aligned(pending)], series, DetectorConfig())

    for trades, report in ((trades_i, report_i), (trades_p, report_p)):
        assert report.trades_opened == 1
        assert trades[0].entry_index == 4
        assert trades[0].outcome == "open"


def test_two_leg_trade_blends_partial_and_remainder_r_multiple():
    """REQ-68.1/69.1/38.2 (S-000 walking skeleton, happy path): the partial
    level resolves strictly before SL, then the remainder rides to the
    original take_profit -- leg 1 closes at partial_price, leg 2 closes at
    take_profit, and r_multiple is the fraction-weighted blend of both
    legs' net_r_multiple (default partial_fraction=0.5)."""
    series = (
        _base_bullish_series()  # 0-5, the last (5) already past fill_index(4)+1, untouched
        .candle(open=1.1010, high=1.1020, low=1.1005, close=1.1015)  # 6 — no touch
        .candle(open=1.1015, high=1.1055, low=1.1010, close=1.1050)  # 7 — touches partial_price (1.1050) only
        .candle(open=1.1020, high=1.1040, low=1.1015, close=1.1030)  # 8 — filler, no touch of SL/TP
        .candle(open=1.1050, high=1.1105, low=1.1045, close=1.1095)  # 9 — touches take_profit (1.1100)
        .build()
    )
    signal = _signal(anchor_index=0, direction="bullish", entry_type="body", retest_index=2)
    htf_context = CRTRange(
        model="2-candle", high=1.1100, low=1.0950, start_index=0, end_index=1,
        resolution="true_break", resolved_at_index=1,
    )

    trades, _ = simulate([_aligned(signal, htf_context=htf_context)], series, DetectorConfig())

    trade = trades[0]
    entry, stop = 1.1000, 1.0988  # protected_extreme(anchor.low=1.0990) - sl_buffer_price(0.0002)
    r_leg1 = (1.1050 - entry) / (entry - stop)  # partial_price = (entry + take_profit) / 2 (REQ-68 V2)
    r_leg2 = (1.1100 - entry) / (entry - stop)
    expected_blended = 0.5 * r_leg1 + 0.5 * r_leg2

    assert trade.partial_exit_index == 7
    assert trade.partial_exit_price == 1.1050
    assert abs(trade.partial_r_multiple - r_leg1) < 1e-9
    assert trade.partial_gap_filled is False
    assert trade.exit_index == 9
    assert trade.exit_price == 1.1100
    assert abs(trade.r_multiple - expected_blended) < 1e-9
    assert trade.outcome == "win"


def test_two_leg_trade_leg2_uses_unmoved_original_stop():
    """REQ-68.2 (edge, two-leg win-then-loss): the partial fires at index 7
    same as the win-win scenario, but the remainder then reverses and hits
    the ORIGINAL stop-loss at index 8 -- never moved or re-based after the
    partial fired."""
    series = (
        _base_bullish_series()
        .candle(open=1.1010, high=1.1020, low=1.1005, close=1.1015)  # 6 — no touch
        .candle(open=1.1015, high=1.1055, low=1.1010, close=1.1050)  # 7 — touches partial_price (1.1050) only
        .candle(open=1.1020, high=1.1030, low=1.0985, close=1.0990)  # 8 — reverses, touches ORIGINAL SL (1.0988)
        .build()
    )
    signal = _signal(anchor_index=0, direction="bullish", entry_type="body", retest_index=2)
    htf_context = CRTRange(
        model="2-candle", high=1.1100, low=1.0950, start_index=0, end_index=1,
        resolution="true_break", resolved_at_index=1,
    )

    trades, _ = simulate([_aligned(signal, htf_context=htf_context)], series, DetectorConfig())

    trade = trades[0]
    entry, stop = 1.1000, 1.0988
    r_leg1 = (1.1050 - entry) / (entry - stop)  # partial_price = (entry + take_profit) / 2 (REQ-68 V2)
    r_leg2 = (stop - entry) / (entry - stop)  # exit at stop itself -> -1.0
    expected_blended = 0.5 * r_leg1 + 0.5 * r_leg2

    assert trade.stop_loss == stop  # unmoved, unchanged from the candidate's original stop
    assert trade.exit_index == 8
    assert trade.exit_price == stop  # leg 2 closed at the SAME original stop, never re-based
    assert abs(trade.r_multiple - expected_blended) < 1e-9
    assert trade.partial_exit_index == 7
    assert trade.partial_exit_price == 1.1050


def test_sl_wins_tie_against_partial_collapses_to_single_leg():
    """REQ-68.3/38.3/69.3 (edge): stop-loss resolves at index 6, strictly
    before the partial level would resolve at index 7 -- SL wins, matching
    this codebase's pre-existing pessimistic tie-break (REQ-33), generalized
    to the partial level. The trade collapses to EXACTLY the single-leg
    resolution this codebase produced before REQ-68: no partial leg
    recorded, r_multiple unblended."""
    series = (
        _base_bullish_series()
        .candle(open=1.1010, high=1.1015, low=1.0980, close=1.1000)  # 6 — touches SL (1.0988) only
        .candle(open=1.1015, high=1.1027, low=1.1010, close=1.1020)  # 7 — SL already won at 6; irrelevant either way
        .build()
    )
    signal = _signal(anchor_index=0, direction="bullish", entry_type="body", retest_index=2)
    # Explicit htf_context (not the module-level _HTF_CONTEXT, whose midpoint
    # 1.1000 coincides with entry_price and would touch on the fill candle
    # itself) -- partial_price=1.1050 here (entry-to-target midpoint, REQ-68
    # V2), never even reached by this series; SL fires first at candle 6
    # regardless.
    htf_context = CRTRange(
        model="2-candle", high=1.1100, low=1.0950, start_index=0, end_index=1,
        resolution="true_break", resolved_at_index=1,
    )

    trades, _ = simulate([_aligned(signal, htf_context=htf_context)], series, DetectorConfig())

    trade = trades[0]
    assert trade.exit_index == 6
    assert trade.outcome == "loss"
    assert trade.exit_price == trade.stop_loss
    assert trade.r_multiple == -1.0  # unblended REQ-48 formula, exactly as before REQ-68
    assert trade.partial_exit_index is None
    assert trade.partial_exit_price is None
    assert trade.partial_r_multiple is None
    assert trade.partial_gap_filled is False


def test_partial_leg_gap_through_fills_at_open():
    """REQ-68.4 (edge): the resolving candle's open already lies beyond
    partial_price (1.1050) -- leg 1 fills at the candle's actual open
    (1.1060), not at partial_price itself, mirroring REQ-34's existing
    gap-through rule applied identically to this level."""
    series = (
        _base_bullish_series()
        .candle(open=1.1010, high=1.1020, low=1.1005, close=1.1015)  # 6 — no touch
        .candle(open=1.1060, high=1.1070, low=1.1055, close=1.1065)  # 7 — gaps through partial(1.1050) at open
        .candle(open=1.1050, high=1.1105, low=1.1045, close=1.1095)  # 8 — touches take_profit (1.1100)
        .build()
    )
    signal = _signal(anchor_index=0, direction="bullish", entry_type="body", retest_index=2)
    htf_context = CRTRange(
        model="2-candle", high=1.1100, low=1.0950, start_index=0, end_index=1,
        resolution="true_break", resolved_at_index=1,
    )

    trades, _ = simulate([_aligned(signal, htf_context=htf_context)], series, DetectorConfig())

    trade = trades[0]
    assert trade.partial_exit_index == 7
    assert trade.partial_exit_price == 1.1060  # the candle's actual open, not partial_price(1.1050)
    assert trade.partial_gap_filled is True


def test_partial_fraction_zero_reproduces_single_leg_output():
    """REQ-68.5/38.3: at partial_fraction=0.0, leg 1 must NEVER be eligible
    to fire -- the resulting Trade (outcome/exit_index/exit_price/
    r_multiple) matches this codebase's pre-existing single-leg resolution,
    AND all 4 partial-leg fields stay None/False (they must NOT merely
    equal a zero-weighted contribution -- the leg must never fire at all)."""
    series = (
        _base_bullish_series()
        .candle(open=1.1010, high=1.1020, low=1.1005, close=1.1015)  # 6 — no touch
        .candle(open=1.1015, high=1.1027, low=1.1010, close=1.1020)  # 7 — touches partial_price (1.1025) only
        .candle(open=1.1020, high=1.1040, low=1.1015, close=1.1030)  # 8 — filler, no touch of SL/TP
        .candle(open=1.1050, high=1.1105, low=1.1045, close=1.1095)  # 9 — touches take_profit (1.1100)
        .build()
    )
    signal = _signal(anchor_index=0, direction="bullish", entry_type="body", retest_index=2)
    htf_context = CRTRange(
        model="2-candle", high=1.1100, low=1.0950, start_index=0, end_index=1,
        resolution="true_break", resolved_at_index=1,
    )
    config = DetectorConfig(backtest=BacktestConfig(partial_fraction=0.0))

    trades, _ = simulate([_aligned(signal, htf_context=htf_context)], series, config)

    trade = trades[0]
    entry, stop = 1.1000, 1.0988
    expected_r = (1.1100 - entry) / (entry - stop)  # single-leg REQ-48 formula, entirely unblended

    assert trade.exit_index == 9
    assert trade.exit_price == 1.1100
    assert trade.outcome == "win"
    assert abs(trade.r_multiple - expected_r) < 1e-9
    assert trade.partial_exit_index is None
    assert trade.partial_exit_price is None
    assert trade.partial_r_multiple is None
    assert trade.partial_gap_filled is False


def test_open_trade_has_no_partial_leg_fields():
    """REQ-68.6/38.1: neither SL, TP, nor the partial level is ever touched
    by series end -- the trade stays "open", and none of the 4 new
    partial-leg fields are populated (mirrors REQ-38.1's pre-existing
    all-None/False contract for an open trade)."""
    series = _base_bullish_series().build()
    # A wide HTF context keeps TP(1.1200) and partial(1.1050) both well
    # beyond the remaining series' price action (max high=1.1010) -- unlike
    # the module-level _HTF_CONTEXT, whose midpoint (1.1000) happens to
    # coincide with entry_price and would touch immediately.
    htf_context = CRTRange(
        model="2-candle", high=1.1200, low=1.0900, start_index=0, end_index=1,
        resolution="true_break", resolved_at_index=1,
    )
    signal = _signal(anchor_index=0, direction="bullish", entry_type="body", retest_index=2)

    trades, _ = simulate([_aligned(signal, htf_context=htf_context)], series, DetectorConfig())

    trade = trades[0]
    assert trade.outcome == "open"
    assert trade.partial_exit_index is None
    assert trade.partial_exit_price is None
    assert trade.partial_r_multiple is None
    assert trade.partial_gap_filled is False


def test_two_leg_blended_r_zero_cost_is_bit_identical():
    """REQ-69.2: at the default trading_cost_price=0.0, the blended
    r_multiple is bit-identical to a zero-cost computation -- regardless of
    partial_fraction (checked here at a non-default 0.3, not just the
    default 0.5)."""
    series = (
        _base_bullish_series()
        .candle(open=1.1010, high=1.1020, low=1.1005, close=1.1015)  # 6 — no touch
        .candle(open=1.1015, high=1.1055, low=1.1010, close=1.1050)  # 7 — touches partial_price (1.1050) only
        .candle(open=1.1020, high=1.1040, low=1.1015, close=1.1030)  # 8 — filler, no touch of SL/TP
        .candle(open=1.1050, high=1.1105, low=1.1045, close=1.1095)  # 9 — touches take_profit (1.1100)
        .build()
    )
    signal = _signal(anchor_index=0, direction="bullish", entry_type="body", retest_index=2)
    htf_context = CRTRange(
        model="2-candle", high=1.1100, low=1.0950, start_index=0, end_index=1,
        resolution="true_break", resolved_at_index=1,
    )
    config = DetectorConfig(backtest=BacktestConfig(partial_fraction=0.3))

    trades, _ = simulate([_aligned(signal, htf_context=htf_context)], series, config)

    trade = trades[0]
    entry, stop = 1.1000, 1.0988
    r_leg1 = (1.1050 - entry) / (entry - stop)  # partial_price = (entry + take_profit) / 2 (REQ-68 V2)
    r_leg2 = (1.1100 - entry) / (entry - stop)
    expected_blended = 0.3 * r_leg1 + 0.7 * r_leg2  # exact zero-cost formula, no cost term anywhere

    assert trade.r_multiple == expected_blended  # bit-identical, not merely close


def test_same_candle_sl_and_tp_resolves_as_loss_with_ambiguous_flag():
    """REQ-33.1: a single candle touching both SL and TP resolves as a loss
    at the SL price, flagged ambiguous_bar."""
    series = (
        _base_bullish_series()
        .candle(open=1.1010, high=1.1060, low=1.0980, close=1.1020)  # 6 — touches both SL(1.0988) and TP(1.1050)
        .build()
    )
    signal = _signal(anchor_index=0, direction="bullish", entry_type="body", retest_index=2)

    trades, _ = simulate([_aligned(signal)], series, DetectorConfig())

    trade = trades[0]
    assert trade.outcome == "loss"
    assert trade.exit_price == trade.stop_loss
    assert trade.ambiguous_bar is True
    assert trade.gap_filled is False


def test_open_beyond_target_and_low_reaches_stop_still_resolves_at_stop():
    """REQ-33.3: candle opens above TP AND its low also reaches SL, same
    candle -> SL is chosen (REQ-33's pessimism) BEFORE the gap check ever
    inspects the candle's open against TP; the chosen level (SL) is not
    itself gapped through here, so gap_filled=False."""
    series = (
        _base_bullish_series()
        .candle(open=1.1060, high=1.1070, low=1.0980, close=1.1055)  # 6 — open>TP(1.1050) AND low<=SL(1.0988)
        .build()
    )
    signal = _signal(anchor_index=0, direction="bullish", entry_type="body", retest_index=2)

    trades, _ = simulate([_aligned(signal)], series, DetectorConfig())

    trade = trades[0]
    assert trade.outcome == "loss"
    assert trade.exit_price == trade.stop_loss
    assert trade.gap_filled is False


def test_gap_open_beyond_stop_fills_at_the_actual_open_price():
    """REQ-34.1: the resolving exit candle's open already lies beyond the
    chosen (SL) level, with TP untouched that candle -> exit fills at the
    candle's actual open, gap_filled=True."""
    series = (
        CandleSeriesBuilder()
        .candle(open=1.1010, high=1.1020, low=1.1000, close=1.1005)  # 0 — anchor, bearish (protected_extreme=high=1.1020)
        .candle(open=1.1005, high=1.1008, low=1.1000, close=1.1003)  # 1 — filler
        .candle(open=1.1006, high=1.1009, low=1.1004, close=1.1007)  # 2 — retest, no touch (entry=1.1010, body)
        .candle(open=1.1005, high=1.1009, low=1.1002, close=1.1004)  # 3 — no touch
        .candle(open=1.1008, high=1.1012, low=1.1005, close=1.1009)  # 4 — fills (high>=1.1010)
        .candle(open=1.1030, high=1.1035, low=1.1025, close=1.1028)  # 5 — opens beyond SL (1.1022), TP untouched
        .build()
    )
    signal = _signal(anchor_index=0, direction="bearish", entry_type="body", retest_index=2)
    htf_context = CRTRange(
        model="2-candle", high=1.1050, low=1.0950, start_index=0, end_index=1,
        resolution="true_break", resolved_at_index=1,
    )

    trades, _ = simulate([_aligned(signal, htf_context=htf_context)], series, DetectorConfig())

    trade = trades[0]
    assert trade.stop_loss == 1.1022
    assert trade.outcome == "loss"
    assert trade.gap_filled is True
    assert trade.exit_price == 1.1030  # the candle's actual open, not the SL level


def test_wick_entry_resolves_at_retest_index_itself():
    """REQ-50.1: a WICK-type candidate's fill window search resolves at
    retest_index itself, derived from the retest predicate rather than
    special-cased."""
    series = (
        CandleSeriesBuilder()
        .candle(open=1.0998, high=1.1005, low=1.0990, close=1.1002)  # 0 — anchor; wick entry = max(open,close) = 1.1002
        .candle(open=1.1000, high=1.1004, low=1.0999, close=1.1001)  # 1 — filler
        .candle(open=1.1001, high=1.1006, low=1.1000, close=1.1003)  # 2 — retest candle, low<=1.1002 -> touches immediately
        .candle(open=1.1002, high=1.1010, low=1.0998, close=1.1005)  # 3 — after
        .build()
    )
    signal = _signal(anchor_index=0, direction="bullish", entry_type="wick", retest_index=2)

    trades, report = simulate([_aligned(signal)], series, DetectorConfig())

    assert report.trades_opened == 1
    assert trades[0].entry_index == 2
    assert trades[0].entry_price == 1.1002


def test_entry_never_touched_within_max_fill_wait_window_is_excluded():
    """REQ-50.3: the window closes at retest_index + max_fill_wait
    inclusive — a touch one candle past that boundary does not count, and
    the candidate is excluded under never_filled, not counted as a trade."""
    series = (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1010, low=1.0990, close=1.1005)  # 0 — anchor
        .candle(open=1.1005, high=1.1010, low=1.1002, close=1.1005)  # 1 — filler
        .candle(open=1.1002, high=1.1008, low=1.1001, close=1.1004)  # 2 — retest, no touch (entry=1.1000, body)
        .candle(open=1.1003, high=1.1006, low=1.1001, close=1.1002)  # 3 — within window (retest+1), no touch
        .candle(open=1.1002, high=1.1006, low=1.1001, close=1.1003)  # 4 — window closes here (retest+2), no touch
        .candle(open=1.1001, high=1.1005, low=1.0995, close=1.1000)  # 5 — one candle past the window, touches -> too late
        .build()
    )
    signal = _signal(anchor_index=0, direction="bullish", entry_type="body", retest_index=2)
    config = DetectorConfig(backtest=BacktestConfig(max_fill_wait=2))

    trades, report = simulate([_aligned(signal)], series, config)

    assert report.trades_opened == 0
    assert report.excluded_never_filled == 1
    assert trades == []


def test_sl_tp_sweep_excludes_the_fill_candle_itself():
    """REQ-37: the SL/TP resolution sweep begins at fill_index + 1, never
    fill_index itself. The fill candle here ALSO reaches the stop-loss level
    within its own range (low<=stop) — if the sweep started at fill_index,
    the trade would resolve as a loss right there; starting at fill_index+1
    instead, the next candle doesn't touch SL/TP, so the trade stays open."""
    series = (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1010, low=1.0990, close=1.1005)  # 0 — anchor; stop=1.0988
        .candle(open=1.1005, high=1.1010, low=1.1000, close=1.1003)  # 1 — filler
        .candle(open=1.1003, high=1.1008, low=1.1002, close=1.1005)  # 2 — retest, no touch (low>1.1000)
        .candle(open=1.1010, high=1.1015, low=1.0980, close=1.1005)  # 3 — fills (low<=1.1000) AND its own range
        # already reaches SL (low=1.0980<=1.0988) — must NOT resolve here
        .candle(open=1.1000, high=1.1010, low=1.0995, close=1.1002)  # 4 — sweep starts here; no SL/TP touch
        .build()
    )
    signal = _signal(anchor_index=0, direction="bullish", entry_type="body", retest_index=2)

    trades, report = simulate([_aligned(signal)], series, DetectorConfig())

    assert report.trades_opened == 1
    trade = trades[0]
    assert trade.entry_index == 3
    assert series.candles[3].low <= trade.stop_loss  # sanity: the fill candle's own range DOES reach SL
    assert trade.outcome == "open"  # proves the sweep did not resolve on the fill candle itself
    assert trade.exit_index is None


def test_entry_touched_exactly_at_max_fill_wait_boundary_is_included():
    """REQ-50.3: the fill window closes at retest_index + max_fill_wait
    INCLUSIVE — a touch exactly on that boundary candle counts and fills,
    mirroring test_entry_never_touched_within_max_fill_wait_window_is_excluded
    (which only proves the candle one PAST the boundary is rejected)."""
    series = (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1010, low=1.0990, close=1.1005)  # 0 — anchor
        .candle(open=1.1005, high=1.1010, low=1.1002, close=1.1004)  # 1 — filler
        .candle(open=1.1003, high=1.1008, low=1.1002, close=1.1005)  # 2 — retest, no touch
        .candle(open=1.1003, high=1.1007, low=1.1001, close=1.1004)  # 3 — within window, no touch
        .candle(open=1.1002, high=1.1006, low=1.0999, close=1.1001)  # 4 — window boundary (retest+2), touches
        .build()
    )
    signal = _signal(anchor_index=0, direction="bullish", entry_type="body", retest_index=2)
    config = DetectorConfig(backtest=BacktestConfig(max_fill_wait=2))

    trades, report = simulate([_aligned(signal)], series, config)

    assert report.trades_opened == 1
    assert trades[0].entry_index == 4


def test_retest_index_none_excludes_regardless_of_status():
    """REQ-30.3: retest_index is None excludes a candidate under
    excluded_never_confirmed regardless of status -- both the
    pre-confirmation INVALIDATED variant and the never-retested PENDING
    variant."""
    series = _base_bullish_series().build()
    invalidated_never_retested = _signal(
        anchor_index=0, direction="bullish", entry_type="body", retest_index=None,
        status=DetectionStatus.INVALIDATED, origin_index=1,
    )
    pending_never_retested = _signal(
        anchor_index=0, direction="bullish", entry_type="body", retest_index=None,
        status=DetectionStatus.PENDING, origin_index=2,
    )

    trades, report = simulate(
        [_aligned(invalidated_never_retested), _aligned(pending_never_retested)], series, DetectorConfig()
    )

    assert trades == []
    assert report.trades_opened == 0
    assert report.excluded_never_confirmed == 2


def test_fvg_fill_confirmed_signal_excluded_as_no_crt_range():
    """REQ-30.4: a CONFIRMED fvg_fill-confirmed signal has no CRT range at
    all -> excluded_no_crt_range, never reaching the fill mechanism."""
    series = _base_bullish_series().build()
    signal = _signal(
        anchor_index=0, direction="bullish", entry_type="body", retest_index=2,
        confirmation_type="fvg_fill",
    )

    trades, report = simulate([_aligned(signal)], series, DetectorConfig())

    assert trades == []
    assert report.trades_opened == 0
    assert report.excluded_no_crt_range == 1


def test_aligned_confirmed_signal_with_no_key_level_excluded_as_no_key_level():
    """REQ-30.7: an aligned CONFIRMED signal with retest_index set but no
    Key Level recorded is not a trade candidate -- counted under
    excluded_no_key_level, never reaching the fill mechanism."""
    series = _base_bullish_series().build()
    signal = _signal(anchor_index=0, direction="bullish", entry_type="body", retest_index=2)

    trades, report = simulate([_aligned(signal, key_level=None)], series, DetectorConfig())

    assert trades == []
    assert report.trades_opened == 0
    assert report.excluded_no_key_level == 1


def test_unaligned_signal_excluded_regardless_of_status():
    """REQ-30.5/44.2: AlignedSignal.aligned != "aligned" excludes a
    candidate under excluded_unaligned, regardless of the underlying
    Model1Signal.status -- covers both the unaligned and
    insufficient_htf_data tags."""
    series = _base_bullish_series().build()
    confirmed = _signal(anchor_index=0, direction="bullish", entry_type="body", retest_index=2, origin_index=1)
    pending = _signal(
        anchor_index=0, direction="bullish", entry_type="body", retest_index=2,
        status=DetectionStatus.PENDING, origin_index=2,
    )

    trades, report = simulate(
        [
            _aligned(confirmed, htf_context=None, aligned="unaligned"),
            _aligned(pending, htf_context=None, aligned="insufficient_htf_data"),
        ],
        series, DetectorConfig(),
    )

    assert trades == []
    assert report.trades_opened == 0
    assert report.excluded_unaligned == 2


def test_pending_with_retest_resolves_to_a_definite_outcome_like_confirmed():
    """REQ-40.4: a PENDING+retest candidate resolves through stages 4-7
    exactly like an INVALIDATED+retest/CONFIRMED one -- including a
    definite win/loss outcome, not just "open" -- and is counted in
    trades_opened, never disappearing from the signals_considered
    denominator."""
    series = (
        _base_bullish_series()
        .candle(open=1.1010, high=1.1060, low=1.0980, close=1.1020)  # 6 — touches both SL(1.0988) and TP(1.1050)
        .build()
    )
    signal = _signal(
        anchor_index=0, direction="bullish", entry_type="body", retest_index=2,
        status=DetectionStatus.PENDING,
    )

    trades, report = simulate([_aligned(signal)], series, DetectorConfig())

    assert report.signals_considered == 1
    assert report.trades_opened == 1
    assert trades[0].outcome == "loss"
    assert trades[0].exit_price == trades[0].stop_loss


def test_body_type_invalidated_and_pending_never_filled_excluded_not_loss():
    """REQ-50.4: a BODY-type INVALIDATED+retest or PENDING+retest candidate
    whose entry (anchor.open) is never touched within the fill window is
    excluded under excluded_never_filled -- NOT counted as a loss, and not
    counted as a trade at all -- for either candidate type."""
    series = (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1010, low=1.0990, close=1.1005)  # 0 — anchor
        .candle(open=1.1005, high=1.1010, low=1.1002, close=1.1005)  # 1 — filler
        .candle(open=1.1002, high=1.1008, low=1.1001, close=1.1004)  # 2 — retest, no touch (entry=1.1000, body)
        .candle(open=1.1003, high=1.1006, low=1.1001, close=1.1002)  # 3 — within window, no touch
        .candle(open=1.1002, high=1.1006, low=1.1001, close=1.1003)  # 4 — window closes here (retest+2), no touch
        .build()
    )
    config = DetectorConfig(backtest=BacktestConfig(max_fill_wait=2))
    invalidated = _signal(
        anchor_index=0, direction="bullish", entry_type="body", retest_index=2,
        status=DetectionStatus.INVALIDATED,
    )
    pending = _signal(
        anchor_index=0, direction="bullish", entry_type="body", retest_index=2,
        status=DetectionStatus.PENDING,
    )

    for signal in (invalidated, pending):
        trades, report = simulate([_aligned(signal)], series, config)
        assert trades == []
        assert report.trades_opened == 0
        assert report.excluded_never_filled == 1


def test_three_duplicate_candidates_collapse_to_one_lowest_origin_index_survives():
    """REQ-46.1: candidates sharing (anchor_index, direction, entry_price,
    entry_type) collapse to one -- the lowest origin_index survives -- and
    the rest are counted excluded_duplicate."""
    series = _base_bullish_series().build()
    signals = [
        _signal(anchor_index=0, direction="bullish", entry_type="body", retest_index=2, origin_index=5),
        _signal(anchor_index=0, direction="bullish", entry_type="body", retest_index=2, origin_index=2),
        _signal(anchor_index=0, direction="bullish", entry_type="body", retest_index=2, origin_index=8),
    ]
    aligned = [_aligned(s) for s in signals]

    trades, report = simulate(aligned, series, DetectorConfig())

    assert report.trades_opened == 1
    assert report.excluded_duplicate == 2
    assert trades[0].signal_id == "2-0-bullish-purge_engulf-body"  # lowest origin_index (2) survives


def test_differing_entry_type_at_same_anchor_and_price_both_survive():
    """REQ-46.2: entry_type is part of the dedup identity key -- a wick and
    a body candidate at the same anchor survive as distinct candidates, even
    when their computed entry_price VALUES coincide (anchor close<=open
    collapses wick entry (max(open,close)) onto body entry (open), leaving
    entry_type as the only field able to separate the two)."""
    series = (
        CandleSeriesBuilder()
        .candle(open=1.1005, high=1.1010, low=1.0990, close=1.1000)  # 0 — anchor; close<=open -> body entry==wick entry==1.1005
        .candle(open=1.1005, high=1.1010, low=1.1000, close=1.1005)  # 1 — filler
        .candle(open=1.1002, high=1.1008, low=1.1001, close=1.1004)  # 2 — retest; low<=1.1005 -> fills immediately
        .build()
    )
    body = _signal(anchor_index=0, direction="bullish", entry_type="body", retest_index=2, origin_index=1)
    wick = _signal(anchor_index=0, direction="bullish", entry_type="wick", retest_index=2, origin_index=2)

    trades, report = simulate([_aligned(body), _aligned(wick)], series, DetectorConfig())

    assert report.excluded_duplicate == 0
    assert report.trades_opened == 2
    assert {t.entry_price for t in trades} == {1.1005}  # confirms the two entry prices genuinely coincide


def test_candidate_order_does_not_affect_trades_or_buckets():
    """ADR-02 regression: candidates fed to simulate() in shuffled order
    must produce identical trades and reconciliation buckets — pins the
    sort-before-sweep contract at each of the three two_heap_sweep calls."""
    series = _base_bullish_series().build()
    # Distinct anchor_index per signal (0-4) so none dedup-collapse (REQ-46
    # keys on anchor_index); retest_index=2 is valid for all of them.
    signals = [
        _signal(anchor_index=i, direction="bullish", entry_type="body", retest_index=2, origin_index=i)
        for i in range(5)
    ]
    aligned = [_aligned(s) for s in signals]
    ordered_trades, ordered_report = simulate(aligned, series, DetectorConfig())

    shuffled = list(aligned)
    random.Random(3).shuffle(shuffled)
    shuffled_trades, shuffled_report = simulate(shuffled, series, DetectorConfig())

    assert sorted(t.signal_id for t in shuffled_trades) == sorted(t.signal_id for t in ordered_trades)
    assert shuffled_report == ordered_report


def test_risk_reward_below_floor_excluded():
    """REQ-35.1: a candidate whose computed R:R (1.4) falls below the
    min_risk_reward default (2.0) is excluded under excluded_rr_floor."""
    series = _base_bullish_series().build()
    signal = _signal(anchor_index=0, direction="bullish", entry_type="body", retest_index=2)
    # entry=1.1000 (anchor.open), stop=1.0988 (protected_extreme-buffer) -> risk=0.0012.
    # target=entry+1.4*risk=1.10168 -> R:R=1.4, below the 2.0 default floor.
    htf_context = CRTRange(
        model="2-candle", high=1.10168, low=1.0900, start_index=0, end_index=1,
        resolution="true_break", resolved_at_index=1,
    )

    trades, report = simulate([_aligned(signal, htf_context=htf_context)], series, DetectorConfig())

    assert trades == []
    assert report.trades_opened == 0
    assert report.excluded_rr_floor == 1


def test_risk_reward_near_floor_is_still_excluded_floor_not_inert():
    """REQ-35.2: risk 14 pips / reward 20 pips -> R:R ~1.43, still below the
    2.0 default -- the floor rejects a real, non-degenerate candidate, not
    only an extreme one."""
    series = (
        CandleSeriesBuilder()
        .candle(open=1.0998, high=1.1005, low=1.0990, close=1.1002)  # 0 — anchor; wick entry=max(open,close)=1.1002, protected_extreme=low=1.0990
        .candle(open=1.1000, high=1.1004, low=1.0999, close=1.1001)  # 1 — filler
        .candle(open=1.1001, high=1.1006, low=1.1000, close=1.1003)  # 2 — retest
        .build()
    )
    signal = _signal(anchor_index=0, direction="bullish", entry_type="wick", retest_index=2)
    # entry=1.1002 (wick), stop=1.0988 -> risk=0.0014 (14 pips, matches REQ-31.3).
    # target=1.1002+0.0020=1.1022 -> reward=0.0020 (20 pips) -> R:R~1.4286.
    htf_context = CRTRange(
        model="2-candle", high=1.1022, low=1.0900, start_index=0, end_index=1,
        resolution="true_break", resolved_at_index=1,
    )

    trades, report = simulate([_aligned(signal, htf_context=htf_context)], series, DetectorConfig())

    assert trades == []
    assert report.trades_opened == 0
    assert report.excluded_rr_floor == 1


def test_target_behind_entry_excluded_under_the_same_rr_floor_bucket():
    """REQ-35.3: a structurally negative R:R (target behind entry in the
    trade direction) is excluded under the SAME excluded_rr_floor bucket --
    no separate "inverted target" bucket exists."""
    series = _base_bullish_series().build()
    signal = _signal(anchor_index=0, direction="bullish", entry_type="body", retest_index=2)
    # entry=1.1000, target=1.0995 sits BEHIND entry for a bullish trade ->
    # signed reward is negative regardless of risk.
    htf_context = CRTRange(
        model="2-candle", high=1.0995, low=1.0900, start_index=0, end_index=1,
        resolution="true_break", resolved_at_index=1,
    )

    trades, report = simulate([_aligned(signal, htf_context=htf_context)], series, DetectorConfig())

    assert trades == []
    assert report.trades_opened == 0
    assert report.excluded_rr_floor == 1
    assert report.excluded_kill_zone == 0
    assert report.excluded_never_filled == 0


def test_signal_anchored_outside_kill_zone_excluded():
    """REQ-36.1: a signal anchored at 05:30 NY-local (outside the default
    07:00-11:00 NY Kill Zone) is excluded under excluded_kill_zone, with the
    default gate active."""
    series = (
        CandleSeriesBuilder(start=datetime(2026, 1, 1, 10, 30))  # 10:30 UTC -> 05:30 NY (winter, EST)
        .candle(open=1.1000, high=1.1010, low=1.0990, close=1.1005)  # 0 — anchor
        .candle(open=1.1005, high=1.1010, low=1.1000, close=1.1005)  # 1 — filler
        .candle(open=1.1002, high=1.1008, low=1.1001, close=1.1004)  # 2 — retest
        .build()
    )
    signal = _signal(anchor_index=0, direction="bullish", entry_type="body", retest_index=2)

    trades, report = simulate([_aligned(signal)], series, DetectorConfig())

    assert trades == []
    assert report.trades_opened == 0
    assert report.excluded_kill_zone == 1


def test_anchor_inside_kill_zone_not_excluded_even_when_confirmation_lands_outside():
    """REQ-36.3: the kill-zone gate evaluates ONLY the anchor's timestamp --
    a candidate anchored inside the zone is never excluded under
    excluded_kill_zone, even when its retest/confirmation lands 18 candles
    later, well outside the zone (default base @0 = 07:00 NY; @0+18h rolls
    into the next day at 01:00 NY)."""
    builder = CandleSeriesBuilder().candle(open=1.1000, high=1.1010, low=1.0990, close=1.1005)  # 0 — anchor, 07:00 NY (in zone)
    for _ in range(17):
        builder = builder.candle(open=1.1000, high=1.1005, low=1.0998, close=1.1002)  # 1..17 — filler
    builder = builder.candle(open=1.1002, high=1.1006, low=1.0995, close=1.1003)  # 18 — retest, 01:00 NY next day (out of zone)
    series = builder.build()
    signal = _signal(anchor_index=0, direction="bullish", entry_type="body", retest_index=18)

    trades, report = simulate([_aligned(signal)], series, DetectorConfig())

    assert report.signals_considered == 1
    assert report.excluded_kill_zone == 0
