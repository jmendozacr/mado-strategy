"""EXPERIMENTAL: of the FVGs `primitives.fvg.detect_fvgs` detects, how
many are actually followed by a real structural break (`composite.mss
.MSSEvent`, same direction) before they fill? Mirrors
`experimental.order_block_structural_break_check`'s exact question and
boundary conventions (right-closed at fill, same as the OB's
invalidation), applied to FVG instead -- motivated by the FVG-dominance
finding (`sdd/crt-detector-order-block-redefinition/backtest-null-result`):
FVG supplies ~98% of all Key Level credits, so its own structural quality
-- never measured until now -- matters far more than any other source's.

A parallel module rather than a shared one with the OB check: `FVG`'s
field names genuinely differ (`end_index`/`fill_index`, not
`confirmation_index`/`invalidation_index`), and the function is small
enough that forcing a shared abstraction across two different field
shapes would cost more than it saves.

Not a change to anything: reuses `detect_fvgs` and `composite.mss
.detect_mss_events` unmodified, zero production files touched.
"""
from __future__ import annotations

from composite.mss import MSSEvent
from primitives.fvg import FVG

__all__ = ["fvg_followed_by_real_break", "summarize"]


def fvg_followed_by_real_break(fvg: FVG, mss_events: list[MSSEvent]) -> bool:
    """`True` when a same-direction MSS event occurs strictly after the
    FVG forms (`index > fvg.end_index`, the same index
    `primitives.fvg.to_key_levels` already uses as the Key Level's own
    `origin_index`) and at-or-before it fills (right-closed, mirroring the
    OB check's invalidation boundary) -- an open (never-filled) FVG has no
    upper bound."""
    upper_bound = fvg.fill_index
    return any(
        event.direction == fvg.direction
        and event.index > fvg.end_index
        and (upper_bound is None or event.index <= upper_bound)
        for event in mss_events
    )


def summarize(fvgs: list[FVG], mss_events: list[MSSEvent]) -> dict[str, int | float]:
    followed = sum(1 for fvg in fvgs if fvg_followed_by_real_break(fvg, mss_events))
    return {
        "total_fvgs": len(fvgs),
        "fvgs_followed_by_real_break": followed,
        "fraction": followed / len(fvgs) if fvgs else 0.0,
    }
