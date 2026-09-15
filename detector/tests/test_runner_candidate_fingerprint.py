"""Candidate and observation fingerprints.

Candidate: canonical JSON form, sorted by (retest_index, signal_id), SHA-256.
Observation table: computed after nominate(), never passed to selection.*."""

import json

from backtest.candidate import Candidate
from evaluation.direction import FROZEN_POLICY_IDS
from selection.model import (
    CandidateIdentity,
    ClosedTradeOutcome,
    DirectionPolicyObservation,
    OutcomeState,
    Relation,
)


def _make_candidate(signal_id: str, retest_index: int, entry_price: float = 1.0) -> Candidate:
    return Candidate(
        signal_id=signal_id,
        anchor_index=0,
        origin_index=0,
        direction="bullish",
        entry_type="wick",
        retest_index=retest_index,
        entry_price=entry_price,
        stop_loss=0.9,
        take_profit=1.2,
        partial_price=1.1,
    )


def test_same_candidates_different_order_same_fingerprint():
    from runner.candidate_fingerprint import compute_candidate_fingerprint

    c1 = _make_candidate("sig_a", 10)
    c2 = _make_candidate("sig_b", 5)
    fp1 = compute_candidate_fingerprint([c1, c2])
    fp2 = compute_candidate_fingerprint([c2, c1])
    assert fp1 == fp2


def test_different_candidates_different_fingerprint():
    from runner.candidate_fingerprint import compute_candidate_fingerprint

    c1 = _make_candidate("sig_a", 10)
    c2 = _make_candidate("sig_a", 11)
    fp1 = compute_candidate_fingerprint([c1])
    fp2 = compute_candidate_fingerprint([c2])
    assert fp1 != fp2


def test_fingerprint_is_sha256_hex():
    from runner.candidate_fingerprint import compute_candidate_fingerprint

    c = _make_candidate("sig_a", 10)
    fp = compute_candidate_fingerprint([c])
    assert len(fp) == 64
    int(fp, 16)


def test_empty_candidates_produces_fingerprint():
    from runner.candidate_fingerprint import compute_candidate_fingerprint

    fp = compute_candidate_fingerprint([])
    assert len(fp) == 64


def test_candidate_type_has_no_outcome_field():
    fields = {f.name for f in Candidate.__dataclass_fields__.values()}
    forbidden = {"outcome", "r_multiple", "realized_r", "closed_outcome"}
    assert fields.isdisjoint(forbidden)


def test_fingerprint_uses_canonical_json():
    """The candidate fingerprint uses canonical JSON, not pipe-delimited."""
    from runner.candidate_fingerprint import compute_candidate_fingerprint
    import hashlib

    c = _make_candidate("sig_a", 10, entry_price=1.5)
    fp = compute_candidate_fingerprint([c])

    # Reconstruct the expected canonical JSON form
    records = [{
        "signal_id": "sig_a",
        "anchor_index": 0,
        "origin_index": 0,
        "direction": "bullish",
        "entry_type": "wick",
        "retest_index": 10,
        "entry_price": repr(1.5),
        "stop_loss": repr(0.9),
        "take_profit": repr(1.2),
        "partial_price": repr(1.1),
    }]
    expected_payload = json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    expected_fp = hashlib.sha256(expected_payload).hexdigest()
    assert fp == expected_fp


def test_observation_table_fingerprint_exists():
    from runner.candidate_fingerprint import compute_observation_table_fingerprint

    cid = CandidateIdentity("EURUSDm", "15M", "sig_1", 10)
    obs = [
        DirectionPolicyObservation(
            candidate_id=cid,
            context_cluster_id=("EURUSDm", 0, 5, 4),
            policy_id=FROZEN_POLICY_IDS[0],
            relation=Relation.ALIGNED,
            outcome_state=OutcomeState.CLOSED,
            closed_outcome=ClosedTradeOutcome.WIN,
            realized_r=0.5,
        )
    ]
    fp = compute_observation_table_fingerprint(obs)
    assert len(fp) == 64
    int(fp, 16)


def test_observation_table_fingerprint_deterministic():
    from runner.candidate_fingerprint import compute_observation_table_fingerprint

    cid1 = CandidateIdentity("EURUSDm", "15M", "sig_1", 10)
    cid2 = CandidateIdentity("EURUSDm", "15M", "sig_2", 11)
    obs = []
    for cid in [cid1, cid2]:
        for pid in FROZEN_POLICY_IDS:
            obs.append(DirectionPolicyObservation(
                candidate_id=cid,
                context_cluster_id=("EURUSDm", 0, 5, 4),
                policy_id=pid,
                relation=Relation.ALIGNED,
                outcome_state=OutcomeState.CLOSED,
                closed_outcome=ClosedTradeOutcome.WIN,
                realized_r=0.5,
            ))

    fp1 = compute_observation_table_fingerprint(obs)
    fp2 = compute_observation_table_fingerprint(list(reversed(obs)))
    assert fp1 == fp2


def test_observation_table_fingerprint_not_passed_to_selection():
    """Structural: compute_observation_table_fingerprint is never imported
    in any selection/ module."""
    import importlib
    import inspect
    import pkgutil
    import selection

    for _, modname, _ in pkgutil.walk_packages(selection.__path__, selection.__name__ + "."):
        mod = importlib.import_module(modname)
        source = inspect.getsource(mod)
        assert "observation_table_fingerprint" not in source
