from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class KeyLevel:
    """A normalised, source-agnostic price zone a confluence check can
    credit an HTF purge against (SEAM-01). Sources (FVG, ICTOrderBlock,
    BreakerBlock) each own a `to_key_levels` adapter that produces these —
    `alignment` never imports a source detector's own type.

    `breaker_block`'s adapter lives in `entries.breaker_block` rather than
    `primitives/`/`composite/`, because Mado's breaker is defined in terms
    of a failed Model-1 and so needs the `entries` layer; the zone shape
    and the `to_key_levels` convention are otherwise identical to the
    other sources'."""

    kind: Literal["fvg", "ict_order_block", "breaker_block", "msnr"]
    top: float
    bottom: float
    origin_index: int
    expiry_index: int | None = None
