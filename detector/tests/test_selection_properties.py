"""Property tests for Layer-1 invariants that generalize better over random
synthetic input than over a single hand-picked example (spec.md REQ-STAT-03,
REQ-STAT-05, REQ-STAT-06, REQ-STAT-09, REQ-STAT-10). All data synthetic.
"""

import itertools
import random

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from selection.bootstrap import generate_cluster_resample_plan
from selection.estimators import compute_est_b
from selection.model import (
    CandidateIdentity,
    CandidateOutcomeConsistencyError,
    ClosedTradeOutcome,
    DirectionPolicyObservation,
    OutcomeState,
    Relation,
    validate_candidate_consistency,
)

_POLICY = "direction_policy_structural_priority_v1"
_R = st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False)
_counter = itertools.count()


def _candidate() -> CandidateIdentity:
    return CandidateIdentity(
        instrument="EURUSDm", timeframe="15M", signal_id=f"sig-{next(_counter)}", retest_index=1
    )


def _closed(relation: Relation, realized_r: float) -> DirectionPolicyObservation:
    return DirectionPolicyObservation(
        candidate_id=_candidate(),
        context_cluster_id=("EURUSDm", 0, 1, 2),
        policy_id=_POLICY,
        relation=relation,
        outcome_state=OutcomeState.CLOSED,
        closed_outcome=ClosedTradeOutcome.WIN,
        realized_r=realized_r,
    )


def _build_closed(aligned_rs, opposed_rs):
    return [_closed(Relation.ALIGNED, r) for r in aligned_rs] + [
        _closed(Relation.OPPOSED, r) for r in opposed_rs
    ]


# --- UNRESOLVED / OPEN / NEVER_FILLED additions never move EST-B ------------


@settings(max_examples=25)
@given(
    aligned_rs=st.lists(_R, min_size=1, max_size=5),
    opposed_rs=st.lists(_R, min_size=1, max_size=5),
    unresolved_rs=st.lists(
        st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=5,
    ),
)
def test_property_unresolved_additions_never_move_est_b(aligned_rs, opposed_rs, unresolved_rs):
    base = _build_closed(aligned_rs, opposed_rs)
    baseline = compute_est_b(base, _POLICY)
    extended = base + [_closed(Relation.UNRESOLVED, r) for r in unresolved_rs]
    result = compute_est_b(extended, _POLICY)
    assert result.status == baseline.status
    assert result.point == pytest.approx(baseline.point)


@settings(max_examples=25)
@given(aligned_rs=st.lists(_R, min_size=1, max_size=5), opposed_rs=st.lists(_R, min_size=1, max_size=5))
def test_property_open_additions_never_move_est_b(aligned_rs, opposed_rs):
    base = _build_closed(aligned_rs, opposed_rs)
    baseline = compute_est_b(base, _POLICY)
    extended = base + [
        DirectionPolicyObservation(
            candidate_id=_candidate(),
            context_cluster_id=("EURUSDm", 0, 1, 2),
            policy_id=_POLICY,
            relation=Relation.ALIGNED,
            outcome_state=OutcomeState.OPEN,
            closed_outcome=None,
            realized_r=None,
        )
    ]
    result = compute_est_b(extended, _POLICY)
    assert result.point == pytest.approx(baseline.point)


@settings(max_examples=25)
@given(aligned_rs=st.lists(_R, min_size=1, max_size=5), opposed_rs=st.lists(_R, min_size=1, max_size=5))
def test_property_never_filled_additions_never_move_est_b(aligned_rs, opposed_rs):
    base = _build_closed(aligned_rs, opposed_rs)
    baseline = compute_est_b(base, _POLICY)
    extended = base + [
        DirectionPolicyObservation(
            candidate_id=_candidate(),
            context_cluster_id=("EURUSDm", 0, 1, 2),
            policy_id=_POLICY,
            relation=Relation.OPPOSED,
            outcome_state=OutcomeState.NEVER_FILLED,
            closed_outcome=None,
            realized_r=None,
        )
    ]
    result = compute_est_b(extended, _POLICY)
    assert result.point == pytest.approx(baseline.point)


# --- Input order never changes the point estimate ----------------------------


@settings(max_examples=25)
@given(
    aligned_rs=st.lists(_R, min_size=1, max_size=6),
    opposed_rs=st.lists(_R, min_size=1, max_size=6),
    seed=st.integers(min_value=0, max_value=10_000),
)
def test_property_input_order_does_not_change_point_estimate(aligned_rs, opposed_rs, seed):
    observations = _build_closed(aligned_rs, opposed_rs)
    shuffled = observations.copy()
    random.Random(seed).shuffle(shuffled)
    original = compute_est_b(observations, _POLICY)
    reordered = compute_est_b(shuffled, _POLICY)
    assert original.point == pytest.approx(reordered.point)


# --- Same seed, same inputs -> identical resample plan -----------------------


@settings(max_examples=15)
@given(cluster_count=st.integers(min_value=1, max_value=5), replicates=st.integers(min_value=1, max_value=15))
def test_property_same_seed_yields_identical_plan(cluster_count, replicates):
    observations = [
        DirectionPolicyObservation(
            candidate_id=_candidate(),
            context_cluster_id=("EURUSDm", i, i + 1, i + 2),
            policy_id=_POLICY,
            relation=Relation.ALIGNED,
            outcome_state=OutcomeState.CLOSED,
            closed_outcome=ClosedTradeOutcome.WIN,
            realized_r=1.0,
        )
        for i in range(cluster_count)
    ]
    seed = np.random.SeedSequence([20260910])
    rng_a = np.random.Generator(np.random.PCG64(seed))
    rng_b = np.random.Generator(np.random.PCG64(np.random.SeedSequence([20260910])))
    plan_a = generate_cluster_resample_plan(observations, ("EURUSDm",), rng_a, replicates=replicates)
    plan_b = generate_cluster_resample_plan(observations, ("EURUSDm",), rng_b, replicates=replicates)
    assert plan_a == plan_b


# --- Candidate economic consistency (REQ-STAT-03) fail-closed ---------------


def test_property_consistent_candidate_across_policies_never_raises():
    candidate = _candidate()
    observations = [
        DirectionPolicyObservation(
            candidate_id=candidate,
            context_cluster_id=("EURUSDm", 0, 1, 2),
            policy_id=policy_id,
            relation=relation,
            outcome_state=OutcomeState.CLOSED,
            closed_outcome=ClosedTradeOutcome.WIN,
            realized_r=1.0,
        )
        for policy_id, relation in [
            ("P1", Relation.ALIGNED),
            ("P2", Relation.OPPOSED),
            ("P3", Relation.UNRESOLVED),
            ("P4", Relation.ALIGNED),
        ]
    ]
    validate_candidate_consistency(observations)  # must not raise


def test_property_inconsistent_candidate_across_policies_always_raises():
    candidate = _candidate()
    observations = [
        DirectionPolicyObservation(
            candidate_id=candidate,
            context_cluster_id=("EURUSDm", 0, 1, 2),
            policy_id="P1",
            relation=Relation.ALIGNED,
            outcome_state=OutcomeState.CLOSED,
            closed_outcome=ClosedTradeOutcome.WIN,
            realized_r=1.0,
        ),
        DirectionPolicyObservation(
            candidate_id=candidate,
            context_cluster_id=("EURUSDm", 0, 1, 2),
            policy_id="P2",
            relation=Relation.OPPOSED,
            outcome_state=OutcomeState.CLOSED,
            closed_outcome=ClosedTradeOutcome.WIN,
            realized_r=2.0,  # differs -> violates REQ-STAT-03
        ),
    ]
    with pytest.raises(CandidateOutcomeConsistencyError):
        validate_candidate_consistency(observations)
