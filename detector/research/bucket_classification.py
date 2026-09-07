"""A/B/C/D prevalence bucket classification — RESEARCH TOOLING.

Frozen 2026-09-06, alongside `research.order_block`/`research.displacement`.
A single, versioned, unit-tested mapping from (Order Block alignment,
Displacement alignment) to a bucket letter — ending the same
reproduce-it-by-hand-in-prose problem those two modules end for their own
detections.

Leaf module: no imports beyond `typing`, so it carries none of the
`.importlinter` leaf-package concerns `order_block.py`/`displacement.py`
document — still colocated under `research/` because it only has meaning
paired with those two modules' alignment outputs.
"""

from typing import Literal

Alignment = Literal["aligned", "opposed"]
Bucket = Literal["A", "B", "C", "D"]


def classify(ob_alignment: Alignment, displacement_alignment: Alignment) -> Bucket:
    """Fixed bucket convention (do not change):

    A = OB aligned    + Disp aligned   (both aligned)
    B = OB opposed    + Disp aligned   (only displacement aligned)
    C = OB aligned    + Disp opposed   (only OB aligned)
    D = OB opposed    + Disp opposed   (both opposed)
    """
    if ob_alignment == "aligned" and displacement_alignment == "aligned":
        return "A"
    if ob_alignment == "opposed" and displacement_alignment == "aligned":
        return "B"
    if ob_alignment == "aligned" and displacement_alignment == "opposed":
        return "C"
    return "D"
