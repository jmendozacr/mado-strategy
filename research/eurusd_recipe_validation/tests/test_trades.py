import importlib.util
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from research.eurusd_recipe_validation.trades import ClosedTrade, in_recipe_session, ordered, session_day

_SCANNER_RULES = Path(__file__).resolve().parents[3] / "scanner" / "rules.py"


def _live_scanner_rules():
    """Loads `scanner/rules.py` by path. `scanner/` is a flat script
    directory, not an importable package from here, so there is no import
    that would reach it -- and copying its session test into this package
    is exactly the kind of duplication that silently drifts, which is what
    this module exists to prevent."""
    spec = importlib.util.spec_from_file_location("_live_scanner_rules", _SCANNER_RULES)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_live_scanner_rules_module_is_where_this_package_expects_it():
    assert _SCANNER_RULES.is_file(), f"expected the live scanner's rules at {_SCANNER_RULES}"


def test_the_research_session_rule_agrees_with_the_live_scanner_hour_by_hour():
    """Covers both DST transitions and every hour of the clock -- if the
    live recipe's session window is ever changed, this fails instead of the
    comparison silently measuring a window the scanner no longer trades."""
    live = _live_scanner_rules()
    timestamp = datetime(2024, 1, 1, 0, 0)
    end = datetime(2026, 1, 1, 0, 0)
    while timestamp < end:
        assert in_recipe_session(timestamp) == live._in_session(timestamp), timestamp
        timestamp += timedelta(hours=1)


@pytest.mark.parametrize(
    "utc_hour, expected_offset_days",
    [(12, 0), (4, 0), (3, -1), (1, -1), (23, 0)],
)
def test_session_day_resolves_the_ny_local_calendar_date(utc_hour, expected_offset_days):
    # 2024-06-10 is EDT (UTC-4): 03:00 UTC is still 23:00 on 2024-06-09 in
    # New York, and 04:00 UTC is the first hour of 2024-06-10 there.
    timestamp = datetime(2024, 6, 10, utc_hour)
    assert session_day(timestamp) == (timestamp.date() + timedelta(days=expected_offset_days))


def test_session_day_follows_real_dst_rules_rather_than_a_fixed_offset():
    # 03:00 UTC is 22:00 the previous day under EST (UTC-5) but 23:00 the
    # same previous day under EDT (UTC-4) -- both land on the day before.
    assert session_day(datetime(2024, 1, 15, 3)) == datetime(2024, 1, 14).date()
    assert session_day(datetime(2024, 7, 15, 3)) == datetime(2024, 7, 14).date()
    # 04:00 UTC crosses midnight under EDT but not under EST.
    assert session_day(datetime(2024, 1, 15, 4)) == datetime(2024, 1, 14).date()
    assert session_day(datetime(2024, 7, 15, 4)) == datetime(2024, 7, 15).date()


def test_ordered_sorts_by_entry_index_then_signal_id():
    def trade(signal_id, entry_index):
        return ClosedTrade(
            signal_id=signal_id, direction="bullish", entry_index=entry_index, exit_index=entry_index + 1,
            entry_time=datetime(2024, 1, 1, 12), exit_time=datetime(2024, 1, 1, 13),
            outcome="win", r_multiple=1.0,
        )

    shuffled = [trade("z", 5), trade("b", 1), trade("a", 5), trade("c", 1)]
    assert [t.signal_id for t in ordered(shuffled)] == ["b", "c", "a", "z"]
