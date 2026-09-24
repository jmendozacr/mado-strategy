"""EST-B and instrument-delta arithmetic (REQ-STAT-05, REQ-STAT-06,
REQ-STAT-14). Expected values are computed independently by hand in each
test — never by calling `compute_est_b` itself — per the tautology-audit
rule (a self-validating test proves nothing about the arithmetic).
"""

import pytest

from selection.estimators import Computability, compute_est_b, compute_instrument_deltas
from selection.model import (
    CandidateIdentity,
    ClosedTradeOutcome,
    DirectionPolicyObservation,
    OutcomeState,
    Relation,
)

_POLICY = "direction_policy_structural_priority_v1"
_CLUSTER = ("EURUSDm", 10, 20, 25)


def _obs(signal_id: str, instrument: str, outcome_state: OutcomeState, relation: Relation, realized_r):
    closed_outcome = ClosedTradeOutcome.WIN if outcome_state == OutcomeState.CLOSED else None
    return DirectionPolicyObservation(
        candidate_id=CandidateIdentity(
            instrument=instrument, timeframe="15M", signal_id=signal_id, retest_index=42
        ),
        context_cluster_id=(instrument, 10, 20, 25),
        policy_id=_POLICY,
        relation=relation,
        outcome_state=outcome_state,
        closed_outcome=closed_outcome,
        realized_r=realized_r,
    )


# --- Group B: exact EST-B arithmetic -----------------------------------------


def test_est_b_matches_hand_computed_example():
    # ALIGNED: +1.0, +0.5 -> mean +0.75. OPPOSED: -1.0, +0.5 -> mean -0.25.
    # EST-B = 0.75 - (-0.25) = 1.00, independently verified by hand here.
    observations = [
        _obs("a1", "EURUSDm", OutcomeState.CLOSED, Relation.ALIGNED, 1.0),
        _obs("a2", "EURUSDm", OutcomeState.CLOSED, Relation.ALIGNED, 0.5),
        _obs("o1", "EURUSDm", OutcomeState.CLOSED, Relation.OPPOSED, -1.0),
        _obs("o2", "EURUSDm", OutcomeState.CLOSED, Relation.OPPOSED, 0.5),
    ]
    result = compute_est_b(observations, _POLICY)
    assert result.status == Computability.ESTIMABLE
    assert result.point == pytest.approx(1.00)


# --- Group C: UNRESOLVED must not shift EST-B --------------------------------


def test_unresolved_extreme_values_do_not_change_est_b():
    base = [
        _obs("a1", "EURUSDm", OutcomeState.CLOSED, Relation.ALIGNED, 1.0),
        _obs("o1", "EURUSDm", OutcomeState.CLOSED, Relation.OPPOSED, -1.0),
    ]
    baseline = compute_est_b(base, _POLICY)
    with_unresolved = base + [
        _obs("u1", "EURUSDm", OutcomeState.CLOSED, Relation.UNRESOLVED, 1_000_000.0),
        _obs("u2", "EURUSDm", OutcomeState.CLOSED, Relation.UNRESOLVED, -1_000_000.0),
    ]
    result = compute_est_b(with_unresolved, _POLICY)
    assert result.status == baseline.status == Computability.ESTIMABLE
    assert result.point == pytest.approx(baseline.point)


def test_open_and_never_filled_do_not_change_est_b():
    base = [
        _obs("a1", "EURUSDm", OutcomeState.CLOSED, Relation.ALIGNED, 1.0),
        _obs("o1", "EURUSDm", OutcomeState.CLOSED, Relation.OPPOSED, -1.0),
    ]
    baseline = compute_est_b(base, _POLICY)
    with_extra = base + [
        _obs("op1", "EURUSDm", OutcomeState.OPEN, Relation.ALIGNED, None),
        _obs("nf1", "EURUSDm", OutcomeState.NEVER_FILLED, Relation.OPPOSED, None),
    ]
    result = compute_est_b(with_extra, _POLICY)
    assert result.point == pytest.approx(baseline.point)


# --- Group E: NOT ESTIMABLE ---------------------------------------------------


def test_zero_closed_aligned_is_not_estimable():
    observations = [_obs("o1", "EURUSDm", OutcomeState.CLOSED, Relation.OPPOSED, -1.0)]
    result = compute_est_b(observations, _POLICY)
    assert result.status == Computability.NOT_ESTIMABLE
    assert result.point is None


def test_zero_closed_opposed_is_not_estimable():
    observations = [_obs("a1", "EURUSDm", OutcomeState.CLOSED, Relation.ALIGNED, 1.0)]
    result = compute_est_b(observations, _POLICY)
    assert result.status == Computability.NOT_ESTIMABLE
    assert result.point is None


def test_both_empty_is_not_estimable():
    observations: list = []
    result = compute_est_b(observations, _POLICY)
    assert result.status == Computability.NOT_ESTIMABLE
    assert result.point is None


# --- Group F: instrument delta -----------------------------------------------


def test_instrument_delta_computable_positive():
    observations = [
        _obs("a1", "EURUSDm", OutcomeState.CLOSED, Relation.ALIGNED, 1.0),
        _obs("o1", "EURUSDm", OutcomeState.CLOSED, Relation.OPPOSED, 0.5),
    ]
    deltas = compute_instrument_deltas(observations, _POLICY)
    assert len(deltas) == 1
    assert deltas[0].instrument == "EURUSDm"
    assert deltas[0].status == Computability.ESTIMABLE
    assert deltas[0].point == pytest.approx(0.5)


def test_instrument_delta_computable_negative():
    observations = [
        _obs("a1", "EURUSDm", OutcomeState.CLOSED, Relation.ALIGNED, -0.5),
        _obs("o1", "EURUSDm", OutcomeState.CLOSED, Relation.OPPOSED, 0.5),
    ]
    deltas = compute_instrument_deltas(observations, _POLICY)
    assert deltas[0].point == pytest.approx(-1.0)


def test_instrument_delta_exact_boundary_minus_point_two():
    observations = [
        _obs("a1", "EURUSDm", OutcomeState.CLOSED, Relation.ALIGNED, 0.0),
        _obs("o1", "EURUSDm", OutcomeState.CLOSED, Relation.OPPOSED, 0.20),
    ]
    deltas = compute_instrument_deltas(observations, _POLICY)
    assert deltas[0].point == pytest.approx(-0.20)


def test_instrument_delta_below_minus_point_two():
    observations = [
        _obs("a1", "EURUSDm", OutcomeState.CLOSED, Relation.ALIGNED, 0.0),
        _obs("o1", "EURUSDm", OutcomeState.CLOSED, Relation.OPPOSED, 0.30),
    ]
    deltas = compute_instrument_deltas(observations, _POLICY)
    assert deltas[0].point == pytest.approx(-0.30)


def test_instrument_delta_non_computable_because_aligned_empty():
    observations = [_obs("o1", "EURUSDm", OutcomeState.CLOSED, Relation.OPPOSED, 0.5)]
    deltas = compute_instrument_deltas(observations, _POLICY)
    assert deltas[0].status == Computability.NOT_ESTIMABLE
    assert deltas[0].point is None


def test_instrument_delta_non_computable_because_opposed_empty():
    observations = [_obs("a1", "EURUSDm", OutcomeState.CLOSED, Relation.ALIGNED, 0.5)]
    deltas = compute_instrument_deltas(observations, _POLICY)
    assert deltas[0].status == Computability.NOT_ESTIMABLE
    assert deltas[0].point is None


def test_instrument_deltas_never_cross_instruments():
    observations = [
        _obs("a1", "EURUSDm", OutcomeState.CLOSED, Relation.ALIGNED, 1.0),
        _obs("o1", "EURUSDm", OutcomeState.CLOSED, Relation.OPPOSED, 0.0),
        _obs("a2", "GBPUSDm", OutcomeState.CLOSED, Relation.ALIGNED, -1.0),
        _obs("o2", "GBPUSDm", OutcomeState.CLOSED, Relation.OPPOSED, 0.0),
    ]
    deltas = {d.instrument: d for d in compute_instrument_deltas(observations, _POLICY)}
    assert deltas["EURUSDm"].point == pytest.approx(1.0)
    assert deltas["GBPUSDm"].point == pytest.approx(-1.0)
