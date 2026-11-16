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
