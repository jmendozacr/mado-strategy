import datetime as dt

from core.candle import Candle, OHLCSeries

from behavior.post_stop_metrics import compute_post_stop_behavior
from behavior.recovery_analysis import (
    RELEVANT_DIFFERENCE_PP,
    _quantiles,
    analyze_recovery,
    recovery_control_to_event_record,
)
from control.sampling import ControlEvent, MatchTier, sample_controls
from schema.events import (
    EventRecord,
    ExitReasonBasis,
    FeaturesAtStop,
    FeaturesPreEntry,
    Identification,
    Outcome,
    OriginalOperation,
)
from stats.bootstrap import block_bootstrap_paired_diff_ci


def _proportion(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def test_quantiles_helper_basic():
    q = _quantiles([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    assert q[0.5] in (5, 6)
    assert _quantiles([]) == {q: None for q in (0.1, 0.25, 0.5, 0.75, 0.9)}


def test_relevant_difference_requires_both_ci_exclusion_and_magnitude():
    # CI excludes zero but magnitude is tiny (< 5pp) -- not "relevant".
    tiny_pairs = [(0.52, 0.50, ("EURUSD", 2021, i)) for i in range(200)]
    result = block_bootstrap_paired_diff_ci(tiny_pairs, statistic=_proportion, ci=0.95)
    relevant = (
        result["ci_low"] is not None and (result["ci_low"] > 0 or result["ci_high"] < 0)
        and abs(result["point_estimate"]) >= RELEVANT_DIFFERENCE_PP
    )
    assert abs(result["point_estimate"] - 0.02) < 1e-9
    assert relevant is False  # magnitude below the 5pp bar


def test_relevant_difference_true_for_a_clear_large_gap():
    large_pairs = [(0.80, 0.50, ("EURUSD", 2021, i)) for i in range(200)]
    result = block_bootstrap_paired_diff_ci(large_pairs, statistic=_proportion, ci=0.95)
    relevant = (
        result["ci_low"] is not None and (result["ci_low"] > 0 or result["ci_high"] < 0)
        and abs(result["point_estimate"]) >= RELEVANT_DIFFERENCE_PP
    )
    assert relevant is True


def _synthetic_series(instrument: str, start: dt.datetime, n_bars: int) -> OHLCSeries:
    candles = [
        Candle(start + dt.timedelta(minutes=15 * i), open=1.10, high=1.1005, low=1.0995, close=1.10)
        for i in range(n_bars)
    ]
    return OHLCSeries(candles=tuple(candles), instrument=instrument, timeframe="M15")


def _make_record(event_id, exit_ts, entry_price=1.11, exit_price=1.10) -> EventRecord:
    identification = Identification(
        event_id=event_id, source_path="x", source_version="x", instrument="EURUSD",
        session_label="9am", config_id="d3_c2", original_direction="bullish",
    )
    operation = OriginalOperation(
        entry_price=entry_price, stop_loss=exit_price, take_profit=1.13, risk_price=abs(entry_price - exit_price),
        activation_ts=None, order_placed_ts=None,
        entry_ts=exit_ts - dt.timedelta(hours=1), exit_ts=exit_ts,
        exit_price=exit_price, outcome=Outcome.LOSS, r_multiple=-1.0,
        exit_reason="stop_loss", exit_reason_basis=ExitReasonBasis.INFERRED_BINARY,
        ambiguous_bar=False, gap_filled=False, has_partial_exit=False,
    )
    features_pre_entry = FeaturesPreEntry(
        feeder_ref_available_ts=None, activation_instant_ts=None, model1_available_ts=None,
        order_placed_ts=None, time_from_activation_to_order_s=None,
        planned_risk_price=operation.risk_price, planned_reward_price=0.02, planned_rr=2.0,
    )
    features_at_stop = FeaturesAtStop(
        exit_ts=exit_ts, exit_price=exit_price, outcome=Outcome.LOSS, r_multiple=-1.0,
        speed_to_stop_s=3600.0, ambiguous_bar=False, gap_filled=False,
    )
    return EventRecord(identification, operation, features_pre_entry, features_at_stop)


def test_recovery_control_record_uses_target_distance_not_risk_price():
    start = dt.datetime(2021, 1, 4, 0, 0)
    series = _synthetic_series("EURUSD", start, 5000)
    control = ControlEvent(
        control_id="control:e0", matched_event_id="e0", instrument="EURUSD", origin_model="9am",
        direction="bullish", period_bucket="2021-2023", control_ts=start + dt.timedelta(hours=100),
        risk_price=0.01, target_distance=0.015, atr_at_control=0.001, atr_at_matched_event=0.001,
        actual_stop_time_ny=4.0, control_reference_time_ny=4.0, match_tier=MatchTier.MATCHED,
    )
    record = recovery_control_to_event_record(control, series)
    assert abs(record.operation.entry_price - record.operation.exit_price) - 0.015 < 1e-9
    assert record.operation.risk_price == 0.015  # uses target_distance, not the control's own risk_price (0.01)


def test_analyze_recovery_end_to_end_smoke():
    start = dt.datetime(2021, 1, 4, 9, 0)
    weeks = 12
    series = {"EURUSD": _synthetic_series("EURUSD", start, weeks * 7 * 24 * 4)}
    eligible = [_make_record(f"e{i}", start + dt.timedelta(hours=37 * i)) for i in range(10)]
    eligible_behaviors = {
        r.identification.event_id: compute_post_stop_behavior(r, series["EURUSD"]) for r in eligible
    }
    sampling_result = sample_controls(eligible, series, seed=1, pool_size=30)

    result = analyze_recovery(eligible, eligible_behaviors, sampling_result.controls, series)
    assert "ci_low" in result.primary_endpoint
    assert set(result.secondary_by_horizon.keys()) == {"1h", "4h", "1d", "3d"}
    assert result.n_censored_by_3d >= 0
    assert "EURUSD" in result.by_instrument
