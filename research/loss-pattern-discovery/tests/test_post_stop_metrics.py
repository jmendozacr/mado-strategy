import datetime as dt

import pytest
from core.candle import Candle, OHLCSeries

from behavior.post_stop_metrics import (
    CONTINUATION_REVERSAL_THRESHOLD_R,
    compute_atr_at_event,
    compute_post_stop_behavior,
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


def _make_record(direction="bullish", exit_ts=None, exit_price=1.10, risk_price=0.01, entry_price=None):
    exit_ts = exit_ts or dt.datetime(2026, 1, 1, 10, 0)
    entry_price = entry_price if entry_price is not None else (exit_price + risk_price if direction == "bullish" else exit_price - risk_price)
    identification = Identification(
        event_id="e1", source_path="x", source_version="x", instrument="EURUSD",
        session_label="9am", config_id="d3_c2", original_direction=direction,
    )
    stop_loss = exit_price
    take_profit = entry_price + 2 * risk_price if direction == "bullish" else entry_price - 2 * risk_price
    operation = OriginalOperation(
        entry_price=entry_price, stop_loss=stop_loss, take_profit=take_profit, risk_price=risk_price,
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


def _series(candles):
    return OHLCSeries(candles=tuple(candles), instrument="EURUSD", timeframe="M15")


def test_first_actionable_ts_is_exit_plus_one_m15_bar():
    exit_ts = dt.datetime(2026, 1, 1, 10, 0)
    record = _make_record(exit_ts=exit_ts)
    candles = [Candle(exit_ts + dt.timedelta(minutes=15), open=1.10, high=1.10, low=1.10, close=1.10)]
    [behavior] = compute_post_stop_behavior(record, _series(candles), horizons=(("4h", dt.timedelta(hours=4)),))
    assert behavior.first_actionable_ts == exit_ts + dt.timedelta(minutes=15)


def test_exit_bar_itself_is_excluded_from_raw_extremes():
    # A candle AT exit_ts with an extreme high/low must never leak into
    # raw_max/raw_min/MFE/MAE -- only strictly-after bars may.
    exit_ts = dt.datetime(2026, 1, 1, 10, 0)
    record = _make_record(exit_ts=exit_ts, exit_price=1.10)
    exit_bar_with_extreme = Candle(exit_ts, open=1.10, high=5.0, low=-5.0, close=1.10)  # must be ignored
    next_bar = Candle(exit_ts + dt.timedelta(minutes=15), open=1.10, high=1.101, low=1.099, close=1.1005)
    outcomes = compute_post_stop_behavior(
        record, _series([exit_bar_with_extreme, next_bar]), horizons=(("4h", dt.timedelta(hours=4)),)
    )
    assert outcomes[0].raw_max_price < 2.0
    assert outcomes[0].raw_min_price > -2.0


def test_incomplete_horizon_is_censored_not_fabricated():
    exit_ts = dt.datetime(2026, 1, 1, 10, 0)
    record = _make_record(exit_ts=exit_ts)
    candles = [Candle(exit_ts + dt.timedelta(minutes=15), open=1.10, high=1.10, low=1.10, close=1.10)]
    [behavior] = compute_post_stop_behavior(record, _series(candles), horizons=(("3d", dt.timedelta(days=3)),))
    assert behavior.censored is True
    assert behavior.bars_available == 1


def test_weekend_gap_is_flagged_without_interpolation():
    exit_ts = dt.datetime(2026, 1, 2, 16, 0)  # Friday
    record = _make_record(exit_ts=exit_ts)
    candles = [
        Candle(exit_ts + dt.timedelta(minutes=15), open=1.10, high=1.10, low=1.10, close=1.10),
        # Next bar is Monday -- a real weekend gap, not a missing-data artifact to fill in.
        Candle(exit_ts + dt.timedelta(days=3), open=1.10, high=1.10, low=1.10, close=1.10),
    ]
    [behavior] = compute_post_stop_behavior(record, _series(candles), horizons=(("3d", dt.timedelta(days=3)),))
    assert behavior.weekend_gap_spanned is True
    # bars are kept as-is, never an invented bar filling the gap
    assert behavior.bars_available == 2


def test_mfe_mae_respect_bearish_direction():
    exit_ts = dt.datetime(2026, 1, 1, 10, 0)
    record = _make_record(direction="bearish", exit_ts=exit_ts, exit_price=1.10, risk_price=0.01)
    # price rises after a bearish SL -- that is CONTINUATION (against original direction = adverse)
    candles = [
        Candle(exit_ts + dt.timedelta(minutes=15 * i), open=1.10 + 0.001 * i,
               high=1.10 + 0.002 * i, low=1.10 + 0.0005 * i, close=1.10 + 0.0015 * i)
        for i in range(1, 10)
    ]
    [behavior] = compute_post_stop_behavior(record, _series(candles), horizons=(("4h", dt.timedelta(hours=4)),))
    assert behavior.mae_price > 0  # adverse (price rose, against the original bearish direction)
    assert behavior.mfe_price == 0.0


def test_r_normalization_requires_valid_risk_price():
    exit_ts = dt.datetime(2026, 1, 1, 10, 0)
    record = _make_record(exit_ts=exit_ts, risk_price=0.01)
    object.__setattr__(record.operation, "risk_price", 0.0)  # invalid risk -- must not divide by zero
    candles = [Candle(exit_ts + dt.timedelta(minutes=15), open=1.105, high=1.106, low=1.104, close=1.105)]
    [behavior] = compute_post_stop_behavior(record, _series(candles), horizons=(("4h", dt.timedelta(hours=4)),))
    assert behavior.mfe_r is None
    assert behavior.mae_r is None
    assert behavior.mfe_atr is None or behavior.atr_at_event is None  # unaffected code path, sanity


def test_atr_at_event_never_uses_bars_after_the_event():
    event_ts = dt.datetime(2026, 1, 1, 10, 0)
    pre_candles = [
        Candle(event_ts - dt.timedelta(minutes=15 * i), open=1.10, high=1.10 + 0.001, low=1.10 - 0.001, close=1.10)
        for i in range(20, 0, -1)
    ]
    post_candle_with_huge_range = Candle(event_ts + dt.timedelta(minutes=15), open=1.10, high=9.0, low=0.1, close=1.10)
    series = _series(pre_candles + [Candle(event_ts, open=1.10, high=1.101, low=1.099, close=1.10), post_candle_with_huge_range])
    atr = compute_atr_at_event(series, event_ts)
    assert atr is not None
    assert atr < 1.0  # would be huge if the post-event bar leaked in


def test_continuation_reversal_first_move_uses_preregistered_threshold():
    exit_ts = dt.datetime(2026, 1, 1, 10, 0)
    record = _make_record(direction="bullish", exit_ts=exit_ts, exit_price=1.10, risk_price=0.01)
    # Immediately reverses back up past the 0.25R threshold (0.0025 price).
    candles = [
        Candle(exit_ts + dt.timedelta(minutes=15), open=1.10, high=1.1026, low=1.10, close=1.1026),
    ]
    [behavior] = compute_post_stop_behavior(record, _series(candles), horizons=(("4h", dt.timedelta(hours=4)),))
    assert behavior.first_move_direction == "reversal"
    assert CONTINUATION_REVERSAL_THRESHOLD_R == 0.25


def test_same_bar_tie_on_both_thresholds_resolves_to_continuation_not_reversal():
    # A single bar whose range crosses BOTH the 0.25R continuation and
    # reversal thresholds has unknowable true intrabar order -- this must
    # resolve pessimistically to "continuation" (never overstate reversal
    # evidence from an ambiguous bar), mirroring this project's existing
    # SL-wins-ties convention.
    exit_ts = dt.datetime(2026, 1, 1, 10, 0)
    record = _make_record(direction="bullish", exit_ts=exit_ts, exit_price=1.10, risk_price=0.01)
    candles = [
        Candle(exit_ts + dt.timedelta(minutes=15), open=1.10, high=1.1026, low=1.0974, close=1.10),
    ]
    [behavior] = compute_post_stop_behavior(record, _series(candles), horizons=(("4h", dt.timedelta(hours=4)),))
    assert behavior.first_move_direction == "continuation"
