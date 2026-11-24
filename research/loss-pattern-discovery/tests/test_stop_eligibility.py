import datetime as dt

import pytest

from eligibility.stop_eligibility import StopEligibility, classify, classify_all
from extract.from_causal_lookahead_audit import extract
from schema.events import (
    EventRecord,
    ExitReasonBasis,
    FeaturesAtStop,
    FeaturesPreEntry,
    Identification,
    Outcome,
    OriginalOperation,
)
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _make_loss_record(
    entry_price=1.10,
    stop_loss=1.09,
    take_profit=1.12,
    exit_price=1.09,
    has_partial_exit=False,
    ambiguous_bar=False,
    gap_filled=False,
) -> EventRecord:
    identification = Identification(
        event_id="e1", source_path="x", source_version="x", instrument="EURUSD",
        session_label="9am", config_id="d3_c2", original_direction="bullish",
    )
    operation = OriginalOperation(
        entry_price=entry_price, stop_loss=stop_loss, take_profit=take_profit,
        risk_price=abs(entry_price - stop_loss),
        activation_ts=dt.datetime(2026, 1, 1, 9), order_placed_ts=dt.datetime(2026, 1, 1, 9),
        entry_ts=dt.datetime(2026, 1, 1, 9), exit_ts=dt.datetime(2026, 1, 1, 10),
        exit_price=exit_price, outcome=Outcome.LOSS, r_multiple=-1.0,
        exit_reason="stop_loss", exit_reason_basis=ExitReasonBasis.INFERRED_BINARY,
        ambiguous_bar=ambiguous_bar, gap_filled=gap_filled, has_partial_exit=has_partial_exit,
    )
    features_pre_entry = FeaturesPreEntry(
        feeder_ref_available_ts=None, activation_instant_ts=None, model1_available_ts=None,
        order_placed_ts=None, time_from_activation_to_order_s=None,
        planned_risk_price=operation.risk_price, planned_reward_price=abs(take_profit - entry_price),
        planned_rr=2.0,
    )
    features_at_stop = FeaturesAtStop(
        exit_ts=operation.exit_ts, exit_price=exit_price, outcome=Outcome.LOSS, r_multiple=-1.0,
        speed_to_stop_s=3600.0, ambiguous_bar=ambiguous_bar, gap_filled=gap_filled,
    )
    return EventRecord(identification, operation, features_pre_entry, features_at_stop)


def test_a_loss_is_not_automatically_classified_as_confirmed_stop():
    # exit_price matches neither stop_loss, take_profit, nor entry_price, and
    # gap_filled=False -- the classifier must not assume this was a stop.
    record = _make_loss_record(entry_price=1.10, stop_loss=1.09, take_profit=1.12, exit_price=1.105)
    result = classify(record)
    assert result.category is StopEligibility.OTHER_NEGATIVE_EXIT
    assert result.category is not StopEligibility.CONFIRMED_STOP


def test_confirmed_stop_requires_exit_price_at_the_stop_level():
    record = _make_loss_record(entry_price=1.10, stop_loss=1.09, take_profit=1.12, exit_price=1.09)
    result = classify(record)
    assert result.category is StopEligibility.CONFIRMED_STOP
    assert result.stop_reference_price == pytest.approx(1.09)


def test_partial_exit_preserved_and_referenced_against_entry_price_not_stop_loss():
    # breakeven_after_partial=True for this source: a loss on a partial-exit
    # trade must reference entry_price, not the original stop_loss column.
    record = _make_loss_record(
        entry_price=1.10, stop_loss=1.09, take_profit=1.12, exit_price=1.10, has_partial_exit=True,
    )
    result = classify(record)
    assert result.category is StopEligibility.STOP_AFTER_PARTIAL
    assert result.stop_reference_price == pytest.approx(1.10)  # entry_price, not 1.09


def test_partial_exit_at_original_stop_loss_price_is_not_misclassified_as_confirmed():
    # breakeven_after_partial=True makes leg 2's adverse level entry_price,
    # never the original stop_loss, for every partial-exit trade in this
    # source -- exit_price landing exactly on the ORIGINAL stop_loss on a
    # partial-exit trade does not correspond to any real engine output, so
    # the classifier must refuse to call it Confirmed (it must not silently
    # assume the original stop_loss is still the right reference) rather
    # than mislabel it.
    record = _make_loss_record(
        entry_price=1.10, stop_loss=1.09, take_profit=1.12, exit_price=1.09, has_partial_exit=True,
    )
    result = classify(record)
    assert result.category is not StopEligibility.CONFIRMED_STOP


def test_partial_exit_gap_through_breakeven_still_tagged_stop_after_partial():
    # Price gapped past the moved breakeven level -- still a genuine partial-
    # exit stop, just executed worse than entry_price.
    record = _make_loss_record(
        entry_price=1.10, stop_loss=1.09, take_profit=1.12, exit_price=1.098,
        has_partial_exit=True, gap_filled=True,
    )
    result = classify(record)
    assert result.category is StopEligibility.STOP_AFTER_PARTIAL
    assert result.stop_reference_price == pytest.approx(1.10)


def test_ambiguous_bar_never_promoted_to_confirmed_even_at_exact_stop_price():
    record = _make_loss_record(
        entry_price=1.10, stop_loss=1.09, take_profit=1.12, exit_price=1.09, ambiguous_bar=True,
    )
    result = classify(record)
    assert result.category is StopEligibility.AMBIGUOUS_STOP
    assert result.category is not StopEligibility.CONFIRMED_STOP
    assert result.confidence < 0.98


def test_gap_filled_away_from_stop_level_still_confirmed():
    # Price gapped through the stop; executed worse than the nominal level --
    # still a genuine, confirmed stop execution, not ambiguous or other.
    record = _make_loss_record(
        entry_price=1.10, stop_loss=1.09, take_profit=1.12, exit_price=1.085, gap_filled=True,
    )
    result = classify(record)
    assert result.category is StopEligibility.CONFIRMED_STOP


def test_open_outcome_is_its_own_category_not_a_stop_judgment():
    record = _make_loss_record()
    object.__setattr__(record.operation, "outcome", Outcome.OPEN)
    object.__setattr__(record.operation, "exit_price", None)
    result = classify(record)
    assert result.category is StopEligibility.OPEN_CENSORED


def test_classify_refuses_to_judge_a_win():
    record = _make_loss_record()
    object.__setattr__(record.operation, "outcome", Outcome.WIN)
    object.__setattr__(record.operation, "r_multiple", 1.5)
    with pytest.raises(ValueError):
        classify(record)


def test_real_dataset_eligibility_distribution_is_mostly_confirmed():
    records = extract(REPO_ROOT)
    results = classify_all(records)
    counts = {}
    for r in results.values():
        counts[r.category] = counts.get(r.category, 0) + 1
    total = len(results)
    assert total == 1269  # 1265 losses + 4 open
    # Regression guard, not a tuned threshold: this source's reward
    # structure (breakeven_after_partial) makes confirmed stops the
    # overwhelming majority -- a large drop here would mean either the
    # source changed or this classifier broke, either way worth noticing.
    assert counts.get(StopEligibility.CONFIRMED_STOP, 0) / total > 0.95
    assert counts.get(StopEligibility.OTHER_NEGATIVE_EXIT, 0) == 0
