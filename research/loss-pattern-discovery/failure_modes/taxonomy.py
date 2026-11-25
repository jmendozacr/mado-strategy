"""Multidimensional failure-mode taxonomy (Phase 4, Deliverable C).

Deliberately NOT five mutually-exclusive labels: duration, favorable-
excursion, and path-integrity are independent dimensions that combine
freely -- a trade can be fast AND show no favorable excursion AND be fully
reconstructible, all at once.

Threshold justification (declared before computing any Phase-4 result, see
docs/22-phase4-design-and-pre-registration.md):

- Favorable-excursion cut points reuse `CONTINUATION_REVERSAL_THRESHOLD_R`
  (0.25R, already pre-registered in Phase 2/3 for an unrelated purpose --
  reused here for consistency, not re-tuned) and `MATERIAL_EXCURSION_R`
  (1.0R, the position's own risk distance -- a structurally meaningful
  unit, not fit to any outcome).
- Duration is reported as a CONTINUOUS distribution primarily
  (`docs/26-failure-mode-atlas.md`); the only duration-related categorical
  fact used anywhere is `n_observable_bars == 0`, which is a DATA-INTEGRITY
  fact (no bars exist to look at between entry and exit), not a chosen cut
  point. Duration terciles shown for descriptive readability
  (`duration_tercile_labels`) are labeled explicitly as percentile bins of
  the observed sample, never as a claimed natural category, and are never
  used to select or threshold anything else.
"""
from __future__ import annotations

from dataclasses import dataclass

from behavior.post_stop_metrics import CONTINUATION_REVERSAL_THRESHOLD_R
from behavior.pre_stop_trajectory import PathIntegrity, PreStopTrajectory

MATERIAL_EXCURSION_R = 1.0  # the position's own risk distance -- structural, not tuned


class ExcursionClass:
    NONE = "none"  # < 0.25R
    PARTIAL = "partial"  # 0.25R .. 1.0R
    MATERIAL = "material"  # >= 1.0R
    UNKNOWN = "unknown"  # integrity != reconstructible, or risk invalid


@dataclass(frozen=True)
class FailureModeClassification:
    event_id: str
    integrity: str  # PathIntegrity.*
    zero_observable_path: bool  # n_observable_bars == 0 -- a data-integrity fact, not a chosen cut
    duration_bars: int
    excursion_class: str  # ExcursionClass.*
    mfe_pre_sl_r: float | None  # the continuous value excursion_class was derived from


def classify(trajectory: PreStopTrajectory) -> FailureModeClassification:
    if trajectory.integrity != PathIntegrity.RECONSTRUCTIBLE or trajectory.mfe_pre_sl_r is None:
        excursion_class = ExcursionClass.UNKNOWN
    elif trajectory.mfe_pre_sl_r < CONTINUATION_REVERSAL_THRESHOLD_R:
        excursion_class = ExcursionClass.NONE
    elif trajectory.mfe_pre_sl_r < MATERIAL_EXCURSION_R:
        excursion_class = ExcursionClass.PARTIAL
    else:
        excursion_class = ExcursionClass.MATERIAL

    return FailureModeClassification(
        event_id=trajectory.event_id,
        integrity=trajectory.integrity,
        zero_observable_path=trajectory.n_observable_bars == 0,
        duration_bars=trajectory.duration_bars,
        excursion_class=excursion_class,
        mfe_pre_sl_r=trajectory.mfe_pre_sl_r,
    )


def duration_tercile_labels(all_duration_bars: list[int]) -> dict[int, str]:
    """Purely descriptive percentile bins of THIS sample's own duration
    distribution -- labeled explicitly as bins, never as a claimed natural
    category, and never used to threshold or select anything else."""
    if not all_duration_bars:
        return {}
    ordered = sorted(all_duration_bars)
    n = len(ordered)
    t1 = ordered[n // 3]
    t2 = ordered[(2 * n) // 3]

    def label(value: int) -> str:
        if value <= t1:
            return "fast_tercile"
        if value <= t2:
            return "mid_tercile"
        return "slow_tercile"

    return {v: label(v) for v in all_duration_bars}
