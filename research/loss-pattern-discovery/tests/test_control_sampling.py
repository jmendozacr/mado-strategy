import datetime as dt

from core.candle import Candle, OHLCSeries

from control.sampling import (
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


def _make_real_event(event_id: str, instrument: str, exit_ts: dt.datetime, direction="bullish") -> EventRecord:
    identification = Identification(
        event_id=event_id, source_path="x", source_version="x", instrument=instrument,
        session_label="9am", config_id="d3_c2", original_direction=direction,
    )
    operation = OriginalOperation(
        entry_price=1.11, stop_loss=1.10, take_profit=1.13, risk_price=0.01,
        activation_ts=None, order_placed_ts=None,
        entry_ts=exit_ts - dt.timedelta(hours=1), exit_ts=exit_ts,
        exit_price=1.10, outcome=Outcome.LOSS, r_multiple=-1.0,
        exit_reason="stop_loss", exit_reason_basis=ExitReasonBasis.INFERRED_BINARY,
        ambiguous_bar=False, gap_filled=False, has_partial_exit=False,
    )
    features_pre_entry = FeaturesPreEntry(
        feeder_ref_available_ts=None, activation_instant_ts=None, model1_available_ts=None,
        order_placed_ts=None, time_from_activation_to_order_s=None,
        planned_risk_price=0.01, planned_reward_price=0.02, planned_rr=2.0,
    )
    features_at_stop = FeaturesAtStop(
        exit_ts=exit_ts, exit_price=1.10, outcome=Outcome.LOSS, r_multiple=-1.0,
        speed_to_stop_s=3600.0, ambiguous_bar=False, gap_filled=False,
    )
    return EventRecord(identification, operation, features_pre_entry, features_at_stop)


def test_period_bucket_assignment():
    assert period_bucket(dt.datetime(2016, 5, 1)) == "2015-2017"
    assert period_bucket(dt.datetime(2022, 5, 1)) == "2021-2023"
    assert period_bucket(dt.datetime(2030, 1, 1)) is None


def test_sampling_is_deterministic_for_a_fixed_seed():
    start = dt.datetime(2021, 1, 4, 0, 0)
    series = {"EURUSD": _synthetic_series("EURUSD", start, 2000)}
    events = [_make_real_event(f"e{i}", "EURUSD", start + dt.timedelta(hours=100 + i)) for i in range(5)]

    controls_a = sample_controls(events, series, seed=42, pool_size=30)
    controls_b = sample_controls(events, series, seed=42, pool_size=30)
    assert [c.control_ts for c in controls_a] == [c.control_ts for c in controls_b]


def test_different_seeds_can_produce_different_controls():
    start = dt.datetime(2021, 1, 4, 0, 0)
    series = {"EURUSD": _synthetic_series("EURUSD", start, 2000)}
    events = [_make_real_event(f"e{i}", "EURUSD", start + dt.timedelta(hours=100 + i)) for i in range(5)]

    controls_a = sample_controls(events, series, seed=1, pool_size=30)
    controls_b = sample_controls(events, series, seed=2, pool_size=30)
    assert [c.control_ts for c in controls_a] != [c.control_ts for c in controls_b]


def test_controls_respect_the_exclusion_buffer_around_real_events():
    start = dt.datetime(2021, 1, 4, 0, 0)
    series = {"EURUSD": _synthetic_series("EURUSD", start, 2000)}
    events = [_make_real_event("e0", "EURUSD", start + dt.timedelta(hours=100))]

    controls = sample_controls(events, series, seed=7, pool_size=50)
    for control in controls:
        for event in events:
            assert abs(control.control_ts - event.operation.exit_ts) >= dt.timedelta(hours=4)


def test_controls_do_not_silently_duplicate_the_same_timestamp_when_pool_is_large_enough():
    start = dt.datetime(2021, 1, 4, 0, 0)
    series = {"EURUSD": _synthetic_series("EURUSD", start, 5000)}
    events = [_make_real_event(f"e{i}", "EURUSD", start + dt.timedelta(hours=50 * i)) for i in range(10)]

    controls = sample_controls(events, series, seed=3, pool_size=100)
    timestamps = [c.control_ts for c in controls]
    assert len(timestamps) == len(set(timestamps))


def test_control_to_event_record_only_uses_pre_control_information():
    start = dt.datetime(2021, 1, 4, 0, 0)
    series = _synthetic_series("EURUSD", start, 2000)
    events = [_make_real_event("e0", "EURUSD", start + dt.timedelta(hours=100))]
    controls = sample_controls(events, {"EURUSD": series}, seed=5, pool_size=30)
    assert controls  # sanity: at least one control was produced
    record = control_to_event_record(controls[0], series)
    assert record.operation.exit_ts == controls[0].control_ts
    assert record.operation.risk_price == controls[0].risk_price
