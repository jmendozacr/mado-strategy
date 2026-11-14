"""Redefined ICT Order Block detector -- structural, not a bare 2-candle
engulfment test. Composes the order-block-redefinition chain
(`odd/tasks/detector-order-block-redefinition.md`, S2-S6, T4):

    Market Structure (swing high/low) -> BOS -> Displacement ->
    backward scan for the last opposing candle = the Order Block.

BOS reuses `composite.mss.detect_mss_events` UNMODIFIED (S3): the
decisive close-based break it already detects is exactly the BOS
confirmation this change's own product decision picked, so no new
wick-confirmation mode was needed. `primitives.swing.classify_trend`
(Market Structure's HH/HL/LH/LL labels) is available but not consumed
here -- MSS's own last-high/last-low tracking already supplies the
"broke the most recent opposite swing" mechanism the chain needs; the
labels are descriptive context, not a computational dependency, and
wiring them in is deferred rather than smuggled into this walking
skeleton.

Not wired into `cli.py`/production: this is the walking-skeleton proof
(S8) that the mechanism works on real data before the archived,
signed-spec detector it is meant to REPLACE gets touched -- see the
feature doc for why that swap is a separate, later, higher-risk step.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from core.candle import Candle, OHLCSeries
from core.key_level import KeyLevel
from primitives.swing import SwingPoint, detect_swings

from composite.displacement import confirm_displacement
from composite.mss import MSSEvent, detect_mss_events
from composite.order_block_scan import scan_for_anchor

Direction = Literal["bullish", "bearish"]
Status = Literal["active", "mitigated", "invalidated"]

_LOOKBACK_CANDLES = 20  # S5: Model1Config.max_retest_lookback's existing precedent


@dataclass(frozen=True)
class ICTOrderBlock:
    anchor_index: int
    break_index: int
    confirmation_index: int
    direction: Direction
    top: float
    bottom: float
    status: Status
    mitigation_index: int | None = None
    invalidation_index: int | None = None


def detect_order_blocks(
    series: OHLCSeries,
    swings: list[SwingPoint] | None = None,
    mss_events: list[MSSEvent] | None = None,
) -> list[ICTOrderBlock]:
    """`swings`/`mss_events` let a caller that already computed them for
    the same series reuse them, matching the `crt_ranges`/`fvgs` reuse
    pattern elsewhere in this codebase. `None` self-computes both."""
    candles = series.candles
    if swings is None:
        swings = detect_swings(series)
    if mss_events is None:
        mss_events = detect_mss_events(series, swings=swings)

    blocks = []
    for event in mss_events:
        confirmation_index = confirm_displacement(candles, event.index, event.direction)
        if confirmation_index is None:
            continue
        anchor_index = scan_for_anchor(
            candles, event.index, event.direction, lookback=_LOOKBACK_CANDLES
        )
        if anchor_index is None:
            continue
        anchor = candles[anchor_index]
        top, bottom = anchor.high, anchor.low
        mitigation_index, invalidation_index = _resolve_lifecycle(
            candles, confirmation_index, event.direction, top, bottom
        )
        status: Status = (
            "invalidated" if invalidation_index is not None
            else "mitigated" if mitigation_index is not None
            else "active"
        )
        blocks.append(
            ICTOrderBlock(
                anchor_index=anchor_index, break_index=event.index,
                confirmation_index=confirmation_index, direction=event.direction,
                top=top, bottom=bottom, status=status,
                mitigation_index=mitigation_index, invalidation_index=invalidation_index,
            )
        )
    return blocks


def _resolve_lifecycle(
    candles: tuple[Candle, ...],
    confirmation_index: int,
    direction: Direction,
    top: float,
    bottom: float,
) -> tuple[int | None, int | None]:
    """Forward scan from `confirmation_index + 1` (S6: the zone is not
    live before it is provably knowable). Mitigation (S4, touch: any
    wick overlap) is recorded on first occurrence; invalidation (S4,
    close beyond the zone) ends the scan -- a candle that both touches
    and closes beyond in the same bar reports the same index for both."""
    mitigation_index: int | None = None
    for index in range(confirmation_index + 1, len(candles)):
        candle = candles[index]
        if mitigation_index is None and candle.low <= top and candle.high >= bottom:
            mitigation_index = index
        invalidated = (
            (direction == "bullish" and candle.close < bottom)
            or (direction == "bearish" and candle.close > top)
        )
        if invalidated:
            return mitigation_index, index
    return mitigation_index, None


def to_key_levels(blocks: list[ICTOrderBlock]) -> list[KeyLevel]:
    """`origin_index` = `confirmation_index` (S6: first provably-knowable
    index, never the anchor candle's own index -- SEAM-02's convention).
    `expiry_index` = `invalidation_index`; mitigation does not end a
    level's validity, only invalidation does."""
    return [
        KeyLevel(
            kind="ict_order_block", top=b.top, bottom=b.bottom,
            origin_index=b.confirmation_index, expiry_index=b.invalidation_index,
        )
        for b in blocks
    ]
