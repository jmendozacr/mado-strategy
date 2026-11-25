import datetime as dt
from pathlib import Path

import pytest

from eligibility.stop_eligibility import classify_all
from extract.from_causal_lookahead_audit import extract
from features.confirmation_window_features import (
    compute_all_confirmation_window_features,
    compute_confirmation_window_features,
)
from schema.events import (
    EventRecord,
    ExitReasonBasis,
    FeaturesAtStop,
    FeaturesPreEntry,
    Identification,
    Outcome,
    OriginalOperation,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _record(
    model, model1_available_ts, order_placed_ts=None, entry_ts=None, event_id="e1",
):
    order_placed_ts = order_placed_ts if order_placed_ts is not None else model1_available_ts
    entry_ts = entry_ts if entry_ts is not None else order_placed_ts
    identification = Identification(
        event_id=event_id, source_path="x", source_version="x", instrument="EURUSD",
        session_label=model, config_id="d3_c2", original_direction="bullish",
    )
    operation = OriginalOperation(
        entry_price=1.10, stop_loss=1.09, take_profit=1.13, risk_price=0.01,
        activation_ts=model1_available_ts - dt.timedelta(minutes=30), order_placed_ts=order_placed_ts,
        entry_ts=entry_ts, exit_ts=entry_ts, exit_price=1.09, outcome=Outcome.LOSS, r_multiple=-1.01,
        exit_reason="stop_loss", exit_reason_basis=ExitReasonBasis.INFERRED_BINARY,
        ambiguous_bar=False, gap_filled=False, has_partial_exit=False,
    )
    features_pre_entry = FeaturesPreEntry(
        feeder_ref_available_ts=None, activation_instant_ts=operation.activation_ts,
        model1_available_ts=model1_available_ts, order_placed_ts=order_placed_ts,
        time_from_activation_to_order_s=1800.0, planned_risk_price=0.01, planned_reward_price=0.03, planned_rr=3.0,
    )
    features_at_stop = FeaturesAtStop(
        exit_ts=entry_ts, exit_price=1.09, outcome=Outcome.LOSS, r_multiple=-1.01,
        speed_to_stop_s=0.0, ambiguous_bar=False, gap_filled=False,
    )
    return EventRecord(identification, operation, features_pre_entry, features_at_stop)


def test_1am_window_boundaries_are_02_to_04_ny():
    # Confirmation bar open at 03:00 NY (EST, winter) on 2026-01-15 ->
    # model1_available_ts (close) = 03:15 NY = 08:15 UTC.
    model1_available_ts = dt.datetime(2026, 1, 15, 8, 15)
    record = _record("1am", model1_available_ts)
    f = compute_confirmation_window_features(record)
    assert f.window_start_at == dt.datetime(2026, 1, 15, 7, 0)   # 02:00 NY EST = 07:00 UTC
    assert f.window_end_at == dt.datetime(2026, 1, 15, 9, 0)     # 04:00 NY EST = 09:00 UTC
    assert f.window_duration_minutes == pytest.approx(120.0)


def test_9am_window_boundaries_are_09_to_13_ny_not_09_to_1030():
    # Confirmation bar open at 11:00 NY (EST) on 2026-01-15 -> within the
    # TRUE 09:00-13:00 window but OUTSIDE the stale 09:00-10:30 one --
    # this is exactly the regression Phase 7's Unit A caught.
    confirmation_bar_open = dt.datetime(2026, 1, 15, 16, 0)  # 11:00 NY EST = 16:00 UTC
    model1_available_ts = confirmation_bar_open + dt.timedelta(minutes=15)
    record = _record("9am", model1_available_ts)
    f = compute_confirmation_window_features(record)
    assert f.window_start_at == dt.datetime(2026, 1, 15, 14, 0)  # 09:00 NY EST = 14:00 UTC
    assert f.window_end_at == dt.datetime(2026, 1, 15, 18, 0)    # 13:00 NY EST = 18:00 UTC
    assert f.window_duration_minutes == pytest.approx(240.0)
    assert f.window_start_at <= f.confirmation_bar_open <= f.window_end_at


def test_confirmation_available_at_is_bar_open_plus_15_minutes():
    model1_available_ts = dt.datetime(2026, 1, 15, 8, 15)
    record = _record("1am", model1_available_ts)
    f = compute_confirmation_window_features(record)
    assert f.confirmation_bar_open == model1_available_ts - dt.timedelta(minutes=15)
    assert f.confirmation_available_at == model1_available_ts
    assert f.confirmation_available_at - f.confirmation_bar_open == dt.timedelta(minutes=15)


def test_order_placement_never_precedes_confirmation_availability():
    model1_available_ts = dt.datetime(2026, 1, 15, 8, 15)
    record = _record("1am", model1_available_ts, order_placed_ts=model1_available_ts)
    f = compute_confirmation_window_features(record)
    assert f.order_placed_at >= f.confirmation_available_at


def test_fill_never_precedes_order_placement_in_well_formed_data():
    model1_available_ts = dt.datetime(2026, 1, 15, 8, 15)
    entry_ts = model1_available_ts + dt.timedelta(minutes=30)
    record = _record("1am", model1_available_ts, order_placed_ts=model1_available_ts, entry_ts=entry_ts)
    f = compute_confirmation_window_features(record)
    assert f.order_to_fill_minutes == pytest.approx(30.0)
    assert f.order_to_fill_minutes >= 0


def test_elapsed_and_relative_position_respect_window_duration():
    # Confirmation bar open exactly 1 hour (4 M15 bars) into the 1AM window.
    window_start_utc = dt.datetime(2026, 1, 15, 7, 0)  # 02:00 NY EST
    confirmation_bar_open = window_start_utc + dt.timedelta(hours=1)
    model1_available_ts = confirmation_bar_open + dt.timedelta(minutes=15)
    record = _record("1am", model1_available_ts)
    f = compute_confirmation_window_features(record)
    assert f.confirmation_elapsed_minutes == pytest.approx(60.0)
    assert f.confirmation_remaining_minutes == pytest.approx(60.0)  # 120 - 60
    assert f.confirmation_relative_position == pytest.approx(0.5)
    assert f.confirmation_bar_position == pytest.approx(4.0)  # 60 / 15


def test_est_edt_transition_is_handled_by_real_zoneinfo_not_a_fixed_offset():
    # 2026-03-08 is a US DST transition date (02:00 EST -> 03:00 EDT).
    # 1AM's window start (02:00 NY) sits right at the transition; confirm
    # the UTC instant differs from a non-DST date by the correct amount
    # (EST=UTC-5 before, EDT=UTC-4 after) via the real zoneinfo database,
    # never a hand-rolled fixed-offset rule.
    before_dst = dt.datetime(2026, 2, 8, 8, 15)   # confirmation bar close, winter
    after_dst = dt.datetime(2026, 3, 15, 8, 15)    # confirmation bar close, well after the transition
    f_before = compute_confirmation_window_features(_record("1am", before_dst))
    f_after = compute_confirmation_window_features(_record("1am", after_dst))
    # EST (UTC-5): 02:00 NY = 07:00 UTC. EDT (UTC-4): 02:00 NY = 06:00 UTC.
    assert f_before.window_start_at.hour == 7
    assert f_after.window_start_at.hour == 6


def test_missing_model1_available_ts_is_reported_not_invented():
    record = _record("1am", dt.datetime(2026, 1, 15, 8, 15))
    object.__setattr__(record.features_pre_entry, "model1_available_ts", None)
    f = compute_confirmation_window_features(record)
    assert f.window_start_at is None
    assert "model1_available_ts_missing" in f.missing_reasons


def test_unknown_origin_model_is_reported_not_invented():
    record = _record("5am", dt.datetime(2026, 1, 15, 8, 15))
    f = compute_confirmation_window_features(record)
    assert f.window_start_at is None
    assert any("unknown_origin_model" in r for r in f.missing_reasons)


def test_deterministic():
    model1_available_ts = dt.datetime(2026, 1, 15, 8, 15)
    record = _record("1am", model1_available_ts)
    assert compute_confirmation_window_features(record) == compute_confirmation_window_features(record)


def test_compute_all_maps_each_event_independently():
    r1 = _record("1am", dt.datetime(2026, 1, 15, 8, 15), event_id="a")
    r2 = _record("9am", dt.datetime(2026, 1, 15, 14, 45), event_id="b")
    out = compute_all_confirmation_window_features([r1, r2])
    assert set(out.keys()) == {"a", "b"}
    assert out["a"].origin_model == "1am"
    assert out["b"].origin_model == "9am"


def test_real_data_window_and_causal_ordering_invariants():
    """Requirement proofs 3,4,5,6,8,9,15,20: run against the FULL real
    population once -- the module must never silently pass a violation."""
    records = extract(REPO_ROOT)
    executed = [r for r in records if r.operation.outcome is not Outcome.OPEN]
    classify_all(records)  # sanity: extraction + eligibility don't interact badly with this module
    feats = compute_all_confirmation_window_features(executed)

    for r in executed:
        f = feats[r.identification.event_id]
        if f.window_start_at is None:
            continue
        assert f.window_start_at <= f.confirmation_bar_open <= f.window_end_at
        assert -1e-6 <= f.confirmation_elapsed_minutes <= f.window_duration_minutes + 1e-6
        assert f.order_placed_at >= f.confirmation_available_at
        if f.order_to_fill_minutes is not None:
            assert f.order_to_fill_minutes >= 0
