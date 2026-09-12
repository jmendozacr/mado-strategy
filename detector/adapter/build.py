"""The Layer-2 transactional facade (spec.md Section O, REQ-STAT-19..30):
validates everything, constructs the full `DirectionPolicyObservation`
universe, validates the finished universe, and returns it as one immutable
tuple — no partial/lazy output ever escapes a failed run."""

from evaluation.direction import FROZEN_POLICY_IDS

from adapter.bundle import InstrumentRunBundle
from adapter.cluster import lookup_context_cluster, reconstruct_context_clusters
from adapter.cutoff import validate_candidate_cutoff, validate_outcome_followup_cutoff
from adapter.identity import recover_candidate_identity, reconcile_population_evaluations
from adapter.relation import map_relation
from adapter.trade_join import (
    map_trade_outcome,
    prove_functional_join,
    trade_join_key,
    verify_aggregate_completeness,
)
from selection.model import DirectionPolicyObservation, validate_candidate_consistency


def build_direction_policy_observations(
    bundle: InstrumentRunBundle,
) -> tuple[DirectionPolicyObservation, ...]:
    """Fail-before-statistics (Section O): every validation below MUST
    succeed before a single `DirectionPolicyObservation` is constructed;
    any failure raises and returns nothing — never a partial universe."""
    series = bundle.population.series

    # 1) Aggregate completeness BEFORE any Candidate absence is read as
    #    NEVER_FILLED (REQ-STAT-25).
    verify_aggregate_completeness(bundle.population, bundle.trades, bundle.reconciliation)

    # 2) Recover each Candidate's full identity and validate the frozen
    #    population-admission boundary (REQ-STAT-01/29).
    identities = []
    for candidate in bundle.population.candidates:
        validate_candidate_cutoff(candidate.retest_index, series, bundle.candidate_cutoff_end_utc)
        identities.append(recover_candidate_identity(series, candidate))

    # 3) Independent Candidate<->DirectionEvaluation reconciliation, whole
    #    run, orphan-checked (REQ-STAT-26).
    reconciled = reconcile_population_evaluations(identities, bundle.evaluations)

    # 4) TradeJoinKey functional-dependency proof, whole run (REQ-STAT-24).
    _, key_to_trade = prove_functional_join(identities, bundle.trades, bundle.instrument)

    # 5) Cluster reconstruction, full series only (REQ-STAT-28).
    cluster_map = reconstruct_context_clusters(bundle.instrument, bundle.htf_series, series, bundle.config)

    # Deterministic Candidate order (Section spec: (retest_index, signal_id)),
    # policy P1-P4 within each (FROZEN_POLICY_IDS' own declared order).
    ordered_identities = sorted(identities, key=lambda identity: (identity.retest_index, identity.signal_id))

    observations: list[DirectionPolicyObservation] = []
    for identity in ordered_identities:
        trade = key_to_trade.get(trade_join_key(identity))
        outcome_state, closed_outcome, realized_r = map_trade_outcome(trade)

        exit_index = trade.exit_index if trade is not None else None
        validate_outcome_followup_cutoff(exit_index, series, bundle.outcome_followup_end_utc)

        context_cluster_id = lookup_context_cluster(cluster_map, identity.signal_id)
        by_policy = reconciled[identity]

        for policy_id in FROZEN_POLICY_IDS:
            row = by_policy[policy_id]
            observations.append(
                DirectionPolicyObservation(
                    candidate_id=identity,
                    context_cluster_id=context_cluster_id,
                    policy_id=policy_id,
                    relation=map_relation(row.relation),
                    outcome_state=outcome_state,
                    closed_outcome=closed_outcome,
                    realized_r=realized_r,
                )
            )

    # Final defense-in-depth: cardinality (4N) and Layer-1's own
    # cross-policy economic-outcome consistency check (REQ-STAT-03).
    expected_count = 4 * len(ordered_identities)
    if len(observations) != expected_count:
        raise AssertionError(
            f"output cardinality violated: {len(observations)} observations for "
            f"{len(ordered_identities)} candidates, expected {expected_count}"
        )
    validate_candidate_consistency(observations)

    return tuple(observations)
