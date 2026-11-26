from datetime import date

from conftest import M15, flat_bucket, ny_ts

import causal_anchor_v2 as ca
from core.candle import Candle, OHLCSeries
from core.config import BacktestConfig, DetectorConfig, Model1Config
from primitives.swing import detect_swings
from raza_h4fvg.candidate_and_fill import resolve_candidate

SESSION_DATE = date(2024, 6, 10)


def _config(min_risk_reward=2.0, trading_cost_price=0.0):
    backtest = BacktestConfig(
        sl_buffer_atr_multiple=0.3, min_stop_distance_price=0.0, min_risk_reward=min_risk_reward,
        trading_cost_price=trading_cost_price, kill_zone_gated=False, max_fill_wait=20,
        partial_fraction=0.0, breakeven_after_partial=False,
    )
    return DetectorConfig(backtest=backtest)


def _confirm_sequence(open_ts):
    return [
        Candle(open_ts + 0 * M15, open=1.02, high=1.03, low=1.00, close=1.01),
        Candle(open_ts + 1 * M15, open=1.01, high=1.02, low=0.95, close=0.96),
        Candle(open_ts + 2 * M15, open=0.97, high=1.06, low=0.96, close=1.05),
        Candle(open_ts + 3 * M15, open=1.05, high=1.06, low=0.99, close=1.03),
        Candle(open_ts + 4 * M15, open=1.04, high=1.07, low=1.03, close=1.06),
    ]


def _confirmed_signal(window_bars_after_confirm, base_after=1.06):
    ts_1300 = ny_ts(SESSION_DATE.year, SESSION_DATE.month, SESSION_DATE.day, 13)
    seq = _confirm_sequence(ts_1300)
    tail = flat_bucket(ts_1300 + 5 * M15, window_bars_after_confirm, base=base_after, flat_delta=0.001)
    candles = tuple(seq + tail)
    signal = ca.confirm_in_ltf_window_v2(candles, (0, len(candles) - 1), "bullish", Model1Config())
    assert signal is not None and signal.status.name == "CONFIRMED"
    return signal, candles


def _confirmed_signal_with_guaranteed_touch(n_flat_tail_bars, touch_low=0.50):
    """Same confirm sequence, followed by one bar that dips low enough
    to touch ANY plausible bullish entry price from that sequence, then
    flat bars -- avoids having to predict `_select_entry`'s own exact
    output value."""
    ts_1300 = ny_ts(SESSION_DATE.year, SESSION_DATE.month, SESSION_DATE.day, 13)
    seq = _confirm_sequence(ts_1300)
    touch_bar = [Candle(ts_1300 + 5 * M15, open=1.06, high=1.07, low=touch_low, close=1.06)]
    tail = flat_bucket(ts_1300 + 6 * M15, n_flat_tail_bars, base=1.06, flat_delta=0.001)
    candles = tuple(seq + touch_bar + tail)
    signal = ca.confirm_in_ltf_window_v2(candles, (0, len(candles) - 1), "bullish", Model1Config())
    assert signal is not None and signal.status.name == "CONFIRMED"
    return signal, candles


def test_rr_floor_rejected_when_target_too_close():
    signal, candles = _confirmed_signal(window_bars_after_confirm=30)
    m15 = OHLCSeries(candles=candles, instrument="TEST", timeframe="M15")
    config = _config(min_risk_reward=2.0)
    swings = detect_swings(m15, config.swing)
    indices = [s.index for s in swings]
    timestamps = [c.timestamp for c in candles]

    # reference_high very close to entry -> low reward, fails the 2.0 floor
    result = resolve_candidate(
        signal, m15, config, swings, indices, reference_high=1.08, reference_low=0.90,
        current_open_ts=ny_ts(SESSION_DATE.year, SESSION_DATE.month, SESSION_DATE.day, 9),
        m15_timestamps=timestamps,
    )
    assert result.outcome == "RR_FLOOR_REJECTED"
    assert result.risk_reward < 2.0


def test_entered_when_rr_passes_and_price_touches_entry():
    signal, candles = _confirmed_signal_with_guaranteed_touch(n_flat_tail_bars=40)
    m15 = OHLCSeries(candles=candles, instrument="TEST", timeframe="M15")
    config = _config(min_risk_reward=2.0)
    swings = detect_swings(m15, config.swing)
    indices = [s.index for s in swings]
    timestamps = [c.timestamp for c in candles]

    result = resolve_candidate(
        signal, m15, config, swings, indices, reference_high=1.50, reference_low=0.10,
        current_open_ts=ny_ts(SESSION_DATE.year, SESSION_DATE.month, SESSION_DATE.day, 9),
        m15_timestamps=timestamps,
    )
    assert result.outcome == "ENTERED"
    assert result.trade is not None
    assert result.trade.outcome in ("win", "loss", "open")


def test_unfilled_order_when_price_never_touches_entry_before_1500_cutoff():
    ts_1300 = ny_ts(SESSION_DATE.year, SESSION_DATE.month, SESSION_DATE.day, 13)
    seq = _confirm_sequence(ts_1300)
    # Price runs AWAY from the entry (far above it) for the rest of the window, up to just before 15:00 --
    # never touches back down to the entry price, and nothing exists after the cutoff.
    tail = flat_bucket(ts_1300 + 5 * M15, 3, base=5.00, flat_delta=0.001)  # 13:15*... stays far away, few bars only
    candles = tuple(seq + tail)
    signal = ca.confirm_in_ltf_window_v2(candles, (0, len(candles) - 1), "bullish", Model1Config())
    assert signal is not None and signal.status.name == "CONFIRMED"

    m15 = OHLCSeries(candles=candles, instrument="TEST", timeframe="M15")
    config = _config(min_risk_reward=2.0)
    swings = detect_swings(m15, config.swing)
    indices = [s.index for s in swings]
    timestamps = [c.timestamp for c in candles]

    result = resolve_candidate(
        signal, m15, config, swings, indices, reference_high=1.50, reference_low=0.90,
        current_open_ts=ny_ts(SESSION_DATE.year, SESSION_DATE.month, SESSION_DATE.day, 9),
        m15_timestamps=timestamps,
    )
    assert result.outcome == "UNFILLED_ORDER"
