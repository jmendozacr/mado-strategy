"""EXPERIMENTAL: of the swing points `primitives.swing.detect_swings`
flags (a structure-free 3-candle fractal, no significance filter at
all), how many are ever actually confirmed as real market structure --
i.e. later decisively broken, per `composite.mss.detect_mss_events`?

Motivated by the entry-mechanism exploration (2026-11-09): the dormant
alternate entry families on `detector-feeder-chain-dol-entries`
(`entries/breaker_block.py`/`turtle_soup.py`/`cisd.py`) and this
session's own `composite/ote.py` `impulse_leg` both depend on
`detect_swings`; its own real-data quality has never been measured,
despite the same "structure-free detector, unbounded" shape that was
already found and fixed for the archived Order Block
(`sdd/crt-detector-order-block-redefinition`).

Not circular: `detect_mss_events` does derive its candidate breaks from
the same swing list, but whether a given swing is EVER actually broken
(vs. sitting unconfirmed, or still open) is a genuine fact about the
real price series, not a tautology -- exactly as "is this OB/FVG zone
later broken" was for the two prior structural-break checks this session
already built and relied on.

Reuses `detect_swings` and `detect_mss_events` unmodified; zero
production files touched.
"""
from __future__ import annotations

from composite.mss import MSSEvent
from primitives.swing import SwingPoint

__all__ = ["swing_confirmed_by_mss", "summarize"]


def swing_confirmed_by_mss(
    swing: SwingPoint, mss_events: list[MSSEvent], window: int | None = None,
) -> bool:
    """`True` when this EXACT swing (structural equality: index, price,
    AND kind -- an outside candle's same-index high and low are two
    different swings) appears as some `MSSEvent.broken_swing`.

    `window` (inclusive, `None` = unbounded): the first pass of this
    measurement found 95.9-98.7% unbounded across 3 real series --
    uninformative, not a quality signal. In a series that trends over
    time almost every local extreme is EVENTUALLY exceeded by something,
    regardless of whether that swing was structurally meaningful when it
    formed. `window` bounds "confirmed" to within a trading-relevant
    horizon of the swing's own index, matching this codebase's own
    `Model1Config.max_retest_lookback=20` precedent."""
    return any(
        event.broken_swing == swing and (window is None or event.index <= swing.index + window)
        for event in mss_events
    )


def summarize(
    swings: list[SwingPoint], mss_events: list[MSSEvent], window: int | None = None,
) -> dict[str, int | float]:
    confirmed = sum(1 for swing in swings if swing_confirmed_by_mss(swing, mss_events, window))
    return {
        "total_swings": len(swings),
        "swings_confirmed_by_mss": confirmed,
        "fraction": confirmed / len(swings) if swings else 0.0,
    }
