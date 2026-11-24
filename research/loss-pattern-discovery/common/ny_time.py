"""New York local-time conversion for broker-UTC timestamps.

`data/*.csv` timestamps are broker time, independently confirmed by a prior,
separate investigation in this repo
(`openspec/changes/archive/crt-detector-htf-timezone-anchor/triage.md`) to be
a fixed UTC+0 grid with no DST of its own. New York's OWN daylight-saving
calendar (EST = UTC-5 in winter, EDT = UTC-4 in summer, transitioning per the
IANA `America/New_York` zone) is a SEPARATE clock from the broker's fixed
one. This module converts broker-UTC timestamps to true NY wall-clock time
using the stdlib `zoneinfo` database (no new dependency) -- never a
hand-rolled DST rule, which is exactly the kind of assumption Phase 3 was
asked not to repeat.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

UTC = ZoneInfo("UTC")
NY = ZoneInfo("America/New_York")


def to_ny(ts: datetime) -> datetime:
    """Convert one naive broker-UTC timestamp to aware NY local time."""
    return ts.replace(tzinfo=UTC).astimezone(NY)


def ny_hour_of_day(ts: datetime) -> float:
    ny = to_ny(ts)
    return ny.hour + ny.minute / 60.0


def ny_hours_of_day_bulk(timestamps: list[datetime]) -> list[float]:
    """Vectorized NY-hour-of-day for many timestamps at once (pandas-backed
    tz conversion) -- fast enough to build a control candidate pool from a
    multi-year, ~100k-bar M15 slice; a per-timestamp `to_ny` loop over that
    many bars would be the same class of O(n)-per-call cost Phase 2 already
    had to fix once in `common/series_index.py`."""
    if not timestamps:
        return []
    series = pd.to_datetime(pd.Series(timestamps)).dt.tz_localize("UTC").dt.tz_convert(NY)
    return (series.dt.hour + series.dt.minute / 60.0).tolist()


def circular_hour_distance(a: float, b: float) -> float:
    """Distance between two hour-of-day values on a 24h clock, wrapping at
    midnight (e.g. 23.5 and 0.5 are 1.0 apart, not 23.0)."""
    diff = abs(a - b) % 24
    return min(diff, 24 - diff)
