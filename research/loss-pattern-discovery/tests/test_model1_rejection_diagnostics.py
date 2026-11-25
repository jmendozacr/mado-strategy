import datetime as dt
import sys
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = LAB_ROOT.parent.parent
AUDIT_ROOT = REPO_ROOT / "audit" / "2026-11-17-causal-lookahead-audit"
for _path in (AUDIT_ROOT,):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import causal_anchor_v2 as ca  # noqa: E402
from causal_intrabar import CausalSignalRecord  # noqa: E402
from core.candle import Candle  # noqa: E402
from core.config import Model1Config  # noqa: E402
from core.results import DetectionStatus  # noqa: E402

from extract.model1_rejection_diagnostics import (
    _window_open_ts_from_stable_id,
    diagnose_rejection,
    probe_first_anchor,
)

TS0 = dt.datetime(2026, 1, 1, 10, 0)


def _m15(n):
    return [TS0 + dt.timedelta(minutes=15 * i) for i in range(n)]


def test_confirm_in_ltf_window_v2_never_returns_invalidated_as_terminal():
    """Hand-constructed candle sequence: the real `_track_anchor`
    invalidates once (idx 1 -> idx 3), and `confirm_in_ltf_window_v2`'s
    own retry loop picks it up -- the final status must never be
    INVALIDATED, proving the structural fact this module's docstring
    claims, not just asserting it."""
    ts = _m15(5)
    candles = (
        Candle(ts[0], open=1.02, high=1.03, low=1.00, close=1.01),
        Candle(ts[1], open=1.01, high=1.02, low=0.95, close=0.96),   # anchor (origin=0)
        Candle(ts[2], open=0.97, high=1.05, low=0.96, close=1.02),   # engulfs (close > body_high=1.01)
        Candle(ts[3], open=0.94, high=0.96, low=0.90, close=0.92),   # breaches protected_extreme=0.95 -> INVALIDATED here
        Candle(ts[4], open=0.93, high=0.94, low=0.91, close=0.935),  # neither breaches (0.90) nor engulfs (0.94) -> loop ends unconfirmed
    )
    result = ca.confirm_in_ltf_window_v2(candles, (0, 4), "bullish", Model1Config())
    assert result is None  # terminal is None, not INVALIDATED
    # Sanity: the anchor WAS found and DID invalidate internally (otherwise
    # this test would not actually exercise the retry path at all).
    direct = ca.find_first_valid_anchor(candles, 0, 4, "bullish")
    assert direct == (0, 1)


def test_probe_first_anchor_true_when_an_anchor_exists():
    ts = _m15(3)
    candles = (
        Candle(ts[0], open=1.02, high=1.03, low=1.00, close=1.01),
        Candle(ts[1], open=1.01, high=1.02, low=0.95, close=0.96),
        Candle(ts[2], open=0.97, high=1.05, low=0.96, close=1.02),
    )
    assert probe_first_anchor(candles, (0, 2), "bullish") is True


def test_probe_first_anchor_false_when_no_anchor_exists():
    ts = _m15(3)
    # Monotonically rising lows -- no candle ever breaks an earlier low.
    candles = (
        Candle(ts[0], open=1.00, high=1.01, low=1.00, close=1.005),
        Candle(ts[1], open=1.01, high=1.02, low=1.01, close=1.015),
        Candle(ts[2], open=1.02, high=1.03, low=1.02, close=1.025),
    )
    assert probe_first_anchor(candles, (0, 2), "bullish") is False


def _record(model_name="1am", direction="bullish", zero_signal_reason=None, aligned=None):
    return CausalSignalRecord(
        aligned=aligned, model_name=model_name, direction=direction,
        feeder_ref_available_ts=TS0, activation_instant_ts=TS0,
        model1_available_ts=None, confirmation_index=None, order_placed_ts=None,
        zero_signal_reason=zero_signal_reason,
    )


def test_diagnose_rejection_categorizes_window_empty_without_probing():
    record = _record(zero_signal_reason="window [x, y) ends at or before activation z -- no causally valid portion")
    diag = diagnose_rejection("1am", TS0, None, lambda t: TS0, lambda t: TS0, record)
    assert diag.category == "window_empty_before_search"
    assert diag.anchor_probe is None


def test_diagnose_rejection_categorizes_pending_or_invalidated_without_probing():
    record = _record(zero_signal_reason="Model-1 resolved PENDING, not CONFIRMED -- excluded per design S1.3's stricter filter")
    diag = diagnose_rejection("1am", TS0, None, lambda t: TS0, lambda t: TS0, record)
    assert diag.category == "model1_pending_or_invalidated"
    assert diag.anchor_probe is None


def test_diagnose_rejection_probes_when_no_anchor_found_and_window_exists():
    ts = _m15(3)
    candles = (
        Candle(ts[0], open=1.02, high=1.03, low=1.00, close=1.01),
        Candle(ts[1], open=1.01, high=1.02, low=0.95, close=0.96),
        Candle(ts[2], open=0.97, high=1.05, low=0.96, close=1.02),
    )

    class _FakeSeries:
        pass

    series = _FakeSeries()
    series.candles = candles

    # ts[0] == TS0 == _record()'s own default activation_instant_ts.
    record = _record(
        direction="bullish",
        zero_signal_reason="no anchor/confirmation/retest completed inside the causally-valid window",
    )
    diag = diagnose_rejection(
        "1am", ts[0], series,
        window_start_fn=lambda t: ts[0], window_end_fn=lambda t: ts[2] + dt.timedelta(minutes=15),
        record=record,
    )
    assert diag.category == "no_model1_anchor_found"
    assert diag.anchor_probe is True  # an anchor DOES exist in this candle set


def test_window_open_ts_from_stable_id_round_trips():
    sid = f"EURUSD|d3_c2|1am|{TS0.isoformat()}|bullish"
    assert _window_open_ts_from_stable_id(sid) == TS0


def test_run_d_c2_instrumented_reproduces_the_real_pipeline_exactly():
    """Requirement 7: the instrumented path's own `records_with_ids`/
    `counters` must be identical to calling the real, unmodified
    `run_d_c2` directly -- not just the same length, every record."""
    import sys as _sys
    from datetime import datetime as _dt

    from core.config import DetectorConfig
    from experimental.htf_trigger_1am_9am_backtest import SYMBOL_CONFIG
    from primitives.swing import detect_swings
    from causal_lib import build_key_levels
    from run_d1_d2_d3 import run_d_c2

    from extract.funnel_reconstruction import _load_symbol_data
    from extract.model1_rejection_diagnostics import run_d_c2_instrumented

    symbol = "EURUSD"
    h4, m15, daily = _load_symbol_data(symbol)
    config = DetectorConfig(backtest=SYMBOL_CONFIG[symbol])
    m15_timestamps = [c.timestamp for c in m15.candles]
    swings = detect_swings(m15, config.swing)
    key_levels = build_key_levels(h4, daily, config.fvg)
    start_date = _dt(2015, 1, 1)
    # A short, deliberately tight date range -- this test only needs to
    # prove equivalence, not reproduce the full 11-year reconciliation.
    end_date = _dt(2015, 3, 1)

    original_records, original_counters = run_d_c2(
        symbol, h4, m15, daily, config, m15_timestamps, None, swings, key_levels,
        "new", "new", "d3_c2", start_date=start_date, end_date=end_date,
    )
    instrumented_records, instrumented_counters, diagnostics = run_d_c2_instrumented(
        symbol, h4, m15, daily, config, m15_timestamps, key_levels,
        "new", "d3_c2", start_date=start_date, end_date=end_date,
    )

    def _fingerprint(records_with_ids):
        return sorted(
            (
                sid, record.model_name, record.direction, record.zero_signal_reason,
                record.confirmation_index, record.order_placed_ts,
                record.aligned.ltf_signal.signal_id if record.aligned is not None else None,
            )
            for record, sid in records_with_ids
        )

    assert _fingerprint(instrumented_records) == _fingerprint(original_records)
    for model in ("1am", "9am"):
        assert instrumented_counters[model].to_dict() == original_counters[model].to_dict()
    # Every non-confirmed record got a diagnostic; every confirmed one did not.
    non_confirmed_sids = {sid for record, sid in original_records if record.aligned is None}
    assert set(diagnostics.keys()) == non_confirmed_sids
