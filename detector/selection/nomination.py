"""SEL-A eligibility, ranking, and nomination (spec.md Section E,
REQ-STAT-13..17). `evaluate_eligibility` reports auditable typed reasons —
never a bare boolean — so a failure can always be traced to the exact
condition that produced it; `nominate` only ranks and applies the
tie/zero-eligible rules on top.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from selection.bootstrap import BootstrapResult, CIComputability
from selection.estimators import Computability, ESTBResult, InstrumentDelta

MEI_R = 0.20
INSTRUMENT_VETO_THRESHOLD = -0.20


class IneligibilityReason(StrEnum):
    EST_B_NOT_ESTIMABLE = "EST_B_NOT_ESTIMABLE"
    BELOW_MEI = "BELOW_MEI"
    CI_NOT_COMPUTABLE = "CI_NOT_COMPUTABLE"
    CI_LOWER_NOT_POSITIVE = "CI_LOWER_NOT_POSITIVE"
    INSTRUMENT_VETO = "INSTRUMENT_VETO"


@dataclass(frozen=True)
class PolicyEligibility:
    policy_id: str
    eligible: bool
    reasons: tuple[IneligibilityReason, ...]
    est_b_point: float | None
    ci_lower: float | None
    ci_upper: float | None


def evaluate_eligibility(
    policy_id: str,
    est_b: ESTBResult,
    bootstrap: BootstrapResult,
    instrument_deltas: Sequence[InstrumentDelta],
) -> PolicyEligibility:
    reasons: list[IneligibilityReason] = []

    if est_b.status != Computability.ESTIMABLE:
        reasons.append(IneligibilityReason.EST_B_NOT_ESTIMABLE)
    elif est_b.point < MEI_R:
        reasons.append(IneligibilityReason.BELOW_MEI)

    if bootstrap.ci_status != CIComputability.COMPUTABLE:
        reasons.append(IneligibilityReason.CI_NOT_COMPUTABLE)
    elif not bootstrap.lower > 0:
        reasons.append(IneligibilityReason.CI_LOWER_NOT_POSITIVE)

    if any(
        delta.status == Computability.ESTIMABLE and delta.point <= INSTRUMENT_VETO_THRESHOLD
        for delta in instrument_deltas
    ):
        reasons.append(IneligibilityReason.INSTRUMENT_VETO)

    return PolicyEligibility(
        policy_id=policy_id,
        eligible=not reasons,
        reasons=tuple(reasons),
        est_b_point=est_b.point,
        ci_lower=bootstrap.lower,
        ci_upper=bootstrap.upper,
    )


@dataclass(frozen=True)
class NominationResult:
    nominee: str | None
    eligibilities: tuple[PolicyEligibility, ...]


def nominate(eligibilities: Sequence[PolicyEligibility]) -> NominationResult:
    """Rank eligible policies by full-precision CI lower bound, descending.
    Zero eligible, or an exact tie at the top, both yield `NO POLICY
    NOMINATED` — no secondary tiebreak, no threshold relaxation."""
    eligible = [e for e in eligibilities if e.eligible]
    if not eligible:
        return NominationResult(nominee=None, eligibilities=tuple(eligibilities))

    ranked = sorted(eligible, key=lambda e: e.ci_lower, reverse=True)
    top = ranked[0]
    if len(ranked) > 1 and ranked[1].ci_lower == top.ci_lower:
        return NominationResult(nominee=None, eligibilities=tuple(eligibilities))
    return NominationResult(nominee=top.policy_id, eligibilities=tuple(eligibilities))
