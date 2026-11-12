"""HTF-first Turtle Soup + Key Level trigger (odd/tasks/htf-turtle-soup-trigger.md
S1-S6): scoped to the 9:00 NY model only. The broker's H4 series is a fixed-UTC
grid (00/04/08/12/16/20 UTC) that never literally opens a candle at 09:00 NY
(13:00 UTC in EDT, 14:00 UTC in EST) -- both fall inside the 12:00 UTC
candle's own window, so that candle (and its array-adjacent predecessor, the
08:00 UTC candle) stands in for "the 9am model's HTF candle" and "the
previous HTF candle" (S6), rather than building a new NY-anchored synthetic
4H aggregation.

A genuine same-candle Turtle Soup (wick beyond the previous candle's high/low,
close back inside it) is NOT expressible via `primitives.crt_range`/`_resolve`
-- verified before building: `_resolve`'s `"false_break"` can never fire at
`resolved_offset == 1` (its false_break check only looks at a `poke_side` set
on a PRIOR iteration), so a single candle that both pokes and closes back is
classified `None` (unresolved), not `false_break`. This module checks the
candle pair directly instead, then feeds a hand-built `CRTRange` (bounds =
the previous candle's own high/low) into the existing, UNCHANGED key-level
crediting functions (`_key_level_credit_map`/`_purge_reaction`) so that part
of the logic is reused verbatim, not reimplemented.

S1's "mientras estoy tocando un key level" is part of the trigger condition,
not optional: a candle that Turtle-Soups the previous one but touches no
registered Key Level is not reported as a trigger at all.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from alignment.htf_ltf import _key_level_credit_map, _purge_reaction
from core.candle import Candle
from core.config import Model1Config
from core.key_level import KeyLevel
from core.results import DetectionStatus
from entries.model1 import Direction, Model1Signal, _track_anchor
from primitives.crt_range import CRTRange, first_breach_index

_TRIGGER_UTC_HOUR = 12  # the H4 candle whose [12:00, 16:00) UTC window contains 09:00-10:30 NY in both DST states
_UTC = ZoneInfo("UTC")
_NY = ZoneInfo("America/New_York")
_WINDOW_START_HOUR_NY = 9  # S4: the 9:00/NY model only
_WINDOW_DURATION = timedelta(hours=1, minutes=30)  # S4: 1.5h, verified against charter-11's own windows


@dataclass(frozen=True)
class HTFTrigger:
    candle_index: int
    direction: Direction
    key_level: KeyLevel
    key_level_reaction: Literal["reject_close_inside", "continuation"]


def find_9am_turtle_soup_triggers(
    htf_candles: tuple[Candle, ...], key_levels: list[KeyLevel]
) -> list[HTFTrigger]:
    """One entry per qualifying 12:00 UTC candle: a same-candle Turtle Soup of
    the immediately preceding (08:00 UTC) candle, AND a credited Key Level
    touch on that same candle (S1, S2). Both directions are checked
    independently (an outside-bar candle that sweeps both sides can produce
    two triggers, mirroring this project's existing outside-bar handling in
    `composite.order_flow`) -- no retry/lookback beyond this one candle pair
    (S3): a candle that merely closes beyond the previous candle's range (a
    continuation, not a rejection) never triggers, and nothing here looks
    further back or forward to compensate.
    """
    triggers: list[HTFTrigger] = []
    for i in range(1, len(htf_candles)):
        candle = htf_candles[i]
        if candle.timestamp.hour != _TRIGGER_UTC_HOUR or candle.timestamp.minute != 0:
            continue
        prev = htf_candles[i - 1]

        for direction, swept in (
            ("bearish", candle.high > prev.high and candle.close <= prev.high),
            ("bullish", candle.low < prev.low and candle.close >= prev.low),
        ):
            if not swept:
                continue
            crt_range = CRTRange(
                model="2-candle", high=prev.high, low=prev.low,
                start_index=i - 1, end_index=i, resolution="false_break", resolved_at_index=i,
            )
            key_level = _key_level_credit_map(htf_candles, {i: crt_range}, key_levels).get(i)
            if key_level is None:
                continue
            reaction = _purge_reaction(candle, crt_range)
            triggers.append(
                HTFTrigger(candle_index=i, direction=direction, key_level=key_level, key_level_reaction=reaction)
            )
    return triggers


def confirmation_window_utc(trigger_candle: Candle) -> tuple[datetime, datetime]:
    """S4: 09:00-10:30 NY-local, DST-aware, on the trigger candle's own NY
    calendar day -- returned as naive UTC wall-clock timestamps (the same
    convention `Candle.timestamp` already uses throughout this codebase).
    """
    ny_day = trigger_candle.timestamp.replace(tzinfo=_UTC).astimezone(_NY).date()
    window_start_ny = datetime(ny_day.year, ny_day.month, ny_day.day, _WINDOW_START_HOUR_NY, tzinfo=_NY)
    window_end_ny = window_start_ny + _WINDOW_DURATION
    return (
        window_start_ny.astimezone(_UTC).replace(tzinfo=None),
        window_end_ny.astimezone(_UTC).replace(tzinfo=None),
    )


def ltf_window_indices(
    ltf_candles: tuple[Candle, ...], window_start_utc: datetime, window_end_utc: datetime
) -> tuple[int, int] | None:
    """The `[start, end]` LTF candle index range (inclusive both ends)
    falling inside `[window_start_utc, window_end_utc)`. `None` if no LTF
    candle falls inside the window at all."""
    start_index: int | None = None
    end_index: int | None = None
    for i, candle in enumerate(ltf_candles):
        if window_start_utc <= candle.timestamp < window_end_utc:
            if start_index is None:
                start_index = i
            end_index = i
    if start_index is None:
        return None
    return (start_index, end_index)


def confirm_in_ltf_window(
    ltf_candles: tuple[Candle, ...],
    ltf_ranges: list[CRTRange],
    window: tuple[int, int],
    direction: Direction,
    config: Model1Config,
) -> Model1Signal | None:
    """S1's "buscamos la confirmación en 15m con lo que tenemos": the
    existing Model-1 anchor/confirm/retest machinery, reused as-is, applied
    only to the earliest LTF anchor (across all `ltf_ranges`) that falls
    inside `window` and matches `direction` -- picking the winner is a
    smaller version of `causal.signals.causal_purge_engulf_signals`'
    R-strict dedup (earliest anchor wins, tie-break lowest `start_index`),
    not a new rule.

    The retry-on-invalidation stepping mirrors `causal.retry_chain.
    chained_purge_engulf_signal`, but its stop condition is different (S3):
    there is no HTF range left to re-check for a `true_break` here -- the
    HTF event already resolved, once, as the trigger itself. Instead, every
    `_track_anchor` call is run against `ltf_candles` TRUNCATED to `window`'s
    own end -- so nothing past the window can ever be seen, confirmed, or
    retried into, by construction (no separate bounds check needed: a chain
    that reaches the window's last candle finds an empty scan range on its
    next retry and naturally returns `None`).
    """
    start_idx, end_idx = window
    truncated = ltf_candles[: end_idx + 1]

    candidates: list[tuple[int, CRTRange]] = []
    for ltf_range in ltf_ranges:
        resolved_at = min(ltf_range.resolved_at_index, end_idx)
        if ltf_range.start_index >= resolved_at:
            continue
        anchor_index = (
            first_breach_index(truncated, ltf_range.start_index, resolved_at, high=ltf_range.high)
            if direction == "bearish"
            else first_breach_index(truncated, ltf_range.start_index, resolved_at, low=ltf_range.low)
        )
        if anchor_index is not None and start_idx <= anchor_index <= end_idx:
            candidates.append((anchor_index, ltf_range))
    if not candidates:
        return None
    candidates.sort(key=lambda pair: (pair[0], pair[1].start_index))
    current_anchor, winning_range = candidates[0]
    purge_target = winning_range.high if direction == "bearish" else winning_range.low
    origin_index = winning_range.start_index

    while True:
        result = _track_anchor(truncated, current_anchor, direction, purge_target, "purge_engulf", config, origin_index)
        if result is None or result.status != DetectionStatus.INVALIDATED:
            return result
        current_anchor = result.confirmation_index
