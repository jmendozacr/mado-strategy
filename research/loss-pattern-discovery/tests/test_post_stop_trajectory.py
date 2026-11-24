import datetime as dt

import pytest
from core.candle import Candle, OHLCSeries

from extract.post_stop_trajectory import compute_post_stop_outcomes
from schema.events import (
    EventRecord,
    ExitReasonBasis,
    FeaturesAtStop,
    FeaturesPreEntry,
    Identification,
    Outcome,
    OriginalOperation,
)


def _make_bullish_sl_record(exit_ts: dt.datetime, exit_price: float, risk_price: float) -> EventRecord:
    identification = Identification(
        event_id="e1", source_path="x", source_version="x", instrument="EURUSD",
        session_label="9am", config_id="d3_c2", original_direction="bullish",
    )
    operation = OriginalOperation(
        entry_price=exit_price + risk_price, stop_loss=exit_price,
        take_profit=exit_price + 2 * risk_price, risk_price=risk_price,
        activation_ts=None, order_placed_ts=None,
        entry_ts=exit_ts - dt.timedelta(hours=1), exit_ts=exit_ts,
        exit_price=exit_price, outcome=Outcome.LOSS, r_multiple=-1.0,
        exit_reason="stop_loss", exit_reason_basis=ExitReasonBasis.INFERRED_BINARY,
        ambiguous_bar=False, gap_filled=False, has_partial_exit=False,
    )
    features_pre_entry = FeaturesPreEntry(
        feeder_ref_available_ts=None, activation_instant_ts=None, model1_available_ts=None,
        order_placed_ts=None, time_from_activation_to_order_s=None,
        planned_risk_price=risk_price, planned_reward_price=2 * risk_price, planned_rr=2.0,
    )
    features_at_stop = FeaturesAtStop(
        exit_ts=exit_ts, exit_price=exit_price, outcome=Outcome.LOSS, r_multiple=-1.0,
        speed_to_stop_s=3600.0, ambiguous_bar=False, gap_filled=False,
    )
    return EventRecord(identification, operation, features_pre_entry, features_at_stop)


def _series(candles: list[Candle]) -> OHLCSeries:
    return OHLCSeries(candles=tuple(candles), instrument="EURUSD", timeframe="M15")


def test_continuation_against_original_direction_grows_mae():
    exit_ts = dt.datetime(2026, 1, 1, 10, 0)
    exit_price = 1.10
    record = _make_bullish_sl_record(exit_ts, exit_price, risk_price=0.01)
    # price keeps falling after the SL (continuation of the losing move)
    candles = [
        Candle(exit_ts + dt.timedelta(minutes=15 * i), open=1.10 - 0.001 * i,
               high=1.10 - 0.001 * i, low=1.10 - 0.002 * i, close=1.10 - 0.0015 * i)
        for i in range(1, 20)
    ]
    outcomes = compute_post_stop_outcomes(record, _series(candles), horizons=(("4h", dt.timedelta(hours=4)),))
    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome.mae_price > 0
    assert outcome.mfe_price == 0.0  # price never reversed back up above exit_price
    assert outcome.censored is False


def test_reversal_toward_original_direction_grows_mfe():
    exit_ts = dt.datetime(2026, 1, 1, 10, 0)
    exit_price = 1.10
    record = _make_bullish_sl_record(exit_ts, exit_price, risk_price=0.01)
    # price reverses back up after the SL
    candles = [
        Candle(exit_ts + dt.timedelta(minutes=15 * i), open=1.10 + 0.001 * i,
               high=1.10 + 0.002 * i, low=1.10 + 0.0005 * i, close=1.10 + 0.0015 * i)
        for i in range(1, 20)
    ]
    outcomes = compute_post_stop_outcomes(record, _series(candles), horizons=(("4h", dt.timedelta(hours=4)),))
    outcome = outcomes[0]
    assert outcome.mfe_price > 0
    assert outcome.mae_price == 0.0


def test_censored_when_data_runs_out_before_horizon():
    exit_ts = dt.datetime(2026, 1, 1, 10, 0)
    record = _make_bullish_sl_record(exit_ts, exit_price=1.10, risk_price=0.01)
    candles = [Candle(exit_ts + dt.timedelta(minutes=15), open=1.10, high=1.10, low=1.10, close=1.10)]
    outcomes = compute_post_stop_outcomes(record, _series(candles), horizons=(("3d", dt.timedelta(days=3)),))
    assert outcomes[0].censored is True
    assert outcomes[0].bars_available == 1


def test_no_bars_after_exit_is_fully_censored():
    exit_ts = dt.datetime(2026, 1, 1, 10, 0)
    record = _make_bullish_sl_record(exit_ts, exit_price=1.10, risk_price=0.01)
    candles = [Candle(exit_ts - dt.timedelta(minutes=15), open=1.10, high=1.10, low=1.10, close=1.10)]
    outcomes = compute_post_stop_outcomes(record, _series(candles), horizons=(("4h", dt.timedelta(hours=4)),))
    assert outcomes[0].censored is True
    assert outcomes[0].bars_available == 0
    assert outcomes[0].mfe_price is None


def test_missing_exit_ts_raises():
    record = _make_bullish_sl_record(dt.datetime(2026, 1, 1, 10, 0), 1.10, 0.01)
    object.__setattr__(record.operation, "exit_ts", None)
    with pytest.raises(ValueError):
        compute_post_stop_outcomes(record, _series([]))
