"""EXPERIMENTAL check: of the Order Blocks `primitives.ict_order_block`
detects, how many are actually followed by a real structural break (an
`composite.mss.MSSEvent`, same direction) before they invalidate?

**Why this exists.** `detect_ict_order_blocks` is a pure 2-candle
engulfment test (REQ-61) -- it has no notion of "impulse" or "break of
structure" at all, unlike how a discretionary trader marks an Order Block
(the last opposite candle before a move that actually breaks structure).
This measures the gap between the two: a candle-pattern OB is a real Key
Level candidate only if a genuine MSS later confirms the zone actually
mattered.

Not a change to anything: reuses `detect_ict_order_blocks` and
`detect_mss_events` unmodified, zero production files touched.
"""
from __future__ import annotations

from composite.mss import MSSEvent
from primitives.ict_order_block import ICTOrderBlock

__all__ = ["ob_followed_by_real_break", "summarize"]


def ob_followed_by_real_break(ob: ICTOrderBlock, mss_events: list[MSSEvent]) -> bool:
    """`True` when a same-direction MSS event occurs strictly after this
    OB formed (`index > ob.confirmation_index`) and at-or-before it
    invalidates (right-closed, mirroring `KeyLevel.expiry_index`'s own
    boundary convention) -- an open (never-invalidated) OB has no upper
    bound, matching how it stays a live Key Level for the rest of the
    series."""
    upper_bound = ob.invalidation_index if ob.invalidation_index is not None else None
    return any(
        event.direction == ob.direction
        and event.index > ob.confirmation_index
        and (upper_bound is None or event.index <= upper_bound)
        for event in mss_events
    )


def summarize(
    obs: list[ICTOrderBlock], mss_events: list[MSSEvent]
) -> dict[str, int | float]:
    followed = sum(1 for ob in obs if ob_followed_by_real_break(ob, mss_events))
    return {
        "total_obs": len(obs),
        "obs_followed_by_real_break": followed,
        "fraction": followed / len(obs) if obs else 0.0,
    }
