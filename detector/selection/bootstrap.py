"""Paired instrument-stratified HTF-context cluster bootstrap (spec.md
Section E, REQ-STAT-07..12). `generate_cluster_resample_plan` (the RNG draw)
is kept separate from `apply_plan_to_policy` (a pure read of an already-made
plan) precisely so the SAME plan can be replayed unchanged against all 4
policies (REQ-STAT-09) — no policy consumes its own slice of the generator.
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

import numpy as np

from selection.model import (
    DirectionPolicyObservation,
    OutcomeState,
    Relation,
    validate_candidate_consistency,
)

FROZEN_SEED_SEQUENCE: tuple[int, ...] = (20260910,)
FROZEN_REPLICATES = 10_000

ClusterId = tuple[str, int, int, int]


def frozen_rng() -> np.random.Generator:
    """The one frozen V1 RNG (REQ-STAT-10) — never `random`, never numpy's
    global state, never a policy-specific generator."""
    return np.random.Generator(np.random.PCG64(np.random.SeedSequence(list(FROZEN_SEED_SEQUENCE))))


def bootstrap_universe(
    observations: Sequence[DirectionPolicyObservation], instrument: str
) -> tuple[ClusterId, ...]:
    """U-1: every distinct cluster for `instrument` containing >= 1 CLOSED
    observation, in a fixed deterministic order (sorted) so replicate draws
    can index it stably. Eligibility is a property of the cluster/candidate,
    never of `policy_id` — a candidate's `outcome_state` is invariant across
    its 4 policy rows (REQ-STAT-03), so this never needs a policy filter."""
    clusters = {
        obs.context_cluster_id
        for obs in observations
        if obs.candidate_id.instrument == instrument and obs.outcome_state == OutcomeState.CLOSED
    }
    return tuple(sorted(clusters))


@dataclass(frozen=True)
class ResamplePlan:
    instruments: tuple[str, ...]
    universes: dict[str, tuple[ClusterId, ...]]
    draws: tuple[dict[str, tuple[int, ...]], ...]


def generate_cluster_resample_plan(
    observations: Sequence[DirectionPolicyObservation],
    instruments: Sequence[str],
    rng: np.random.Generator,
    replicates: int,
) -> ResamplePlan:
    """Draw, once per replicate per instrument, `K` cluster indices with
    replacement from that instrument's U-1 universe — never per policy."""
    universes = {instrument: bootstrap_universe(observations, instrument) for instrument in instruments}
    draws: list[dict[str, tuple[int, ...]]] = []
    for _ in range(replicates):
        replicate_draw: dict[str, tuple[int, ...]] = {}
        for instrument in instruments:
            k = len(universes[instrument])
            if k == 0:
                replicate_draw[instrument] = ()
                continue
            sampled = rng.integers(0, k, size=k, endpoint=False)
            replicate_draw[instrument] = tuple(int(index) for index in sampled)
        draws.append(replicate_draw)
    return ResamplePlan(instruments=tuple(instruments), universes=universes, draws=tuple(draws))


class ReplicateStatus(StrEnum):
    VALID = "VALID"
    UNDEFINED = "UNDEFINED"


@dataclass(frozen=True)
class ReplicateResult:
    status: ReplicateStatus
    point: float | None


def apply_plan_to_policy(
    observations: Sequence[DirectionPolicyObservation],
    policy_id: str,
    plan: ResamplePlan,
    replicate_index: int,
) -> ReplicateResult:
    """Replay one replicate's cluster draw against one policy's CLOSED rows,
    pooled across every instrument in the plan (`selection.pooling`):
    drawing a cluster twice counts its CLOSED observations twice."""
    draw = plan.draws[replicate_index]
    aligned_rs: list[float] = []
    opposed_rs: list[float] = []
    for instrument in plan.instruments:
        by_cluster: dict[ClusterId, list[DirectionPolicyObservation]] = defaultdict(list)
        for obs in observations:
            if (
                obs.policy_id == policy_id
                and obs.candidate_id.instrument == instrument
                and obs.outcome_state == OutcomeState.CLOSED
            ):
                by_cluster[obs.context_cluster_id].append(obs)

        universe = plan.universes[instrument]
        for cluster_index in draw.get(instrument, ()):
            for obs in by_cluster.get(universe[cluster_index], ()):
                if obs.relation == Relation.ALIGNED:
                    aligned_rs.append(obs.realized_r)
                elif obs.relation == Relation.OPPOSED:
                    opposed_rs.append(obs.realized_r)

    if not aligned_rs or not opposed_rs:
        return ReplicateResult(status=ReplicateStatus.UNDEFINED, point=None)
    point = sum(aligned_rs) / len(aligned_rs) - sum(opposed_rs) / len(opposed_rs)
    return ReplicateResult(status=ReplicateStatus.VALID, point=point)


def percentile_ci(values: Sequence[float]) -> tuple[float, float]:
    """The frozen two-sided percentile bounds (REQ-STAT-12): 0.625%/99.375%,
    `numpy.percentile`'s `linear` interpolation."""
    lower, upper = np.percentile(values, [0.625, 99.375], method="linear")
    return float(lower), float(upper)


class CIComputability(StrEnum):
    COMPUTABLE = "COMPUTABLE"
    NOT_COMPUTABLE = "NOT_COMPUTABLE"


@dataclass(frozen=True)
class BootstrapResult:
    ci_status: CIComputability
    lower: float | None
    upper: float | None


def bootstrap_est_b(
    observations: Sequence[DirectionPolicyObservation], policy_id: str, plan: ResamplePlan
) -> BootstrapResult:
    """U-2: even one `UNDEFINED` replicate among the fixed set poisons the
    whole CI — no drop, no retry, no reseed, no imputation."""
    validate_candidate_consistency(observations)
    points: list[float] = []
    for replicate_index in range(len(plan.draws)):
        result = apply_plan_to_policy(observations, policy_id, plan, replicate_index)
        if result.status == ReplicateStatus.UNDEFINED:
            return BootstrapResult(ci_status=CIComputability.NOT_COMPUTABLE, lower=None, upper=None)
        points.append(result.point)
    lower, upper = percentile_ci(points)
    return BootstrapResult(ci_status=CIComputability.COMPUTABLE, lower=lower, upper=upper)
