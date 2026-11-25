import datetime as dt

from core.candle import Candle, OHLCSeries

from eligibility.stop_eligibility import classify_all
from eligibility.stop_timing_decomposition import TimingCategory, classify_all_timing, classify_timing
from schema.events import (
    EventRecord,
    ExitReasonBasis,
    FeaturesAtStop,
    FeaturesPreEntry,
    Identification,
    Outcome,
    OriginalOperation,
)
from stats.stop_timing_decomposition import build_decomposition_table, gap_decomposition, verify_decomposition_identity


def _series(candles) -> OHLCSeries:
    return OHLCSeries(candles=tuple(candles), instrument="EURUSD", timeframe="M15")


def _record(
    event_id, entry_ts, exit_ts, outcome=Outcome.LOSS, model="9am", direction="bullish",
    entry_price=1.10, stop_loss=1.09, exit_price=None, ambiguous_bar=False, gap_filled=False,
    instrument="EURUSD",
):
    if exit_price is None:
        exit_price = stop_loss if outcome is Outcome.LOSS else 1.13
    identification = Identification(
        event_id=event_id, source_path="x", source_version="x", instrument=instrument,
        session_label=model, config_id="d3_c2", original_direction=direction,
    )
    operation = OriginalOperation(
        entry_price=entry_price, stop_loss=stop_loss, take_profit=1.13, risk_price=abs(entry_price - stop_loss),
        activation_ts=entry_ts - dt.timedelta(minutes=30) if entry_ts else None,
        order_placed_ts=entry_ts, entry_ts=entry_ts, exit_ts=exit_ts, exit_price=exit_price,
        outcome=outcome, r_multiple=-1.0 if outcome is Outcome.LOSS else (2.0 if outcome is Outcome.WIN else None),
        exit_reason="stop_loss" if outcome is Outcome.LOSS else None, exit_reason_basis=ExitReasonBasis.INFERRED_BINARY,
        ambiguous_bar=ambiguous_bar, gap_filled=gap_filled, has_partial_exit=False,
    )
    features_pre_entry = FeaturesPreEntry(
        feeder_ref_available_ts=None, activation_instant_ts=operation.activation_ts,
        model1_available_ts=None, order_placed_ts=entry_ts, time_from_activation_to_order_s=1800.0,
        planned_risk_price=operation.risk_price, planned_reward_price=0.03, planned_rr=2.0,
    )
    features_at_stop = FeaturesAtStop(
        exit_ts=exit_ts, exit_price=exit_price, outcome=outcome, r_multiple=operation.r_multiple,
        speed_to_stop_s=(exit_ts - entry_ts).total_seconds() if (exit_ts and entry_ts) else None,
        ambiguous_bar=ambiguous_bar, gap_filled=gap_filled,
    )
    return EventRecord(identification, operation, features_pre_entry, features_at_stop)


def test_same_bar_confirmed_stop_is_e0():
    ts = dt.datetime(2026, 1, 1, 10, 0)
    record = _record("e0", ts, ts)
    series = _series([Candle(ts, open=1.095, high=1.095, low=1.08, close=1.08)])
    eligibility = classify_all([record])
    classification = classify_timing(record, series, eligibility)
    assert classification.category is TimingCategory.SAME_BAR_SL
    assert classification.duration_bars == 0


def test_next_bar_confirmed_stop_is_e1():
    entry_ts = dt.datetime(2026, 1, 1, 10, 0)
    exit_ts = entry_ts + dt.timedelta(minutes=15)
    record = _record("e1", entry_ts, exit_ts)
    series = _series([
        Candle(entry_ts, open=1.11, high=1.111, low=1.10, close=1.105),
        Candle(exit_ts, open=1.10, high=1.10, low=1.09, close=1.09),
    ])
    eligibility = classify_all([record])
    classification = classify_timing(record, series, eligibility)
    assert classification.category is TimingCategory.NEXT_BAR_SL
    assert classification.duration_bars == 1


def test_later_bar_confirmed_stop_is_e2():
    entry_ts = dt.datetime(2026, 1, 1, 10, 0)
    exit_ts = entry_ts + dt.timedelta(minutes=30)
    record = _record("e2", entry_ts, exit_ts)
    series = _series([
        Candle(entry_ts, open=1.11, high=1.111, low=1.10, close=1.105),
        Candle(entry_ts + dt.timedelta(minutes=15), open=1.105, high=1.106, low=1.10, close=1.10),
        Candle(exit_ts, open=1.10, high=1.10, low=1.09, close=1.09),
    ])
    eligibility = classify_all([record])
    classification = classify_timing(record, series, eligibility)
    assert classification.category is TimingCategory.LATER_SL
    assert classification.duration_bars == 2


def test_win_is_other_exit_never_a_stop_category():
    ts = dt.datetime(2026, 1, 1, 10, 0)
    record = _record("win1", ts, ts + dt.timedelta(minutes=15), outcome=Outcome.WIN, exit_price=1.13)
    series = _series([
        Candle(ts, open=1.10, high=1.101, low=1.099, close=1.10),
        Candle(ts + dt.timedelta(minutes=15), open=1.12, high=1.13, low=1.12, close=1.13),
    ])
    eligibility = classify_all([record])
    classification = classify_timing(record, series, eligibility)
    assert classification.category is TimingCategory.OTHER_EXIT
    assert classification.duration_bars is None


def test_ambiguous_bar_loss_never_promoted_to_a_stop_category():
    # ambiguous_bar=True routes to AMBIGUOUS_STOP in stop_eligibility -- this
    # module must never override that with a same/next/later-bar label.
    ts = dt.datetime(2026, 1, 1, 10, 0)
    record = _record("amb1", ts, ts, ambiguous_bar=True)
    series = _series([Candle(ts, open=1.095, high=1.14, low=1.08, close=1.09)])
    eligibility = classify_all([record])
    classification = classify_timing(record, series, eligibility)
    assert classification.category is TimingCategory.OTHER_EXIT


def test_open_is_censored_with_no_duration():
    ts = dt.datetime(2026, 1, 1, 10, 0)
    record = _record("open1", ts, None, outcome=Outcome.OPEN, exit_price=None)
    series = _series([Candle(ts, open=1.10, high=1.10, low=1.10, close=1.10)])
    eligibility = classify_all([record])
    classification = classify_timing(record, series, eligibility)
    assert classification.category is TimingCategory.OPEN_CENSORED
    assert classification.duration_bars is None


def test_classify_all_timing_is_deterministic():
    ts = dt.datetime(2026, 1, 1, 10, 0)
    record = _record("det1", ts, ts)
    series_by_instrument = {"EURUSD": _series([Candle(ts, open=1.095, high=1.095, low=1.08, close=1.08)])}
    first = classify_all_timing([record], series_by_instrument)
    second = classify_all_timing([record], series_by_instrument)
    assert first == second


def _build_scenario():
    """4 events per model: one E0, one E1, one win, one ambiguous -- enough
    to exercise the full decomposition table and the gap identity with a
    non-degenerate denominator."""
    ts = dt.datetime(2026, 1, 1, 10, 0)
    records = []
    for model, n_e0 in (("1am", 2), ("9am", 1)):
        records.append(_record(f"{model}-e0-1", ts, ts, model=model))
        if n_e0 > 1:
            records.append(_record(f"{model}-e0-2", ts, ts, model=model))
        records.append(_record(
            f"{model}-e1", ts, ts + dt.timedelta(minutes=15), model=model,
        ))
        records.append(_record(f"{model}-win", ts, ts, outcome=Outcome.WIN, model=model, exit_price=1.13))
    series_by_instrument = {"EURUSD": _series([
        Candle(ts, open=1.095, high=1.111, low=1.08, close=1.09),
        Candle(ts + dt.timedelta(minutes=15), open=1.10, high=1.10, low=1.09, close=1.09),
    ])}
    return records, series_by_instrument


def test_decomposition_table_denominators_are_consistent_across_categories():
    records, series_by_instrument = _build_scenario()
    table = build_decomposition_table(records, series_by_instrument)
    for model, row in table["by_model"].items():
        category_sum = sum(row[c.value] for c in TimingCategory)
        assert category_sum == row["n_total"]


def test_decomposition_identity_e0_plus_e1_equals_combined_rate():
    records, series_by_instrument = _build_scenario()
    table = build_decomposition_table(records, series_by_instrument)
    identity = verify_decomposition_identity(table)
    for model_result in identity.values():
        assert model_result["identity_holds"]


def test_gap_decomposition_sum_of_parts_matches_combined_gap():
    records, series_by_instrument = _build_scenario()
    from eligibility.stop_timing_decomposition import classify_all_timing as _cat
    timing_by_id = _cat(records, series_by_instrument)
    eligibility = classify_all(records)
    result = gap_decomposition(records, eligibility, timing_by_id)
    assert result["sum_of_parts_matches_combined"]
