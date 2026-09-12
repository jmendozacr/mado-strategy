"""Layer-1 domain model: the statistical observation record and its
construction invariants (spec.md Section A/B/C, REQ-STAT-01, REQ-STAT-03).

Zero filesystem/data-loading imports (REQ-STAT-22) — this module knows only
about in-memory records a caller hands it. It does not import `evaluation`
or `backtest`: `Relation`/`OutcomeState` are Layer-1's own frozen mirrors of
the evaluation seam's vocabulary, not a re-export of it, so Layer-1 stays
importable without pulling in anything outcome-bearing.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite


class SelectionIntegrityError(Exception):
    """A `DirectionPolicyObservation`, or a batch of them, violates the
    Layer-1 statistical contract."""


class OutcomeRealizedRMismatchError(SelectionIntegrityError):
    """`realized_r is not None` must hold iff `outcome_state == CLOSED`
    (spec.md Section C) — this also covers a CLOSED row carrying a
    non-finite `realized_r` (NaN/+inf/-inf), which is never a valid
    economic outcome."""


class CandidateOutcomeConsistencyError(SelectionIntegrityError):
    """One `CandidateIdentity` has exactly one economic outcome (REQ-STAT-03)
    — only `relation` may vary across its policy rows."""


class ClosedOutcomeMismatchError(SelectionIntegrityError):
    """`closed_outcome ∈ {WIN, LOSS}` must hold iff `outcome_state == CLOSED`
    (spec.md Section C/C2, V2) — WR's categorical source, independent of
    `realized_r` and never derived from it."""


class Computability(StrEnum):
    """Shared point-estimate status (EST-B, instrument delta, WR) — lives
    here rather than in `estimators`/`stratify` so neither has to import the
    other just to share this vocabulary."""

    ESTIMABLE = "ESTIMABLE"
    NOT_ESTIMABLE = "NOT_ESTIMABLE"


@dataclass(frozen=True)
class CandidateIdentity:
    """The full `population.key` 4-tuple (PREREGISTERED PROTOCOL, spec.md
    Section A) — never narrowed to the `(instrument, signal_id)` join key,
    which is a Layer-2 adapter concern, not a Layer-1 identity concern."""

    instrument: str
    timeframe: str
    signal_id: str
    retest_index: int


class OutcomeState(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    NEVER_FILLED = "NEVER_FILLED"


class Relation(StrEnum):
    """Frozen input, never recomputed here (REQ-STAT-21): Layer-1 consumes
    `relation` exactly as the evaluation seam produced it."""

    ALIGNED = "ALIGNED"
    OPPOSED = "OPPOSED"
    UNRESOLVED = "UNRESOLVED"


class ClosedTradeOutcome(StrEnum):
    """WR's categorical source (spec.md Section C2, V2) — carried forward
    verbatim from the pre-existing `Trade.outcome` contract at the Layer-2
    join. NEVER derived from `realized_r`'s sign: WR and MeanR/EST-B are two
    independent statistics over the same CLOSED population."""

    WIN = "win"
    LOSS = "loss"


@dataclass(frozen=True)
class DirectionPolicyObservation:
    candidate_id: CandidateIdentity
    context_cluster_id: tuple[str, int, int, int]
    policy_id: str
    relation: Relation
    outcome_state: OutcomeState
    closed_outcome: ClosedTradeOutcome | None
    realized_r: float | None

    def __post_init__(self) -> None:
        is_closed = self.outcome_state == OutcomeState.CLOSED
        has_r = self.realized_r is not None
        has_closed_outcome = self.closed_outcome is not None

        if is_closed and not has_r:
            raise OutcomeRealizedRMismatchError(
                f"CLOSED observation must carry a realized_r, got None "
                f"(candidate={self.candidate_id})"
            )
        if not is_closed and has_r:
            raise OutcomeRealizedRMismatchError(
                f"{self.outcome_state} observation must not carry a realized_r, "
                f"got {self.realized_r!r} (candidate={self.candidate_id})"
            )
        if is_closed and not isfinite(self.realized_r):
            raise OutcomeRealizedRMismatchError(
                f"CLOSED realized_r must be finite, got {self.realized_r!r} "
                f"(candidate={self.candidate_id})"
            )

        if is_closed and not has_closed_outcome:
            raise ClosedOutcomeMismatchError(
                f"CLOSED observation must carry a closed_outcome (WIN/LOSS), got None "
                f"(candidate={self.candidate_id})"
            )
        if not is_closed and has_closed_outcome:
            raise ClosedOutcomeMismatchError(
                f"{self.outcome_state} observation must not carry a closed_outcome, "
                f"got {self.closed_outcome!r} (candidate={self.candidate_id})"
            )


def validate_candidate_consistency(observations: Sequence[DirectionPolicyObservation]) -> None:
    """REQ-STAT-03: one `CandidateIdentity` carries exactly one economic
    outcome across all of its policy rows — only `relation` may differ."""
    seen: dict[CandidateIdentity, tuple[OutcomeState, ClosedTradeOutcome | None, float | None]] = {}
    for obs in observations:
        economic = (obs.outcome_state, obs.closed_outcome, obs.realized_r)
        prior = seen.get(obs.candidate_id)
        if prior is None:
            seen[obs.candidate_id] = economic
        elif prior != economic:
            raise CandidateOutcomeConsistencyError(
                f"candidate {obs.candidate_id} has inconsistent outcome across "
                f"policies: {prior} vs {economic}"
            )
