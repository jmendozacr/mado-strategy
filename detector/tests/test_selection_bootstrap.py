"""Paired instrument-stratified cluster bootstrap (spec.md Section E,
REQ-STAT-07..12). All fixtures synthetic; RNG draws are either hand-fixed
(`ResamplePlan` built directly, no RNG involved) or, where RNG determinism
itself is under test, re-derived independently via the same public numpy
API rather than by calling the production wrapper twice and trusting it.
"""

import numpy as np
import pytest

from selection.bootstrap import (
    FROZEN_REPLICATES,
    FROZEN_SEED_SEQUENCE,
    CIComputability,
    ReplicateStatus,
    ResamplePlan,
    apply_plan_to_policy,
    bootstrap_est_b,
    bootstrap_universe,
    frozen_rng,
    generate_cluster_resample_plan,
    percentile_ci,
)
from selection.model import (
    CandidateIdentity,
    ClosedTradeOutcome,
    DirectionPolicyObservation,
    OutcomeState,
    Relation,
)

CLUSTER_A = ("EURUSDm", 0, 5, 6)
CLUSTER_B = ("EURUSDm", 10, 15, 16)
CLUSTER_C = ("GBPUSDm", 0, 5, 6)
CLUSTER_D = ("GBPUSDm", 10, 15, 16)


def _obs(signal_id, instrument, cluster, outcome_state, relation, realized_r, policy_id="P1"):
    closed_outcome = ClosedTradeOutcome.WIN if outcome_state == OutcomeState.CLOSED else None
    return DirectionPolicyObservation(
        candidate_id=CandidateIdentity(
            instrument=instrument, timeframe="15M", signal_id=signal_id, retest_index=1
        ),
        context_cluster_id=cluster,
        policy_id=policy_id,
        relation=relation,
        outcome_state=outcome_state,
        closed_outcome=closed_outcome,
        realized_r=realized_r,
    )


# --- Group G/H/I: cluster identity, U-1 universe, instrument stratification --


def test_u1_universe_excludes_open_only_and_never_filled_only_clusters():
    observations = [
        _obs("a1", "EURUSDm", CLUSTER_A, OutcomeState.CLOSED, Relation.ALIGNED, 1.0),
        _obs("a2", "EURUSDm", CLUSTER_A, OutcomeState.OPEN, Relation.ALIGNED, None),
        _obs("b1", "EURUSDm", CLUSTER_B, OutcomeState.OPEN, Relation.ALIGNED, None),
        _obs("c1", "GBPUSDm", CLUSTER_C, OutcomeState.NEVER_FILLED, Relation.OPPOSED, None),
        _obs("d1", "GBPUSDm", CLUSTER_D, OutcomeState.CLOSED, Relation.OPPOSED, -1.0),
    ]
    assert bootstrap_universe(observations, "EURUSDm") == (CLUSTER_A,)
    assert bootstrap_universe(observations, "GBPUSDm") == (CLUSTER_D,)


def test_u1_universe_never_crosses_instruments():
    observations = [
        _obs("a1", "EURUSDm", CLUSTER_A, OutcomeState.CLOSED, Relation.ALIGNED, 1.0),
        _obs("d1", "GBPUSDm", CLUSTER_D, OutcomeState.CLOSED, Relation.OPPOSED, -1.0),
    ]
    assert CLUSTER_D not in bootstrap_universe(observations, "EURUSDm")
    assert CLUSTER_A not in bootstrap_universe(observations, "GBPUSDm")


# --- Group J: paired resampling across P1-P4 ---------------------------------


def test_apply_plan_uses_the_same_draw_across_policies():
    cluster_x = ("EURUSDm", 0, 5, 6)
    cluster_y = ("EURUSDm", 10, 15, 16)
    observations = [
        _obs("x1", "EURUSDm", cluster_x, OutcomeState.CLOSED, Relation.ALIGNED, 1.0, policy_id="P1"),
        _obs("x1", "EURUSDm", cluster_x, OutcomeState.CLOSED, Relation.OPPOSED, 1.0, policy_id="P2"),
        _obs("y1", "EURUSDm", cluster_y, OutcomeState.CLOSED, Relation.OPPOSED, -2.0, policy_id="P1"),
        _obs("y1", "EURUSDm", cluster_y, OutcomeState.CLOSED, Relation.ALIGNED, -2.0, policy_id="P2"),
    ]
    # universe sorts to (cluster_x, cluster_y); draw (1, 0) means "cluster_y
    # once, cluster_x once" -- hand-fixed, no RNG involved.
    plan = ResamplePlan(
        instruments=("EURUSDm",),
        universes={"EURUSDm": (cluster_x, cluster_y)},
        draws=({"EURUSDm": (1, 0)},),
    )
    result_p1 = apply_plan_to_policy(observations, "P1", plan, 0)
    result_p2 = apply_plan_to_policy(observations, "P2", plan, 0)

    # P1: ALIGNED={1.0} (cluster_x), OPPOSED={-2.0} (cluster_y) -> 1.0-(-2.0)=3.0
    assert result_p1.status == ReplicateStatus.VALID
    assert result_p1.point == pytest.approx(3.0)
    # P2 (same draw, opposite relation labelling): ALIGNED={-2.0}, OPPOSED={1.0} -> -3.0
    assert result_p2.status == ReplicateStatus.VALID
    assert result_p2.point == pytest.approx(-3.0)


def test_apply_plan_replicates_cluster_contribution_when_drawn_twice():
    cluster_x = ("EURUSDm", 0, 5, 6)
    cluster_y = ("EURUSDm", 10, 15, 16)
    observations = [
        _obs("x1", "EURUSDm", cluster_x, OutcomeState.CLOSED, Relation.ALIGNED, 1.0),
        _obs("y1", "EURUSDm", cluster_y, OutcomeState.CLOSED, Relation.OPPOSED, -1.0),
    ]
    plan = ResamplePlan(
        instruments=("EURUSDm",),
        universes={"EURUSDm": (cluster_x, cluster_y)},
        draws=({"EURUSDm": (0, 0, 1)},),
    )
    result = apply_plan_to_policy(observations, "P1", plan, 0)
    # ALIGNED={1.0, 1.0} mean=1.0, OPPOSED={-1.0} mean=-1.0 -> 1.0-(-1.0)=2.0
    assert result.point == pytest.approx(2.0)


# --- Group L / U-2: one undefined replicate poisons the whole CI ------------


def test_one_undefined_replicate_makes_ci_not_computable():
    cluster_x = ("EURUSDm", 0, 5, 6)
    cluster_y = ("EURUSDm", 10, 15, 16)
    observations = [
        _obs("x1", "EURUSDm", cluster_x, OutcomeState.CLOSED, Relation.ALIGNED, 1.0),
        _obs("y1", "EURUSDm", cluster_y, OutcomeState.CLOSED, Relation.OPPOSED, -1.0),
    ]
    plan = ResamplePlan(
        instruments=("EURUSDm",),
        universes={"EURUSDm": (cluster_x, cluster_y)},
        draws=(
            {"EURUSDm": (0, 1)},  # valid
            {"EURUSDm": (0, 0)},  # undefined: only ALIGNED drawn, OPPOSED empty
            {"EURUSDm": (1, 0)},  # valid
        ),
    )
    result = bootstrap_est_b(observations, "P1", plan)
    assert result.ci_status == CIComputability.NOT_COMPUTABLE
    assert result.lower is None
    assert result.upper is None


def test_all_valid_replicates_yield_computable_ci():
    cluster_x = ("EURUSDm", 0, 5, 6)
    observations = [
        _obs("x1", "EURUSDm", cluster_x, OutcomeState.CLOSED, Relation.ALIGNED, 1.0),
        _obs("x2", "EURUSDm", cluster_x, OutcomeState.CLOSED, Relation.OPPOSED, -1.0),
    ]
    plan = ResamplePlan(
        instruments=("EURUSDm",),
        universes={"EURUSDm": (cluster_x,)},
        draws=({"EURUSDm": (0,)},) * 5,
    )
    result = bootstrap_est_b(observations, "P1", plan)
    assert result.ci_status == CIComputability.COMPUTABLE
    assert isinstance(result.lower, float)
    assert isinstance(result.upper, float)


# --- Group M: percentile CI, exact bounds via independent hand arithmetic ---


def test_percentile_ci_matches_hand_computed_linear_interpolation():
    # N=5, sorted [10,20,30,40,50]. Linear-method rank = p/100*(N-1).
    # 0.625th: rank=0.025 -> 10 + 0.025*(20-10) = 10.25
    # 99.375th: rank=3.975 -> 40 + 0.975*(50-40) = 49.75
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    lower, upper = percentile_ci(values)
    assert lower == pytest.approx(10.25)
    assert upper == pytest.approx(49.75)


def test_percentile_ci_matches_raw_numpy_call_with_frozen_params():
    values = list(range(1, 101))
    expected_lower, expected_upper = np.percentile(values, [0.625, 99.375], method="linear")
    lower, upper = percentile_ci(values)
    assert lower == pytest.approx(expected_lower)
    assert upper == pytest.approx(expected_upper)


# --- Group K: deterministic RNG ----------------------------------------------


def test_frozen_rng_matches_exact_frozen_construction():
    expected = np.random.Generator(np.random.PCG64(np.random.SeedSequence([20260910])))
    actual = frozen_rng()
    assert list(expected.integers(0, 1000, size=5)) == list(actual.integers(0, 1000, size=5))


def test_same_seed_and_inputs_yield_identical_plan():
    observations = [
        _obs("a1", "EURUSDm", CLUSTER_A, OutcomeState.CLOSED, Relation.ALIGNED, 1.0),
        _obs("d1", "GBPUSDm", CLUSTER_D, OutcomeState.CLOSED, Relation.OPPOSED, -1.0),
    ]
    plan1 = generate_cluster_resample_plan(observations, ("EURUSDm", "GBPUSDm"), frozen_rng(), replicates=25)
    plan2 = generate_cluster_resample_plan(observations, ("EURUSDm", "GBPUSDm"), frozen_rng(), replicates=25)
    assert plan1 == plan2


def test_different_generator_yields_different_draws():
    observations = [
        _obs("a1", "EURUSDm", CLUSTER_A, OutcomeState.CLOSED, Relation.ALIGNED, 1.0),
        _obs("b1", "EURUSDm", CLUSTER_B, OutcomeState.CLOSED, Relation.OPPOSED, -1.0),
    ]
    plan_frozen = generate_cluster_resample_plan(observations, ("EURUSDm",), frozen_rng(), replicates=20)
    plan_other = generate_cluster_resample_plan(
        observations, ("EURUSDm",), np.random.default_rng(123), replicates=20
    )
    assert plan_frozen.draws != plan_other.draws


def test_frozen_replicate_count_and_seed_sequence():
    assert FROZEN_REPLICATES == 10_000
    assert FROZEN_SEED_SEQUENCE == (20260910,)


# --- Group V: policy iteration order does not change per-policy results -----


def test_policy_call_order_does_not_change_bootstrap_result():
    cluster_x = ("EURUSDm", 0, 5, 6)
    cluster_y = ("EURUSDm", 10, 15, 16)
    observations = [
        _obs("x1", "EURUSDm", cluster_x, OutcomeState.CLOSED, Relation.ALIGNED, 1.0, policy_id="P1"),
        _obs("x2", "EURUSDm", cluster_x, OutcomeState.CLOSED, Relation.ALIGNED, 2.0, policy_id="P2"),
        _obs("y1", "EURUSDm", cluster_y, OutcomeState.CLOSED, Relation.OPPOSED, -1.0, policy_id="P1"),
        _obs("y2", "EURUSDm", cluster_y, OutcomeState.CLOSED, Relation.OPPOSED, -2.0, policy_id="P2"),
    ]
    plan = ResamplePlan(
        instruments=("EURUSDm",),
        universes={"EURUSDm": (cluster_x, cluster_y)},
        draws=({"EURUSDm": (0, 1)},) * 5,
    )
    p1_first = bootstrap_est_b(observations, "P1", plan)
    p2_first = bootstrap_est_b(observations, "P2", plan)
    p2_again = bootstrap_est_b(observations, "P2", plan)
    p1_again = bootstrap_est_b(observations, "P1", plan)
    assert p1_first == p1_again
    assert p2_first == p2_again
    assert p1_first != p2_first


# --- Frozen V1 experiment config, exercised at full scale on tiny data -----


def test_frozen_replicate_count_runs_end_to_end_on_synthetic_data():
    cluster_x = ("EURUSDm", 0, 5, 6)
    observations = [
        _obs("x1", "EURUSDm", cluster_x, OutcomeState.CLOSED, Relation.ALIGNED, 1.0),
        _obs("x2", "EURUSDm", cluster_x, OutcomeState.CLOSED, Relation.OPPOSED, -1.0),
    ]
    plan = generate_cluster_resample_plan(
        observations, ("EURUSDm",), frozen_rng(), replicates=FROZEN_REPLICATES
    )
    result = bootstrap_est_b(observations, "P1", plan)
    assert result.ci_status == CIComputability.COMPUTABLE
