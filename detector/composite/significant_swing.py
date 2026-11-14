"""Significance-filtered swing detection. `primitives.swing.detect_swings`
is a structure-free 3-candle fractal with no significance test at all --
measured (`detector/swing-detection/structural-break-confirmation-rate`)
at only ~51% real-data quality (confirmed by a genuine structural break
within a 20-candle horizon), explaining the ~1-signal-per-candle
explosion the dormant TSQ entry families produced when run once on real
data.

Filters to swings followed by real DISPLACEMENT away from them --
reuses `composite.displacement.confirm_displacement` unmodified, the
same test already validated for the Order Block redefinition
(`odd/tasks/detector-order-block-redefinition.md`). A swing only counts
if price actually moved away from it with force (>=1x ATR14 within 3
candles), not merely a local 3-candle wiggle.

Lives in `composite/`, not `primitives/swing.py` itself, because it
depends on `composite.displacement` -- `primitives` cannot import
`composite` (ADR-01). `primitives.swing.detect_swings` stays completely
unchanged; this is an additive, OPT-IN alternative any composite-layer
consumer can choose (e.g. `composite.mss.detect_mss_events`'s own
`swings` injection parameter, or `composite.ote.impulse_leg`) -- no
existing caller is affected by this module's existence.
"""
from __future__ import annotations

from typing import Literal

from core.candle import OHLCSeries
from primitives.swing import SwingPoint, detect_swings

from composite.displacement import confirm_displacement

_DISPLACEMENT_DIRECTION: dict[str, Literal["bullish", "bearish"]] = {
    "high": "bearish",
    "low": "bullish",
}


def detect_significant_swings(
    series: OHLCSeries, max_displacement_candles: int = 3
) -> list[SwingPoint]:
    """A subset of `detect_swings(series)` -- never more, only a filter.
    Displacement is measured starting the candle AFTER the swing forms
    (`swing.index + 1`): the swing candle's own formation is not itself
    "the move away from it"."""
    candles = series.candles
    return [
        swing
        for swing in detect_swings(series)
        if confirm_displacement(
            candles, swing.index + 1, _DISPLACEMENT_DIRECTION[swing.kind], max_displacement_candles,
        ) is not None
    ]
