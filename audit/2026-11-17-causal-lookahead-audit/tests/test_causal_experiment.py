"""Causality tests for the Phase 2 experimental reproduction (S6). Kept
entirely under audit/2026-11-17-causal-lookahead-audit/ -- nothing under
detector/ or scanner/ is touched by this suite, and nothing here imports
from this suite into production code.

Run: detector/.venv/Scripts/python.exe -m pytest audit/2026-11-17-causal-lookahead-audit/tests -v
"""
import os
import sys
from datetime import datetime, timedelta

import pytest

AUDIT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.abspath(os.path.join(AUDIT_DIR, "..", ".."))
DATA_DIR = os.path.join(REPO_ROOT, "data")

from backtest.candidate import Candidate  # noqa: E402
from backtest.population import build_stage6_population  # noqa: E402
from backtest.simulate import simulate  # noqa: E402
from causal.htf_trigger import MODEL_1AM, MODEL_9AM, confirmation_window_utc, find_1am_9am_aligned_signals  # noqa: E402
from core.candle import Candle, OHLCSeries  # noqa: E402
from core.config import DetectorConfig  # noqa: E402
from experimental.htf_trigger_1am_9am_backtest import SYMBOL_CONFIG, _find_csv  # noqa: E402
from ingestion.loader import load_mt5_csv  # noqa: E402
from ingestion.pairing import load_pair  # noqa: E402

import causal_lib  # noqa: E402
from fill_b1 import fill_pass_b1  # noqa: E402


def _m15(prices_low, start=datetime(2026, 1, 1, 0, 0)):
    return tuple(
        Candle(timestamp=start + timedelta(minutes=15 * i), open=100.0, high=max(100.0, low), low=low, close=100.0)
        for i, low in enumerate(prices_low)
    )


# ---------------------------------------------------------------------------
# S6.4 "activar órdenes en el primer instante realmente permitido" / S6.2
# "prohibir uso anticipado del cierre H4" -- the core B1 causal guarantee.
# ---------------------------------------------------------------------------

def test_m15_index_at_or_after_bisects_correctly():
    class _Shared:
        m15_timestamps = [datetime(2026, 1, 1, 0, 0) + timedelta(minutes=15 * i) for i in range(5)]

    shared = _Shared()
    assert causal_lib.m15_index_at_or_after(shared, datetime(2025, 12, 31)) == 0
    assert causal_lib.m15_index_at_or_after(shared, shared.m15_timestamps[2]) == 2
    assert causal_lib.m15_index_at_or_after(shared, shared.m15_timestamps[2] + timedelta(seconds=1)) == 3
    assert causal_lib.m15_index_at_or_after(shared, datetime(2027, 1, 1)) is None


def test_trigger_h4_close_is_open_plus_four_hours():
    class _H4:
        candles = (Candle(timestamp=datetime(2026, 3, 10, 4, 0), open=1, high=1, low=1, close=1),)

    class _Shared:
        h4 = _H4()

    assert causal_lib.trigger_h4_close(_Shared(), 0) == datetime(2026, 3, 10, 8, 0)


def test_fill_pass_b1_never_fills_before_placement_even_when_price_already_touched_entry():
    """A bullish candidate's entry_price=100 is touched at M15 index 0 --
    chronologically before placement (index 1). Production `_fill_pass`,
    anchored on retest_index=0, WOULD credit that early touch. B1's
    placement-floored fill pass must not: the first candle it is even
    eligible to consider is index 1, and that candle doesn't touch (low=110),
    so the credited fill must be the later touch at index 2, never index 0."""
    candles = _m15([90.0, 110.0, 95.0])  # touches at 0 and 2, not at 1
    candidate = Candidate(
        signal_id="sig-1", anchor_index=0, origin_index=0, direction="bullish", entry_type="wick",
        retest_index=0, entry_price=100.0, stop_loss=90.0, take_profit=120.0, partial_price=110.0,
    )
    placement_index_by_signal_id = {"sig-1": 1}  # placement is index 1, NOT retest_index (0)

    filled, never_filled, skipped = fill_pass_b1(
        [candidate], candles, max_fill_wait=20, placement_index_by_signal_id=placement_index_by_signal_id
    )

    assert skipped == 0
    assert never_filled == 0
    assert len(filled) == 1
    resolved_candidate, fill_index = filled[0]
    assert resolved_candidate.signal_id == "sig-1"
    assert fill_index == 2, "must skip index 0's touch (before placement) and resolve at index 2, not index 0"


def test_fill_pass_b1_candidate_with_no_determinable_placement_never_fills():
    candles = _m15([90.0, 90.0, 90.0])
    candidate = Candidate(
        signal_id="sig-2", anchor_index=0, origin_index=0, direction="bullish", entry_type="wick",
        retest_index=0, entry_price=100.0, stop_loss=90.0, take_profit=120.0, partial_price=110.0,
    )
    filled, never_filled, skipped = fill_pass_b1([candidate], candles, max_fill_wait=20, placement_index_by_signal_id={})
    assert filled == []
    assert skipped == 1
    assert never_filled == 0


def test_fill_pass_b1_respects_max_fill_wait_counted_from_placement_not_retest():
    """S6.5 'calcular vencimientos desde la colocación': retest_index=0,
    placement_index=10, max_fill_wait=2 -- a touch at index 11 is within 2
    candles of PLACEMENT (eligible) even though it is 11 candles past the
    historical retest_index; a touch at index 13 is NOT (3 candles past
    placement) and must expire."""
    lows = [110.0] * 20
    lows[11] = 90.0  # touches at index 11: placement(10) + 1 <= max_fill_wait(2) -> fills
    candles = _m15(lows)
    candidate = Candidate(
        signal_id="sig-3", anchor_index=0, origin_index=0, direction="bullish", entry_type="wick",
        retest_index=0, entry_price=100.0, stop_loss=80.0, take_profit=120.0, partial_price=110.0,
    )
    filled, never_filled, skipped = fill_pass_b1(
        [candidate], candles, max_fill_wait=2, placement_index_by_signal_id={"sig-3": 10}
    )
    assert len(filled) == 1
    assert filled[0][1] == 11

    lows2 = [110.0] * 20
    lows2[13] = 90.0  # touches only at index 13: placement(10)+3 > max_fill_wait(2) -> expires, never fills
    candles2 = _m15(lows2)
    candidate2 = Candidate(**{**candidate.__dict__, "signal_id": "sig-4"})
    filled2, never_filled2, _ = fill_pass_b1(
        [candidate2], candles2, max_fill_wait=2, placement_index_by_signal_id={"sig-4": 10}
    )
    assert filled2 == []
    assert never_filled2 == 1


# ---------------------------------------------------------------------------
# S6.6 "resolver correctamente eventos simultáneos" / EST vs EDT pinning
# (user-specified correction: NY 09:00-10:30 == UTC 14:00-15:30 in EST,
# UTC 13:00-14:30 in EDT).
# ---------------------------------------------------------------------------

def test_confirmation_window_9am_model_est_vs_edt():
    est_trigger = Candle(timestamp=datetime(2026, 1, 15, 12, 0), open=1, high=1, low=1, close=1)  # winter
    edt_trigger = Candle(timestamp=datetime(2026, 7, 15, 12, 0), open=1, high=1, low=1, close=1)  # summer

    est_start, est_end = confirmation_window_utc(est_trigger, MODEL_9AM)
    edt_start, edt_end = confirmation_window_utc(edt_trigger, MODEL_9AM)

    assert (est_start, est_end) == (datetime(2026, 1, 15, 14, 0), datetime(2026, 1, 15, 15, 30))
    assert (edt_start, edt_end) == (datetime(2026, 7, 15, 13, 0), datetime(2026, 7, 15, 14, 30))

    # The entire 9am window ends strictly before the true H4 close (16:00 UTC)
    # in BOTH DST states -- the Phase 1 finding, pinned as a regression test.
    h4_close = est_trigger.timestamp + timedelta(hours=4)
    assert est_end <= h4_close
    h4_close_edt = edt_trigger.timestamp + timedelta(hours=4)
    assert edt_end <= h4_close_edt


def test_confirmation_window_1am_model_est_straddles_close_edt_does_not():
    est_trigger = Candle(timestamp=datetime(2026, 1, 15, 4, 0), open=1, high=1, low=1, close=1)
    edt_trigger = Candle(timestamp=datetime(2026, 7, 15, 4, 0), open=1, high=1, low=1, close=1)

    est_start, est_end = confirmation_window_utc(est_trigger, MODEL_1AM)
    edt_start, edt_end = confirmation_window_utc(edt_trigger, MODEL_1AM)

    assert (est_start, est_end) == (datetime(2026, 1, 15, 7, 0), datetime(2026, 1, 15, 9, 0))
    assert (edt_start, edt_end) == (datetime(2026, 7, 15, 6, 0), datetime(2026, 7, 15, 8, 0))

    h4_close_est = est_trigger.timestamp + timedelta(hours=4)
    h4_close_edt = edt_trigger.timestamp + timedelta(hours=4)
    assert est_end > h4_close_est, "EST: a post-close sliver [08:00,09:00) remains -- causally valid for B2"
    assert edt_end == h4_close_edt, "EDT: window ends exactly at close -- nothing remains for B2"


# ---------------------------------------------------------------------------
# End-to-end: Arm A must reproduce production exactly; B2 must never use
# pre-close information. Real (small-sliced) EURUSD data, not synthetic --
# exercises the real detection pipeline, just on a short window so it runs
# in seconds, not hours.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def eurusd_small_slice():
    h4_csv = _find_csv(DATA_DIR, "EURUSD", "H4")
    m15_csv = _find_csv(DATA_DIR, "EURUSD", "M15")
    d1_csv = _find_csv(DATA_DIR, "EURUSD", "D1")
    h4_full, m15_full = load_pair(htf_csv=h4_csv, htf_symbol="EURUSD", ltf_csv=m15_csv, ltf_symbol="EURUSD")
    daily_full = load_mt5_csv(d1_csv, symbol="EURUSD")
    h4 = h4_full.up_to(600)
    daily = daily_full.up_to(120)
    cutoff = h4.candles[-1].timestamp
    m15_count = sum(1 for c in m15_full.candles if c.timestamp <= cutoff)
    m15 = m15_full.up_to(m15_count)
    config = DetectorConfig(backtest=SYMBOL_CONFIG["EURUSD"])
    return h4, m15, daily, config


def test_arm_a_signals_matches_production_find_1am_9am_aligned_signals_exactly(eurusd_small_slice):
    """S6.8 'garantizar que el Brazo A reproduce exactamente el baseline':
    the same (signal_id, model) pairs, in the same order, as calling the
    REAL production entry point directly -- proves causal_lib.arm_a_signals
    is a faithful reproduction of find_1am_9am_aligned_signals, not a
    reimplementation that happens to look similar."""
    h4, m15, daily, config = eurusd_small_slice
    shared = causal_lib.compute_shared_detection(m15, h4, daily, config)

    results_a, _sig2stable, _sig2h4close = causal_lib.arm_a_signals(shared, "EURUSD")
    reproduced = [(aligned.ltf_signal.signal_id, model) for aligned, model, _sid in results_a]

    key_levels = causal_lib.build_key_levels(h4, daily, config.fvg)
    production = find_1am_9am_aligned_signals(h4.candles, m15, key_levels, config.crt_range, config.model1)
    expected = [(aligned.ltf_signal.signal_id, model) for aligned, model in production]

    assert reproduced == expected
    assert len(expected) > 0, "fixture produced zero signals -- widen the slice, this test proves nothing empty"


def test_arm_b2_never_returns_a_signal_confirmed_before_its_h4_close(eurusd_small_slice):
    """S6.1/S6.3: for every B2 signal produced, its retest completion
    (confirmation_index, the M15 bar the retest/confirmation resolved on)
    must fall at a timestamp >= the triggering H4 candle's true close --
    never reinterpreting a pre-close confirmation as valid."""
    h4, m15, daily, config = eurusd_small_slice
    shared = causal_lib.compute_shared_detection(m15, h4, daily, config)

    results_b2, sig2h4close, zero_reasons = causal_lib.arm_b2_signals(shared, "EURUSD")

    checked = 0
    for aligned, _model, _sid in results_b2:
        signal = aligned.ltf_signal
        h4_close = sig2h4close[signal.signal_id]
        confirmation_ts = m15.candles[signal.confirmation_index].timestamp
        assert confirmation_ts >= h4_close, (
            f"B2 signal {signal.signal_id} confirmed at {confirmation_ts} before its H4 close {h4_close}"
        )
        checked += 1
    # Not asserting checked > 0: on a short slice B2 legitimately may find
    # none (S3's own "repórtalo como resultado legítimo"). zero_reasons
    # must then explain every trigger instead.
    assert checked > 0 or len(zero_reasons) > 0


def test_build_stage6_population_and_simulate_accept_b2_signals_unmodified(eurusd_small_slice):
    """Confirms B2's aligned signals flow through the UNMODIFIED production
    `build_stage6_population`/`simulate` without needing any adapter --
    the only divergence from production is the window passed into
    `confirm_in_ltf_window`, nothing downstream."""
    h4, m15, daily, config = eurusd_small_slice
    shared = causal_lib.compute_shared_detection(m15, h4, daily, config)
    results_b2, _sig2h4close, _zero = causal_lib.arm_b2_signals(shared, "EURUSD")
    aligned_signals_b2 = [aligned for aligned, _model, _sid in results_b2]

    population = build_stage6_population(aligned_signals_b2, m15, config, swings=shared.swings)
    trades, report = simulate(aligned_signals_b2, m15, config, swings=shared.swings)
    assert report.trades_opened == len(trades)
    assert all(t.r_multiple is None or isinstance(t.r_multiple, float) for t in trades)
