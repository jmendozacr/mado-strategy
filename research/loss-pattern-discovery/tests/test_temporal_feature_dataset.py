import datetime as dt

from core.candle import Candle, OHLCSeries

from schema.events import (
    EventRecord,
    ExitReasonBasis,
    FeaturesAtStop,
    FeaturesPreEntry,
    Identification,
    Outcome,
    OriginalOperation,
)
from stats.temporal_feature_dataset import build_temporal_feature_dataset

TS = dt.datetime(2026, 1, 15, 8, 15)  # model1_available_ts for 1am: 03:00 NY close


def _record(event_id, model="1am"):
    identification = Identification(
        event_id=event_id, source_path="x", source_version="x", instrument="EURUSD",
        session_label=model, config_id="d3_c2", original_direction="bullish",
    )
    operation = OriginalOperation(
        entry_price=1.10, stop_loss=1.09, take_profit=1.13, risk_price=0.01,
        activation_ts=TS - dt.timedelta(minutes=30), order_placed_ts=TS,
        entry_ts=TS, exit_ts=TS, exit_price=1.09, outcome=Outcome.LOSS, r_multiple=-1.01,
        exit_reason="stop_loss", exit_reason_basis=ExitReasonBasis.INFERRED_BINARY,
        ambiguous_bar=False, gap_filled=False, has_partial_exit=False,
    )
    features_pre_entry = FeaturesPreEntry(
        feeder_ref_available_ts=None, activation_instant_ts=operation.activation_ts,
        model1_available_ts=TS, order_placed_ts=TS, time_from_activation_to_order_s=1800.0,
        planned_risk_price=0.01, planned_reward_price=0.03, planned_rr=3.0,
    )
    features_at_stop = FeaturesAtStop(
        exit_ts=TS, exit_price=1.09, outcome=Outcome.LOSS, r_multiple=-1.01,
        speed_to_stop_s=0.0, ambiguous_bar=False, gap_filled=False,
    )
    return EventRecord(identification, operation, features_pre_entry, features_at_stop)


def _series():
    candles = [Candle(TS - dt.timedelta(minutes=15 * i), open=1.10, high=1.101, low=1.099, close=1.10)
               for i in range(20, 0, -1)] + [Candle(TS, open=1.10, high=1.101, low=1.099, close=1.10)]
    return {"EURUSD": OHLCSeries(candles=tuple(candles), instrument="EURUSD", timeframe="M15")}


def test_dataset_joins_window_and_pre_entry_features():
    record = _record("e1")
    dataset = build_temporal_feature_dataset([record], _series())
    row = dataset["e1"]
    assert row.origin_model == "1am"
    assert row.instrument == "EURUSD"
    assert row.confirmation_elapsed_minutes is not None
    assert row.window_duration_minutes == 120.0  # 1AM, unaffected by the 9AM correction
    assert row.risk_price == 0.01


def test_period_bucket_is_assigned_from_entry_ts():
    record = _record("e1")
    dataset = build_temporal_feature_dataset([record], _series())
    assert dataset["e1"].period_bucket == "2024-2026"


def test_missing_reasons_combine_window_and_pre_entry_sources():
    record = _record("e1")
    object.__setattr__(record.features_pre_entry, "model1_available_ts", None)
    dataset = build_temporal_feature_dataset([record], _series())
    assert "model1_available_ts_missing" in dataset["e1"].missing_reasons


def test_dataset_keyed_by_event_id_for_multiple_records():
    r1, r2 = _record("a", "1am"), _record("b", "9am")
    dataset = build_temporal_feature_dataset([r1, r2], _series())
    assert set(dataset.keys()) == {"a", "b"}
    assert dataset["b"].origin_model == "9am"
