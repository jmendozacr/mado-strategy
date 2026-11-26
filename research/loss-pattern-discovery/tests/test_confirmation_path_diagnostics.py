import datetime as dt
import sys
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = LAB_ROOT.parent.parent
AUDIT_ROOT = REPO_ROOT / "audit" / "2026-11-17-causal-lookahead-audit"
for _path in (AUDIT_ROOT,):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from core.candle import Candle  # noqa: E402
from core.config import Model1Config  # noqa: E402

from extract.confirmation_path_diagnostics import (
    confirm_in_ltf_window_v2_traced,
    trace_confirmation_path_for_record,
)

TS0 = dt.datetime(2026, 1, 1, 10, 0)


def _m15(n):
    return [TS0 + dt.timedelta(minutes=15 * i) for i in range(n)]


def _direct_confirm_candles():
    """Zero invalidations: anchor(1) engulfs(2), retest-touches(3), confirms(4)."""
    ts = _m15(7)
    return (
        Candle(ts[0], open=1.02, high=1.03, low=1.00, close=1.01),
        Candle(ts[1], open=1.01, high=1.02, low=0.95, close=0.96),
        Candle(ts[2], open=0.97, high=1.06, low=0.96, close=1.05),
        Candle(ts[3], open=1.05, high=1.06, low=0.99, close=1.03),
        Candle(ts[4], open=1.04, high=1.07, low=1.03, close=1.06),
        Candle(ts[5], open=1.06, high=1.07, low=1.05, close=1.065),
        Candle(ts[6], open=1.065, high=1.07, low=1.06, close=1.066),
    )


def test_direct_confirmation_has_zero_invalidations_and_one_attempt():
    candles = _direct_confirm_candles()
    path = confirm_in_ltf_window_v2_traced(candles, (0, 6), "bullish", Model1Config())
    assert path.terminal_status == "CONFIRMED"
    assert path.internal_invalidation_count == 0
    assert path.confirmation_attempt_count == 1
    assert path.first_anchor_index == 1
    assert path.final_anchor_index == 1
    assert path.terminal_signal.status.name == "CONFIRMED"
    assert path.terminal_signal.confirmation_index == 4


def _one_invalidation_then_confirm_candles():
    ts = _m15(7)
    return (
        Candle(ts[0], open=1.02, high=1.03, low=1.00, close=1.01),
        Candle(ts[1], open=1.01, high=1.02, low=0.95, close=0.96),  # anchor attempt 0
        Candle(ts[2], open=0.97, high=1.05, low=0.96, close=1.02),  # engulfs attempt 0
        Candle(ts[3], open=0.94, high=0.96, low=0.90, close=0.92),  # invalidates attempt 0 -> becomes anchor 1
        Candle(ts[4], open=0.93, high=0.97, low=0.92, close=0.96),  # engulfs attempt 1
        Candle(ts[5], open=0.97, high=0.98, low=0.93, close=0.95),  # retest-touch attempt 1
        Candle(ts[6], open=0.96, high=0.99, low=0.95, close=0.98),  # confirms attempt 1
    )


def test_confirmation_after_one_invalidation_records_its_real_trajectory():
    candles = _one_invalidation_then_confirm_candles()
    path = confirm_in_ltf_window_v2_traced(candles, (0, 6), "bullish", Model1Config())
    assert path.terminal_status == "CONFIRMED"
    assert path.internal_invalidation_count == 1
    assert path.confirmation_attempt_count == 2
    assert [a.status for a in path.attempts] == ["INVALIDATED", "CONFIRMED"]
    assert path.first_anchor_index == 1
    assert path.final_anchor_index == 3  # the invalidating candle becomes the next anchor
    assert path.terminal_signal.anchor_index == 3
    assert path.terminal_signal.confirmation_index == 6


def _two_invalidations_then_confirm_candles():
    ts = _m15(9)
    return (
        Candle(ts[0], open=1.02, high=1.03, low=1.00, close=1.01),
        Candle(ts[1], open=1.01, high=1.02, low=0.95, close=0.96),  # anchor attempt 0
        Candle(ts[2], open=0.97, high=1.05, low=0.96, close=1.02),  # engulfs attempt 0
        Candle(ts[3], open=0.94, high=0.96, low=0.90, close=0.92),  # invalidates attempt 0 -> anchor 1
        Candle(ts[4], open=0.93, high=0.97, low=0.91, close=0.96),  # engulfs attempt 1
        Candle(ts[5], open=0.95, high=0.96, low=0.85, close=0.88),  # invalidates attempt 1 -> anchor 2
        Candle(ts[6], open=0.89, high=0.99, low=0.87, close=0.97),  # engulfs attempt 2
        Candle(ts[7], open=0.97, high=0.98, low=0.90, close=0.96),  # retest-touch attempt 2
        Candle(ts[8], open=0.95, high=1.00, low=0.94, close=0.99),  # confirms attempt 2
    )


def test_confirmation_after_multiple_invalidations_records_every_restart():
    candles = _two_invalidations_then_confirm_candles()
    path = confirm_in_ltf_window_v2_traced(candles, (0, 8), "bullish", Model1Config())
    assert path.terminal_status == "CONFIRMED"
    assert path.internal_invalidation_count == 2
    assert path.confirmation_attempt_count == 3
    assert [a.status for a in path.attempts] == ["INVALIDATED", "INVALIDATED", "CONFIRMED"]
    assert [a.anchor_index for a in path.attempts] == [1, 3, 5]
    assert path.final_anchor_index == 5
    assert path.terminal_signal.confirmation_index == 8


def test_window_exhaustion_after_engulf_without_retest_is_pending_with_no_fictitious_restart():
    ts = _m15(4)
    candles = (
        Candle(ts[0], open=1.02, high=1.03, low=1.00, close=1.01),
        Candle(ts[1], open=1.01, high=1.02, low=0.95, close=0.96),
        Candle(ts[2], open=0.97, high=1.05, low=0.96, close=1.02),  # engulfs
        Candle(ts[3], open=1.03, high=1.04, low=0.98, close=1.00),  # retest-touch, never closes beyond its open
    )
    path = confirm_in_ltf_window_v2_traced(candles, (0, 3), "bullish", Model1Config())
    assert path.terminal_status == "PENDING"
    assert path.internal_invalidation_count == 0
    assert path.confirmation_attempt_count == 1
    assert path.terminal_signal.status.name == "PENDING"


def test_window_exhaustion_without_ever_engulfing_is_none_with_no_fictitious_restart():
    ts = _m15(3)
    candles = (
        Candle(ts[0], open=1.02, high=1.03, low=1.00, close=1.01),
        Candle(ts[1], open=1.01, high=1.02, low=0.95, close=0.96),
        Candle(ts[2], open=0.97, high=0.99, low=0.94, close=0.98),  # neither engulfs nor invalidates
    )
    path = confirm_in_ltf_window_v2_traced(candles, (0, 2), "bullish", Model1Config())
    # An anchor WAS found (index 1) -- unlike the "no anchor at all" case,
    # this returns a ConfirmationPath whose terminal_signal is None
    # (matching `_track_anchor`'s own `None` return when it never engulfs),
    # never a bare top-level `None`.
    assert path.terminal_status == "NONE"
    assert path.terminal_signal is None
    assert path.internal_invalidation_count == 0
    assert path.confirmation_attempt_count == 1


def test_no_anchor_at_all_returns_none_not_a_degenerate_path():
    ts = _m15(3)
    # Monotonically rising lows -- no candle ever breaks an earlier low.
    candles = (
        Candle(ts[0], open=1.00, high=1.01, low=1.00, close=1.005),
        Candle(ts[1], open=1.01, high=1.02, low=1.01, close=1.015),
        Candle(ts[2], open=1.02, high=1.03, low=1.02, close=1.025),
    )
    path = confirm_in_ltf_window_v2_traced(candles, (0, 2), "bullish", Model1Config())
    assert path is None


def test_attempt_count_equals_invalidation_count_plus_one_always():
    """The algebraic identity from docs/79 section 1 -- checked directly,
    not just asserted, across every terminal shape this module can
    produce."""
    for candles, window in (
        (_direct_confirm_candles(), (0, 6)),
        (_one_invalidation_then_confirm_candles(), (0, 6)),
        (_two_invalidations_then_confirm_candles(), (0, 8)),
    ):
        path = confirm_in_ltf_window_v2_traced(candles, window, "bullish", Model1Config())
        assert path.confirmation_attempt_count == path.internal_invalidation_count + 1


def test_never_reads_candles_beyond_the_window_end_even_when_poisoned():
    """Requirement 10: append two extra candles after the true window end
    that WOULD change the outcome if read (a close breaching the final
    anchor's protected extreme) -- the traced result must be byte-identical
    to the un-poisoned run, because `window=(0, 6)` truncates the array the
    same way the real `confirm_in_ltf_window_v2` does."""
    base = _one_invalidation_then_confirm_candles()
    ts_extra = _m15(9)[7:]
    poisoned = base + (
        Candle(ts_extra[0], open=0.80, high=0.81, low=0.79, close=0.80),  # would invalidate if read
        Candle(ts_extra[1], open=0.70, high=0.71, low=0.69, close=0.70),
    )
    path_clean = confirm_in_ltf_window_v2_traced(base, (0, 6), "bullish", Model1Config())
    path_poisoned = confirm_in_ltf_window_v2_traced(poisoned, (0, 6), "bullish", Model1Config())
    assert path_poisoned.terminal_signal == path_clean.terminal_signal
    assert path_poisoned.attempts == path_clean.attempts


def test_trace_confirmation_path_for_record_reproduces_the_real_pipeline_exactly():
    """Requirement 1/14: the instrumented trace's own terminal
    `Model1Signal` must equal the real, unmodified `confirm_in_ltf_window_v2`'s
    own output for the SAME inputs -- equality of the dataclass (every
    field), not just a matching length or count."""
    import causal_anchor_v2 as ca

    candles = _two_invalidations_then_confirm_candles()
    direct = ca.confirm_in_ltf_window_v2(candles, (0, 8), "bullish", Model1Config())
    traced = confirm_in_ltf_window_v2_traced(candles, (0, 8), "bullish", Model1Config())
    assert traced.terminal_signal == direct


def test_run_d_c2_with_confirmation_paths_reproduces_the_real_pipeline_exactly():
    """Real-data equivalence proof (requirements 1, 2, 14): the
    instrumented runner's own `records_with_ids`/`counters` must be
    identical to calling the real, unmodified `run_d_c2` directly, and
    every CONFIRMED record must receive a reconstructed path whose own
    terminal signal matches that record's real `aligned.ltf_signal`
    exactly."""
    from datetime import datetime as _dt

    from causal_lib import build_key_levels
    from core.config import DetectorConfig
    from experimental.htf_trigger_1am_9am_backtest import SYMBOL_CONFIG
    from primitives.swing import detect_swings
    from run_d1_d2_d3 import run_d_c2

    from extract.confirmation_path_diagnostics import run_d_c2_with_confirmation_paths
    from extract.funnel_reconstruction import _load_symbol_data

    symbol = "EURUSD"
    h4, m15, daily = _load_symbol_data(symbol)
    config = DetectorConfig(backtest=SYMBOL_CONFIG[symbol])
    m15_timestamps = [c.timestamp for c in m15.candles]
    detect_swings(m15, config.swing)
    key_levels = build_key_levels(h4, daily, config.fvg)
    start_date = _dt(2015, 1, 1)
    end_date = _dt(2015, 3, 1)

    original_records, original_counters = run_d_c2(
        symbol, h4, m15, daily, config, m15_timestamps, None, None, key_levels,
        "new", "new", "d3_c2", start_date=start_date, end_date=end_date,
    )
    traced_records, traced_counters, paths = run_d_c2_with_confirmation_paths(
        symbol, h4, m15, daily, config, m15_timestamps, key_levels,
        "new", "d3_c2", start_date=start_date, end_date=end_date,
    )

    def _fingerprint(records_with_ids):
        return sorted(
            (sid, r.model_name, r.direction, r.confirmation_index,
             r.aligned.ltf_signal.signal_id if r.aligned is not None else None)
            for r, sid in records_with_ids
        )

    assert _fingerprint(traced_records) == _fingerprint(original_records)
    for model in ("1am", "9am"):
        assert traced_counters[model].to_dict() == original_counters[model].to_dict()

    confirmed_sids = {sid for record, sid in original_records if record.aligned is not None}
    assert set(paths.keys()) == confirmed_sids
    n_matched = 0
    for record, sid in original_records:
        if record.aligned is None:
            continue
        path = paths[sid]
        assert path is not None, f"{sid}: confirmed record got no reconstructed path"
        assert path.terminal_signal == record.aligned.ltf_signal
        n_matched += 1
    assert n_matched == len(confirmed_sids) > 0
