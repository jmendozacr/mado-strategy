"""TDD tests for news_calendar.py's pure matching logic (the HTTP fetch is
a thin wrapper, not unit-tested here -- verified once with a real call)."""
import sys
from datetime import datetime

sys.path.insert(0, r"D:\Josué\Documents\proyectos\mado-strategy\scanner")

from news_calendar import is_near_high_impact_news  # noqa: E402


def _event(title, country, iso_date, impact):
    return {"title": title, "country": country, "date": iso_date, "impact": impact}


def test_within_window_before_event_is_near():
    events = [_event("CPI m/m", "USD", "2026-10-19T12:30:00+00:00", "High")]
    ts = datetime(2026, 10, 19, 12, 29, 0)  # 1 minute before, UTC naive
    assert is_near_high_impact_news(ts, events, relevant_currencies=("USD", "EUR"))


def test_within_window_after_event_is_near():
    events = [_event("CPI m/m", "USD", "2026-10-19T12:30:00+00:00", "High")]
    ts = datetime(2026, 10, 19, 12, 31, 30)  # 1.5 minutes after
    assert is_near_high_impact_news(ts, events, relevant_currencies=("USD", "EUR"))


def test_outside_window_is_not_near():
    events = [_event("CPI m/m", "USD", "2026-10-19T12:30:00+00:00", "High")]
    ts = datetime(2026, 10, 19, 12, 35, 0)  # 5 minutes after -> outside 2min window
    assert not is_near_high_impact_news(ts, events, relevant_currencies=("USD", "EUR"))


def test_low_impact_event_never_counts():
    events = [_event("Retail Sales", "USD", "2026-10-19T12:30:00+00:00", "Low")]
    ts = datetime(2026, 10, 19, 12, 30, 0)
    assert not is_near_high_impact_news(ts, events, relevant_currencies=("USD", "EUR"))


def test_irrelevant_currency_never_counts():
    events = [_event("Employment Change", "AUD", "2026-10-19T12:30:00+00:00", "High")]
    ts = datetime(2026, 10, 19, 12, 30, 0)
    assert not is_near_high_impact_news(ts, events, relevant_currencies=("USD", "EUR"))


def test_timezone_offset_is_normalized_to_utc():
    # event at 08:30 EDT (-04:00) == 12:30 UTC
    events = [_event("CPI m/m", "USD", "2026-10-19T08:30:00-04:00", "High")]
    ts = datetime(2026, 10, 19, 12, 30, 0)  # naive UTC
    assert is_near_high_impact_news(ts, events, relevant_currencies=("USD",))
