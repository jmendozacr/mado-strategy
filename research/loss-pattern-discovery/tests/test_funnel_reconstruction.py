import datetime as dt

import pytest

from core.candle import Candle, OHLCSeries

from extract.funnel_reconstruction import (
    ModelFunnelSplit,
    _covariates_for_group,
    _eligible_and_skipped,
    verify_against_pooled_counts,
)


def _candidate(signal_id):
    from backtest.candidate import Candidate
    return Candidate(
        signal_id=signal_id, anchor_index=0, origin_index=0, direction="bullish", entry_type="wick",
        retest_index=0, entry_price=1.10, stop_loss=1.09, take_profit=1.13, partial_price=1.115,
    )


def _candles(n, start=dt.datetime(2026, 1, 1, 0, 0)):
    return tuple(Candle(start + dt.timedelta(minutes=15 * i), open=1.1, high=1.1, low=1.1, close=1.1) for i in range(n))


def test_eligible_candidate_has_order_placed_within_series():
    candles = _candles(5)
    timestamps = [c.timestamp for c in candles]
    candidate = _candidate("a")
    order_placed = {"a": timestamps[2]}
    confirmation_idx = {"a": 0}
    eligible, skipped = _eligible_and_skipped([candidate], candles, timestamps, order_placed, confirmation_idx)
    assert [c.signal_id for c in eligible] == ["a"]
    assert skipped == []


def test_candidate_with_order_placed_beyond_series_is_skipped():
    candles = _candles(5)
    timestamps = [c.timestamp for c in candles]
    candidate = _candidate("b")
    order_placed = {"b": timestamps[-1] + dt.timedelta(days=365)}  # far beyond the series
    confirmation_idx = {"b": 0}
    eligible, skipped = _eligible_and_skipped([candidate], candles, timestamps, order_placed, confirmation_idx)
    assert eligible == []
    assert [c.signal_id for c in skipped] == ["b"]


def test_candidate_missing_from_order_placed_map_defaults_to_skipped():
    candles = _candles(5)
    timestamps = [c.timestamp for c in candles]
    candidate = _candidate("c")
    eligible, skipped = _eligible_and_skipped([candidate], candles, timestamps, {}, {})
    assert eligible == []
    assert [c.signal_id for c in skipped] == ["c"]


def test_eligible_and_skipped_partition_is_exhaustive_and_disjoint():
    candles = _candles(5)
    timestamps = [c.timestamp for c in candles]
    candidates = [_candidate("x"), _candidate("y")]
    order_placed = {"x": timestamps[1], "y": timestamps[-1] + dt.timedelta(days=1)}
    confirmation_idx = {"x": 0, "y": 0}
    eligible, skipped = _eligible_and_skipped(candidates, candles, timestamps, order_placed, confirmation_idx)
    assert len(eligible) + len(skipped) == len(candidates)
    assert {c.signal_id for c in eligible} | {c.signal_id for c in skipped} == {"x", "y"}
    assert {c.signal_id for c in eligible} & {c.signal_id for c in skipped} == set()


def test_eligible_and_skipped_and_covariates_are_deterministic():
    candles = _candles(20)
    timestamps = [c.timestamp for c in candles]
    candidates = [_candidate("x"), _candidate("y")]
    order_placed = {"x": timestamps[18], "y": timestamps[-1] + dt.timedelta(days=1)}
    confirmation_idx = {"x": 0, "y": 0}
    series = OHLCSeries(candles=candles, instrument="EURUSD", timeframe="M15")

    run1 = _eligible_and_skipped(candidates, candles, timestamps, order_placed, confirmation_idx)
    run2 = _eligible_and_skipped(candidates, candles, timestamps, order_placed, confirmation_idx)
    assert [c.signal_id for c in run1[0]] == [c.signal_id for c in run2[0]]
    assert [c.signal_id for c in run1[1]] == [c.signal_id for c in run2[1]]

    cov1 = _covariates_for_group(candidates, series, order_placed)
    cov2 = _covariates_for_group(candidates, series, order_placed)
    assert cov1 == cov2


def test_partition_and_covariates_are_order_independent():
    candles = _candles(20)
    timestamps = [c.timestamp for c in candles]
    candidates = [_candidate("x"), _candidate("y"), _candidate("z")]
    order_placed = {
        "x": timestamps[18], "y": timestamps[-1] + dt.timedelta(days=1), "z": timestamps[17],
    }
    confirmation_idx = {"x": 0, "y": 0, "z": 0}
    series = OHLCSeries(candles=candles, instrument="EURUSD", timeframe="M15")

    forward = _eligible_and_skipped(candidates, candles, timestamps, order_placed, confirmation_idx)
    reversed_ = _eligible_and_skipped(list(reversed(candidates)), candles, timestamps, order_placed, confirmation_idx)
    assert {c.signal_id for c in forward[0]} == {c.signal_id for c in reversed_[0]}
    assert {c.signal_id for c in forward[1]} == {c.signal_id for c in reversed_[1]}

    cov_forward = _covariates_for_group(candidates, series, order_placed)
    cov_reversed = _covariates_for_group(list(reversed(candidates)), series, order_placed)
    assert cov_forward["atr_at_order_placement"]["median"] == cov_reversed["atr_at_order_placement"]["median"]
    assert cov_forward["atr_at_order_placement"]["n"] == cov_reversed["atr_at_order_placement"]["n"]


def test_verify_against_pooled_counts_detects_a_real_match():
    result = {
        "splits": {
            "1am": ModelFunnelSplit(candidates_built=10, filled=8, never_filled=2, skipped_no_placement=0),
            "9am": ModelFunnelSplit(candidates_built=20, filled=15, never_filled=4, skipped_no_placement=1),
        },
        "pooled_check": {"candidates_built": 30, "filled": 23, "never_filled": 6, "skipped_no_placement": 1},
    }
    verification = verify_against_pooled_counts(result)
    assert verification["matches"] is True


def test_covariates_for_group_uses_only_bars_closed_before_order_placement():
    # 20 bars of history before order_placed_ts, enough for a 14-bar ATR.
    order_placed_ts = dt.datetime(2026, 1, 1, 5, 0)
    history = [
        Candle(order_placed_ts - dt.timedelta(minutes=15 * i), open=1.10, high=1.102, low=1.098, close=1.10)
        for i in range(20, 0, -1)
    ]
    series = OHLCSeries(candles=tuple(history), instrument="EURUSD", timeframe="M15")
    candidate = _candidate("a")  # entry_price=1.10, stop_loss=1.09 -> risk_price=0.01
    result = _covariates_for_group([candidate], series, {"a": order_placed_ts})
    assert result["atr_at_order_placement"]["n"] == 1
    assert result["atr_at_order_placement"]["median"] == pytest.approx(0.004)  # high-low=0.004 every bar
    assert result["planned_risk_atr_at_order_placement"]["median"] == pytest.approx(0.01 / 0.004)


def test_covariates_for_group_never_uses_a_bar_at_or_after_order_placement():
    order_placed_ts = dt.datetime(2026, 1, 1, 5, 0)
    history = [
        Candle(order_placed_ts - dt.timedelta(minutes=15 * i), open=1.10, high=1.102, low=1.098, close=1.10)
        for i in range(20, 0, -1)
    ]
    # A wild bar AT order_placed_ts itself -- must never affect the ATR.
    history_with_future = history + [Candle(order_placed_ts, open=1.10, high=50.0, low=0.001, close=25.0)]
    series = OHLCSeries(candles=tuple(history_with_future), instrument="EURUSD", timeframe="M15")
    candidate = _candidate("a")
    result = _covariates_for_group([candidate], series, {"a": order_placed_ts})
    assert result["atr_at_order_placement"]["median"] == pytest.approx(0.004)


def test_covariates_for_group_skips_candidates_with_no_order_placed_timestamp():
    series = OHLCSeries(candles=_candles(20), instrument="EURUSD", timeframe="M15")
    candidate = _candidate("a")
    result = _covariates_for_group([candidate], series, {})
    assert result["atr_at_order_placement"]["n"] == 0


def test_verify_against_pooled_counts_detects_a_real_mismatch():
    result = {
        "splits": {
            "1am": ModelFunnelSplit(candidates_built=10, filled=8, never_filled=2, skipped_no_placement=0),
            "9am": ModelFunnelSplit(candidates_built=20, filled=15, never_filled=4, skipped_no_placement=1),
        },
        # Deliberately wrong pooled total (candidates_built off by one) --
        # the reconciliation must catch this, never silently accept it.
        "pooled_check": {"candidates_built": 31, "filled": 23, "never_filled": 6, "skipped_no_placement": 1},
    }
    verification = verify_against_pooled_counts(result)
    assert verification["matches"] is False
