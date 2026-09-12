"""Layer-1 domain model construction invariants (REQ-STAT-01, REQ-STAT-03).

Every fixture here is SYNTHETIC — no real Trade/Stage6Population/outcome is
read. This module proves only that `DirectionPolicyObservation` enforces its
own construction contract; it never touches join/cluster/bootstrap logic.
"""

import math

import pytest

from selection.model import (
    CandidateIdentity,
    CandidateOutcomeConsistencyError,
    ClosedOutcomeMismatchError,
    ClosedTradeOutcome,
    DirectionPolicyObservation,
    OutcomeRealizedRMismatchError,
    OutcomeState,
    Relation,
    validate_candidate_consistency,
)

_CANDIDATE = CandidateIdentity(
    instrument="EURUSDm", timeframe="15M", signal_id="sig-1", retest_index=42
)
_CLUSTER = ("EURUSDm", 10, 20, 25)


def _observation(
    outcome_state: OutcomeState,
    realized_r: float | None,
    closed_outcome: ClosedTradeOutcome | None = None,
    relation: Relation = Relation.ALIGNED,
):
    return DirectionPolicyObservation(
        candidate_id=_CANDIDATE,
        context_cluster_id=_CLUSTER,
        policy_id="direction_policy_structural_priority_v1",
        relation=relation,
        outcome_state=outcome_state,
        closed_outcome=closed_outcome,
        realized_r=realized_r,
    )


# --- Group A: CLOSED / OPEN / NEVER_FILLED invariants ------------------------


def test_closed_with_win_and_finite_r_is_valid():
    obs = _observation(OutcomeState.CLOSED, 1.5, ClosedTradeOutcome.WIN)
    assert obs.outcome_state == OutcomeState.CLOSED
    assert obs.closed_outcome == ClosedTradeOutcome.WIN
    assert obs.realized_r == 1.5


def test_closed_with_loss_and_finite_r_is_valid():
    obs = _observation(OutcomeState.CLOSED, -0.8, ClosedTradeOutcome.LOSS)
    assert obs.closed_outcome == ClosedTradeOutcome.LOSS


def test_closed_with_none_is_invalid():
    with pytest.raises(OutcomeRealizedRMismatchError):
        _observation(OutcomeState.CLOSED, None, ClosedTradeOutcome.WIN)


def test_open_with_none_is_valid():
    obs = _observation(OutcomeState.OPEN, None)
    assert obs.realized_r is None
    assert obs.closed_outcome is None


def test_open_with_r_is_invalid():
    with pytest.raises(OutcomeRealizedRMismatchError):
        _observation(OutcomeState.OPEN, 1.0)


def test_never_filled_with_none_is_valid():
    obs = _observation(OutcomeState.NEVER_FILLED, None)
    assert obs.realized_r is None
    assert obs.closed_outcome is None


def test_never_filled_with_r_is_invalid():
    with pytest.raises(OutcomeRealizedRMismatchError):
        _observation(OutcomeState.NEVER_FILLED, 1.0)


@pytest.mark.parametrize("bad_r", [math.nan, math.inf, -math.inf])
def test_closed_with_non_finite_r_is_invalid(bad_r):
    with pytest.raises(OutcomeRealizedRMismatchError):
        _observation(OutcomeState.CLOSED, bad_r, ClosedTradeOutcome.WIN)


# --- closed_outcome invariants (V2: spec.md Section C/C2, REQ-STAT-01) -------


def test_closed_with_finite_r_but_no_closed_outcome_is_invalid():
    with pytest.raises(ClosedOutcomeMismatchError):
        _observation(OutcomeState.CLOSED, 1.0, closed_outcome=None)


def test_closed_with_closed_outcome_but_no_r_is_invalid():
    with pytest.raises(OutcomeRealizedRMismatchError):
        _observation(OutcomeState.CLOSED, None, ClosedTradeOutcome.WIN)


def test_open_with_closed_outcome_is_invalid():
    with pytest.raises(ClosedOutcomeMismatchError):
        _observation(OutcomeState.OPEN, None, ClosedTradeOutcome.WIN)


def test_never_filled_with_closed_outcome_is_invalid():
    with pytest.raises(ClosedOutcomeMismatchError):
        _observation(OutcomeState.NEVER_FILLED, None, ClosedTradeOutcome.LOSS)


# --- Group W: candidate economic pairing (REQ-STAT-03) -----------------------


def test_same_candidate_identical_economics_across_policies_is_valid():
    observations = [
        DirectionPolicyObservation(
            candidate_id=_CANDIDATE,
            context_cluster_id=_CLUSTER,
            policy_id=policy_id,
            relation=relation,
            outcome_state=OutcomeState.CLOSED,
            closed_outcome=ClosedTradeOutcome.WIN,
            realized_r=1.0,
        )
        for policy_id, relation in [
            ("direction_policy_structural_priority_v1", Relation.ALIGNED),
            ("direction_policy_corroboration_v1", Relation.OPPOSED),
            ("direction_policy_noncontradiction_v1", Relation.UNRESOLVED),
            ("direction_policy_bias_veto_v1", Relation.ALIGNED),
        ]
    ]
    validate_candidate_consistency(observations)  # must not raise


def test_same_candidate_differing_realized_r_across_policies_is_invalid():
    observations = [
        DirectionPolicyObservation(
            candidate_id=_CANDIDATE,
            context_cluster_id=_CLUSTER,
            policy_id="direction_policy_structural_priority_v1",
            relation=Relation.ALIGNED,
            outcome_state=OutcomeState.CLOSED,
            closed_outcome=ClosedTradeOutcome.WIN,
            realized_r=1.0,
        ),
        DirectionPolicyObservation(
            candidate_id=_CANDIDATE,
            context_cluster_id=_CLUSTER,
            policy_id="direction_policy_corroboration_v1",
            relation=Relation.OPPOSED,
            outcome_state=OutcomeState.CLOSED,
            closed_outcome=ClosedTradeOutcome.WIN,
            realized_r=-1.0,
        ),
    ]
    with pytest.raises(CandidateOutcomeConsistencyError):
        validate_candidate_consistency(observations)


def test_same_candidate_differing_outcome_state_across_policies_is_invalid():
    observations = [
        DirectionPolicyObservation(
            candidate_id=_CANDIDATE,
            context_cluster_id=_CLUSTER,
            policy_id="direction_policy_structural_priority_v1",
            relation=Relation.ALIGNED,
            outcome_state=OutcomeState.CLOSED,
            closed_outcome=ClosedTradeOutcome.WIN,
            realized_r=1.0,
        ),
        DirectionPolicyObservation(
            candidate_id=_CANDIDATE,
            context_cluster_id=_CLUSTER,
            policy_id="direction_policy_corroboration_v1",
            relation=Relation.OPPOSED,
            outcome_state=OutcomeState.OPEN,
            closed_outcome=None,
            realized_r=None,
        ),
    ]
    with pytest.raises(CandidateOutcomeConsistencyError):
        validate_candidate_consistency(observations)


def test_same_candidate_differing_closed_outcome_across_policies_is_invalid():
    """V2: closed_outcome is part of the candidate's single economic outcome
    (REQ-STAT-03) — it must agree across all 4 policy rows, exactly like
    outcome_state/realized_r. Only `relation` may differ."""
    observations = [
        DirectionPolicyObservation(
            candidate_id=_CANDIDATE,
            context_cluster_id=_CLUSTER,
            policy_id="direction_policy_structural_priority_v1",
            relation=Relation.ALIGNED,
            outcome_state=OutcomeState.CLOSED,
            closed_outcome=ClosedTradeOutcome.WIN,
            realized_r=1.0,
        ),
        DirectionPolicyObservation(
            candidate_id=_CANDIDATE,
            context_cluster_id=_CLUSTER,
            policy_id="direction_policy_corroboration_v1",
            relation=Relation.OPPOSED,
            outcome_state=OutcomeState.CLOSED,
            closed_outcome=ClosedTradeOutcome.LOSS,
            realized_r=1.0,
        ),
    ]
    with pytest.raises(CandidateOutcomeConsistencyError):
        validate_candidate_consistency(observations)
