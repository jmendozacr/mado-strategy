import datetime as dt

from core.candle import Candle, OHLCSeries

from common.trade_timing import compute_trade_timing
from schema.events import (
    EventRecord,
    ExitReasonBasis,
    FeaturesAtStop,
    FeaturesPreEntry,
    Identification,
    Outcome,
    OriginalOperation,
)


def _series(candles) -> OHLCSeries:
    return OHLCSeries(candles=tuple(candles), instrument="EURUSD", timeframe="M15")


def _make_record(entry_ts, exit_ts, outcome=Outcome.LOSS) -> EventRecord:
    identification = Identification(
        event_id="e0", source_path="x", source_version="x", instrument="EURUSD",
        session_label="9am", config_id="d3_c2", original_direction="bullish",
    )
    operation = OriginalOperation(
        entry_price=1.10, stop_loss=1.09, take_profit=1.13, risk_price=0.01,
        activation_ts=entry_ts - dt.timedelta(minutes=30), order_placed_ts=entry_ts,
        entry_ts=entry_ts, exit_ts=exit_ts, exit_price=1.09 if outcome is Outcome.LOSS else 1.13,
        outcome=outcome, r_multiple=-1.0 if outcome is Outcome.LOSS else 2.0,
        exit_reason="stop_loss", exit_reason_basis=ExitReasonBasis.INFERRED_BINARY,
        ambiguous_bar=False, gap_filled=False, has_partial_exit=False,
    )
    features_pre_entry = FeaturesPreEntry(
        feeder_ref_available_ts=None, activation_instant_ts=operation.activation_ts,
        model1_available_ts=None, order_placed_ts=entry_ts, time_from_activation_to_order_s=1800.0,
        planned_risk_price=0.01, planned_reward_price=0.02, planned_rr=2.0,
    )
    features_at_stop = FeaturesAtStop(
        exit_ts=exit_ts, exit_price=operation.exit_price, outcome=outcome, r_multiple=operation.r_multiple,
        speed_to_stop_s=(exit_ts - entry_ts).total_seconds() if exit_ts else None,
        ambiguous_bar=False, gap_filled=False,
    )
    return EventRecord(identification, operation, features_pre_entry, features_at_stop)


def test_same_bar_is_duration_zero():
    entry_ts = dt.datetime(2026, 1, 1, 10, 0)
    record = _make_record(entry_ts, entry_ts)
    series = _series([Candle(entry_ts, open=1.10, high=1.10, low=1.09, close=1.09)])
    timing = compute_trade_timing(record, series)
    assert timing.duration_bars == 0
    assert timing.same_or_next_bar is True


def test_next_bar_is_duration_one():
    entry_ts = dt.datetime(2026, 1, 1, 10, 0)
    exit_ts = entry_ts + dt.timedelta(minutes=15)
    record = _make_record(entry_ts, exit_ts)
    series = _series([
        Candle(entry_ts, open=1.10, high=1.101, low=1.099, close=1.10),
        Candle(exit_ts, open=1.10, high=1.10, low=1.09, close=1.09),
    ])
    timing = compute_trade_timing(record, series)
    assert timing.duration_bars == 1
    assert timing.same_or_next_bar is True


def test_two_bars_later_is_not_same_or_next():
    entry_ts = dt.datetime(2026, 1, 1, 10, 0)
    exit_ts = entry_ts + dt.timedelta(minutes=30)
    record = _make_record(entry_ts, exit_ts)
    series = _series([
        Candle(entry_ts, open=1.10, high=1.101, low=1.099, close=1.10),
        Candle(entry_ts + dt.timedelta(minutes=15), open=1.10, high=1.1005, low=1.0995, close=1.10),
        Candle(exit_ts, open=1.10, high=1.10, low=1.09, close=1.09),
    ])
    timing = compute_trade_timing(record, series)
    assert timing.duration_bars == 2
    assert timing.same_or_next_bar is False


def test_weekend_gap_does_not_shrink_bar_count_duration():
    # Entry Friday, exit the following Monday -- many CALENDAR hours, but
    # if the series has no bars in between, duration_bars still counts
    # correctly off the actual bar INDEX distance, never off wall-clock time.
    entry_ts = dt.datetime(2026, 1, 2, 20, 0)  # Friday
    exit_ts = entry_ts + dt.timedelta(hours=50)  # Monday, big wall-clock gap
    record = _make_record(entry_ts, exit_ts)
    series = _series([
        Candle(entry_ts, open=1.10, high=1.101, low=1.099, close=1.10),
        Candle(entry_ts + dt.timedelta(minutes=15), open=1.10, high=1.1005, low=1.0995, close=1.10),
        Candle(exit_ts, open=1.10, high=1.10, low=1.09, close=1.09),
    ])
    timing = compute_trade_timing(record, series)
    assert timing.duration_bars == 2  # bar-index based, unaffected by the big wall-clock gap
    assert timing.same_or_next_bar is False
    assert timing.duration_s == 50 * 3600  # wall-clock duration is reported separately, never confused with bar count


def test_censored_open_trade_has_no_timing():
    entry_ts = dt.datetime(2026, 1, 1, 10, 0)
    record = _make_record(entry_ts, None, outcome=Outcome.OPEN)
    object.__setattr__(record.operation, "exit_ts", None)
    series = _series([Candle(entry_ts, open=1.10, high=1.10, low=1.10, close=1.10)])
    timing = compute_trade_timing(record, series)
    assert timing.duration_bars is None
    assert timing.same_or_next_bar is None


def test_deterministic():
    entry_ts = dt.datetime(2026, 1, 1, 10, 0)
    exit_ts = entry_ts + dt.timedelta(minutes=30)
    record = _make_record(entry_ts, exit_ts)
    series = _series([
        Candle(entry_ts, open=1.10, high=1.101, low=1.099, close=1.10),
        Candle(entry_ts + dt.timedelta(minutes=15), open=1.10, high=1.1005, low=1.0995, close=1.10),
        Candle(exit_ts, open=1.10, high=1.10, low=1.09, close=1.09),
    ])
    assert compute_trade_timing(record, series) == compute_trade_timing(record, series)
