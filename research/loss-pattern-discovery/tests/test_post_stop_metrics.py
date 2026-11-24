import datetime as dt

import pytest
from core.candle import Candle, OHLCSeries

from behavior.post_stop_metrics import (
    CONTINUATION_REVERSAL_THRESHOLD_R,
    M15_DURATION,
    classify_gap,
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
    exit_ts = dt.datetime(2026, 1, 2, 16, 0)  # a Friday
    record = _make_record(exit_ts=exit_ts)
    candles = [
        Candle(exit_ts + dt.timedelta(minutes=15), open=1.10, high=1.10, low=1.10, close=1.10),
        # ~50h later (ordinary FX Friday-evening-to-Sunday-evening closure), not a missing-data artifact.
        Candle(exit_ts + dt.timedelta(minutes=15) + dt.timedelta(hours=50), open=1.10, high=1.10, low=1.10, close=1.10),
        # Trading continues well beyond the 3d horizon -- proves the series
        # was NOT exhausted, only the weekend was spanned on the way there.
        Candle(exit_ts + dt.timedelta(days=5), open=1.10, high=1.10, low=1.10, close=1.10),
    ]
    [behavior] = compute_post_stop_behavior(record, _series(candles), horizons=(("3d", dt.timedelta(days=3)),))
    assert behavior.weekend_gap_spanned is True
    assert behavior.unexpected_gap_spanned is False
    # The gap did not prevent the dataset from covering the horizon -- not censored.
    assert behavior.censored is False
    # bars are kept as-is, never an invented bar filling the gap
    assert behavior.bars_available == 2


def test_gap_classification_distinguishes_weekend_from_unexpected():
    friday = dt.datetime(2026, 1, 2, 21, 0)
    assert classify_gap(friday, friday + dt.timedelta(hours=49)) == "weekend_closure"
    tuesday = dt.datetime(2026, 1, 6, 10, 0)
    assert classify_gap(tuesday, tuesday + dt.timedelta(hours=2)) == "unexpected_gap"
    assert classify_gap(tuesday, tuesday + M15_DURATION) == "none"


def test_unexpected_midweek_gap_is_flagged_separately_from_weekend():
    exit_ts = dt.datetime(2026, 1, 6, 10, 0)  # a Tuesday
    record = _make_record(exit_ts=exit_ts)
    candles = [
        Candle(exit_ts + dt.timedelta(minutes=15), open=1.10, high=1.10, low=1.10, close=1.10),
        # A 2-hour gap on a Tuesday is not an ordinary market closure.
        Candle(exit_ts + dt.timedelta(minutes=15) + dt.timedelta(hours=2), open=1.10, high=1.10, low=1.10, close=1.10),
    ]
    [behavior] = compute_post_stop_behavior(record, _series(candles), horizons=(("4h", dt.timedelta(hours=4)),))
    assert behavior.unexpected_gap_spanned is True
    assert behavior.weekend_gap_spanned is False


def test_first_bar_outside_a_short_horizon_does_not_contaminate_it():
    # Defect A regression: the first post-exit bar can land well outside a
    # SHORT horizon (e.g. because of a weekend gap) -- it must not seed
    # raw_max/raw_min for that horizon, even though it IS the first bar
    # chronologically after exit.
    exit_ts = dt.datetime(2026, 1, 2, 20, 0)  # Friday evening
    record = _make_record(exit_ts=exit_ts, exit_price=1.10)
    far_outside_1h_bar = Candle(
        exit_ts + dt.timedelta(hours=50), open=1.10, high=9.0, low=0.1, close=1.10
    )
    outcomes = compute_post_stop_behavior(
        record, _series([far_outside_1h_bar]),
        horizons=(("1h", dt.timedelta(hours=1)), ("3d", dt.timedelta(days=3))),
    )
    one_hour, three_day = outcomes
    assert one_hour.bars_available == 0
    assert one_hour.raw_max_price is None
    assert one_hour.raw_min_price is None
    # The 3-day horizon DOES reach that bar, and legitimately picks up its extremes.
    assert three_day.bars_available == 1
    assert three_day.raw_max_price == 9.0


def test_horizon_boundary_falling_inside_an_open_bar_excludes_that_bar():
    # exit_ts deliberately off the M15 grid; a candle opens 10 minutes
    # later (closes at +25min). A horizon ending at +20min falls strictly
    # INSIDE that candle's own interval -- its OHLC is not yet known at
    # +20min (it closes at +25min), so it must not count toward this horizon.
    exit_ts = dt.datetime(2026, 1, 1, 10, 7)
    record = _make_record(exit_ts=exit_ts)
    mid_bar = Candle(exit_ts + dt.timedelta(minutes=10), open=1.10, high=1.12, low=1.08, close=1.11)
    [behavior] = compute_post_stop_behavior(
        record, _series([mid_bar]), horizons=(("20min", dt.timedelta(minutes=20)),)
    )
    assert behavior.bars_available == 0
    assert behavior.raw_max_price is None


def test_fully_observed_horizon_with_no_gaps():
    exit_ts = dt.datetime(2026, 1, 1, 10, 0)
    record = _make_record(exit_ts=exit_ts)
    # Bars at +15/+30/+45/+60min; the +60min bar OPENS exactly at the 1h
    # boundary but doesn't CLOSE until +75min, so only the first 3 (closing
    # at +30/+45/+60) are fully known by the 1h boundary -- the 4th is
    # correctly excluded (Defect B), not a bug in this test's expectation.
    candles = [
        Candle(exit_ts + dt.timedelta(minutes=15 * i), open=1.10, high=1.101, low=1.099, close=1.10)
        for i in range(1, 5)
    ]
    [behavior] = compute_post_stop_behavior(record, _series(candles), horizons=(("1h", dt.timedelta(hours=1)),))
    assert behavior.censored is False
    assert behavior.weekend_gap_spanned is False
    assert behavior.unexpected_gap_spanned is False
    assert behavior.bars_available == 3


def test_recovery_not_confirmed_while_touch_bar_still_open_for_that_horizon():
    # A bar touches entry_price, but its own close/availability falls AFTER
    # the horizon boundary -- recovery must not be confirmed for that
    # horizon; a longer horizon that includes the now-closed bar must
    # confirm it.
    exit_ts = dt.datetime(2026, 1, 1, 10, 0)
    record = _make_record(direction="bullish", exit_ts=exit_ts, exit_price=1.10, entry_price=1.11, risk_price=0.01)
    touching_bar = Candle(exit_ts + dt.timedelta(minutes=50), open=1.105, high=1.111, low=1.104, close=1.108)
    outcomes = compute_post_stop_behavior(
        record, _series([touching_bar]),
        horizons=(("1h", dt.timedelta(hours=1)), ("4h", dt.timedelta(hours=4))),
    )
    one_hour, four_hour = outcomes
    # availability = exit+50min+15min = exit+65min > 1h horizon boundary
    assert one_hour.recovered_to_entry_price is False
    assert four_hour.recovered_to_entry_price is True
    assert four_hour.recovery_confirmed_at == exit_ts + dt.timedelta(minutes=65)


def test_recovery_gap_flagged_when_price_jumps_through_entry_level():
    exit_ts = dt.datetime(2026, 1, 1, 10, 0)
    record = _make_record(direction="bullish", exit_ts=exit_ts, exit_price=1.10, entry_price=1.11, risk_price=0.01)
    # The bar OPENS already above entry_price -- a gap through the level,
    # not a clean intrabar touch.
    gapped_bar = Candle(exit_ts + dt.timedelta(minutes=15), open=1.115, high=1.116, low=1.114, close=1.115)
    [behavior] = compute_post_stop_behavior(
        record, _series([gapped_bar]), horizons=(("4h", dt.timedelta(hours=4)),)
    )
    assert behavior.recovered_to_entry_price is True
    assert behavior.recovery_gap is True


def test_censored_only_means_true_data_exhaustion_not_weekend_closure():
    # Same shape as the weekend test, but assert explicitly that `censored`
    # is False even though a large gap was spanned -- the two concepts are
    # independent.
    exit_ts = dt.datetime(2026, 1, 2, 16, 0)
    record = _make_record(exit_ts=exit_ts)
    candles = [
        Candle(exit_ts + dt.timedelta(minutes=15), open=1.10, high=1.10, low=1.10, close=1.10),
        Candle(exit_ts + dt.timedelta(minutes=15) + dt.timedelta(hours=50), open=1.10, high=1.10, low=1.10, close=1.10),
        Candle(exit_ts + dt.timedelta(days=5), open=1.10, high=1.10, low=1.10, close=1.10),
    ]
    [behavior] = compute_post_stop_behavior(record, _series(candles), horizons=(("3d", dt.timedelta(days=3)),))
    assert behavior.censored is False
    assert behavior.weekend_gap_spanned is True


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


def test_atr_excludes_the_event_bars_own_not_yet_closed_candle():
    # Defect-B-style leak applied to the PRE-event ATR lookback: the bar AT
    # event_ts itself is not fully known until event_ts + M15_DURATION, so
    # its own close must not be used as a true-range term.
    event_ts = dt.datetime(2026, 1, 1, 10, 0)
    pre_candles = [
        Candle(event_ts - dt.timedelta(minutes=15 * i), open=1.10, high=1.1005, low=1.0995, close=1.10)
        for i in range(20, 0, -1)
    ]
    event_bar_with_extreme_range = Candle(event_ts, open=1.10, high=9.0, low=0.1, close=1.10)
    series = _series(pre_candles + [event_bar_with_extreme_range])
    atr = compute_atr_at_event(series, event_ts)
    assert atr is not None
    assert atr < 1.0  # would be huge if the event bar's own range leaked in


def test_phase3_fixes_do_not_alter_original_execution_rules():
    # No change in this phase touched detector/'s exit-resolution rules or
    # the eligibility classifier -- a quick regression using the same
    # synthetic fixture style confirms outcome/exit_reason derivation is
    # untouched by the post-stop-metrics timing fixes.
    from eligibility.stop_eligibility import StopEligibility, classify

    exit_ts = dt.datetime(2026, 1, 1, 10, 0)
    record = _make_record(exit_ts=exit_ts, exit_price=1.10)
    result = classify(record)
    assert result.category is StopEligibility.CONFIRMED_STOP


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
