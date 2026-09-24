"""EST-B and the per-instrument delta guard (spec.md Section E, REQ-STAT-05,
REQ-STAT-06, REQ-STAT-14). Unweighted arithmetic mean only — no
trimming/winsorizing/weighting, per the frozen `primary_estimand`.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from selection.model import Computability, DirectionPolicyObservation
from selection.stratify import stratify

__all__ = ["Computability", "ESTBResult", "InstrumentDelta", "compute_est_b", "compute_instrument_deltas"]


@dataclass(frozen=True)
class ESTBResult:
    status: Computability
    point: float | None


@dataclass(frozen=True)
class InstrumentDelta:
    instrument: str
    status: Computability
    point: float | None


def compute_est_b(observations: Sequence[DirectionPolicyObservation], policy_id: str) -> ESTBResult:
    """`EST-B(P) = MeanR(CLOSED ∩ ALIGNED) - MeanR(CLOSED ∩ OPPOSED)`. Either
    stratum empty on the observed sample -> `NOT_ESTIMABLE`, never a
    divide-by-zero, never `0R`."""
    strata = stratify(observations, policy_id)
    aligned, opposed = strata.closed_aligned, strata.closed_opposed
    if aligned.n == 0 or opposed.n == 0:
        return ESTBResult(status=Computability.NOT_ESTIMABLE, point=None)
    return ESTBResult(status=Computability.ESTIMABLE, point=aligned.mean_r - opposed.mean_r)


def compute_instrument_deltas(
    observations: Sequence[DirectionPolicyObservation], policy_id: str
) -> tuple[InstrumentDelta, ...]:
    """`instrument_delta(P, i)` — the same EST-B formula, restricted to one
    instrument at a time (REQ-STAT-14). Instruments are never pooled here:
    each is its own independent EST-B computation over its own subset."""
    instruments = sorted(
        {obs.candidate_id.instrument for obs in observations if obs.policy_id == policy_id}
    )
    deltas = []
    for instrument in instruments:
        subset = [obs for obs in observations if obs.candidate_id.instrument == instrument]
        result = compute_est_b(subset, policy_id)
        deltas.append(InstrumentDelta(instrument=instrument, status=result.status, point=result.point))
    return tuple(deltas)
