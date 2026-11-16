"""TDD for main._check_pending_partials -- odd/tasks/scanner-breakeven-
after-partial.md T4. Each poll's pass over tracked tickets: detect fill,
detect the partial price touch, close half, move the remainder's SL to
breakeven, stop tracking."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "detector"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main  # noqa: E402


def _tracked_state(ticket="777001"):
    return {"alerted_ids": [], "daily_counts": {}, "pending_partial": {
        ticket: {
            "symbol": "EURUSD", "direction": "bullish", "entry_price": 1.1000,
            "stop_loss": 1.0984, "take_profit": 1.1100, "partial_price": 1.1050, "volume": 0.5,
        },
    }}


class _FakePosition:
    volume = 0.5


class _FakeResult:
    retcode = 10009
    order = 0


def test_partial_reached_closes_half_and_moves_sl_to_breakeven(monkeypatch):
    monkeypatch.setattr(main.mt5_feed, "get_open_position", lambda ticket: _FakePosition())
    monkeypatch.setattr(main.mt5_feed, "current_exit_price", lambda symbol, direction: 1.1055)  # past partial_price
    monkeypatch.setattr(main.mt5_feed, "symbol_trade_specs", lambda symbol: {
        "volume_step": 0.01, "volume_min": 0.01,
    })
    monkeypatch.setattr(main.mt5_feed, "order_succeeded", lambda result: result.retcode == 10009)

    close_calls = []
    monkeypatch.setattr(
        main.mt5_feed, "close_partial_position",
        lambda ticket, symbol, direction, volume: (close_calls.append((ticket, symbol, direction, volume)), _FakeResult())[1],
    )
    sltp_calls = []
    monkeypatch.setattr(
        main.mt5_feed, "modify_stop_loss",
        lambda ticket, symbol, new_sl, take_profit: (sltp_calls.append((ticket, symbol, new_sl, take_profit)), _FakeResult())[1],
    )

    result_state = main._check_pending_partials(_tracked_state())

    assert close_calls == [(777001, "EURUSD", "bullish", 0.25)]  # 0.5 * 0.5 partial_fraction
    assert sltp_calls == [(777001, "EURUSD", 1.1000, 1.1100)]  # new_sl == entry_price, breakeven
    assert "777001" not in result_state["pending_partial"]


def test_partial_not_yet_reached_keeps_tracking_and_takes_no_action(monkeypatch):
    monkeypatch.setattr(main.mt5_feed, "get_open_position", lambda ticket: _FakePosition())
    monkeypatch.setattr(main.mt5_feed, "current_exit_price", lambda symbol, direction: 1.1020)  # below partial_price

    close_calls = []
    monkeypatch.setattr(main.mt5_feed, "close_partial_position", lambda *a, **k: close_calls.append(a))

    result_state = main._check_pending_partials(_tracked_state())

    assert close_calls == []
    assert "777001" in result_state["pending_partial"]


def test_expired_or_cancelled_order_clears_tracking(monkeypatch):
    """Neither a pending order nor an open position exists for the
    ticket -- it expired, was cancelled, or (rare) closed before any
    partial fired. Stop tracking rather than checking forever."""
    monkeypatch.setattr(main.mt5_feed, "get_open_position", lambda ticket: None)
    monkeypatch.setattr(main.mt5_feed, "get_pending_order", lambda ticket: None)

    result_state = main._check_pending_partials(_tracked_state())

    assert "777001" not in result_state["pending_partial"]


def test_still_pending_order_keeps_tracking(monkeypatch):
    """The order hasn't filled yet -- no position, but the order itself
    is still live on the book. Keep waiting, don't clear."""
    monkeypatch.setattr(main.mt5_feed, "get_open_position", lambda ticket: None)
    monkeypatch.setattr(main.mt5_feed, "get_pending_order", lambda ticket: object())

    result_state = main._check_pending_partials(_tracked_state())

    assert "777001" in result_state["pending_partial"]


def test_too_small_to_split_clears_tracking_without_closing_anything(monkeypatch):
    monkeypatch.setattr(main.mt5_feed, "get_open_position", lambda ticket: _FakePosition())
    monkeypatch.setattr(main.mt5_feed, "current_exit_price", lambda symbol, direction: 1.1055)
    monkeypatch.setattr(main.mt5_feed, "symbol_trade_specs", lambda symbol: {
        "volume_step": 0.01, "volume_min": 1.0,  # 0.5-lot position can't clear a 1.0-lot minimum split
    })

    close_calls = []
    monkeypatch.setattr(main.mt5_feed, "close_partial_position", lambda *a, **k: close_calls.append(a))

    result_state = main._check_pending_partials(_tracked_state())

    assert close_calls == []
    assert "777001" not in result_state["pending_partial"]
