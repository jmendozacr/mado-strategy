"""TDD tests for state.py's pure update logic (file IO is a thin wrapper,
not separately unit-tested here)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from state import record_alert, already_alerted, record_pending_partial, clear_pending_partial  # noqa: E402


def test_fresh_state_has_nothing_alerted():
    state = {"alerted_ids": [], "daily_counts": {}}
    assert not already_alerted(state, "A")


def test_record_alert_marks_it_alerted():
    state = {"alerted_ids": [], "daily_counts": {}}
    state = record_alert(state, "A", "EURUSDm", "2026-10-17")
    assert already_alerted(state, "A")


def test_record_alert_increments_daily_count_for_that_symbol_and_day():
    state = {"alerted_ids": [], "daily_counts": {}}
    state = record_alert(state, "A", "EURUSDm", "2026-10-17")
    state = record_alert(state, "B", "EURUSDm", "2026-10-17")
    state = record_alert(state, "C", "GBPUSDm", "2026-10-17")
    assert state["daily_counts"]["2026-10-17"]["EURUSDm"] == 2
    assert state["daily_counts"]["2026-10-17"]["GBPUSDm"] == 1


def test_daily_count_is_scoped_per_day():
    state = {"alerted_ids": [], "daily_counts": {}}
    state = record_alert(state, "A", "EURUSDm", "2026-10-17")
    state = record_alert(state, "B", "EURUSDm", "2026-10-18")
    assert state["daily_counts"]["2026-10-17"]["EURUSDm"] == 1
    assert state["daily_counts"]["2026-10-18"]["EURUSDm"] == 1


def test_record_pending_partial_adds_a_new_tracked_ticket():
    """odd/tasks/scanner-breakeven-after-partial.md T2: each tracked
    ticket carries everything main.py needs on later polls to detect the
    partial and move the remainder's stop -- never re-fetched from MT5."""
    state = {"alerted_ids": [], "daily_counts": {}, "pending_partial": {}}
    state = record_pending_partial(state, "12345", {
        "symbol": "EURUSD", "direction": "bullish", "partial_price": 1.1050,
        "stop_loss": 1.0984, "take_profit": 1.1100, "volume": 0.5,
    })
    assert state["pending_partial"]["12345"]["symbol"] == "EURUSD"
    assert state["pending_partial"]["12345"]["partial_price"] == 1.1050


def test_clear_pending_partial_removes_the_ticket():
    state = {"alerted_ids": [], "daily_counts": {}, "pending_partial": {
        "12345": {"symbol": "EURUSD", "direction": "bullish", "partial_price": 1.1050,
                  "stop_loss": 1.0984, "take_profit": 1.1100, "volume": 0.5},
    }}
    state = clear_pending_partial(state, "12345")
    assert "12345" not in state["pending_partial"]


def test_clear_pending_partial_is_a_no_op_for_an_unknown_ticket():
    """Idempotent: a poll that races with another clear (or retries after
    a partial transient error) must never raise on an already-cleared
    ticket."""
    state = {"alerted_ids": [], "daily_counts": {}, "pending_partial": {}}
    state = clear_pending_partial(state, "does-not-exist")
    assert state["pending_partial"] == {}


def test_record_and_clear_never_mutate_the_input_state():
    original = {"alerted_ids": [], "daily_counts": {}, "pending_partial": {}}
    record_pending_partial(original, "1", {
        "symbol": "EURUSD", "direction": "bullish", "partial_price": 1.1,
        "stop_loss": 1.0, "take_profit": 1.2, "volume": 0.1,
    })
    assert original["pending_partial"] == {}
