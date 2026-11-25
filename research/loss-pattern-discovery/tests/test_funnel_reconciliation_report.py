import datetime as dt

from schema.events import (
    EventRecord,
    ExitReasonBasis,
    FeaturesAtStop,
    FeaturesPreEntry,
    Identification,
    Outcome,
    OriginalOperation,
)
from stats.funnel_reconciliation_report import (
    _ledger_counts_by_model_and_instrument,
    build_reconciliation_table,
    detect_duplicate_event_ids,
)

TS = dt.datetime(2026, 1, 1, 10, 0)


def _record(event_id, model="1am", instrument="EURUSD", outcome=Outcome.LOSS):
    exit_price = 1.09 if outcome is Outcome.LOSS else (1.13 if outcome is Outcome.WIN else None)
    identification = Identification(
        event_id=event_id, source_path="x", source_version="x", instrument=instrument,
        session_label=model, config_id="d3_c2", original_direction="bullish",
    )
    operation = OriginalOperation(
        entry_price=1.10, stop_loss=1.09, take_profit=1.13, risk_price=0.01,
        activation_ts=TS - dt.timedelta(minutes=30), order_placed_ts=TS,
        entry_ts=TS, exit_ts=(TS if outcome is not Outcome.OPEN else None), exit_price=exit_price,
        outcome=outcome, r_multiple=(-1.01 if outcome is Outcome.LOSS else (2.0 if outcome is Outcome.WIN else None)),
        exit_reason=None, exit_reason_basis=ExitReasonBasis.UNKNOWN,
        ambiguous_bar=False, gap_filled=False, has_partial_exit=False,
    )
    features_pre_entry = FeaturesPreEntry(
        feeder_ref_available_ts=None, activation_instant_ts=operation.activation_ts,
        model1_available_ts=None, order_placed_ts=TS, time_from_activation_to_order_s=1800.0,
        planned_risk_price=0.01, planned_reward_price=0.03, planned_rr=3.0,
    )
    features_at_stop = FeaturesAtStop(
        exit_ts=operation.exit_ts, exit_price=exit_price, outcome=outcome, r_multiple=operation.r_multiple,
        speed_to_stop_s=0.0, ambiguous_bar=False, gap_filled=False,
    )
    return EventRecord(identification, operation, features_pre_entry, features_at_stop)


def test_detect_duplicate_event_ids_finds_a_real_duplicate():
    records = [_record("a"), _record("b"), _record("a")]
    assert detect_duplicate_event_ids(records) == ["a"]


def test_detect_duplicate_event_ids_empty_when_all_unique():
    records = [_record("a"), _record("b"), _record("c")]
    assert detect_duplicate_event_ids(records) == []


def test_records_with_unresolvable_model_are_reported_not_silently_dropped():
    records = [_record("a", model="1am"), _record("b", model="5am")]  # "5am" is not a known model
    resolution = _ledger_counts_by_model_and_instrument(records)
    assert resolution["unresolved_event_ids"] == ["b"]
    assert resolution["counts"]["1am"]["EURUSD"]["executed"] == 1


def test_records_with_unresolvable_instrument_are_reported():
    records = [_record("a", instrument="GBPUSD")]  # not one of this lab's three pairs
    resolution = _ledger_counts_by_model_and_instrument(records)
    assert resolution["unresolved_event_ids"] == ["a"]


def test_build_reconciliation_table_flags_fully_reconciled_false_on_duplicate():
    records = [_record("a"), _record("a")]  # deliberate duplicate
    funnel_result = {
        instrument: {"splits": {"1am": {"candidates_built": 0, "filled": 0, "never_filled": 0, "skipped_no_placement": 0},
                                 "9am": {"candidates_built": 0, "filled": 0, "never_filled": 0, "skipped_no_placement": 0}}}
        for instrument in ("EURUSD", "USDCAD", "AUDUSD")
    }
    funnel_result["EURUSD"]["splits"]["1am"]["filled"] = 2  # matches the 2 duplicate records
    table = build_reconciliation_table(funnel_result, records)
    assert table["duplicate_event_ids"] == ["a"]
    assert table["fully_reconciled"] is False
