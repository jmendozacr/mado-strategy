"""High-impact news calendar, sourced from ForexFactory's public weekly
JSON feed (free, no API key). Used only to ANNOTATE alerts with "near
high-impact news" context -- never to auto-suppress a signal, same
inform-don't-suppress design as the rest of the scanner. (FTMO's actual
2-minute restriction only applies to Standard funded accounts, never
during the Challenge/Verification evaluation -- see scanner's ODD tracking
doc for the citation.)
"""
from datetime import datetime, timezone

import requests

_FEED_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
_WINDOW_MINUTES = 2


def fetch_this_week_events() -> list[dict]:
    response = requests.get(_FEED_URL, timeout=10)
    response.raise_for_status()
    return response.json()


def is_near_high_impact_news(
    ts: datetime, events: list[dict], relevant_currencies: tuple[str, ...], window_minutes: int = _WINDOW_MINUTES,
) -> bool:
    """`ts` is naive, treated as UTC (matches the rest of the scanner's
    convention -- core.candle.Candle timestamps are naive UTC throughout)."""
    for event in events:
        if event["impact"] != "High":
            continue
        if event["country"] not in relevant_currencies:
            continue
        event_ts_utc = datetime.fromisoformat(event["date"]).astimezone(timezone.utc).replace(tzinfo=None)
        delta_seconds = abs((ts - event_ts_utc).total_seconds())
        if delta_seconds <= window_minutes * 60:
            return True
    return False
