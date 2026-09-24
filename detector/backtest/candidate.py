from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class Candidate:
    """Everything knowable when a resting entry order becomes live."""

    signal_id: str
    anchor_index: int
    origin_index: int
    direction: Literal["bullish", "bearish"]
    entry_type: Literal["wick", "body"]
    retest_index: int
    entry_price: float
    stop_loss: float
    take_profit: float
    partial_price: float
