import datetime as dt

import pytest

from core.candle import Candle, OHLCSeries

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
from stats.e1_timing_association import (
    model_0_baseline,
    model_1_risk_standardized,
    model_2_timing_standardized,
    model_3_timing_by_subgroup,
)
from stats.early_stop_hypothesis import build_primary_population
from stats.temporal_feature_dataset import TemporalFeatureRow

TS = dt.datetime(2026, 1, 1, 10, 0)
TS_NEXT = TS + dt.timedelta(minutes=15)


def _series():
    series = OHLCSeries(
        candles=(Candle(TS, open=1.10, high=1.101, low=1.099, close=1.10),
                 Candle(TS_NEXT, open=1.10, high=1.10, low=1.09, close=1.09)),
        instrument="EURUSD", timeframe="M15",
    )
    return {"EURUSD": series}


def _record(event_id, model, outcome, instrument="EURUSD"):
    is_e1 = outcome == "e1"
    exit_ts = TS_NEXT if is_e1 else TS
    real_outcome = Outcome.WIN if outcome == "win" else Outcome.LOSS
    exit_price = 1.13 if real_outcome is Outcome.WIN else 1.09
    identification = Identification(
        event_id=event_id, source_path="x", source_version="x", instrument=instrument,
        session_label=model, config_id="d3_c2", original_direction="bullish",
    )
    operation = OriginalOperation(
        entry_price=1.10, stop_loss=1.09, take_profit=1.13, risk_price=0.01,
        activation_ts=TS - dt.timedelta(minutes=30), order_placed_ts=TS,
        entry_ts=TS, exit_ts=exit_ts, exit_price=exit_price, outcome=real_outcome,
        r_multiple=-1.01 if real_outcome is Outcome.LOSS else 2.0,
        exit_reason="stop_loss" if real_outcome is Outcome.LOSS else "take_profit",
        exit_reason_basis=ExitReasonBasis.INFERRED_BINARY, ambiguous_bar=False, gap_filled=False,
        has_partial_exit=False,
    )
    features_pre_entry = FeaturesPreEntry(
        feeder_ref_available_ts=None, activation_instant_ts=operation.activation_ts,
        model1_available_ts=None, order_placed_ts=TS, time_from_activation_to_order_s=1800.0,
        planned_risk_price=0.01, planned_reward_price=0.03, planned_rr=3.0,
    )
    features_at_stop = FeaturesAtStop(
        exit_ts=exit_ts, exit_price=exit_price, outcome=real_outcome, r_multiple=operation.r_multiple,
        speed_to_stop_s=(exit_ts - TS).total_seconds(), ambiguous_bar=False, gap_filled=False,
    )
    return EventRecord(identification, operation, features_pre_entry, features_at_stop)


def _row(event_id, model, risk_atr, elapsed, instrument="EURUSD", period="2024-2026"):
    return TemporalFeatureRow(
        event_id=event_id, origin_model=model, instrument=instrument, direction="bullish",
        period_bucket=period, outcome="loss",
        confirmation_elapsed_minutes=elapsed, confirmation_remaining_minutes=120.0 - elapsed,
        confirmation_relative_position=elapsed / 120.0, confirmation_bar_position=elapsed / 15.0,
        window_duration_minutes=120.0, order_to_fill_minutes=5.0,
        risk_atr=risk_atr, atr_m15_at_entry=0.0008, risk_price=0.01, planned_rr=2.5,
        missing_reasons=(),
    )


def _build():
    records = [
        _record("1am-e1-1", "1am", "e1"), _record("1am-e1-2", "1am", "e1"),
        _record("1am-win-1", "1am", "win"), _record("1am-win-2", "1am", "win"),
        _record("9am-e1-1", "9am", "e1"),
        _record("9am-win-1", "9am", "win"), _record("9am-win-2", "9am", "win"),
        _record("9am-win-3", "9am", "win"),
    ]
    series_by_instrument = _series()
    timing_by_id = classify_all_timing(records, series_by_instrument)
    primary = build_primary_population(records)
    dataset = {
        "1am-e1-1": _row("1am-e1-1", "1am", 1.5, 100.0), "1am-e1-2": _row("1am-e1-2", "1am", 1.2, 20.0),
        "1am-win-1": _row("1am-win-1", "1am", 1.3, 50.0), "1am-win-2": _row("1am-win-2", "1am", 1.4, 60.0),
        "9am-e1-1": _row("9am-e1-1", "9am", 1.1, 100.0),
        "9am-win-1": _row("9am-win-1", "9am", 1.2, 20.0), "9am-win-2": _row("9am-win-2", "9am", 1.3, 30.0),
        "9am-win-3": _row("9am-win-3", "9am", 1.4, 40.0),
    }
    return primary, timing_by_id, dataset


def test_model_0_matches_hand_computed_e1_rate():
    primary, timing_by_id, _ = _build()
    result = model_0_baseline(primary, timing_by_id)
    assert result["rate_1am"] == pytest.approx(2 / 4)  # 2 of 4 1am events are E1
    assert result["rate_9am"] == pytest.approx(1 / 4)  # 1 of 4 9am events are E1


def test_model_1_risk_standardized_has_common_support_and_standardized_gap():
    primary, timing_by_id, dataset = _build()
    result = model_1_risk_standardized(primary, timing_by_id, dataset)
    assert "common_support" in result and "standardized_gap" in result
    assert "cutpoints" in result


def test_model_2_timing_standardized_never_uses_order_to_fill_minutes():
    primary, timing_by_id, dataset = _build()
    result = model_2_timing_standardized(primary, timing_by_id, dataset, "confirmation_elapsed_minutes")
    assert result["field"] == "confirmation_elapsed_minutes"
    assert "common_support" in result and "standardized_gap" in result


def test_model_2_relative_position_is_a_separate_run_from_absolute_minutes():
    primary, timing_by_id, dataset = _build()
    absolute = model_2_timing_standardized(primary, timing_by_id, dataset, "confirmation_elapsed_minutes")
    relative = model_2_timing_standardized(primary, timing_by_id, dataset, "confirmation_relative_position")
    assert absolute["field"] != relative["field"]
    assert absolute["cutpoints"] != relative["cutpoints"]


def test_model_3_is_one_way_never_a_combinatorial_grid():
    primary, timing_by_id, dataset = _build()
    result = model_3_timing_by_subgroup(primary, timing_by_id, dataset, "confirmation_elapsed_minutes")
    assert set(result.keys()) == {"by_instrument", "by_period"}
    assert set(result["by_instrument"].keys()) == {"EURUSD", "USDCAD", "AUDUSD"}
    # No key combines instrument AND period together (no joint grid).
    for sub in result["by_instrument"].values():
        assert "by_period" not in sub
    for sub in result["by_period"].values():
        assert "by_instrument" not in sub


def test_models_are_deterministic():
    primary, timing_by_id, dataset = _build()
    assert model_0_baseline(primary, timing_by_id) == model_0_baseline(primary, timing_by_id)
    assert (
        model_1_risk_standardized(primary, timing_by_id, dataset)
        == model_1_risk_standardized(primary, timing_by_id, dataset)
    )
