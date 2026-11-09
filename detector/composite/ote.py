"""OTE (Optimal Trade Entry) -- the Fibonacci retracement sub-zone
charter-4 S4 [00:07:46-00:09:37] names: "Se aplica la herramienta de
Fibonacci desde el Swing Low hasta el Swing High (en compras) o del
Swing High al Swing Low (en ventas)" / "Zona Clave: El rango situado
entre el 60% y el 75% de retroceso (usualmente pasando por el 50%)".
charter-7 [00:05:33] names a different band, 62-79% -- the two bands are
genuinely inconsistent across episodes, so `band` is a caller-supplied
parameter, never a single frozen default.

Not a validity gate on confluence crediting -- mirrors
`alignment.htf_ltf._purge_reaction`'s own convention
("Reportable alongside key_level (never gates it)"). This module answers
a different, reportable question: is the credited Key Level's zone
positioned inside the OTE retracement band of the impulse leading into
it?
"""
from __future__ import annotations

from typing import Literal

from primitives.swing import SwingPoint

Direction = Literal["bullish", "bearish"]

Band = tuple[float, float]

DISCOUNT_PREMIUM_SPLIT: Band = (0.5, 1.0)
"""charter-2 [00:18:46]/charter-6 [00:02:24]/charter-9/charter-10's
"Equilibrium" concept: discount (bullish) or premium (bearish) is
EVERYTHING from the 50% midpoint back to the impulse's own origin, not a
narrow band -- a broader, user-chosen alternative to the OTE band above.
No new code needed: `ote_zone(start, end, band=DISCOUNT_PREMIUM_SPLIT)`
already computes exactly this half (pinned by this module's own test
suite), since the discount/premium split IS the 50%-100% retracement
band under the same retracement-from-`impulse_end` convention `ote_zone`
already implements."""


def impulse_leg(
    swings: list[SwingPoint], before_index: int, direction: Direction
) -> tuple[float, float] | None:
    """The most recent swing low and swing high, each strictly BEFORE
    `before_index` (no-lookahead: a swing at or after the cutoff was not
    yet knowable), ordered per charter-4's own convention: `(low, high)`
    for a bullish setup, `(high, low)` for bearish. `None` when either
    kind has no qualifying swing yet."""
    last_high: SwingPoint | None = None
    last_low: SwingPoint | None = None
    for swing in swings:
        if swing.index >= before_index:
            break
        if swing.kind == "high":
            last_high = swing
        else:
            last_low = swing

    if last_high is None or last_low is None:
        return None
    if direction == "bullish":
        return (last_low.price, last_high.price)
    return (last_high.price, last_low.price)


def ote_zone(impulse_start: float, impulse_end: float, band: Band) -> tuple[float, float]:
    """The price band `band` (e.g. `(0.60, 0.75)`) represents as a
    retracement FROM `impulse_end` back toward `impulse_start` --
    standard retail/ICT Fibonacci-tool labelling, confirmed against
    charter-4's own "usually passing through 50%" framing (a 60-75%
    retracement sits below the 50% midpoint of a bullish low->high leg).
    Returned `(low, high)`, sorted -- `impulse_start`/`impulse_end` can be
    either order (bullish or bearish leg)."""
    span = impulse_end - impulse_start
    low_pct, high_pct = band
    level_a = impulse_end - span * low_pct
    level_b = impulse_end - span * high_pct
    return (min(level_a, level_b), max(level_a, level_b))


def in_ote_zone(price: float, zone: tuple[float, float]) -> bool:
    """Inclusive edges, matching this codebase's own boundary convention
    elsewhere (e.g. REQ-55.4's confluence-zone edges)."""
    return zone[0] <= price <= zone[1]


def ote_overlaps_zone(level_bottom: float, level_top: float, ote: tuple[float, float]) -> bool:
    """A credited `KeyLevel` is itself a `[bottom, top]` zone, not a
    single price -- geometric overlap (not point containment) is the
    right test, consistent with how confluence crediting itself works."""
    return level_bottom <= ote[1] and level_top >= ote[0]
