"""The one trade record this research package passes between its stages --
RESEARCH TOOLING, not a production entry point, never imported by any
module under `detector/`.

`backtest.simulate.Trade` carries bar INDICES, which are only meaningful
together with the `OHLCSeries` they were produced from. The rolling-window
sizing simulator needs calendar dates, and the two gating rules need both
(indices to decide overlap, timestamps to decide the session day). Rather
than thread the series through every stage, `pipeline.resolve_trades`
flattens a `Trade` + its series into this record once, and every stage
below works on it -- which is also what makes those stages testable without
loading a single CSV.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

_UTC = ZoneInfo("UTC")
_NY = ZoneInfo("America/New_York")

Outcome = Literal["win", "loss", "open"]

# The validated recipe's London+Lunch+NY window, NY-local -- the same bounds
# as the live scanner's `rules._in_session`.
RECIPE_SESSION_START_HOUR = 2
RECIPE_SESSION_END_HOUR = 11


@dataclass(frozen=True)
class ClosedTrade:
    """One simulated trade. Named for the common case, but an unresolved
    trade is representable too (`exit_index`/`exit_time`/`r_multiple` all
    None, `outcome="open"`) because the gating rules still have to account
    for the capital it ties up."""

    signal_id: str
    direction: str
    entry_index: int
    exit_index: int | None
    entry_time: datetime
    exit_time: datetime | None
    outcome: Outcome
    r_multiple: float | None


def session_day(timestamp: datetime) -> date:
    """The NY-local calendar date a UTC-naive bar timestamp falls on.

    Same convention as `core.kill_zone.in_ny_kill_zone` (reused verbatim
    rather than re-derived): series timestamps are UTC wall-clock, and the
    NY boundary is resolved through real `America/New_York` DST rules, not
    a fixed offset.
    """
    return timestamp.replace(tzinfo=_UTC).astimezone(_NY).date()


def ny_hour(timestamp: datetime) -> int:
    """The NY-local hour-of-day a UTC-naive bar timestamp falls in -- the
    unit every session window in this package is expressed in."""
    return timestamp.replace(tzinfo=_UTC).astimezone(_NY).hour


def in_recipe_session(timestamp: datetime) -> bool:
    """The validated recipe's London+Lunch+NY window, 02:00-11:00 NY-local.

    Byte-for-byte the same test as the live scanner's `rules._in_session`
    (`scanner/rules.py`), restated here only because `scanner/` is not an
    importable package from this directory -- the rule itself is copied,
    never re-derived, and `tests/test_trades.py` pins them to agree.
    """
    return RECIPE_SESSION_START_HOUR <= ny_hour(timestamp) < RECIPE_SESSION_END_HOUR


def ordered(trades) -> list[ClosedTrade]:
    """`(entry_index, signal_id)`, the same total order `backtest.simulate`
    already sorts its own output by. Both gating rules are sequential and
    path-dependent, so an unordered input would silently change which
    trades they admit; sorting defensively here makes every stage's result
    independent of how the caller happened to accumulate the list."""
    return sorted(trades, key=lambda t: (t.entry_index, t.signal_id))
