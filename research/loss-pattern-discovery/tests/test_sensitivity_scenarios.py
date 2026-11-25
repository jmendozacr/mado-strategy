import datetime as dt

import pytest

from core.candle import Candle, OHLCSeries

from eligibility.intrabar_ambiguity import classify_all_intrabar_uncertainty
from eligibility.stop_timing_decomposition import classify_all_timing
from schema.events import (
    EventRecord,
    ExitReasonBasis,
    FeaturesAtStop,
    FeaturesPreEntry,
    Identification,
    Outcome,
    OriginalOperation,
)
from stats.early_stop_hypothesis import build_primary_population
from stats.sensitivity_scenarios import scenario_s0, scenario_s1, scenario_s2, scenario_s3

TS = dt.datetime(2026, 1, 1, 10, 0)
TS_NEXT = TS + dt.timedelta(minutes=15)


def _series() -> dict:
    series = OHLCSeries(
        candles=(
            Candle(TS, open=1.095, high=1.15, low=1.08, close=1.09),
            Candle(TS_NEXT, open=1.09, high=1.09, low=1.08, close=1.08),
        ),
        instrument="EURUSD", timeframe="M15",
    )
    return {"EURUSD": series}


def _record(event_id, model, entry_ts, exit_ts, outcome=Outcome.LOSS, entry_price=1.10, stop_loss=1.09):
    exit_price = stop_loss if outcome is Outcome.LOSS else 1.13
    identification = Identification(
        event_id=event_id, source_path="x", source_version="x", instrument="EURUSD",
        session_label=model, config_id="d3_c2", original_direction="bullish",
    )
    operation = OriginalOperation(
        entry_price=entry_price, stop_loss=stop_loss, take_profit=1.13, risk_price=abs(entry_price - stop_loss),
        activation_ts=entry_ts - dt.timedelta(minutes=30), order_placed_ts=entry_ts,
        entry_ts=entry_ts, exit_ts=exit_ts, exit_price=exit_price, outcome=outcome,
        r_multiple=-1.01 if outcome is Outcome.LOSS else 2.0,
        exit_reason="stop_loss" if outcome is Outcome.LOSS else "take_profit",
        exit_reason_basis=ExitReasonBasis.INFERRED_BINARY, ambiguous_bar=False, gap_filled=False,
        has_partial_exit=False,
    )
    features_pre_entry = FeaturesPreEntry(
        feeder_ref_available_ts=None, activation_instant_ts=operation.activation_ts,
        model1_available_ts=None, order_placed_ts=entry_ts, time_from_activation_to_order_s=1800.0,
        planned_risk_price=operation.risk_price, planned_reward_price=0.03, planned_rr=2.0,
    )
    features_at_stop = FeaturesAtStop(
        exit_ts=exit_ts, exit_price=exit_price, outcome=outcome, r_multiple=operation.r_multiple,
        speed_to_stop_s=(exit_ts - entry_ts).total_seconds(), ambiguous_bar=False, gap_filled=False,
    )
    return EventRecord(identification, operation, features_pre_entry, features_at_stop)


def _build():
    records = [
        # 1am: one sequence-verifiable E0, one NOT-verifiable E0, one E1, one win.
        _record("1am-e0v", "1am", TS, TS, entry_price=1.09, stop_loss=1.08),   # open=1.095 >= 1.09 -> verifiable
        _record("1am-e0nv", "1am", TS, TS, entry_price=1.10, stop_loss=1.09),  # open=1.095 < 1.10 -> not verifiable
        _record("1am-e1", "1am", TS, TS_NEXT, entry_price=1.10, stop_loss=1.09),
        _record("1am-win", "1am", TS, TS, outcome=Outcome.WIN),
        # 9am: two wins, one E1 -- no same-bar SL at all for this model.
        _record("9am-win1", "9am", TS, TS, outcome=Outcome.WIN),
        _record("9am-win2", "9am", TS, TS, outcome=Outcome.WIN),
        _record("9am-e1", "9am", TS, TS_NEXT, entry_price=1.10, stop_loss=1.09),
    ]
    series_by_instrument = _series()
    timing_by_id = classify_all_timing(records, series_by_instrument)
    uncertainty_by_id = classify_all_intrabar_uncertainty(records, timing_by_id, series_by_instrument)
    primary = build_primary_population(records)
    return records, primary, timing_by_id, uncertainty_by_id


def test_s0_matches_hand_computed_rates():
    _, primary, timing_by_id, _ = _build()
    result = scenario_s0(primary, timing_by_id)
    assert result["n_1am"] == 4
    assert result["n_9am"] == 3
    assert result["rate_1am"] == pytest.approx(3 / 4)
    assert result["rate_9am"] == pytest.approx(1 / 3)


def test_s1_counts_only_next_bar_not_same_bar():
    _, primary, timing_by_id, _ = _build()
    result = scenario_s1(primary, timing_by_id)
    assert result["rate_1am"] == pytest.approx(1 / 4)
    assert result["rate_9am"] == pytest.approx(1 / 3)


def test_s2_upper_bound_equals_s0_exactly():
    # By construction: the upper bound keeps the engine's own convention for
    # every category, including not-verifiable E0 -- identical to S0.
    _, primary, timing_by_id, uncertainty_by_id = _build()
    s0 = scenario_s0(primary, timing_by_id)
    s2 = scenario_s2(primary, timing_by_id, uncertainty_by_id)
    assert s2["upper_bound"] == s0


def test_s2_lower_bound_never_exceeds_upper_bound():
    _, primary, timing_by_id, uncertainty_by_id = _build()
    s2 = scenario_s2(primary, timing_by_id, uncertainty_by_id)
    assert s2["lower_bound"]["rate_1am"] <= s2["upper_bound"]["rate_1am"]
    assert s2["lower_bound"]["rate_1am"] == pytest.approx(2 / 4)  # e0nv excluded from the numerator only
    # 9am has no not-verifiable E0 at all -- bounds collapse to one point.
    assert s2["lower_bound"]["rate_9am"] == pytest.approx(s2["upper_bound"]["rate_9am"])


def test_s2_never_recodes_the_indeterminate_event_as_win_or_non_entry():
    records, primary, timing_by_id, uncertainty_by_id = _build()
    scenario_s2(primary, timing_by_id, uncertainty_by_id)
    indeterminate = next(r for r in records if r.identification.event_id == "1am-e0nv")
    assert indeterminate.operation.outcome is Outcome.LOSS
    assert indeterminate.operation.entry_ts is not None


def test_s3_excludes_the_not_verifiable_e0_event_and_reports_it():
    _, primary, timing_by_id, uncertainty_by_id = _build()
    result = scenario_s3(primary, timing_by_id, uncertainty_by_id)
    assert result["n_excluded_total"] == 1
    assert result["n_excluded_by_model"] == {"1am": 1}
    assert result["n_total_by_model"] == {"1am": 4, "9am": 3}
    assert result["exclusion_share_by_model"]["1am"] == pytest.approx(0.25)
    assert result["exclusion_share_by_model"]["9am"] == pytest.approx(0.0)
    # retained: 1am {e0v, e1, win} -> 2/3 ; 9am {win1, win2, e1} -> 1/3
    assert result["gap_on_verifiable_subset"]["rate_1am"] == pytest.approx(2 / 3)
    assert result["gap_on_verifiable_subset"]["rate_9am"] == pytest.approx(1 / 3)


def test_scenarios_are_deterministic():
    _, primary, timing_by_id, uncertainty_by_id = _build()
    assert scenario_s0(primary, timing_by_id) == scenario_s0(primary, timing_by_id)
    assert scenario_s1(primary, timing_by_id) == scenario_s1(primary, timing_by_id)
    assert scenario_s2(primary, timing_by_id, uncertainty_by_id) == scenario_s2(primary, timing_by_id, uncertainty_by_id)
    assert scenario_s3(primary, timing_by_id, uncertainty_by_id) == scenario_s3(primary, timing_by_id, uncertainty_by_id)
