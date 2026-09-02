from dataclasses import dataclass
from typing import Literal

from core.candle import Candle, OHLCSeries
from core.config import ICTOrderBlockConfig
from core.key_level import KeyLevel


@dataclass(frozen=True)
class ICTOrderBlock:
    candle_index: int
    confirmation_index: int
    direction: Literal["bullish", "bearish"]
    top: float
    bottom: float
    status: Literal["open", "invalidated"]
    invalidation_index: int | None = None


def detect_ict_order_blocks(
    series: OHLCSeries, config: ICTOrderBlockConfig = ICTOrderBlockConfig(),
) -> list[ICTOrderBlock]:
    """Single forward pass over consecutive candle pairs (i, i+1) (REQ-61):
    checks BOTH the bullish and bearish engulfing conditions unconditionally
    at every pair — no bias input, no external StructureBreak. A qualifying
    pair yields one ICTOrderBlock zoned to candle i's own body; the forward
    invalidation scan (REQ-62) then resolves status/invalidation_index
    independently per block, starting at i+2 (REQ-62.4)."""
    candles = series.candles
    blocks = []
    for i in range(len(candles) - 1):
        anchor, confirmation = candles[i], candles[i + 1]
        direction = _match(anchor, confirmation)
        if direction is None:
            continue
        top = max(anchor.open, anchor.close)
        bottom = min(anchor.open, anchor.close)
        status, invalidation_index = _invalidation(candles, i, top, bottom)
        blocks.append(
            ICTOrderBlock(
                candle_index=i, confirmation_index=i + 1, direction=direction,
                top=top, bottom=bottom, status=status, invalidation_index=invalidation_index,
            )
        )
    return blocks


def _match(anchor: Candle, confirmation: Candle) -> Literal["bullish", "bearish"] | None:
    engulfs = confirmation.high >= anchor.high and confirmation.low <= anchor.low
    if not engulfs:
        return None
    if anchor.close < anchor.open and confirmation.close > confirmation.open:
        return "bullish"
    if anchor.close > anchor.open and confirmation.close < confirmation.open:
        return "bearish"
    return None


def _invalidation(
    candles: tuple[Candle, ...], anchor_index: int, top: float, bottom: float,
) -> tuple[Literal["open", "invalidated"], int | None]:
    """REQ-62: the first candle from i+2 onward whose range overlaps the
    zone at all (wick or body, boundary-inclusive) invalidates. The scan
    starts at i+2, not i+1 — the confirmation candle always overlaps the
    zone by definition of full engulfment, so starting at i+1 would
    trivially self-invalidate every Order Block the instant it forms
    (REQ-62.4)."""
    for i in range(anchor_index + 2, len(candles)):
        candle = candles[i]
        if candle.high >= bottom and candle.low <= top:
            return "invalidated", i
    return "open", None


def to_key_levels(blocks: list[ICTOrderBlock]) -> list[KeyLevel]:
    return [
        KeyLevel(
            kind="ict_order_block", top=b.top, bottom=b.bottom,
            origin_index=b.confirmation_index, expiry_index=b.invalidation_index,
        )
        for b in blocks
    ]
