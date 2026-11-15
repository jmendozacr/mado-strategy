"""TDD tests for state.py's pure update logic (file IO is a thin wrapper,
not separately unit-tested here)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from state import record_alert, already_alerted  # noqa: E402


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
