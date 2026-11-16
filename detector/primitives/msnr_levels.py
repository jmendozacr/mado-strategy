"""MSNR (Malaysian Support & Resistance) A-shape/V-shape key levels:
close-based two-candle pivots -- marked on the CLOSE of the pivot
candle, never the wick, per MSNR's own defining convention (unlike
classic support/resistance, which uses wicks). SBR/RBS role-flips and
QM/Quasimodo reversals are a different, more structural level type and
are deferred to a later task (odd/tasks/msnr-key-levels.md).
"""
from dataclasses import dataclass
from typing import Literal

from core.atr import atr
from core.candle import Candle, OHLCSeries
from core.config import MSNRConfig
from core.key_level import KeyLevel


@dataclass(frozen=True)
class MSNRLevel:
    index: int
    price: float
    kind: Literal["a_shape", "v_shape"]


def detect_msnr_levels(series: OHLCSeries) -> list[MSNRLevel]:
    candles = series.candles
    levels = []
    for i in range(1, len(candles)):
        formed = _formed_pivot(candles[i - 1], candles[i])
        if formed is not None:
            kind, price = formed
            levels.append(MSNRLevel(index=i - 1, price=price, kind=kind))
    return levels


def to_key_levels(
    levels: list[MSNRLevel], candles: tuple[Candle, ...], config: MSNRConfig = MSNRConfig(),
) -> list[KeyLevel]:
    return [
        KeyLevel(
            kind="msnr",
            top=level.price + config.zone_atr_multiple * atr(candles, level.index),
            bottom=level.price - config.zone_atr_multiple * atr(candles, level.index),
            origin_index=level.index,
        )
        for level in levels
    ]


def to_key_levels_with_sbr_rbs(
    levels: list[MSNRLevel], candles: tuple[Candle, ...], config: MSNRConfig = MSNRConfig(),
) -> list[KeyLevel]:
    """SBR (Support Becomes Resistance) / RBS (Resistance Becomes
    Support): a level invalidates the moment a candle CLOSES through it
    (never a wick) -- that close ends the current segment's validity
    (`expiry_index`) and a new segment starts there, defending the SAME
    price with the OPPOSITE role, open-ended until its own next break.
    Chains for as long as the series keeps breaking it."""
    key_levels = []
    for level in levels:
        for origin, expiry in _role_flip_segments(candles, level.index, level.price, level.kind):
            buffer = config.zone_atr_multiple * atr(candles, origin)
            key_levels.append(KeyLevel(
                kind="msnr", top=level.price + buffer, bottom=level.price - buffer,
                origin_index=origin, expiry_index=expiry,
            ))
    return key_levels


def _role_flip_segments(
    candles: tuple[Candle, ...], pivot_index: int, price: float, initial_kind: Literal["a_shape", "v_shape"],
):
    origin = pivot_index
    kind = initial_kind
    for i in range(pivot_index + 1, len(candles)):
        close = candles[i].close
        broken = (kind == "a_shape" and close > price) or (kind == "v_shape" and close < price)
        if broken:
            yield origin, i
            origin = i
            kind = "v_shape" if kind == "a_shape" else "a_shape"
    yield origin, None


def _formed_pivot(prev: Candle, cur: Candle) -> tuple[Literal["a_shape", "v_shape"], float] | None:
    prev_bullish = prev.close > prev.open
    prev_bearish = prev.close < prev.open
    cur_bullish = cur.close > cur.open
    cur_bearish = cur.close < cur.open
    if prev_bullish and cur_bearish:
        return "a_shape", prev.close
    if prev_bearish and cur_bullish:
        return "v_shape", prev.close
    return None
