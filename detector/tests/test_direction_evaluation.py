from dataclasses import replace
from datetime import datetime, timedelta
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import given
from hypothesis import strategies as st

import evaluation.direction as direction_evaluation
from backtest.candidate import Candidate
from backtest.population import Stage6Population
from composite.order_flow import OrderFlowEvent
from core.candle import Candle, OHLCSeries
from evaluation.direction import (
    CandidateProvenanceError,
    CandidateIndexError,
    DirectionEvidence,
    DuplicateCandidateError,
    EvaluationIntegrityError,
    FROZEN_POLICY_IDS,
    PolicyRelation,
    _policy_relation,
    evaluate_direction_policies,
)
from policy.direction import DirectionDecision
from primitives.bias import BiasEvidence
from primitives.swing import SwingPoint


POLICY_IDS = (
    "direction_policy_structural_priority_v1",
    "direction_policy_corroboration_v1",
    "direction_policy_noncontradiction_v1",
    "direction_policy_bias_veto_v1",
)
_SWING_LOW = SwingPoint(index=0, price=1.0, kind="low")
_SWING_HIGH = SwingPoint(index=1, price=2.0, kind="high")


def _series(size: int = 12) -> OHLCSeries:
    candles = tuple(
        Candle(
            timestamp=datetime(2026, 1, 1) + timedelta(minutes=15 * index),
            open=1.0 + index / 100,
            high=1.1 + index / 100,
            low=0.9 + index / 100,
            close=1.05 + index / 100,
        )
        for index in range(size)
    )
    return OHLCSeries(candles=candles, instrument="EURUSDm", timeframe="15M")


def _candidate(signal_id: str = "signal-1", retest_index: int = 3, direction: str = "bullish") -> Candidate:
    return Candidate(
        signal_id=signal_id,
        anchor_index=1,
        origin_index=0,
        direction=direction,
        entry_type="wick",
        retest_index=retest_index,
        entry_price=1.0,
        stop_loss=0.9,
        take_profit=1.2,
        partial_price=1.1,
    )


def _population(series: OHLCSeries, candidates: list[Candidate]) -> Stage6Population:
    return Stage6Population(
        series=series,
        candidates=candidates,
        excluded_no_crt_range=0,
        excluded_unaligned=0,
        excluded_never_confirmed=0,
        excluded_no_key_level=0,
        excluded_duplicate=0,
        excluded_kill_zone=0,
        excluded_rr_floor=0,
    )


def _evaluate(
    series: OHLCSeries, candidates: list[Candidate], evidence: DirectionEvidence
) -> tuple:
    return evaluate_direction_policies(_population(series, candidates), evidence)


def _bias(index: int, direction: str = "bullish") -> BiasEvidence:
    return BiasEvidence(
        observation_index=index,
        close_relation="above" if direction == "bullish" else "below",
        close_signal=direction,
        wick_signal=direction,
    )


def _event(index: int, direction: str = "bullish") -> OrderFlowEvent:
    return OrderFlowEvent(
        direction=direction,
        rejection_reference=_SWING_LOW,
        break_reference=_SWING_HIGH,
        rejection_index=index - 1,
        confirmation_index=index,
    )


def _evidence(series: OHLCSeries, *, events=(), bias_overrides=None) -> DirectionEvidence:
    bias_overrides = bias_overrides or {}
    return DirectionEvidence(
        series=series,
        order_flow_events=tuple(events),
        bias_evidence=tuple(
            bias_overrides.get(index, _bias(index)) for index in range(1, len(series.candles))
        ),
    )


@pytest.mark.parametrize(
    ("candidate_direction", "decision_direction", "expected"),
    [
        ("bullish", "bullish", PolicyRelation.ALIGNED),
        ("bearish", "bearish", PolicyRelation.ALIGNED),
        ("bullish", "bearish", PolicyRelation.OPPOSED),
        ("bearish", "bullish", PolicyRelation.OPPOSED),
        ("bullish", "unresolved", PolicyRelation.UNRESOLVED),
        ("bearish", "unresolved", PolicyRelation.UNRESOLVED),
    ],
)
def test_relation_is_total_over_the_six_direction_pairs(candidate_direction, decision_direction, expected):
    assert _policy_relation(candidate_direction, decision_direction) is expected


@pytest.mark.parametrize(("retest_index", "expected_cutoff"), [(3, 2), (10, 9)])
def test_evaluation_uses_exactly_one_candle_before_retest(retest_index, expected_cutoff):
    series = _series(12)

    rows = _evaluate(series, [_candidate(retest_index=retest_index)], _evidence(series))

    assert [row.decision.cutoff_index for row in rows] == [expected_cutoff] * 4


def test_retest_before_three_fails_without_negative_indexing():
    series = _series()

    with pytest.raises(CandidateIndexError, match="retest_index"):
        _evaluate(series, [_candidate(retest_index=2)], _evidence(series))


def test_bias_must_be_exactly_at_k_minus_one():
    series = _series()
    evidence = _evidence(series, bias_overrides={2: _bias(1), 3: _bias(3)})

    with pytest.raises(CandidateIndexError, match="BiasEvidence"):
        _evaluate(series, [_candidate(retest_index=3)], evidence)


def test_prevents_intrabar_lookahead():
    """Bias@K and OrderFlow@K cannot affect the decision made at K−1."""
    series = _series()
    candidate = _candidate(retest_index=3)
    before_k = _evidence(series, events=[_event(2, "bullish")], bias_overrides={2: _bias(2, "bullish")})
    at_k = _evidence(series, events=[_event(2, "bullish"), _event(3, "bearish")], bias_overrides={2: _bias(2, "bullish"), 3: _bias(3, "bearish")})

    assert _evaluate(series, [candidate], at_k) == _evaluate(
        series, [candidate], before_k
    )


def test_order_flow_after_k_minus_one_is_excluded():
    series = _series()
    candidate = _candidate(retest_index=3)
    eligible = _evidence(series, events=[_event(2, "bullish")])
    future_only = _evidence(series, events=[_event(3, "bearish")])

    assert all(row.decision.order_flow_confirmation_index == 2 for row in _evaluate(series, [candidate], eligible))
    assert all(row.decision.order_flow_confirmation_index is None for row in _evaluate(series, [candidate], future_only))


def test_batch_returns_exactly_four_rows_per_candidate_in_fixed_policy_order():
    series = _series()
    candidates = [_candidate("late", 10), _candidate("early", 3)]

    rows = _evaluate(series, candidates, _evidence(series))

    assert len(rows) == 4 * len(candidates)
    assert [(row.signal_id, row.decision.policy_id) for row in rows] == [
        ("early", policy_id) for policy_id in POLICY_IDS
    ] + [("late", policy_id) for policy_id in POLICY_IDS]


def test_every_policy_receives_the_identical_candidate_identity_universe():
    series = _series()
    rows = _evaluate(series, [_candidate("a", 3), _candidate("b", 10)], _evidence(series))

    identities_by_policy = {
        policy_id: {(row.instrument, row.timeframe, row.signal_id, row.retest_index) for row in rows if row.decision.policy_id == policy_id}
        for policy_id in POLICY_IDS
    }
    assert all(identities == identities_by_policy[POLICY_IDS[0]] for identities in identities_by_policy.values())


def test_combined_evaluation_equals_isolated_policy_evaluation_in_frozen_order():
    series = _series()
    candidate = _candidate()
    evidence = _evidence(series, events=[_event(2)])

    combined = _evaluate(series, [candidate], evidence)
    isolated = tuple(
        row
        for policy_id in FROZEN_POLICY_IDS
        for row in _evaluate(series, [candidate], evidence)
        if row.decision.policy_id == policy_id
    )

    assert combined == isolated


def test_evaluation_is_deterministic_and_does_not_mutate_candidates():
    series = _series()
    candidate = _candidate()
    before = candidate

    first = _evaluate(series, [candidate], _evidence(series))
    second = _evaluate(series, [candidate], _evidence(series))

    assert first == second
    assert candidate == before
    with pytest.raises(FrozenInstanceError):
        first[0].signal_id = "changed"


def test_unresolved_rows_are_preserved():
    series = _series()
    rows = _evaluate(series, [_candidate()], _evidence(series, bias_overrides={2: _bias(2, "bearish")}))

    assert any(row.relation is PolicyRelation.UNRESOLVED for row in rows)


def test_opposed_rows_are_preserved_without_inverting_candidate_direction():
    series = _series()
    rows = _evaluate(
        series, [_candidate(direction="bullish")], _evidence(series, events=[_event(2, "bearish")])
    )

    opposed = next(row for row in rows if row.relation is PolicyRelation.OPPOSED)
    assert opposed.candidate_direction == "bullish"
    assert opposed.decision.direction == "bearish"


def test_duplicate_candidate_identity_fails_instead_of_deduplicating():
    series = _series()

    with pytest.raises(DuplicateCandidateError):
        _evaluate(series, [_candidate(), _candidate()], _evidence(series))


def test_evidence_must_use_the_same_m15_series_object():
    series = _series()
    same_value_but_distinct_series = OHLCSeries(
        candles=series.candles, instrument=series.instrument, timeframe=series.timeframe
    )

    with pytest.raises(CandidateProvenanceError, match="exact"):
        evaluate_direction_policies(_population(series, [_candidate()]), _evidence(same_value_but_distinct_series))


def test_evaluation_rejects_non_m15_series():
    series = _series()
    invalid = OHLCSeries(candles=series.candles, instrument=series.instrument, timeframe="1H")

    with pytest.raises(CandidateProvenanceError, match="15M"):
        _evaluate(invalid, [_candidate()], _evidence(invalid))


def test_evaluation_rejects_an_empty_instrument():
    series = replace(_series(), instrument="")

    with pytest.raises(CandidateProvenanceError, match="instrument"):
        _evaluate(series, [_candidate()], _evidence(series))


def test_evaluation_rejects_a_malformed_candidate_direction():
    series = _series()

    with pytest.raises(EvaluationIntegrityError, match="direction"):
        _evaluate(series, [_candidate(direction="sideways")], _evidence(series))


@pytest.mark.parametrize(
    "candidate",
    [
        _candidate(retest_index=12),
        replace(_candidate(), origin_index=2, anchor_index=1),
        replace(_candidate(), anchor_index=3),
    ],
)
def test_evaluation_rejects_out_of_bounds_or_unordered_candidate_indices(candidate):
    series = _series()

    with pytest.raises(CandidateIndexError, match="candidate indices"):
        _evaluate(series, [candidate], _evidence(series))


@pytest.mark.parametrize(
    "events",
    [
        (_event(2), _event(2, "bearish")),
        (_event(12),),
    ],
)
def test_evaluation_rejects_invalid_order_flow_events(events):
    series = _series()

    with pytest.raises(EvaluationIntegrityError, match="OrderFlowEvent"):
        _evaluate(series, [_candidate()], _evidence(series, events=events))


@given(
    candidate_direction=st.sampled_from(["bullish", "bearish"]),
    policy_direction=st.sampled_from(["bullish", "bearish", "unresolved"]),
    instrument=st.sampled_from(["EURUSDm", "GBPUSDm"]),
    policy_id=st.sampled_from(["property-policy-a", "property-policy-b"]),
    reason=st.sampled_from(["NO_EVIDENCE", "SINGLE_SOURCE", "AGREEMENT"]),
    signal_id=st.sampled_from(["property-signal-a", "property-signal-b"]),
)
def test_relation_depends_only_on_candidate_and_decision_directions(
    candidate_direction, policy_direction, instrument, policy_id, reason, signal_id
):
    def policy(policy_id, reason):
        def decide(_events, _bias, cutoff):
            return DirectionDecision(
                policy_id=policy_id,
                cutoff_index=cutoff,
                direction=policy_direction,
                order_flow_confirmation_index=None,
                order_flow_direction=None,
                normalized_bias_direction="unresolved",
                reason=reason,
            )

        return decide

    series = replace(_series(), instrument=instrument)
    candidate = _candidate(signal_id=signal_id, direction=candidate_direction)
    alternate_series = replace(series, instrument=f"{instrument}-alternate")
    alternate_candidate = replace(candidate, signal_id=f"{signal_id}-alternate")
    expected = (
        PolicyRelation.UNRESOLVED
        if policy_direction == "unresolved"
        else PolicyRelation.ALIGNED
        if policy_direction == candidate_direction
        else PolicyRelation.OPPOSED
    )

    with patch.object(direction_evaluation, "_POLICIES", (("property-policy", policy(policy_id, reason)),)):
        rows = evaluate_direction_policies(_population(series, [candidate]), _evidence(series))
    with patch.object(
        direction_evaluation,
        "_POLICIES",
        (("alternate-policy", policy(f"{policy_id}-alternate", "CONFLICT_UNRESOLVED")),),
    ):
        alternate_rows = evaluate_direction_policies(
            _population(alternate_series, [alternate_candidate]), _evidence(alternate_series)
        )

    assert [row.relation for row in rows] == [expected]
    assert [row.relation for row in alternate_rows] == [expected]


@given(st.lists(st.integers(min_value=3, max_value=10), min_size=1, max_size=4, unique=True))
def test_any_valid_candidate_list_produces_four_rows_and_each_frozen_policy(retest_indices):
    series = _series()
    candidates = [_candidate(f"signal-{index}", retest_index) for index, retest_index in enumerate(retest_indices)]

    rows = _evaluate(series, candidates, _evidence(series))

    assert len(rows) == 4 * len(candidates)
    assert {row.decision.policy_id for row in rows} == set(POLICY_IDS)


def test_future_evidence_and_candles_do_not_change_existing_evaluation():
    series = _series()
    candidate = _candidate(retest_index=3)
    evidence = _evidence(series, events=[_event(2, "bullish")])
    extended = OHLCSeries(
        candles=series.candles + _series(2).candles,
        instrument=series.instrument,
        timeframe=series.timeframe,
    )
    extended_evidence = _evidence(extended, events=[_event(2, "bullish"), _event(11, "bearish")])

    assert _evaluate(series, [candidate], evidence) == _evaluate(
        extended, [candidate], extended_evidence
    )


def test_outcome_firewall_has_no_outcome_fields_or_forbidden_imports():
    source = (Path(__file__).parents[1] / "evaluation" / "direction.py").read_text(encoding="utf-8")
    series = _series()
    row_fields = set(_evaluate(series, [_candidate()], _evidence(series))[0].__dataclass_fields__)

    assert not {"outcome", "r_multiple", "fill_index", "entry_index", "exit_index"} & row_fields
    assert not any(name in source for name in ("backtest.simulate", "backtest.metrics", "backtest.levels", "research"))


def test_import_linter_configuration_enforces_the_evaluation_firewall():
    config = (Path(__file__).parents[1] / ".importlinter").read_text(encoding="utf-8")

    assert "    evaluation" in config
    assert "evaluation -\u003e outcome-bearing modules" in config
    assert "    evaluation" in config.split("forbidden_modules =", 1)[1]
    assert "allow_indirect_imports = true" in config


def test_evaluation_rejects_loose_candidates_at_the_public_boundary():
    series = _series()

    with pytest.raises(CandidateProvenanceError, match="Stage6Population"):
        evaluate_direction_policies([_candidate()], _evidence(series))


def test_evaluation_rejects_evidence_for_an_equal_but_distinct_series_object():
    series = _series()
    distinct_series = OHLCSeries(
        candles=series.candles, instrument=series.instrument, timeframe=series.timeframe
    )

    with pytest.raises(CandidateProvenanceError, match="exact"):
        evaluate_direction_policies(_population(series, [_candidate()]), _evidence(distinct_series))


def test_evaluation_uses_only_candidates_from_the_supplied_population():
    series = _series()
    candidate = _candidate("from-population")

    rows = evaluate_direction_policies(_population(series, [candidate]), _evidence(series))

    assert [(row.signal_id, row.retest_index) for row in rows] == [(candidate.signal_id, 3)] * 4
