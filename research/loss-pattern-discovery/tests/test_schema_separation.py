import dataclasses

from schema.events import EventRecord, FeaturesAtStop, FeaturesPreEntry


def test_features_pre_entry_has_no_outcome_or_exit_fields():
    field_names = {f.name for f in dataclasses.fields(FeaturesPreEntry)}
    leaking = {name for name in field_names if "outcome" in name or "exit" in name or "r_multiple" in name}
    assert not leaking, f"FeaturesPreEntry exposes post-entry fields: {leaking}"


def test_event_record_post_stop_outcomes_defaults_to_empty_list():
    # Two independently-constructed records must not share a mutable default list.
    import datetime as dt

    from schema.events import (
        ExitReasonBasis,
        Identification,
        Outcome,
        OriginalOperation,
    )

    def make_record(event_id: str) -> EventRecord:
        identification = Identification(
            event_id=event_id,
            source_path="x",
            source_version="x",
            instrument="EURUSD",
            session_label="9am",
            config_id="d3_c2",
            original_direction="bullish",
        )
        operation = OriginalOperation(
            entry_price=1.1, stop_loss=1.09, take_profit=1.12, risk_price=0.01,
            activation_ts=None, order_placed_ts=None,
            entry_ts=dt.datetime(2026, 1, 1), exit_ts=dt.datetime(2026, 1, 1, 1),
            exit_price=1.09, outcome=Outcome.LOSS, r_multiple=-1.0,
            exit_reason="stop_loss", exit_reason_basis=ExitReasonBasis.INFERRED_BINARY,
            ambiguous_bar=False, gap_filled=False, has_partial_exit=False,
        )
        features_pre_entry = FeaturesPreEntry(
            feeder_ref_available_ts=None, activation_instant_ts=None,
            model1_available_ts=None, order_placed_ts=None,
            time_from_activation_to_order_s=None,
            planned_risk_price=0.01, planned_reward_price=0.02, planned_rr=2.0,
        )
        features_at_stop = FeaturesAtStop(
            exit_ts=operation.exit_ts, exit_price=operation.exit_price,
            outcome=operation.outcome, r_multiple=operation.r_multiple,
            speed_to_stop_s=3600.0, ambiguous_bar=False, gap_filled=False,
        )
        return EventRecord(identification, operation, features_pre_entry, features_at_stop)

    a = make_record("a")
    b = make_record("b")
    a.post_stop_outcomes.append("sentinel")
    assert b.post_stop_outcomes == []
