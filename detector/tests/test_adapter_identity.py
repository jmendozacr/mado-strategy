"""Groups A/B/C (spec.md Section A/D, REQ-STAT-01/02/26/27): CandidateIdentity
recovery, Candidate<->DirectionEvaluation reconciliation, and the explicit
relation mapping. Synthetic fixtures only (no real Stage6Population)."""

from datetime import datetime, timedelta

import pytest

from adapter.errors import CandidateReconciliationError, RelationMappingError
from adapter.identity import (
    FROZEN_TIMEFRAME,
    recover_candidate_identity,
    reconcile_candidate_evaluations,
    reconcile_population_evaluations,
)
from adapter.relation import map_relation
from backtest.candidate import Candidate
from core.candle import Candle, OHLCSeries
from evaluation.direction import DirectionEvaluation, FROZEN_POLICY_IDS, PolicyRelation
from policy.direction import DirectionDecision
from selection.model import CandidateIdentity, Relation


def _series(instrument: str = "EURUSDm", timeframe: str = "15M", size: int = 6) -> OHLCSeries:
    candles = tuple(
        Candle(
            timestamp=datetime(2026, 1, 1) + timedelta(minutes=15 * i),
            open=1.0, high=1.1, low=0.9, close=1.05,
        )
        for i in range(size)
    )
    return OHLCSeries(candles=candles, instrument=instrument, timeframe=timeframe)


def _candidate(signal_id: str = "0-1-bullish-purge_engulf-wick", retest_index: int = 3) -> Candidate:
    return Candidate(
        signal_id=signal_id, anchor_index=1, origin_index=0, direction="bullish",
        entry_type="wick", retest_index=retest_index, entry_price=1.0, stop_loss=0.9,
        take_profit=1.2, partial_price=1.1,
    )


def _decision(policy_id: str, direction: str = "bullish") -> DirectionDecision:
    return DirectionDecision(
        policy_id=policy_id, cutoff_index=2, direction=direction,
        order_flow_confirmation_index=None, order_flow_direction=None,
        normalized_bias_direction=None, reason="NO_EVIDENCE",
    )


def _evaluation(
    identity: CandidateIdentity, policy_id: str, relation: PolicyRelation = PolicyRelation.ALIGNED,
) -> DirectionEvaluation:
    return DirectionEvaluation(
        instrument=identity.instrument, timeframe=identity.timeframe, signal_id=identity.signal_id,
        retest_index=identity.retest_index, candidate_direction="bullish",
        decision=_decision(policy_id), relation=relation,
    )


def _four_evaluations(identity: CandidateIdentity) -> list[DirectionEvaluation]:
    return [_evaluation(identity, policy_id) for policy_id in FROZEN_POLICY_IDS]


# --- Group A: CandidateIdentity recovery -------------------------------------


def test_recovers_full_four_tuple_identity():
    series = _series()
    candidate = _candidate()
    identity = recover_candidate_identity(series, candidate)
    assert identity == CandidateIdentity(
        instrument="EURUSDm", timeframe="15M", signal_id=candidate.signal_id, retest_index=3
    )


def test_frozen_timeframe_literal_is_15m():
    assert FROZEN_TIMEFRAME == "15M"


def test_unexpected_timeframe_fails_closed_never_normalized():
    series = _series(timeframe="M15")  # a plausible-looking near-miss, never normalized
    with pytest.raises(CandidateReconciliationError):
        recover_candidate_identity(series, _candidate())


# --- Group B: Candidate<->DirectionEvaluation reconciliation -----------------


def test_exactly_four_rows_one_per_policy_reconciles():
    identity = recover_candidate_identity(_series(), _candidate())
    evaluations = _four_evaluations(identity)
    by_policy = reconcile_candidate_evaluations(identity, evaluations)
    assert set(by_policy) == set(FROZEN_POLICY_IDS)
    assert all(row.decision.policy_id == policy_id for policy_id, row in by_policy.items())


def test_missing_policy_fails_closed():
    identity = recover_candidate_identity(_series(), _candidate())
    evaluations = _four_evaluations(identity)[:3]  # drop one policy
    with pytest.raises(CandidateReconciliationError):
        reconcile_candidate_evaluations(identity, evaluations)


def test_duplicate_policy_fails_closed():
    identity = recover_candidate_identity(_series(), _candidate())
    evaluations = _four_evaluations(identity)[:3] + [_four_evaluations(identity)[0]]
    with pytest.raises(CandidateReconciliationError):
        reconcile_candidate_evaluations(identity, evaluations)


def test_unexpected_policy_id_fails_closed():
    identity = recover_candidate_identity(_series(), _candidate())
    evaluations = _four_evaluations(identity)[:3] + [
        _evaluation(identity, "direction_policy_never_registered_v1")
    ]
    with pytest.raises(CandidateReconciliationError):
        reconcile_candidate_evaluations(identity, evaluations)


def test_orphan_evaluation_row_fails_closed():
    """A DirectionEvaluation naming a signal_id no Candidate owns — a
    whole-run concern, since a per-candidate lookup naturally ignores rows
    belonging to other identities."""
    identity = recover_candidate_identity(_series(), _candidate())
    orphan_identity = CandidateIdentity(
        instrument=identity.instrument, timeframe=identity.timeframe,
        signal_id="no-such-signal", retest_index=identity.retest_index,
    )
    evaluations = _four_evaluations(identity) + [_evaluation(orphan_identity, FROZEN_POLICY_IDS[0])]
    with pytest.raises(CandidateReconciliationError):
        reconcile_population_evaluations([identity], evaluations)


def test_candidate_without_any_evaluation_rows_fails_closed():
    identity = recover_candidate_identity(_series(), _candidate())
    with pytest.raises(CandidateReconciliationError):
        reconcile_candidate_evaluations(identity, [])


def test_identity_mismatch_across_rows_fails_closed():
    """Rows referencing the right signal_id but a different retest_index."""
    identity = recover_candidate_identity(_series(), _candidate())
    mismatched = CandidateIdentity(
        instrument=identity.instrument, timeframe=identity.timeframe,
        signal_id=identity.signal_id, retest_index=identity.retest_index + 1,
    )
    evaluations = _four_evaluations(identity)[:3] + [_evaluation(mismatched, FROZEN_POLICY_IDS[3])]
    with pytest.raises(CandidateReconciliationError):
        reconcile_candidate_evaluations(identity, evaluations)


# --- Group C: relation mapping -----------------------------------------------


@pytest.mark.parametrize(
    "policy_relation, expected",
    [
        (PolicyRelation.ALIGNED, Relation.ALIGNED),
        (PolicyRelation.OPPOSED, Relation.OPPOSED),
        (PolicyRelation.UNRESOLVED, Relation.UNRESOLVED),
    ],
)
def test_explicit_exhaustive_relation_mapping(policy_relation, expected):
    assert map_relation(policy_relation) is expected


def test_unexpected_relation_value_fails_closed():
    with pytest.raises(RelationMappingError):
        map_relation("SOMETHING_ELSE")
