"""Deterministic, pre-fill DirectionPolicy labels for frozen candidates."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from backtest.candidate import Candidate
from backtest.population import Stage6Population
from composite.order_flow import OrderFlowEvent
from core.candle import OHLCSeries
from policy.direction import (
    DirectionDecision,
    direction_policy_bias_veto_v1,
    direction_policy_corroboration_v1,
    direction_policy_noncontradiction_v1,
    direction_policy_structural_priority_v1,
)
from primitives.bias import BiasEvidence

_POLICIES: tuple[
    tuple[str, Callable[[Sequence[OrderFlowEvent], BiasEvidence, int], DirectionDecision]], ...
] = (
    ("direction_policy_structural_priority_v1", direction_policy_structural_priority_v1),
    ("direction_policy_corroboration_v1", direction_policy_corroboration_v1),
    ("direction_policy_noncontradiction_v1", direction_policy_noncontradiction_v1),
    ("direction_policy_bias_veto_v1", direction_policy_bias_veto_v1),
)
FROZEN_POLICY_IDS = tuple(policy_id for policy_id, _ in _POLICIES)


class EvaluationIntegrityError(Exception):
    """A supplied candidate or evidence batch violates the seam contract."""


class CandidateIndexError(EvaluationIntegrityError):
    pass


class CandidateProvenanceError(EvaluationIntegrityError):
    pass


class DuplicateCandidateError(EvaluationIntegrityError):
    pass


class EvidenceIntegrityError(EvaluationIntegrityError):
    pass


class PolicyRelation(StrEnum):
    ALIGNED = "ALIGNED"
    OPPOSED = "OPPOSED"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True)
class DirectionEvidence:
    series: OHLCSeries
    order_flow_events: tuple[OrderFlowEvent, ...]
    bias_evidence: tuple[BiasEvidence, ...]


@dataclass(frozen=True)
class DirectionEvaluation:
    instrument: str
    timeframe: str
    signal_id: str
    retest_index: int
    candidate_direction: str
    decision: DirectionDecision
    relation: PolicyRelation


def _policy_relation(candidate_direction: str, decision_direction: str) -> PolicyRelation:
    if decision_direction == "unresolved":
        return PolicyRelation.UNRESOLVED
    if decision_direction == candidate_direction:
        return PolicyRelation.ALIGNED
    return PolicyRelation.OPPOSED


def _validate_evidence(candidate_series: OHLCSeries, evidence: DirectionEvidence) -> dict[int, BiasEvidence]:
    if evidence.series is not candidate_series:
        raise CandidateProvenanceError("evidence must reference the exact candidate OHLCSeries object")
    if not candidate_series.instrument or candidate_series.timeframe != "15M":
        raise CandidateProvenanceError("candidate series must have an instrument and timeframe 15M")

    expected_bias_indices = range(1, len(candidate_series.candles))
    if [item.observation_index for item in evidence.bias_evidence] != list(expected_bias_indices):
        raise CandidateIndexError("BiasEvidence must be dense and ordered for every index from 1")
    if len({item.confirmation_index for item in evidence.order_flow_events}) != len(evidence.order_flow_events):
        raise EvidenceIntegrityError("OrderFlowEvent confirmation_index values must be unique")
    if any(
        event.confirmation_index < 0 or event.confirmation_index >= len(candidate_series.candles)
        for event in evidence.order_flow_events
    ):
        raise EvidenceIntegrityError("OrderFlowEvent confirmation_index is outside the candidate series")
    return {item.observation_index: item for item in evidence.bias_evidence}


def _validate_candidates(candidates: Sequence[Candidate], series: OHLCSeries) -> tuple[Candidate, ...]:
    identities = set()
    for candidate in candidates:
        if candidate.direction not in {"bullish", "bearish"}:
            raise EvaluationIntegrityError("candidate direction must be bullish or bearish")
        if candidate.retest_index < 3:
            raise CandidateIndexError("retest_index must be at least 3")
        if not 0 <= candidate.origin_index <= candidate.anchor_index < candidate.retest_index < len(series.candles):
            raise CandidateIndexError("candidate indices must be ordered and within the candidate series")
        identity = (series.instrument, series.timeframe, candidate.signal_id, candidate.retest_index)
        if identity in identities:
            raise DuplicateCandidateError("candidate identity is duplicated")
        identities.add(identity)
    return tuple(sorted(candidates, key=lambda candidate: (candidate.retest_index, candidate.signal_id)))


def evaluate_direction_policies(
    population: Stage6Population, evidence: DirectionEvidence
) -> tuple[DirectionEvaluation, ...]:
    """Label every candidate in one canonical pre-fill population."""
    if not isinstance(population, Stage6Population):
        raise CandidateProvenanceError("evaluation requires a Stage6Population")

    candidate_series = population.series
    bias_by_index = _validate_evidence(candidate_series, evidence)
    ordered_candidates = _validate_candidates(population.candidates, candidate_series)
    rows = []
    for candidate in ordered_candidates:
        cutoff = candidate.retest_index - 1
        try:
            bias = bias_by_index[cutoff]
        except KeyError as error:
            raise CandidateIndexError("BiasEvidence is required exactly at K-1") from error
        if bias.observation_index != cutoff:
            raise CandidateIndexError("BiasEvidence is required exactly at K-1")
        for _, policy in _POLICIES:
            decision = policy(evidence.order_flow_events, bias, cutoff)
            rows.append(
                DirectionEvaluation(
                    instrument=candidate_series.instrument,
                    timeframe=candidate_series.timeframe,
                    signal_id=candidate.signal_id,
                    retest_index=candidate.retest_index,
                    candidate_direction=candidate.direction,
                    decision=decision,
                    relation=_policy_relation(candidate.direction, decision.direction),
                )
            )
    return tuple(rows)
