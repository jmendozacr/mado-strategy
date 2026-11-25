import datetime as dt

from core.candle import Candle, OHLCSeries

from features.pre_entry_features import compute_pre_entry_features
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


def _history(entry_ts: dt.datetime, n: int = 20) -> list[Candle]:
    return [
        Candle(entry_ts - dt.timedelta(minutes=15 * (n - i)), open=1.10 + 0.0001 * i,
               high=1.1005 + 0.0001 * i, low=1.0995 + 0.0001 * i, close=1.1002 + 0.0001 * i)
        for i in range(n)
    ]


def _make_record(event_id, outcome, entry_ts, risk_price=0.01) -> EventRecord:
    identification = Identification(
        event_id=event_id, source_path="x", source_version="x", instrument="EURUSD",
        session_label="9am", config_id="d3_c2", original_direction="bullish",
    )
    operation = OriginalOperation(
        entry_price=1.11, stop_loss=1.11 - risk_price, take_profit=1.13, risk_price=risk_price,
        activation_ts=entry_ts - dt.timedelta(minutes=30), order_placed_ts=entry_ts,
        entry_ts=entry_ts, exit_ts=entry_ts + dt.timedelta(hours=1),
        exit_price=1.11 - risk_price if outcome is Outcome.LOSS else 1.13,
        outcome=outcome, r_multiple=-1.0 if outcome is Outcome.LOSS else 2.0,
        exit_reason="stop_loss" if outcome is Outcome.LOSS else "take_profit",
        exit_reason_basis=ExitReasonBasis.INFERRED_BINARY,
        ambiguous_bar=False, gap_filled=False, has_partial_exit=False,
    )
    features_pre_entry = FeaturesPreEntry(
        feeder_ref_available_ts=None, activation_instant_ts=operation.activation_ts,
        model1_available_ts=None, order_placed_ts=entry_ts,
        time_from_activation_to_order_s=1800.0,
        planned_risk_price=risk_price, planned_reward_price=0.02, planned_rr=2.0,
    )
    features_at_stop = FeaturesAtStop(
        exit_ts=operation.exit_ts, exit_price=operation.exit_price, outcome=outcome,
        r_multiple=operation.r_multiple, speed_to_stop_s=3600.0, ambiguous_bar=False, gap_filled=False,
    )
    return EventRecord(identification, operation, features_pre_entry, features_at_stop)


def test_win_and_loss_with_identical_pre_entry_history_produce_identical_features():
    entry_ts = dt.datetime(2026, 1, 5, 14, 0)
    history = _history(entry_ts)
    win = _make_record("win0", Outcome.WIN, entry_ts)
    loss = _make_record("loss0", Outcome.LOSS, entry_ts)
    series = _series(history + [Candle(entry_ts, open=1.11, high=1.111, low=1.109, close=1.1105)])

    win_features = compute_pre_entry_features(win, series)
    loss_features = compute_pre_entry_features(loss, series)

    assert win_features.atr_m15_at_entry == loss_features.atr_m15_at_entry
    assert win_features.recent_range_atr == loss_features.recent_range_atr
    assert win_features.prior_m15_return == loss_features.prior_m15_return
    assert win_features.position_in_recent_range == loss_features.position_in_recent_range
    assert win_features.ny_hour_at_entry == loss_features.ny_hour_at_entry


def test_future_candle_does_not_affect_pre_entry_feature():
    entry_ts = dt.datetime(2026, 1, 5, 14, 0)
    history = _history(entry_ts)
    record = _make_record("e0", Outcome.LOSS, entry_ts)
    entry_bar = Candle(entry_ts, open=1.11, high=1.111, low=1.109, close=1.1105)

    series_without_future = _series(history + [entry_bar])
    features_a = compute_pre_entry_features(record, series_without_future)

    future_bar = Candle(entry_ts + dt.timedelta(minutes=15), open=9.0, high=9.0, low=9.0, close=9.0)
    series_with_future = _series(history + [entry_bar, future_bar])
    features_b = compute_pre_entry_features(record, series_with_future)

    assert features_a.atr_m15_at_entry == features_b.atr_m15_at_entry
    assert features_a.recent_range_price == features_b.recent_range_price
    assert features_a.distance_to_recent_high_atr == features_b.distance_to_recent_high_atr


def test_entry_bar_itself_not_used_in_recent_range():
    entry_ts = dt.datetime(2026, 1, 5, 14, 0)
    history = _history(entry_ts)
    # The entry bar has an extreme range that must NOT leak into recent_range_price.
    entry_bar_extreme = Candle(entry_ts, open=1.11, high=9.0, low=0.1, close=1.11)
    record = _make_record("e0", Outcome.LOSS, entry_ts)
    series = _series(history + [entry_bar_extreme])
    features = compute_pre_entry_features(record, series)
    assert features.recent_range_price < 1.0  # would be ~8.9 if the entry bar leaked in


def test_zero_risk_does_not_divide_misleadingly():
    entry_ts = dt.datetime(2026, 1, 5, 14, 0)
    history = _history(entry_ts)
    record = _make_record("e0", Outcome.LOSS, entry_ts, risk_price=0.0)
    series = _series(history + [Candle(entry_ts, open=1.11, high=1.111, low=1.109, close=1.1105)])
    features = compute_pre_entry_features(record, series)
    assert features.risk_atr is None


def test_insufficient_history_is_flagged_not_fabricated():
    entry_ts = dt.datetime(2026, 1, 5, 14, 0)
    record = _make_record("e0", Outcome.LOSS, entry_ts)
    series = _series([Candle(entry_ts, open=1.11, high=1.111, low=1.109, close=1.1105)])  # no prior history at all
    features = compute_pre_entry_features(record, series)
    assert features.recent_range_price is None
    assert "recent_range_insufficient_history" in features.missing_reasons


def test_deterministic_for_identical_inputs():
    entry_ts = dt.datetime(2026, 1, 5, 14, 0)
    history = _history(entry_ts)
    record = _make_record("e0", Outcome.LOSS, entry_ts)
    series = _series(history + [Candle(entry_ts, open=1.11, high=1.111, low=1.109, close=1.1105)])
    a = compute_pre_entry_features(record, series)
    b = compute_pre_entry_features(record, series)
    assert a == b
