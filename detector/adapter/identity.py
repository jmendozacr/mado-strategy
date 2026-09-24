"""Groups A/B (spec.md Section A/D, REQ-STAT-01/02/26): CandidateIdentity
recovery from a frozen Stage6Population Candidate, and independent
Candidate<->DirectionEvaluation reconciliation — never merely trusting the
upstream evaluation seam's own frozen invariant (REQ-STAT-26)."""

from collections.abc import Sequence

from adapter.errors import CandidateReconciliationError
from backtest.candidate import Candidate
from core.candle import OHLCSeries
from evaluation.direction import DirectionEvaluation, FROZEN_POLICY_IDS
from selection.model import CandidateIdentity

FROZEN_TIMEFRAME = "15M"


def recover_candidate_identity(series: OHLCSeries, candidate: Candidate) -> CandidateIdentity:
    """The full `population.key` 4-tuple (spec.md Section A), read directly
    off the owning `OHLCSeries` + `Candidate`. `timeframe` is frozen to the
    literal `"15M"` — an unexpected value (e.g. `"M15"`) is never normalized,
    it fails closed."""
    if series.timeframe != FROZEN_TIMEFRAME:
        raise CandidateReconciliationError(
            f"series.timeframe must be the frozen literal {FROZEN_TIMEFRAME!r}, "
            f"got {series.timeframe!r} — never normalized"
        )
    return CandidateIdentity(
        instrument=series.instrument,
        timeframe=series.timeframe,
        signal_id=candidate.signal_id,
        retest_index=candidate.retest_index,
    )


def _identity_of(row: DirectionEvaluation) -> CandidateIdentity:
    return CandidateIdentity(
        instrument=row.instrument, timeframe=row.timeframe,
        signal_id=row.signal_id, retest_index=row.retest_index,
    )


def reconcile_candidate_evaluations(
    identity: CandidateIdentity, evaluations: Sequence[DirectionEvaluation]
) -> dict[str, DirectionEvaluation]:
    """REQ-STAT-26: independently verify — never merely trust
    `evaluation.direction`'s own invariant — that exactly 4 rows exist for
    `identity`, one per `FROZEN_POLICY_IDS` member, all sharing the identical
    4-tuple identity. Missing policy, duplicate policy, unexpected policy ID,
    or any cross-row identity mismatch fails closed with
    `CandidateReconciliationError`."""
    matching = [row for row in evaluations if _identity_of(row) == identity]
    if len(matching) != len(FROZEN_POLICY_IDS):
        raise CandidateReconciliationError(
            f"candidate {identity} has {len(matching)} DirectionEvaluation rows, "
            f"expected exactly {len(FROZEN_POLICY_IDS)}"
        )

    by_policy: dict[str, DirectionEvaluation] = {}
    for row in matching:
        policy_id = row.decision.policy_id
        if policy_id not in FROZEN_POLICY_IDS:
            raise CandidateReconciliationError(
                f"candidate {identity}: unexpected policy_id {policy_id!r}"
            )
        if policy_id in by_policy:
            raise CandidateReconciliationError(
                f"candidate {identity}: duplicate policy_id {policy_id!r}"
            )
        by_policy[policy_id] = row

    if set(by_policy) != set(FROZEN_POLICY_IDS):
        missing = set(FROZEN_POLICY_IDS) - set(by_policy)
        raise CandidateReconciliationError(
            f"candidate {identity}: missing policy_id(s) {sorted(missing)}"
        )
    return by_policy


def reconcile_population_evaluations(
    identities: Sequence[CandidateIdentity], evaluations: Sequence[DirectionEvaluation]
) -> dict[CandidateIdentity, dict[str, DirectionEvaluation]]:
    """Whole-run reconciliation (Section C's join-integrity table, condition
    1 / REQ-STAT-01/02): every evaluation row MUST reconcile against one of
    `identities` — a row naming a `signal_id`/identity no Candidate owns
    (an orphan) fails closed, not just a per-candidate short count."""
    known = set(identities)
    for row in evaluations:
        if _identity_of(row) not in known:
            raise CandidateReconciliationError(
                f"orphan DirectionEvaluation row: {_identity_of(row)} matches no "
                f"Candidate in this run's Stage6Population"
            )
    return {
        identity: reconcile_candidate_evaluations(identity, evaluations)
        for identity in identities
    }
