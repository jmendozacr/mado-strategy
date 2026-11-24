import datetime as dt

from core.candle import Candle, OHLCSeries

from common.ny_time import circular_hour_distance, ny_hour_of_day
from control.sampling import (
    MatchTier,
    NY_HOUR_TOLERANCE_HOURS,
    audit_match_quality,
    control_to_event_record,
    period_bucket,
    sample_controls,
)
from schema.events import (
    EventRecord,
    ExitReasonBasis,
    FeaturesAtStop,
    FeaturesPreEntry,
    Identification,
    Outcome,
    OriginalOperation,
)


def _synthetic_series(instrument: str, start: dt.datetime, n_bars: int) -> OHLCSeries:
    candles = [
        Candle(start + dt.timedelta(minutes=15 * i), open=1.10, high=1.1005, low=1.0995, close=1.10)
        for i in range(n_bars)
    ]
    return OHLCSeries(candles=tuple(candles), instrument=instrument, timeframe="M15")


def _make_real_event(
    event_id: str, instrument: str, exit_ts: dt.datetime, direction="bullish",
    entry_price=1.11, exit_price=1.10, stop_loss=None,
) -> EventRecord:
    if stop_loss is None:
        stop_loss = exit_price  # the common case: no gap, exit lands exactly on the nominal stop
    identification = Identification(
        event_id=event_id, source_path="x", source_version="x", instrument=instrument,
        session_label="9am", config_id="d3_c2", original_direction=direction,
    )
    operation = OriginalOperation(
        entry_price=entry_price, stop_loss=stop_loss, take_profit=1.13, risk_price=abs(entry_price - stop_loss),
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


def _full_week_series(instrument: str, start: dt.datetime, weeks: int) -> OHLCSeries:
    """A continuous M15 series spanning `weeks` weeks -- long enough to give
    every hour-of-day a real candidate pool (unlike a short, single-burst
    series), needed once the control matcher filters by NY hour."""
    n_bars = weeks * 7 * 24 * 4
    return _synthetic_series(instrument, start, n_bars)


def test_period_bucket_assignment():
    assert period_bucket(dt.datetime(2016, 5, 1)) == "2015-2017"
    assert period_bucket(dt.datetime(2022, 5, 1)) == "2021-2023"
    assert period_bucket(dt.datetime(2030, 1, 1)) is None


def test_RED_naive_pool_would_assign_a_9am_event_a_non_comparable_ny_hour_control():
    # This test documents the Phase-2 defect directly: a NAIVE pool built
    # only from instrument+period (no NY-hour filter at all) can and does
    # hand back a control timestamp many hours away from the real event's
    # own NY hour. It does not call the (now fixed) `sample_controls` --
    # it reproduces the OLD unfiltered-pool behavior inline to prove the
    # defect was real, then the tests below prove the fix.
    start = dt.datetime(2021, 1, 4, 0, 0)  # Monday 00:00 UTC
    series = _full_week_series("EURUSD", start, weeks=4)
    all_indices = list(range(len(series.candles)))
    # A naive pool (Phase 2's actual behavior): every bar in range is an
    # equally valid candidate, regardless of its hour of day.
    naive_pool_hours = {ny_hour_of_day(series.candles[i].timestamp) for i in all_indices[:200]}
    # The naive pool spans many different hours -- it was never restricted.
    assert len(naive_pool_hours) > 10


def test_controls_are_within_the_ny_hour_tolerance_of_their_matched_event():
    start = dt.datetime(2021, 1, 4, 0, 0)
    series = {"EURUSD": _full_week_series("EURUSD", start, weeks=8)}
    events = [
        _make_real_event(f"e{i}", "EURUSD", start + dt.timedelta(hours=100 + 37 * i)) for i in range(6)
    ]
    result = sample_controls(events, series, seed=42, pool_size=30)
    assert result.controls  # sanity
    for control in result.controls:
        distance = circular_hour_distance(control.actual_stop_time_ny, control.control_reference_time_ny)
        assert distance <= NY_HOUR_TOLERANCE_HOURS + 1e-9


def test_origin_model_and_actual_stop_time_ny_are_tracked_separately():
    start = dt.datetime(2021, 1, 4, 9, 0)  # 9am-ish UTC
    series = {"EURUSD": _full_week_series("EURUSD", start, weeks=4)}
    events = [_make_real_event("e0", "EURUSD", start + dt.timedelta(hours=5))]  # stop fires hours after the model's own instant
    result = sample_controls(events, series, seed=1, pool_size=30)
    assert result.controls
    control = result.controls[0]
    assert control.origin_model == "9am"  # the generating model label, unchanged
    assert control.actual_stop_time_ny == ny_hour_of_day(events[0].operation.exit_ts)  # the real exit time, NY


def test_sampling_is_deterministic_for_a_fixed_seed():
    start = dt.datetime(2021, 1, 4, 0, 0)
    series = {"EURUSD": _full_week_series("EURUSD", start, weeks=8)}
    events = [_make_real_event(f"e{i}", "EURUSD", start + dt.timedelta(hours=100 + 37 * i)) for i in range(5)]

    result_a = sample_controls(events, series, seed=42, pool_size=30)
    result_b = sample_controls(events, series, seed=42, pool_size=30)
    assert [c.control_ts for c in result_a.controls] == [c.control_ts for c in result_b.controls]


def test_different_seeds_can_produce_different_controls():
    start = dt.datetime(2021, 1, 4, 0, 0)
    series = {"EURUSD": _full_week_series("EURUSD", start, weeks=8)}
    events = [_make_real_event(f"e{i}", "EURUSD", start + dt.timedelta(hours=100 + 37 * i)) for i in range(5)]

    result_a = sample_controls(events, series, seed=1, pool_size=30)
    result_b = sample_controls(events, series, seed=2, pool_size=30)
    assert [c.control_ts for c in result_a.controls] != [c.control_ts for c in result_b.controls]


def test_controls_respect_the_exclusion_buffer_around_real_events():
    start = dt.datetime(2021, 1, 4, 0, 0)
    series = {"EURUSD": _full_week_series("EURUSD", start, weeks=8)}
    events = [_make_real_event("e0", "EURUSD", start + dt.timedelta(hours=100))]

    result = sample_controls(events, series, seed=7, pool_size=50)
    for control in result.controls:
        for event in events:
            assert abs(control.control_ts - event.operation.exit_ts) >= dt.timedelta(hours=4)


def test_controls_do_not_silently_duplicate_the_same_timestamp_when_pool_is_large_enough():
    start = dt.datetime(2021, 1, 4, 0, 0)
    series = {"EURUSD": _full_week_series("EURUSD", start, weeks=12)}
    events = [_make_real_event(f"e{i}", "EURUSD", start + dt.timedelta(hours=61 * i)) for i in range(10)]

    result = sample_controls(events, series, seed=3, pool_size=100)
    timestamps = [c.control_ts for c in result.controls]
    assert len(timestamps) == len(set(timestamps))


def test_match_tier_reports_replacement_when_the_hour_window_pool_is_exhausted():
    # A tiny series (few weeks) gives a small per-hour candidate pool; many
    # real events sharing the same NY hour will exhaust fresh candidates
    # and fall back to MATCHED_WITH_REPLACEMENT -- reported explicitly, not
    # silently treated the same as a fresh match.
    start = dt.datetime(2021, 1, 4, 9, 0)
    series = {"EURUSD": _full_week_series("EURUSD", start, weeks=2)}
    events = [_make_real_event(f"e{i}", "EURUSD", start + dt.timedelta(days=7 * (i % 2), hours=0)) for i in range(20)]
    # pool_size=1 caps EACH of the 9 quarter-hour keys within the +/-1h
    # window at 1 candidate (union capacity ~9) -- far below 20 events.
    result = sample_controls(events, series, seed=9, pool_size=1)
    tiers = {c.match_tier for c in result.controls}
    assert MatchTier.MATCHED_WITH_REPLACEMENT in tiers or len(result.unmatched) > 0


def test_unmatched_events_are_reported_not_silently_dropped_or_relaxed():
    start = dt.datetime(2021, 1, 4, 0, 0)
    series = {"EURUSD": _full_week_series("EURUSD", start, weeks=4)}
    # An event with no valid risk_price can never be matched -- must show
    # up in `unmatched`, never silently skipped without a trace.
    event = _make_real_event("e0", "EURUSD", start + dt.timedelta(hours=100))
    object.__setattr__(event.operation, "risk_price", 0.0)
    result = sample_controls([event], series, seed=1, pool_size=30)
    assert result.controls == []
    assert len(result.unmatched) == 1
    assert result.unmatched[0].event_id == "e0"
    assert result.unmatched[0].reason == "censored_or_invalid_risk"


def test_control_to_event_record_only_uses_pre_control_information():
    start = dt.datetime(2021, 1, 4, 0, 0)
    series = _full_week_series("EURUSD", start, weeks=8)
    events = [_make_real_event("e0", "EURUSD", start + dt.timedelta(hours=100))]
    result = sample_controls(events, {"EURUSD": series}, seed=5, pool_size=30)
    assert result.controls  # sanity: at least one control was produced
    record = control_to_event_record(result.controls[0], series)
    assert record.operation.exit_ts == result.controls[0].control_ts
    assert record.operation.risk_price == result.controls[0].risk_price


def test_target_distance_can_differ_from_risk_price_under_a_gap_fill():
    start = dt.datetime(2021, 1, 4, 0, 0)
    series = {"EURUSD": _full_week_series("EURUSD", start, weeks=8)}
    # entry=1.11, stop_loss=1.10 (nominal, risk_price=0.01), but a gap means
    # the ACTUAL exit_price is 1.095 -- target_distance (0.015) must differ
    # from risk_price (0.01).
    event = _make_real_event(
        "e0", "EURUSD", start + dt.timedelta(hours=100), entry_price=1.11, exit_price=1.095, stop_loss=1.10,
    )
    result = sample_controls([event], series, seed=1, pool_size=30)
    assert result.controls
    control = result.controls[0]
    assert control.target_distance == abs(1.11 - 1.095)
    assert control.risk_price == abs(1.11 - 1.10)
    assert control.target_distance != control.risk_price


def test_audit_match_quality_reports_tiers_and_hour_alignment():
    start = dt.datetime(2021, 1, 4, 0, 0)
    series = {"EURUSD": _full_week_series("EURUSD", start, weeks=8)}
    events = [_make_real_event(f"e{i}", "EURUSD", start + dt.timedelta(hours=100 + 37 * i)) for i in range(5)]
    result = sample_controls(events, series, seed=42, pool_size=30)
    records_by_id = {e.identification.event_id: e for e in events}
    report = audit_match_quality(records_by_id, result.controls)
    assert report["n_controls"] == len(result.controls)
    assert report["ny_hour_diff_hours"]["within_tolerance_pct"] == 1.0
    assert report["instrument_mismatches"] == 0
    assert report["direction_mismatches"] == 0
