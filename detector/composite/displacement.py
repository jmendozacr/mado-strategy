"""Displacement confirmation, Displacement step of the order-block-
redefinition chain (`odd/tasks/detector-order-block-redefinition.md`
S2/S5/T2). A production counterpart to `research/displacement.py`'s
frozen ">=1x ATR14 body sum over <=3 candles" test -- NOT a reuse of that
module, which `.importlinter`'s `no-research-in-production` contract
forbids importing from any production layer; the same thresholds are
reimplemented here independently so this composite module stays
production-legal.
"""
from __future__ import annotations

from typing import Literal

from core.atr import atr
from core.candle import Candle

Direction = Literal["bullish", "bearish"]

_DISPLACEMENT_MULTIPLIER = 1.0
_MAX_DISPLACEMENT_CANDLES = 3


def confirm_displacement(
    candles: tuple[Candle, ...],
    break_index: int,
    direction: Direction,
    max_candles: int = _MAX_DISPLACEMENT_CANDLES,
) -> int | None:
    """The first index at which the NET body movement accumulated from
    `break_index` (inclusive), over at most `max_candles`, reaches
    `>=1x ATR14` AND nets in `direction` -- `None` if it never does within
    the window or the series ends first. ATR is read once, at
    `break_index` (the break's own volatility context), fixed for the
    whole window rather than recomputed per candle -- displacement is
    judged against the volatility AT THE BREAK, not a moving target.

    Net (not absolute) body sum is the test: a window whose bodies net
    near zero (a two-sided chop that happens to be individually large)
    must not confirm, even if the SUM OF MAGNITUDES alone would clear the
    threshold -- this is stricter than `research/displacement.py`'s own
    unconstrained abs-sum test, which derives direction from the net sign
    rather than requiring it match a caller-given one.
    """
    threshold = atr(candles, break_index) * _DISPLACEMENT_MULTIPLIER
    sign = 1.0 if direction == "bullish" else -1.0
    net = 0.0

    for offset in range(max_candles):
        index = break_index + offset
        if index >= len(candles):
            return None
        candle = candles[index]
        net += candle.close - candle.open
        if net * sign >= threshold:
            return index

    return None
