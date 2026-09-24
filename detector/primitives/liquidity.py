from dataclasses import dataclass
from typing import Literal

from core.candle import OHLCSeries


@dataclass(frozen=True)
class LiquidityCandidate:
    kind: Literal["high", "low"]
    price: float
    source_index: int


def detect_liquidity_candidates(series: OHLCSeries) -> list[LiquidityCandidate]:
    """One HIGH and one LOW candidate per candle (REQ-LIQ-01), unbounded --
    "corto plazo" is deliberately left unoperationalized here; it belongs
    to a future selector's windowing, not to existence (REQ-LIQ-01 design
    note). No deduplication by price (REQ-LIQ-03): identity is
    (source_index, kind). No CRT-awareness (REQ-LIQ-09): this module has
    no dependency beyond core.candle."""
    candidates = []
    for i, candle in enumerate(series.candles):
        candidates.append(LiquidityCandidate(kind="high", price=candle.high, source_index=i))
        candidates.append(LiquidityCandidate(kind="low", price=candle.low, source_index=i))
    return candidates
