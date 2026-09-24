"""Candidate-universe fingerprint and observation-table fingerprint.

Candidate fingerprint: sort by (retest_index, signal_id), canonical JSON,
SHA-256 hash. Outcome-free by construction (Candidate has no outcome field).

Observation-table fingerprint: computed AFTER nominate() returns, records
the full joined observation set for reproducibility. Never passed to any
selection.* function."""

import hashlib
import json
from collections.abc import Sequence

from backtest.candidate import Candidate
from selection.model import DirectionPolicyObservation


def compute_candidate_fingerprint(candidates: Sequence[Candidate]) -> str:
    """Deterministic SHA-256 over the sorted candidate universe in canonical JSON."""
    sorted_candidates = sorted(candidates, key=lambda c: (c.retest_index, c.signal_id))
    records = []
    for c in sorted_candidates:
        records.append({
            "signal_id": c.signal_id,
            "anchor_index": c.anchor_index,
            "origin_index": c.origin_index,
            "direction": c.direction,
            "entry_type": c.entry_type,
            "retest_index": c.retest_index,
            "entry_price": repr(c.entry_price),
            "stop_loss": repr(c.stop_loss),
            "take_profit": repr(c.take_profit),
            "partial_price": repr(c.partial_price),
        })
    payload = json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def compute_observation_table_fingerprint(
    observations: Sequence[DirectionPolicyObservation],
) -> str:
    """Deterministic SHA-256 over the full observation table AFTER nominate().
    Sorted by (retest_index, signal_id, policy_id) for determinism.
    Never passed to any selection.* function."""
    sorted_obs = sorted(
        observations,
        key=lambda o: (o.candidate_id.retest_index, o.candidate_id.signal_id, o.policy_id),
    )
    records = []
    for o in sorted_obs:
        records.append({
            "instrument": o.candidate_id.instrument,
            "timeframe": o.candidate_id.timeframe,
            "signal_id": o.candidate_id.signal_id,
            "retest_index": o.candidate_id.retest_index,
            "context_cluster_id": list(o.context_cluster_id),
            "policy_id": o.policy_id,
            "relation": o.relation.value,
            "outcome_state": o.outcome_state.value,
            "closed_outcome": o.closed_outcome.value if o.closed_outcome is not None else None,
            "realized_r": repr(o.realized_r) if o.realized_r is not None else None,
        })
    payload = json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
