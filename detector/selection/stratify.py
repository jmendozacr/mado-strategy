"""Per-policy stratum construction (spec.md Section E/H, REQ-STAT-04,
REQ-STAT-06). One grouping pass, reused by `estimators`, `bootstrap`, and
`nomination` — the strata are the shared vocabulary every downstream
statistic reads from, computed once instead of re-filtered per caller.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from selection.model import (
    ClosedTradeOutcome,
    Computability,
    DirectionPolicyObservation,
    OutcomeState,
    Relation,
    validate_candidate_consistency,
)


@dataclass(frozen=True)
class RelationStratum:
    relation: Relation
    n: int
    share: float | None
    mean_r: float | None
    wr_status: Computability
    wr: float | None


@dataclass(frozen=True)
class PolicyStrata:
    policy_id: str
    total_n: int
    closed_n: int
    open_n: int
    never_filled_n: int
    closed_aligned: RelationStratum
    closed_opposed: RelationStratum
    closed_unresolved: RelationStratum


def _mean_r(rows: Sequence[DirectionPolicyObservation]) -> float | None:
    if not rows:
        return None
    return sum(row.realized_r for row in rows) / len(rows)


def _wr(rows: Sequence[DirectionPolicyObservation]) -> tuple[Computability, float | None]:
    """WR (spec.md Section C2/E, V2): reads `closed_outcome` ONLY — never
    `realized_r`'s sign. `rows` here are already the CLOSED rows for one
    relation stratum, so the denominator is simply `len(rows)`."""
    if not rows:
        return Computability.NOT_ESTIMABLE, None
    wins = sum(1 for row in rows if row.closed_outcome == ClosedTradeOutcome.WIN)
    return Computability.ESTIMABLE, wins / len(rows)


def _relation_stratum(
    relation: Relation, rows: Sequence[DirectionPolicyObservation], total_n: int
) -> RelationStratum:
    wr_status, wr = _wr(rows)
    return RelationStratum(
        relation=relation,
        n=len(rows),
        share=(len(rows) / total_n) if total_n else None,
        mean_r=_mean_r(rows),
        wr_status=wr_status,
        wr=wr,
    )


def stratify(observations: Sequence[DirectionPolicyObservation], policy_id: str) -> PolicyStrata:
    """Group one policy's observations into CLOSED/OPEN/NEVER_FILLED counts
    plus the three CLOSED relation strata (ALIGNED/OPPOSED/UNRESOLVED) EST-B
    and its instrument deltas read from. Re-validates REQ-STAT-03 on the
    full incoming batch (not just this policy's slice) so no per-policy
    caller can skip the fail-closed check."""
    validate_candidate_consistency(observations)
    policy_rows = [obs for obs in observations if obs.policy_id == policy_id]
    closed = [obs for obs in policy_rows if obs.outcome_state == OutcomeState.CLOSED]
    open_rows = [obs for obs in policy_rows if obs.outcome_state == OutcomeState.OPEN]
    never_filled = [obs for obs in policy_rows if obs.outcome_state == OutcomeState.NEVER_FILLED]
    total_n = len(policy_rows)

    return PolicyStrata(
        policy_id=policy_id,
        total_n=total_n,
        closed_n=len(closed),
        open_n=len(open_rows),
        never_filled_n=len(never_filled),
        closed_aligned=_relation_stratum(
            Relation.ALIGNED, [o for o in closed if o.relation == Relation.ALIGNED], total_n
        ),
        closed_opposed=_relation_stratum(
            Relation.OPPOSED, [o for o in closed if o.relation == Relation.OPPOSED], total_n
        ),
        closed_unresolved=_relation_stratum(
            Relation.UNRESOLVED, [o for o in closed if o.relation == Relation.UNRESOLVED], total_n
        ),
    )
