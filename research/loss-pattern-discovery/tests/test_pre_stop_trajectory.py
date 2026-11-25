import datetime as dt

from core.candle import Candle, OHLCSeries

from behavior.pre_stop_trajectory import PathIntegrity, compute_pre_stop_trajectory
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


def _make_record(
    entry_ts, exit_ts, direction="bullish", entry_price=1.10, stop_loss=1.09, exit_price=None,
) -> EventRecord:
    exit_price = exit_price if exit_price is not None else stop_loss
    identification = Identification(
        event_id="e0", source_path="x", source_version="x", instrument="EURUSD",
        session_label="9am", config_id="d3_c2", original_direction=direction,
    )
    operation = OriginalOperation(
        entry_price=entry_price, stop_loss=stop_loss, take_profit=entry_price + 0.02,
        risk_price=abs(entry_price - stop_loss),
        activation_ts=entry_ts - dt.timedelta(minutes=30), order_placed_ts=entry_ts,
        entry_ts=entry_ts, exit_ts=exit_ts, exit_price=exit_price,
        outcome=Outcome.LOSS, r_multiple=-1.0, exit_reason="stop_loss",
        exit_reason_basis=ExitReasonBasis.INFERRED_BINARY,
        ambiguous_bar=False, gap_filled=(exit_price != stop_loss), has_partial_exit=False,
    )
    features_pre_entry = FeaturesPreEntry(
        feeder_ref_available_ts=None, activation_instant_ts=operation.activation_ts,
        model1_available_ts=None, order_placed_ts=entry_ts, time_from_activation_to_order_s=1800.0,
        planned_risk_price=operation.risk_price, planned_reward_price=0.02, planned_rr=2.0,
    )
    features_at_stop = FeaturesAtStop(
        exit_ts=exit_ts, exit_price=exit_price, outcome=Outcome.LOSS, r_multiple=-1.0,
        speed_to_stop_s=(exit_ts - entry_ts).total_seconds(), ambiguous_bar=False,
        gap_filled=operation.gap_filled,
    )
    return EventRecord(identification, operation, features_pre_entry, features_at_stop)


def test_exit_bar_does_not_retroactively_contribute_to_primary_mfe():
    entry_ts = dt.datetime(2026, 1, 1, 10, 0)
    exit_ts = entry_ts + dt.timedelta(minutes=30)  # one middle bar at +15min
    record = _make_record(entry_ts, exit_ts, entry_price=1.10, stop_loss=1.09)
    entry_bar = Candle(entry_ts, open=1.10, high=1.102, low=1.099, close=1.101)
    middle_bar = Candle(entry_ts + dt.timedelta(minutes=15), open=1.101, high=1.1015, low=1.1005, close=1.101)
    exit_bar_extreme = Candle(exit_ts, open=1.101, high=9.0, low=1.09, close=1.09)  # defines the SL
    series = _series([entry_bar, middle_bar, exit_bar_extreme])
    trajectory = compute_pre_stop_trajectory(record, series)
    assert trajectory.integrity == PathIntegrity.RECONSTRUCTIBLE
    # If the exit bar's 9.0 high leaked in, mfe_pre_sl_price would be huge.
    assert trajectory.mfe_pre_sl_price < 0.01


def test_entry_bar_does_not_retroactively_contribute_to_primary_mfe():
    entry_ts = dt.datetime(2026, 1, 1, 10, 0)
    exit_ts = entry_ts + dt.timedelta(minutes=30)
    record = _make_record(entry_ts, exit_ts, entry_price=1.10, stop_loss=1.09)
    entry_bar_extreme = Candle(entry_ts, open=1.10, high=9.0, low=1.099, close=1.101)
    middle_bar = Candle(entry_ts + dt.timedelta(minutes=15), open=1.101, high=1.1015, low=1.1005, close=1.101)
    exit_bar = Candle(exit_ts, open=1.101, high=1.101, low=1.09, close=1.09)
    series = _series([entry_bar_extreme, middle_bar, exit_bar])
    trajectory = compute_pre_stop_trajectory(record, series)
    assert trajectory.mfe_pre_sl_price < 0.01
    # the sensitivity variant INCLUDING the entry bar should show the leak instead
    assert trajectory.mfe_including_entry_bar_r > 100


def test_mfe_mae_respect_bearish_direction():
    entry_ts = dt.datetime(2026, 1, 1, 10, 0)
    exit_ts = entry_ts + dt.timedelta(minutes=45)
    record = _make_record(entry_ts, exit_ts, direction="bearish", entry_price=1.10, stop_loss=1.11)
    entry_bar = Candle(entry_ts, open=1.10, high=1.101, low=1.099, close=1.10)
    middle1 = Candle(entry_ts + dt.timedelta(minutes=15), open=1.10, high=1.1005, low=1.095, close=1.096)
    middle2 = Candle(entry_ts + dt.timedelta(minutes=30), open=1.096, high=1.098, low=1.094, close=1.097)
    exit_bar = Candle(exit_ts, open=1.097, high=1.11, low=1.097, close=1.11)
    series = _series([entry_bar, middle1, middle2, exit_bar])
    trajectory = compute_pre_stop_trajectory(record, series)
    # bearish: favorable = price falling. MAE pre-SL = adverse rise (max high - entry_price among middle bars).
    assert trajectory.mfe_pre_sl_price > 0  # price fell (favorable for a short) in the middle bars
    assert trajectory.mae_pre_sl_price >= 0


def test_zero_risk_price_no_misleading_division():
    entry_ts = dt.datetime(2026, 1, 1, 10, 0)
    exit_ts = entry_ts + dt.timedelta(minutes=30)
    record = _make_record(entry_ts, exit_ts, entry_price=1.10, stop_loss=1.10)  # risk_price == 0
    middle_bar = Candle(entry_ts + dt.timedelta(minutes=15), open=1.10, high=1.1005, low=1.0995, close=1.10)
    series = _series([Candle(entry_ts, open=1.10, high=1.10, low=1.10, close=1.10), middle_bar,
                       Candle(exit_ts, open=1.10, high=1.10, low=1.10, close=1.10)])
    trajectory = compute_pre_stop_trajectory(record, series)
    assert trajectory.mfe_pre_sl_r is None
    assert trajectory.had_material_favorable_excursion is None


def test_gap_uses_actual_executed_exit_price_not_planned_stop_loss():
    entry_ts = dt.datetime(2026, 1, 1, 10, 0)
    exit_ts = entry_ts + dt.timedelta(minutes=45)
    # Planned stop_loss=1.09, but a gap means the real exit_price is 1.085.
    record = _make_record(entry_ts, exit_ts, entry_price=1.10, stop_loss=1.09, exit_price=1.085)
    entry_bar = Candle(entry_ts, open=1.10, high=1.105, low=1.099, close=1.102)
    middle = Candle(entry_ts + dt.timedelta(minutes=15), open=1.102, high=1.106, low=1.101, close=1.104)
    exit_bar = Candle(exit_ts, open=1.09, high=1.09, low=1.085, close=1.085)
    series = _series([entry_bar, middle, exit_bar])
    trajectory = compute_pre_stop_trajectory(record, series)
    # retracement is measured from the best favorable price down to the
    # ACTUAL exit (1.085), not the planned stop_loss (1.09).
    assert trajectory.retracement_from_best_favorable_price == abs(1.106 - 1.085)


def test_insufficient_when_sl_fires_on_the_entry_bar_itself():
    entry_ts = dt.datetime(2026, 1, 1, 10, 0)
    record = _make_record(entry_ts, entry_ts, entry_price=1.10, stop_loss=1.09)  # same bar
    series = _series([Candle(entry_ts, open=1.10, high=1.101, low=1.089, close=1.09)])
    trajectory = compute_pre_stop_trajectory(record, series)
    assert trajectory.integrity == PathIntegrity.INSUFFICIENT
    assert trajectory.mfe_pre_sl_r is None  # never fabricated as 0
    assert trajectory.n_observable_bars == 0


def test_ambiguous_when_entry_and_exit_are_adjacent_bars():
    entry_ts = dt.datetime(2026, 1, 1, 10, 0)
    exit_ts = entry_ts + dt.timedelta(minutes=15)  # next bar, zero bars strictly between
    record = _make_record(entry_ts, exit_ts, entry_price=1.10, stop_loss=1.09)
    series = _series([
        Candle(entry_ts, open=1.10, high=1.101, low=1.099, close=1.10),
        Candle(exit_ts, open=1.10, high=1.10, low=1.09, close=1.09),
    ])
    trajectory = compute_pre_stop_trajectory(record, series)
    assert trajectory.integrity == PathIntegrity.AMBIGUOUS
    assert trajectory.mfe_pre_sl_r is None


def test_deterministic_for_identical_inputs():
    entry_ts = dt.datetime(2026, 1, 1, 10, 0)
    exit_ts = entry_ts + dt.timedelta(minutes=45)
    record = _make_record(entry_ts, exit_ts, entry_price=1.10, stop_loss=1.09)
    series = _series([
        Candle(entry_ts, open=1.10, high=1.101, low=1.099, close=1.10),
        Candle(entry_ts + dt.timedelta(minutes=15), open=1.10, high=1.1005, low=1.0995, close=1.10),
        Candle(exit_ts, open=1.10, high=1.10, low=1.09, close=1.09),
    ])
    a = compute_pre_stop_trajectory(record, series)
    b = compute_pre_stop_trajectory(record, series)
    assert a == b


def test_post_sl_changes_never_affect_the_trajectory_or_taxonomy():
    from failure_modes.taxonomy import classify

    entry_ts = dt.datetime(2026, 1, 1, 10, 0)
    exit_ts = entry_ts + dt.timedelta(minutes=30)
    record = _make_record(entry_ts, exit_ts, entry_price=1.10, stop_loss=1.09)
    series = _series([
        Candle(entry_ts, open=1.10, high=1.101, low=1.099, close=1.10),
        Candle(entry_ts + dt.timedelta(minutes=15), open=1.10, high=1.1005, low=1.0995, close=1.10),
        Candle(exit_ts, open=1.10, high=1.10, low=1.09, close=1.09),
    ])
    trajectory_before = compute_pre_stop_trajectory(record, series)
    classification_before = classify(trajectory_before)

    # Mutate something that only post-stop analysis would ever touch.
    record.post_stop_outcomes.append(object())

    trajectory_after = compute_pre_stop_trajectory(record, series)
    classification_after = classify(trajectory_after)
    assert trajectory_before == trajectory_after
    assert classification_before == classification_after
