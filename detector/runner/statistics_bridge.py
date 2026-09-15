"""Single full-dataset statistical calculation.

The ONLY module in runner/ that calls frozen_rng(). Materializes one
ResamplePlan, invokes stratify/EST-B/bootstrap/instrument-deltas/
nomination exactly once on the full concatenated observation set. Returns
typed results with no logger and no print."""

from collections.abc import Sequence
from dataclasses import dataclass

from evaluation.direction import FROZEN_POLICY_IDS
from selection.bootstrap import (
    BootstrapResult,
    ResamplePlan,
    bootstrap_est_b,
    frozen_rng,
    generate_cluster_resample_plan,
    FROZEN_REPLICATES,
)
from selection.estimators import ESTBResult, InstrumentDelta, compute_est_b, compute_instrument_deltas
from selection.model import DirectionPolicyObservation
from selection.nomination import NominationResult, PolicyEligibility, evaluate_eligibility, nominate
from selection.stratify import PolicyStrata, stratify


@dataclass(frozen=True)
class StatisticsResult:
    strata: dict[str, PolicyStrata]
    est_b_results: dict[str, ESTBResult]
    bootstrap_results: dict[str, BootstrapResult]
    instrument_deltas: dict[str, tuple[InstrumentDelta, ...]]
    eligibilities: tuple[PolicyEligibility, ...]
    nomination: NominationResult
    plan: ResamplePlan


def compute_all_statistics(
    observations: Sequence[DirectionPolicyObservation],
    instruments: tuple[str, ...],
) -> StatisticsResult:
    """One RNG, one plan, one pass over all 4 policies."""
    rng = frozen_rng()
    plan = generate_cluster_resample_plan(observations, instruments, rng, FROZEN_REPLICATES)

    all_strata: dict[str, PolicyStrata] = {}
    all_est_b: dict[str, ESTBResult] = {}
    all_bootstrap: dict[str, BootstrapResult] = {}
    all_deltas: dict[str, tuple[InstrumentDelta, ...]] = {}
    eligibilities: list[PolicyEligibility] = []

    for policy_id in FROZEN_POLICY_IDS:
        strata_result = stratify(observations, policy_id)
        est_b = compute_est_b(observations, policy_id)
        bootstrap_result = bootstrap_est_b(observations, policy_id, plan)
        deltas = compute_instrument_deltas(observations, policy_id)
        eligibility = evaluate_eligibility(policy_id, est_b, bootstrap_result, deltas)

        all_strata[policy_id] = strata_result
        all_est_b[policy_id] = est_b
        all_bootstrap[policy_id] = bootstrap_result
        all_deltas[policy_id] = deltas
        eligibilities.append(eligibility)

    nomination_result = nominate(eligibilities)

    return StatisticsResult(
        strata=all_strata,
        est_b_results=all_est_b,
        bootstrap_results=all_bootstrap,
        instrument_deltas=all_deltas,
        eligibilities=tuple(eligibilities),
        nomination=nomination_result,
        plan=plan,
    )
