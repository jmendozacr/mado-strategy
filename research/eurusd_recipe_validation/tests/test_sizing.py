from datetime import datetime, timedelta

import pytest

from research.eurusd_recipe_validation.sizing import simulate_rolling_windows
from research.eurusd_recipe_validation.trades import ClosedTrade

_DAY_ZERO = datetime(2024, 1, 1, 12, 0)  # 12:00 UTC is the same NY calendar date year-round


def _trade(signal_id, day_offset, r_multiple):
    """One closed trade whose exit lands `day_offset` days after day zero."""
    exit_time = _DAY_ZERO + timedelta(days=day_offset)
    return ClosedTrade(
        signal_id=signal_id,
        direction="bullish",
        entry_index=day_offset,
        exit_index=day_offset,
        entry_time=exit_time,
        exit_time=exit_time,
        outcome="win" if r_multiple > 0 else "loss",
        r_multiple=r_multiple,
    )


def _open_trade(signal_id, day_offset):
    entry_time = _DAY_ZERO + timedelta(days=day_offset)
    return ClosedTrade(
        signal_id=signal_id, direction="bullish", entry_index=day_offset, exit_index=None,
        entry_time=entry_time, exit_time=None, outcome="open", r_multiple=None,
    )


def _run(trades, **overrides):
    kwargs = dict(
        risk_per_trade_pct=1.0, max_drawdown_pct=10.0, daily_loss_limit_pct=5.0, window_days=10
    )
    kwargs.update(overrides)
    return simulate_rolling_windows(trades, **kwargs)


def test_an_empty_population_produces_no_windows_and_no_fail_rate():
    result = _run([])
    assert result.windows == ()
    assert result.fail_dd_fraction is None
    assert result.fail_daily_loss_fraction is None


def test_a_span_shorter_than_the_window_produces_no_windows():
    trades = [_trade("a", 0, 1.0), _trade("b", 5, 1.0)]
    assert _run(trades, window_days=10).windows == ()


def test_window_count_is_every_full_window_start_day_in_the_span():
    # Span day 0..11 inclusive = 12 days; 10-day windows => 3 start days.
    trades = [_trade("a", 0, 1.0), _trade("b", 11, 1.0)]
    assert len(_run(trades, window_days=10).windows) == 3


def test_a_window_covers_window_days_inclusive_of_its_start():
    trades = [_trade("a", 0, 1.0), _trade("b", 9, 1.0)]
    window = _run(trades, window_days=10).windows[0]
    assert (window.start_date, window.end_date) == (_DAY_ZERO.date(), (_DAY_ZERO + timedelta(days=9)).date())
    assert window.trades == 2


def test_trades_outside_a_window_are_excluded_from_it():
    trades = [_trade("a", 0, -5.0), _trade("b", 10, 1.0), _trade("c", 19, 1.0)]
    windows = _run(trades, window_days=10).windows
    assert windows[0].trades == 1 and windows[0].total_r == pytest.approx(-5.0)
    assert windows[-1].trades == 2 and windows[-1].total_r == pytest.approx(2.0)


def test_unclosed_trades_are_ignored_entirely():
    trades = [_trade("a", 0, 1.0), _open_trade("x", 3), _trade("b", 9, 1.0)]
    window = _run(trades, window_days=10).windows[0]
    assert window.trades == 2


def test_a_shallow_drawdown_breaches_nothing():
    trades = [_trade("a", 0, -5.0), _trade("b", 5, 3.0), _trade("c", 9, 4.0)]
    window = _run(trades, window_days=10).windows[0]
    assert window.worst_drawdown_r == pytest.approx(5.0)
    assert window.worst_drawdown_pct == pytest.approx(5.0)
    assert not window.breached_max_drawdown


def test_the_floor_breach_is_inclusive_of_the_cap():
    # 1.0% risk x -10R = exactly -10.0%, the Phase-1 cap.
    window = _run([_trade("a", 0, -10.0), _trade("b", 9, 0.5)], window_days=10).windows[0]
    assert window.worst_drawdown_pct == pytest.approx(10.0)
    assert window.breached_max_drawdown


def test_one_r_short_of_the_cap_does_not_breach():
    window = _run([_trade("a", 0, -9.0), _trade("b", 9, 0.5)], window_days=10).windows[0]
    assert not window.breached_max_drawdown


def test_risk_per_trade_scales_the_drawdown_against_a_static_cap():
    trades = [_trade("a", 0, -10.0), _trade("b", 9, 0.5)]
    assert not _run(trades, risk_per_trade_pct=0.5, window_days=10).windows[0].breached_max_drawdown
    assert _run(trades, risk_per_trade_pct=1.5, window_days=10).windows[0].breached_max_drawdown


def test_the_floor_basis_ignores_a_dip_that_never_reaches_below_the_window_start():
    # +20R then -12R: never below the window's own starting balance.
    trades = [_trade("a", 0, 20.0), _trade("b", 5, -12.0), _trade("c", 9, 0.5)]
    window = _run(trades, window_days=10).windows[0]
    assert window.worst_drawdown_r == pytest.approx(0.0)
    assert not window.breached_max_drawdown


def test_the_peak_to_trough_basis_catches_that_same_dip():
    trades = [_trade("a", 0, 20.0), _trade("b", 5, -12.0), _trade("c", 9, 0.5)]
    window = _run(trades, window_days=10, drawdown_basis="peak_to_trough").windows[0]
    assert window.worst_drawdown_r == pytest.approx(12.0)
    assert window.breached_max_drawdown


def test_an_unknown_drawdown_basis_is_rejected():
    with pytest.raises(ValueError, match="drawdown_basis"):
        _run([_trade("a", 0, 1.0), _trade("b", 9, 1.0)], drawdown_basis="trailing")


def test_the_daily_loss_limit_is_measured_per_session_day():
    # -4R and -2R on the SAME day at 1.0% risk = -6.0%, past the 5% cap;
    # the same two losses on different days would not breach.
    same_day = [_trade("a", 0, -4.0), _trade("b", 0, -2.0), _trade("c", 9, 0.5)]
    spread = [_trade("a", 0, -4.0), _trade("b", 1, -2.0), _trade("c", 9, 0.5)]
    assert _run(same_day, window_days=10).windows[0].breached_daily_loss
    assert not _run(spread, window_days=10).windows[0].breached_daily_loss


def test_the_worst_daily_loss_is_reported_as_a_positive_percentage():
    window = _run([_trade("a", 0, -4.0), _trade("b", 9, 1.0)], window_days=10).windows[0]
    assert window.worst_daily_loss_pct == pytest.approx(4.0)


def test_fail_fractions_count_breaching_windows_over_all_windows():
    # Day 0 holds a -10R cluster, so only windows containing day 0 breach.
    trades = [_trade("a", 0, -10.0), _trade("b", 11, 1.0)]
    result = _run(trades, window_days=10)
    breaching = [w for w in result.windows if w.breached_max_drawdown]
    assert len(result.windows) == 3 and len(breaching) == 1
    assert result.fail_dd_fraction == pytest.approx(1 / 3)


def test_the_result_echoes_the_parameters_it_was_run_with():
    result = _run([_trade("a", 0, 1.0), _trade("b", 9, 1.0)], window_days=10)
    assert (result.risk_per_trade_pct, result.max_drawdown_pct, result.window_days) == (1.0, 10.0, 10)
    assert result.drawdown_basis == "initial_balance_floor"
