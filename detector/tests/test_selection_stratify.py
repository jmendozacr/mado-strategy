"""Stratum construction (REQ-STAT-04, REQ-STAT-06) — synthetic fixtures only.

Group C (UNRESOLVED reportability) and Group D (OPEN/NEVER_FILLED distinct
counts) live here: they are properties of `stratify()`'s grouping, not of
any single estimator. WR tests (V2, spec.md Section C2/E) live here too —
WR is a stratum-level statistic, computed alongside N/share/MeanR.
"""

from selection.estimators import Computability
from selection.model import (
    CandidateIdentity,
    ClosedTradeOutcome,
    DirectionPolicyObservation,
    OutcomeState,
    Relation,
)
from selection.stratify import stratify

_POLICY = "direction_policy_structural_priority_v1"
_CLUSTER = ("EURUSDm", 10, 20, 25)


def _candidate(signal_id: str) -> CandidateIdentity:
    return CandidateIdentity(instrument="EURUSDm", timeframe="15M", signal_id=signal_id, retest_index=42)


def _obs(
    signal_id: str,
    outcome_state: OutcomeState,
    relation: Relation,
    realized_r: float | None,
    closed_outcome: ClosedTradeOutcome | None = None,
):
    if closed_outcome is None and outcome_state == OutcomeState.CLOSED:
        closed_outcome = ClosedTradeOutcome.WIN  # arbitrary valid default for tests that don't care about WR
    return DirectionPolicyObservation(
        candidate_id=_candidate(signal_id),
        context_cluster_id=_CLUSTER,
        policy_id=_POLICY,
        relation=relation,
        outcome_state=outcome_state,
        closed_outcome=closed_outcome,
        realized_r=realized_r,
    )


def test_closed_open_never_filled_counts_are_distinct():
    observations = [
        _obs("c1", OutcomeState.CLOSED, Relation.ALIGNED, 1.0),
        _obs("c2", OutcomeState.CLOSED, Relation.OPPOSED, -1.0),
        _obs("c3", OutcomeState.OPEN, Relation.ALIGNED, None),
        _obs("c4", OutcomeState.OPEN, Relation.ALIGNED, None),
        _obs("c5", OutcomeState.OPEN, Relation.ALIGNED, None),
        _obs("c6", OutcomeState.NEVER_FILLED, Relation.OPPOSED, None),
    ]
    strata = stratify(observations, _POLICY)
    assert strata.closed_n == 2
    assert strata.open_n == 3
    assert strata.never_filled_n == 1
    assert strata.total_n == 6


def test_unresolved_stratum_is_reported_with_its_own_n_and_mean_r():
    observations = [
        _obs("c1", OutcomeState.CLOSED, Relation.ALIGNED, 1.0),
        _obs("c2", OutcomeState.CLOSED, Relation.UNRESOLVED, 1000.0),
        _obs("c3", OutcomeState.CLOSED, Relation.UNRESOLVED, -1000.0),
    ]
    strata = stratify(observations, _POLICY)
    assert strata.closed_unresolved.n == 2
    assert strata.closed_unresolved.mean_r == 0.0
    assert strata.closed_unresolved.relation == Relation.UNRESOLVED


def test_empty_stratum_has_zero_n_and_no_mean_r():
    observations = [_obs("c1", OutcomeState.CLOSED, Relation.ALIGNED, 1.0)]
    strata = stratify(observations, _POLICY)
    assert strata.closed_opposed.n == 0
    assert strata.closed_opposed.mean_r is None


def test_stratify_filters_by_policy_id():
    other_policy = "direction_policy_corroboration_v1"
    observations = [
        _obs("c1", OutcomeState.CLOSED, Relation.ALIGNED, 1.0),
        DirectionPolicyObservation(
            candidate_id=_candidate("c2"),
            context_cluster_id=_CLUSTER,
            policy_id=other_policy,
            relation=Relation.ALIGNED,
            outcome_state=OutcomeState.CLOSED,
            closed_outcome=ClosedTradeOutcome.WIN,
            realized_r=99.0,
        ),
    ]
    strata = stratify(observations, _POLICY)
    assert strata.total_n == 1
    assert strata.closed_aligned.n == 1
    assert strata.closed_aligned.mean_r == 1.0


# --- WR (V2, spec.md Section C2/E, REQ-STAT-04/06) --------------------------


def test_wr_aligned_two_wins_one_loss():
    # ALIGNED CLOSED: WIN, WIN, LOSS -> WR = 2/3, independently computed here.
    observations = [
        _obs("a1", OutcomeState.CLOSED, Relation.ALIGNED, 1.0, ClosedTradeOutcome.WIN),
        _obs("a2", OutcomeState.CLOSED, Relation.ALIGNED, 1.0, ClosedTradeOutcome.WIN),
        _obs("a3", OutcomeState.CLOSED, Relation.ALIGNED, -1.0, ClosedTradeOutcome.LOSS),
    ]
    strata = stratify(observations, _POLICY)
    assert strata.closed_aligned.wr_status == Computability.ESTIMABLE
    assert strata.closed_aligned.wr == 2 / 3


def test_wr_opposed_all_losses():
    # OPPOSED CLOSED: LOSS, LOSS -> WR = 0.0
    observations = [
        _obs("o1", OutcomeState.CLOSED, Relation.OPPOSED, -1.0, ClosedTradeOutcome.LOSS),
        _obs("o2", OutcomeState.CLOSED, Relation.OPPOSED, -0.5, ClosedTradeOutcome.LOSS),
    ]
    strata = stratify(observations, _POLICY)
    assert strata.closed_opposed.wr == 0.0


def test_wr_unresolved_half_wins():
    # UNRESOLVED CLOSED: WIN, LOSS -> WR = 0.5
    observations = [
        _obs("u1", OutcomeState.CLOSED, Relation.UNRESOLVED, 1.0, ClosedTradeOutcome.WIN),
        _obs("u2", OutcomeState.CLOSED, Relation.UNRESOLVED, -1.0, ClosedTradeOutcome.LOSS),
    ]
    strata = stratify(observations, _POLICY)
    assert strata.closed_unresolved.wr == 0.5


def test_wr_empty_closed_stratum_is_not_estimable():
    observations = [_obs("a1", OutcomeState.CLOSED, Relation.ALIGNED, 1.0)]
    strata = stratify(observations, _POLICY)
    assert strata.closed_opposed.wr_status == Computability.NOT_ESTIMABLE
    assert strata.closed_opposed.wr is None


def test_wr_unaffected_by_open_and_never_filled():
    observations = [
        _obs("a1", OutcomeState.CLOSED, Relation.ALIGNED, 1.0, ClosedTradeOutcome.WIN),
        _obs("a2", OutcomeState.CLOSED, Relation.ALIGNED, -1.0, ClosedTradeOutcome.LOSS),
    ]
    observations += [
        _obs(f"open-{i}", OutcomeState.OPEN, Relation.ALIGNED, None) for i in range(100)
    ]
    observations += [
        _obs(f"nf-{i}", OutcomeState.NEVER_FILLED, Relation.ALIGNED, None) for i in range(100)
    ]
    strata = stratify(observations, _POLICY)
    assert strata.closed_aligned.wr == 0.5
    assert strata.open_n == 100
    assert strata.never_filled_n == 100


def test_wr_reads_closed_outcome_not_realized_r_sign():
    """R-sign independence (Section 18): both observations carry a NEGATIVE
    realized_r, yet one is labelled WIN. A `sign(realized_r) > 0` implementation
    would read this as 0 wins out of 2 (WR=0.0); reading `closed_outcome`
    correctly gives 1 win out of 2 (WR=0.5) — the two approaches diverge,
    so this actually discriminates a buggy sign-based implementation."""
    observations = [
        _obs("w1", OutcomeState.CLOSED, Relation.ALIGNED, -1.0, ClosedTradeOutcome.WIN),
        _obs("l1", OutcomeState.CLOSED, Relation.ALIGNED, -1.0, ClosedTradeOutcome.LOSS),
    ]
    strata = stratify(observations, _POLICY)
    assert strata.closed_aligned.wr == 0.5
