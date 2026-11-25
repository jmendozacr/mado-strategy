import datetime as dt

from core.candle import Candle, OHLCSeries

from eligibility.stop_eligibility import classify_all
from schema.events import (
    EventRecord,
    ExitReasonBasis,
    FeaturesAtStop,
    FeaturesPreEntry,
    Identification,
    Outcome,
    OriginalOperation,
)
from stats.early_stop_hypothesis import (
    assign_stratum,
    build_primary_population,
    common_support,
    duration_explains_integrity,
    is_confirmed_stop,
    quintile_cutpoints,
    standardized_gap,
    unadjusted_gap,
)


def _series(candles) -> OHLCSeries:
    return OHLCSeries(candles=tuple(candles), instrument="EURUSD", timeframe="M15")


def _make_record(
    event_id, model, outcome, entry_ts, exit_ts=None, exit_price=None, has_partial_exit=False,
    ambiguous_bar=False,
) -> EventRecord:
    exit_ts = exit_ts if exit_ts is not None else (entry_ts + dt.timedelta(hours=1) if outcome is not Outcome.OPEN else None)
    exit_price = exit_price if exit_price is not None else (1.09 if outcome is Outcome.LOSS else (1.13 if outcome is Outcome.WIN else None))
    identification = Identification(
        event_id=event_id, source_path="x", source_version="x", instrument="EURUSD",
        session_label=model, config_id="d3_c2", original_direction="bullish",
    )
    operation = OriginalOperation(
        entry_price=1.10, stop_loss=1.09, take_profit=1.13, risk_price=0.01,
        activation_ts=entry_ts - dt.timedelta(minutes=30), order_placed_ts=entry_ts,
        entry_ts=entry_ts, exit_ts=exit_ts, exit_price=exit_price,
        outcome=outcome, r_multiple=(-1.0 if outcome is Outcome.LOSS else (2.0 if outcome is Outcome.WIN else None)),
        exit_reason=("stop_loss" if outcome is Outcome.LOSS else ("take_profit" if outcome is Outcome.WIN else None)),
        exit_reason_basis=ExitReasonBasis.INFERRED_BINARY,
        ambiguous_bar=ambiguous_bar, gap_filled=False, has_partial_exit=has_partial_exit,
    )
    features_pre_entry = FeaturesPreEntry(
        feeder_ref_available_ts=None, activation_instant_ts=operation.activation_ts,
        model1_available_ts=None, order_placed_ts=entry_ts, time_from_activation_to_order_s=1800.0,
        planned_risk_price=0.01, planned_reward_price=0.02, planned_rr=2.0,
    )
    features_at_stop = FeaturesAtStop(
        exit_ts=exit_ts, exit_price=exit_price, outcome=outcome, r_multiple=operation.r_multiple,
        speed_to_stop_s=(exit_ts - entry_ts).total_seconds() if exit_ts else None,
        ambiguous_bar=ambiguous_bar, gap_filled=False,
    )
    return EventRecord(identification, operation, features_pre_entry, features_at_stop)


def test_is_confirmed_stop_excludes_wins_and_ambiguous():
    entry_ts = dt.datetime(2026, 1, 1, 10, 0)
    win = _make_record("w0", "9am", Outcome.WIN, entry_ts)
    loss = _make_record("l0", "9am", Outcome.LOSS, entry_ts, exit_price=1.09)
    ambiguous = _make_record("a0", "9am", Outcome.LOSS, entry_ts, exit_price=1.09, ambiguous_bar=True)
    eligibility = classify_all([win, loss, ambiguous])
    assert is_confirmed_stop("w0", eligibility) is False
    assert is_confirmed_stop("l0", eligibility) is True
    assert is_confirmed_stop("a0", eligibility) is False


def test_partial_exit_win_not_flagged_as_confirmed_stop():
    entry_ts = dt.datetime(2026, 1, 1, 10, 0)
    win_with_partial = _make_record("w0", "9am", Outcome.WIN, entry_ts, has_partial_exit=True)
    eligibility = classify_all([win_with_partial])
    assert is_confirmed_stop("w0", eligibility) is False


def test_build_primary_population_excludes_open_only():
    entry_ts = dt.datetime(2026, 1, 1, 10, 0)
    win = _make_record("w0", "9am", Outcome.WIN, entry_ts)
    loss = _make_record("l0", "9am", Outcome.LOSS, entry_ts)
    open_trade = _make_record("o0", "9am", Outcome.OPEN, entry_ts)
    population = build_primary_population([win, loss, open_trade])
    ids = {r.identification.event_id for r in population}
    assert ids == {"w0", "l0"}
    assert "o0" not in ids  # open/censored excluded, never treated as a loss


def test_quintile_cutpoints_and_assign_stratum():
    values = list(range(1, 101))  # 1..100
    cutpoints = quintile_cutpoints([float(v) for v in values])
    assert len(cutpoints) == 4
    assert assign_stratum(1.0, cutpoints) == 0
    assert assign_stratum(100.0, cutpoints) == 4
    # monotonic: a higher value never lands in a lower stratum
    assert assign_stratum(20.0, cutpoints) <= assign_stratum(80.0, cutpoints)


def test_common_support_flags_insufficient_strata_and_reports_share():
    entry_ts = dt.datetime(2026, 1, 1, 10, 0)
    recs_1am = [_make_record(f"a{i}", "1am", Outcome.LOSS, entry_ts) for i in range(5)]  # too few
    recs_9am = [_make_record(f"b{i}", "9am", Outcome.LOSS, entry_ts) for i in range(25)]  # enough
    strata_by_id = {r.identification.event_id: 0 for r in recs_1am + recs_9am}
    support = common_support({"1am": recs_1am, "9am": recs_9am}, strata_by_id)
    assert support["by_stratum"][0]["sufficient_common_support"] is False
    assert support["unsupported_share_1am"] == 1.0
    assert support["unsupported_share_9am"] == 1.0  # stratum 0 is the ONLY stratum, and it's unsupported for both


def test_standardized_gap_excludes_unsupported_strata_and_is_deterministic():
    entry_ts = dt.datetime(2026, 1, 1, 10, 0)
    recs_1am = [_make_record(f"a{i}", "1am", Outcome.LOSS, entry_ts) for i in range(25)]
    recs_9am = [_make_record(f"b{i}", "9am", Outcome.LOSS, entry_ts) for i in range(25)]
    strata_by_id = {r.identification.event_id: 0 for r in recs_1am + recs_9am}
    flags_by_id = {r.identification.event_id: True for r in recs_1am + recs_9am}
    records_by_model = {"1am": recs_1am, "9am": recs_9am}
    support = common_support(records_by_model, strata_by_id)

    result_a = standardized_gap(records_by_model, flags_by_id, strata_by_id, support)
    result_b = standardized_gap(records_by_model, flags_by_id, strata_by_id, support)
    assert result_a == result_b
    assert result_a["standardized_rate_1am"] == 1.0
    assert result_a["diff_1am_minus_9am"] == 0.0


def test_unadjusted_gap_is_deterministic_and_matches_point_estimate():
    entry_ts = dt.datetime(2026, 1, 1, 10, 0)
    recs_1am = [_make_record(f"a{i}", "1am", Outcome.LOSS, entry_ts) for i in range(10)]
    recs_9am = [_make_record(f"b{i}", "9am", Outcome.LOSS, entry_ts) for i in range(10)]
    flags_by_id = {r.identification.event_id: (i < 5) for i, r in enumerate(recs_1am)}
    flags_by_id.update({r.identification.event_id: False for r in recs_9am})
    result_a = unadjusted_gap({"1am": recs_1am, "9am": recs_9am}, flags_by_id)
    result_b = unadjusted_gap({"1am": recs_1am, "9am": recs_9am}, flags_by_id)
    assert result_a == result_b
    assert result_a["rate_1am"] == 0.5
    assert result_a["rate_9am"] == 0.0
    assert result_a["diff_1am_minus_9am"] == 0.5


def test_duration_explains_integrity_zero_mismatches_by_construction():
    entry_ts = dt.datetime(2026, 1, 1, 10, 0)
    same_bar = _make_record("s0", "9am", Outcome.LOSS, entry_ts, exit_ts=entry_ts, exit_price=1.09)
    adjacent = _make_record(
        "s1", "9am", Outcome.LOSS, entry_ts, exit_ts=entry_ts + dt.timedelta(minutes=15), exit_price=1.09,
    )
    later = _make_record(
        "s2", "9am", Outcome.LOSS, entry_ts, exit_ts=entry_ts + dt.timedelta(minutes=45), exit_price=1.09,
    )
    series = _series([
        Candle(entry_ts, open=1.10, high=1.101, low=1.089, close=1.09),
        Candle(entry_ts + dt.timedelta(minutes=15), open=1.09, high=1.095, low=1.085, close=1.09),
        Candle(entry_ts + dt.timedelta(minutes=30), open=1.09, high=1.095, low=1.085, close=1.09),
        Candle(entry_ts + dt.timedelta(minutes=45), open=1.09, high=1.09, low=1.08, close=1.09),
    ])
    series_by_instrument = {"EURUSD": series}
    result = duration_explains_integrity([same_bar, adjacent, later], series_by_instrument)
    assert result["n_mismatches"] == 0
    assert result["n_checked"] == 3
