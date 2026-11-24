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
from validate.integrity import (
    check_duplicate_ids,
    check_outcome_r_sign,
    check_price_side_consistency,
    check_temporal_ordering,
)


def _make_record(
    event_id="e1",
    direction="bullish",
    entry_price=1.10,
    stop_loss=1.09,
    take_profit=1.12,
    outcome=Outcome.LOSS,
    r_multiple=-1.0,
    order_placed_ts=dt.datetime(2026, 1, 1, 9, 0),
    entry_ts=dt.datetime(2026, 1, 1, 9, 0),
    exit_ts=dt.datetime(2026, 1, 1, 10, 0),
) -> EventRecord:
    identification = Identification(
        event_id=event_id, source_path="x", source_version="x",
        instrument="EURUSD", session_label="9am", config_id="d3_c2",
        original_direction=direction,
    )
    operation = OriginalOperation(
        entry_price=entry_price, stop_loss=stop_loss, take_profit=take_profit,
        risk_price=abs(entry_price - stop_loss),
        activation_ts=order_placed_ts, order_placed_ts=order_placed_ts,
        entry_ts=entry_ts, exit_ts=exit_ts,
        exit_price=stop_loss, outcome=outcome, r_multiple=r_multiple,
        exit_reason="stop_loss", exit_reason_basis=ExitReasonBasis.INFERRED_BINARY,
        ambiguous_bar=False, gap_filled=False, has_partial_exit=False,
    )
    features_pre_entry = FeaturesPreEntry(
        feeder_ref_available_ts=order_placed_ts, activation_instant_ts=order_placed_ts,
        model1_available_ts=order_placed_ts, order_placed_ts=order_placed_ts,
        time_from_activation_to_order_s=0.0,
        planned_risk_price=operation.risk_price,
        planned_reward_price=abs(take_profit - entry_price), planned_rr=2.0,
    )
    features_at_stop = FeaturesAtStop(
        exit_ts=exit_ts, exit_price=operation.exit_price, outcome=outcome,
        r_multiple=r_multiple, speed_to_stop_s=3600.0, ambiguous_bar=False, gap_filled=False,
    )
    return EventRecord(identification, operation, features_pre_entry, features_at_stop)


def test_clean_record_has_no_issues():
    record = _make_record()
    assert check_temporal_ordering(record) == []
    assert check_price_side_consistency(record) == []
    assert check_outcome_r_sign(record) == []


def test_bad_chronology_is_flagged():
    record = _make_record(entry_ts=dt.datetime(2026, 1, 1, 11, 0), exit_ts=dt.datetime(2026, 1, 1, 10, 0))
    issues = check_temporal_ordering(record)
    assert any(issue.check == "temporal_ordering" for issue in issues)


def test_bad_price_side_for_bullish_is_flagged():
    # stop_loss above entry_price is nonsensical for a bullish trade.
    record = _make_record(direction="bullish", entry_price=1.10, stop_loss=1.11, take_profit=1.12)
    issues = check_price_side_consistency(record)
    assert len(issues) == 1


def test_loss_with_positive_r_is_flagged():
    record = _make_record(outcome=Outcome.LOSS, r_multiple=0.5)
    issues = check_outcome_r_sign(record)
    assert len(issues) == 1


def test_duplicate_ids_are_flagged():
    records = [_make_record(event_id="dup"), _make_record(event_id="dup"), _make_record(event_id="unique")]
    issues = check_duplicate_ids(records)
    assert len(issues) == 1
    assert issues[0].event_id == "dup"
