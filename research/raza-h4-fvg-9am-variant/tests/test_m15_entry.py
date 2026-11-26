from datetime import date, timedelta

from conftest import M15, flat_bucket, ny_ts, override

from core.config import Model1Config
from raza_h4fvg.m15_entry import search_entry

SESSION_DATE = date(2024, 6, 10)


def _confirm_sequence(open_ts):
    """The SAME zero-invalidation bullish anchor/engulf/retest/confirm
    sequence used throughout this lab's own prior real-function tests
    (Phase 10's test_confirmation_path_diagnostics.py) -- anchor at
    bar 1, engulf at bar 2, retest-touch at bar 3, confirms at bar 4."""
    from core.candle import Candle
    return [
        Candle(open_ts + 0 * M15, open=1.02, high=1.03, low=1.00, close=1.01),
        Candle(open_ts + 1 * M15, open=1.01, high=1.02, low=0.95, close=0.96),
        Candle(open_ts + 2 * M15, open=0.97, high=1.06, low=0.96, close=1.05),
        Candle(open_ts + 3 * M15, open=1.05, high=1.06, low=0.99, close=1.03),
        Candle(open_ts + 4 * M15, open=1.04, high=1.07, low=1.03, close=1.06),
    ]


def _window_series(prefix_candles, window_open_ts_1300, n_window_bars=8):
    tail = flat_bucket(window_open_ts_1300, n_window_bars, base=1.05, flat_delta=0.001)
    all_candles = tuple(prefix_candles + tail)
    timestamps = [c.timestamp for c in all_candles]
    return all_candles, timestamps


def test_enter_candidate_when_confirmation_completes_within_the_window():
    ts_1300 = ny_ts(SESSION_DATE.year, SESSION_DATE.month, SESSION_DATE.day, 13)
    seq = _confirm_sequence(ts_1300)  # anchor/engulf/retest/confirm ALL at/after 13:00
    tail = flat_bucket(ts_1300 + 5 * M15, 10, base=1.06, flat_delta=0.001)
    candles = tuple(seq + tail)
    timestamps = [c.timestamp for c in candles]
    current_open_ts = ny_ts(SESSION_DATE.year, SESSION_DATE.month, SESSION_DATE.day, 9)

    result = search_entry(
        timestamps, candles, current_open_ts, "bullish",
        swept_extreme=0.80, target_edge=2.00, config=Model1Config(),
    )
    assert result.outcome == "ENTER_CANDIDATE"
    assert result.signal is not None
    assert result.signal.status.name == "CONFIRMED"


def test_pre_1300_confirmation_is_never_used_fresh_anchor_search_finds_nothing():
    ts_1200 = ny_ts(SESSION_DATE.year, SESSION_DATE.month, SESSION_DATE.day, 12)
    prefix = _confirm_sequence(ts_1200)  # the ONLY valid confirm sequence is entirely BEFORE 13:00
    ts_1300 = ny_ts(SESSION_DATE.year, SESSION_DATE.month, SESSION_DATE.day, 13)
    candles, timestamps = _window_series(prefix, ts_1300, n_window_bars=8)
    current_open_ts = ny_ts(SESSION_DATE.year, SESSION_DATE.month, SESSION_DATE.day, 9)

    result = search_entry(
        timestamps, candles, current_open_ts, "bullish",
        swept_extreme=0.80, target_edge=2.00, config=Model1Config(),
    )
    assert result.outcome == "EXPIRED"


def test_discard_target_before_entry_when_price_reaches_target_before_confirmation():
    ts_1300 = ny_ts(SESSION_DATE.year, SESSION_DATE.month, SESSION_DATE.day, 13)
    seq = _confirm_sequence(ts_1300)  # confirms at bar 4 (close=1.06)
    tail = flat_bucket(ts_1300 + 5 * M15, 10, base=1.06, flat_delta=0.001)
    candles = tuple(seq + tail)
    timestamps = [c.timestamp for c in candles]
    current_open_ts = ny_ts(SESSION_DATE.year, SESSION_DATE.month, SESSION_DATE.day, 9)

    # bar 2 (index 2, 13:30) has high=1.06 -- set target_edge so it is reached THERE, before bar 4's confirm.
    result = search_entry(
        timestamps, candles, current_open_ts, "bullish",
        swept_extreme=0.80, target_edge=1.055, config=Model1Config(),
    )
    assert result.outcome == "DISCARD_TARGET_BEFORE_ENTRY"
    assert result.invalidation_index == 2


def test_discard_swept_extreme_breach_when_price_re_breaches_before_confirmation():
    ts_1300 = ny_ts(SESSION_DATE.year, SESSION_DATE.month, SESSION_DATE.day, 13)
    seq = _confirm_sequence(ts_1300)
    tail = flat_bucket(ts_1300 + 5 * M15, 10, base=1.06, flat_delta=0.001)
    candles = tuple(seq + tail)
    timestamps = [c.timestamp for c in candles]
    current_open_ts = ny_ts(SESSION_DATE.year, SESSION_DATE.month, SESSION_DATE.day, 9)

    # bar 1 (index 1, 13:15, the anchor bar itself) has low=0.95 -- set
    # swept_extreme so this re-breaches it, before bar 4's confirm.
    result = search_entry(
        timestamps, candles, current_open_ts, "bullish",
        swept_extreme=0.965, target_edge=2.00, config=Model1Config(),
    )
    assert result.outcome == "DISCARD_SWEPT_EXTREME_BREACH"
    assert result.invalidation_index == 1


def test_expired_when_nothing_happens_in_the_window():
    ts_1300 = ny_ts(SESSION_DATE.year, SESSION_DATE.month, SESSION_DATE.day, 13)
    candles = tuple(flat_bucket(ts_1300, 8, base=1.05, flat_delta=0.0005))
    timestamps = [c.timestamp for c in candles]
    current_open_ts = ny_ts(SESSION_DATE.year, SESSION_DATE.month, SESSION_DATE.day, 9)

    result = search_entry(
        timestamps, candles, current_open_ts, "bullish",
        swept_extreme=0.80, target_edge=2.00, config=Model1Config(),
    )
    assert result.outcome == "EXPIRED"
