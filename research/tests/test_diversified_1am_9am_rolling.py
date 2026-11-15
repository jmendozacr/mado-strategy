from datetime import datetime, timedelta

from core.candle import Candle, OHLCSeries

from backtest.simulate import Trade
from research.diversified_1am_9am_rolling import combined_rolling_window, monthly_breakdown, to_closed_trades

_START = datetime(2026, 1, 1, 15, 0)  # 15:00 UTC -> safely mid-day NY-local, same calendar day


def _series(n: int) -> OHLCSeries:
    candles = tuple(
        Candle(timestamp=_START + timedelta(minutes=15 * i), open=1.0, high=1.0, low=1.0, close=1.0)
        for i in range(n)
    )
    return OHLCSeries(candles=candles, instrument="X", timeframe="15M")


def _trade(signal_id, entry_index, exit_index, outcome, r_multiple):
    return Trade(
        signal_id=signal_id, anchor_index=entry_index, direction="bullish", entry_index=entry_index,
        entry_price=1.0, stop_loss=0.9, take_profit=1.1, exit_index=exit_index, exit_price=1.0,
        outcome=outcome, r_multiple=r_multiple, ambiguous_bar=False, gap_filled=False,
        partial_exit_index=None, partial_exit_price=None,
        partial_r_multiple=None, partial_gap_filled=False,
    )


def test_to_closed_trades_maps_bar_indices_to_real_timestamps():
    series = _series(10)
    trade = _trade("s1", entry_index=2, exit_index=5, outcome="win", r_multiple=1.5)

    closed = to_closed_trades([trade], series)

    assert len(closed) == 1
    assert closed[0].signal_id == "s1"
    assert closed[0].entry_time == series.candles[2].timestamp
    assert closed[0].exit_time == series.candles[5].timestamp
    assert closed[0].outcome == "win"
    assert closed[0].r_multiple == 1.5


def test_to_closed_trades_leaves_an_unresolved_trade_with_no_exit_time():
    series = _series(10)
    trade = _trade("s1", entry_index=2, exit_index=None, outcome="open", r_multiple=None)

    closed = to_closed_trades([trade], series)

    assert closed[0].exit_time is None
    assert closed[0].outcome == "open"


def test_combined_rolling_window_merges_every_symbol_into_one_account():
    """Two symbols, each with one win on a DIFFERENT real calendar day --
    the combined window must see both trades (2 trades, not 1), proving
    the merge actually happened rather than one symbol silently winning."""
    series_a = _series(5)
    series_b = OHLCSeries(
        candles=tuple(
            Candle(timestamp=_START + timedelta(days=1, minutes=15 * i), open=1.0, high=1.0, low=1.0, close=1.0)
            for i in range(5)
        ),
        instrument="Y", timeframe="15M",
    )
    trades_a = [_trade("a1", 0, 1, "win", 2.0)]
    trades_b = [_trade("b1", 0, 1, "win", 1.0)]

    result = combined_rolling_window(
        {"A": (trades_a, series_a), "B": (trades_b, series_b)},
        risk_per_trade_pct=1.0, max_drawdown_pct=10.0, window_days=2,
    )

    assert len(result.windows) > 0
    assert all(w.trades == 2 for w in result.windows)
    assert result.fail_dd_fraction == 0.0


def test_monthly_breakdown_groups_across_symbols_by_close_month():
    """A January win and a February loss, from DIFFERENT symbols, must
    land in two separate rows -- proves both the cross-symbol merge and
    the month grouping, not just one of them."""
    series_jan = _series(5)  # _START = 2026-01-01 15:00 UTC
    series_feb = OHLCSeries(
        candles=tuple(
            Candle(timestamp=datetime(2026, 2, 10, 15, 0) + timedelta(minutes=15 * i), open=1.0, high=1.0, low=1.0, close=1.0)
            for i in range(5)
        ),
        instrument="Y", timeframe="15M",
    )
    trades_jan = [_trade("a1", 0, 1, "win", 2.0)]
    trades_feb = [_trade("b1", 0, 1, "loss", -1.0)]

    rows = monthly_breakdown(
        {"A": (trades_jan, series_jan), "B": (trades_feb, series_feb)},
        risk_per_trade_pct=1.0, initial_balance=10000.0,
    )

    assert rows == [
        {"year": 2026, "month": 1, "trades": 1, "win_rate": 1.0, "total_r": 2.0, "dollar_pnl": 200.0},
        {"year": 2026, "month": 2, "trades": 1, "win_rate": 0.0, "total_r": -1.0, "dollar_pnl": -100.0},
    ]
