from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class KeyLevel:
    """A normalised, source-agnostic price zone a confluence check can
    credit an HTF purge against (SEAM-01). Sources (FVG, ICTOrderBlock now;
    Breaker Block later) each own a `to_key_levels` adapter that produces
    these — `alignment` never imports a source detector's own type."""

    kind: Literal["fvg", "ict_order_block"]
    top: float
    bottom: float
    origin_index: int
    expiry_index: int | None = None
