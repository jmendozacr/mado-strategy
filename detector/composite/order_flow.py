from dataclasses import dataclass
from typing import Literal

from core.candle import Candle, OHLCSeries
from core.config import OrderFlowConfig
from primitives.swing import SwingPoint, detect_swings

__all__ = ["OrderFlowEvent", "detect_order_flow_events"]

# NOT reused from `composite/mss.py::detect_mss_events`, despite the
# superficial similarity (both are a forward pass over swings pairing a
# broken/rejected level with an opposite-kind reference):
#   - `decisive_close_ratio`: MSS requires a close to clear a swing by a
#     configurable fraction of the swing-to-opposite-extreme distance.
#     Order Flow's break test (REQ-OF-01/spec Decision 3) is a bare
#     strict-inequality close, no buffer — a deliberately different,
#     independently-justified rule (symmetry with the rejection test, not
#     inherited from MSS's own threshold).
#   - MSS's close-only break mode with no prior wick/reject requirement:
#     Order Flow requires a wick-cross-then-close-back REJECTION before a
#     break can even be evaluated (REQ-OF-01) — MSS has no such precondition.
#   - MSS's "prior opposite swing must already exist" precondition
#     (`composite/mss.py::_pending_breaks`, `if opposite_swing is None:
#     continue`): Order Flow's break_reference may be confirmed AFTER the
#     rejection (REQ-OF-02.4) — a materially looser, independently-justified
#     temporal model.
# `primitives/swing.py::detect_swings`/`SwingPoint` ARE reused exactly,
# unmodified, as the sole source of candidate reference points.


@dataclass(frozen=True)
class OrderFlowEvent:
    direction: Literal["bullish", "bearish"]
    rejection_reference: SwingPoint
    break_reference: SwingPoint
    rejection_index: int
    confirmation_index: int


@dataclass(frozen=True)
class _PendingCandidate:
    rejection_reference: SwingPoint
    rejection_index: int


def detect_order_flow_events(
    series: OHLCSeries, config: OrderFlowConfig = OrderFlowConfig()
) -> list[OrderFlowEvent]:
    """Two-phase forward pass per candle (REQ-OF-07): first resolve each
    direction's existing pending candidate (invalidation, then break) using
    only swings confirmed strictly before the candle; only then check
    whether the candle itself creates a new rejection, independently per
    direction (REQ-OF-04/08). Bullish and bearish candidates are tracked
    independently, never arbitrated against each other (REQ-OF-04/09) — an
    old-anchoring defect (a global-extreme reference standing unbroken
    indefinitely) ruled out recency-based selection in favor of magnitude,
    per `explore.md` Section M.A, so reference selection here is always "most
    recently confirmed unbroken", never "most extreme price" (REQ-OF-02).

    A SwingPoint is "broken" (REQ-OF-03) the moment any candle strictly
    after it closes beyond its price — permanently, and identically whether
    that break serves as a successful break_reference confirmation or as a
    rejection_reference's own structural invalidation (REQ-OF-04.3): both
    are the same predicate applied to different swings, not two rules.
    """
    candles = series.candles
    swings = detect_swings(series)
    highs = [s for s in swings if s.kind == "high"]
    lows = [s for s in swings if s.kind == "low"]

    events: list[OrderFlowEvent] = []
    pending_bullish: _PendingCandidate | None = None
    pending_bearish: _PendingCandidate | None = None
    broken: set[SwingPoint] = set()

    for c, candle in enumerate(candles):
        avail_highs = [s for s in highs if s.index <= c - 2 and s not in broken]
        avail_lows = [s for s in lows if s.index <= c - 2 and s not in broken]

        # Phase 1 — resolve existing pending candidates first (REQ-OF-07).
        if pending_bullish is not None:
            rejection_reference = pending_bullish.rejection_reference
            if candle.close < rejection_reference.price:
                pending_bullish = None  # REQ-OF-04.3: structural invalidation
            else:
                break_reference = _select_reference(
                    avail_highs, min_price=rejection_reference.price
                )
                if break_reference is not None and candle.close > break_reference.price:
                    events.append(
                        OrderFlowEvent(
                            direction="bullish",
                            rejection_reference=rejection_reference,
                            break_reference=break_reference,
                            rejection_index=pending_bullish.rejection_index,
                            confirmation_index=c,
                        )
                    )
                    pending_bullish = None  # REQ-OF-04.4: consumed

        if pending_bearish is not None:
            rejection_reference = pending_bearish.rejection_reference
            if candle.close > rejection_reference.price:
                pending_bearish = None
            else:
                break_reference = _select_reference(
                    avail_lows, max_price=rejection_reference.price
                )
                if break_reference is not None and candle.close < break_reference.price:
                    events.append(
                        OrderFlowEvent(
                            direction="bearish",
                            rejection_reference=rejection_reference,
                            break_reference=break_reference,
                            rejection_index=pending_bearish.rejection_index,
                            confirmation_index=c,
                        )
                    )
                    pending_bearish = None

        # Phase 2 — evaluate `c` for a new rejection, independently per
        # direction (REQ-OF-04/08: always replaces the direction's own
        # previous candidate, whatever Phase 1 just did to it).
        bullish_candidate = _select_reference(avail_lows)
        if (
            bullish_candidate is not None
            and candle.low < bullish_candidate.price
            and candle.close > bullish_candidate.price
        ):
            pending_bullish = _PendingCandidate(
                rejection_reference=bullish_candidate, rejection_index=c
            )

        bearish_candidate = _select_reference(avail_highs)
        if (
            bearish_candidate is not None
            and candle.high > bearish_candidate.price
            and candle.close < bearish_candidate.price
        ):
            pending_bearish = _PendingCandidate(
                rejection_reference=bearish_candidate, rejection_index=c
            )

        # Advance "broken" status using this candle's own close, for every
        # swing it could possibly break (REQ-OF-03: strict inequality, no
        # buffer, permanent once true). Swings not yet confirmed structurally
        # cannot be broken by their own confirming candle (REQ-OF-07.2), so
        # scanning the full swing list here — not just `avail_*` — is safe.
        for swing in swings:
            if swing.index < c and swing not in broken and _breaks(swing, candle):
                broken.add(swing)

    return events


def _select_reference(
    candidates: list[SwingPoint],
    min_price: float | None = None,
    max_price: float | None = None,
) -> SwingPoint | None:
    """The confirmed, unbroken SwingPoint with the highest `confirmation_index`
    (index+1, so highest `index` is equivalent) among `candidates` — recency,
    never magnitude (REQ-OF-02). `min_price`/`max_price` apply the
    correct-side guardrail (REQ-OF-02.2) when selecting a break_reference
    relative to an already-fixed rejection_reference; omitted when selecting
    a fresh rejection_reference candidate, which has no other reference to
    sit relative to.
    """
    eligible = candidates
    if min_price is not None:
        eligible = [s for s in eligible if s.price > min_price]
    if max_price is not None:
        eligible = [s for s in eligible if s.price < max_price]
    if not eligible:
        return None
    return max(eligible, key=lambda s: s.index)


def _breaks(swing: SwingPoint, candle: Candle) -> bool:
    if swing.kind == "high":
        return candle.close > swing.price
    return candle.close < swing.price
