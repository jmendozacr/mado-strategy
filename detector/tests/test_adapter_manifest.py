"""REQ-STAT-19/32/31: manifest schema validation, protocol-artifact hash
checking, and execution-baseline ownership — real execution stays
impossible until Layer-3 exists and closes out. Synthetic temp files only."""

import dataclasses
from datetime import datetime

import pytest

from adapter.dataset import sha256_of_file
from adapter.errors import FrozenArtifactMismatchError
from adapter.manifest import (
    GapAllowlistEntry,
    Manifest,
    is_execution_authorized,
    validate_protocol_hash,
    verify_protected_paths_clean,
)
from evaluation.direction import FROZEN_POLICY_IDS


def _manifest(**overrides) -> Manifest:
    defaults = dict(
        experiment_id="direction-policy-discovery-v1",
        protocol_artifact_path="detector/research/direction_policy_discovery_v1_amendment_1.json",
        protocol_artifact_sha256="47b17d7891f6f9a2d2d30f83df88b060840a895484a78e763c8f46da1ea8de4d",
        direction_policy_implementation_commit="7b09c31877a5e5978e10b6832f5b7f3010276f1d",
        evaluation_seam_spec_commit="6104343488cc0dd6df7b4d311dc2cdf6893f2ccb",
        evaluation_seam_implementation_commit="26d94be6eed49d1883f1454d2ceea0bc0e80b4ac",
        evaluation_seam_closeout_commit="7775a25c011254555c74021e83a4dad044700d83",
        statistical_spec_v3_commit="86c91506132292d5c9076462118cb5d32efe5807",
        layer1_implementation_commit="75d9c37ac08a314a6518484b7e62ee3c7eb798c1",
        policy_ids=tuple(FROZEN_POLICY_IDS),
        dataset_identity="EURUSDm-GBPUSDm-DXYm-15M-discovery-window",
        dataset_file_hashes=(("EURUSDm.csv", "aaa"), ("GBPUSDm.csv", "bbb")),
        population_definition_ref="backtest.population.build_stage6_population",
        candidate_identity_fields=("instrument", "timeframe", "signal_id", "retest_index"),
        trade_join_key_fields=("instrument", "signal_id"),
        outcome_fields=("realized_r", "closed_outcome"),
        est_b_definition="mean(realized_r|ALIGNED,CLOSED) - mean(realized_r|OPPOSED,CLOSED)",
        mei_r=0.20,
        cluster_definition_ref="alignment.htf_ltf.tag_alignment",
        bootstrap_config=(("replicates", 10000), ("seed", 20260910)),
        nomination_rule_ref="selection.rule",
        cost_assumptions=(("trading_cost_price", 0.0),),
        protected_paths=("detector/policy/", "detector/evaluation/", "detector/selection/"),
        protected_paths_version="v1",
    )
    defaults.update(overrides)
    return Manifest(**defaults)


def test_valid_manifest_constructs():
    manifest = _manifest()
    assert manifest.mei_r == 0.20


def test_policy_ids_must_be_exactly_the_four_frozen_ids():
    with pytest.raises(FrozenArtifactMismatchError):
        _manifest(policy_ids=("direction_policy_structural_priority_v1",))


def test_candidate_identity_and_trade_join_key_must_be_named_distinctly():
    with pytest.raises(FrozenArtifactMismatchError):
        _manifest(trade_join_key_fields=("instrument", "timeframe", "signal_id", "retest_index"))


def test_mei_r_must_be_the_frozen_020():
    with pytest.raises(FrozenArtifactMismatchError):
        _manifest(mei_r=0.30)


def test_baseline_commit_requires_layer2_and_layer3_commits_first():
    with pytest.raises(FrozenArtifactMismatchError):
        _manifest(measurement_execution_baseline_commit="deadbeef" * 5)


def test_baseline_commit_valid_once_layer2_and_layer3_recorded():
    manifest = _manifest(
        layer2_implementation_commit="a" * 40, layer3_implementation_commit="b" * 40,
        measurement_execution_baseline_commit="c" * 40,
    )
    assert manifest.measurement_execution_baseline_commit == "c" * 40


# --- protocol hash ------------------------------------------------------


def test_protocol_hash_matches(tmp_path):
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text('{"key": "value"}')
    manifest = _manifest(protocol_artifact_sha256=sha256_of_file(protocol_path))
    validate_protocol_hash(manifest, str(protocol_path))  # must not raise


def test_protocol_hash_drift_fails_closed(tmp_path):
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text('{"key": "value"}')
    manifest = _manifest(protocol_artifact_sha256="0" * 64)
    with pytest.raises(FrozenArtifactMismatchError):
        validate_protocol_hash(manifest, str(protocol_path))


# --- execution-baseline ownership (REQ-STAT-31) -----------------------------


def test_execution_not_authorized_without_baseline_commit():
    manifest = _manifest()
    assert is_execution_authorized(manifest) is False


def test_execution_authorized_once_baseline_recorded():
    manifest = _manifest(
        layer2_implementation_commit="a" * 40, layer3_implementation_commit="b" * 40,
        measurement_execution_baseline_commit="c" * 40,
    )
    assert is_execution_authorized(manifest) is True


def test_this_repos_current_state_can_never_honestly_authorize_execution():
    """Layer-3 does not exist yet in this codebase — any manifest this
    session could honestly build has no layer3_implementation_commit, so
    execution stays impossible, per REQ-STAT-31 and this task's own
    constraint (do not fabricate a baseline hash)."""
    manifest = _manifest()  # no layer2/layer3/baseline commits — the honest state today
    assert is_execution_authorized(manifest) is False


# --- protected paths (Section N) --------------------------------------------


def test_clean_protected_paths_passes():
    verify_protected_paths_clean(
        protected_paths=("detector/selection/",), changed_paths=("detector/viz/overlay.py",),
        baseline_commit="c" * 40,
    )  # must not raise


def test_modified_protected_path_fails_closed():
    with pytest.raises(FrozenArtifactMismatchError):
        verify_protected_paths_clean(
            protected_paths=("detector/selection/",), changed_paths=("detector/selection/model.py",),
            baseline_commit="c" * 40,
        )


def test_unrelated_working_tree_changes_outside_protected_paths_need_not_abort():
    verify_protected_paths_clean(
        protected_paths=("detector/selection/", "detector/policy/"),
        changed_paths=("docs/charter-9.md", "detector/viz/overlay.py"),
        baseline_commit="c" * 40,
    )  # must not raise


# --- dataset_gap_allowlist (REQ-STAT-32/34, V4) ------------------------------


def test_manifest_defaults_to_empty_gap_allowlist():
    manifest = _manifest()
    assert manifest.dataset_gap_allowlist == ()


def test_manifest_can_carry_a_frozen_gap_allowlist():
    entry = GapAllowlistEntry(
        instrument="EURUSDm", granularity="15M",
        gap_start=datetime(2026, 1, 2, 23, 45), gap_end=datetime(2026, 1, 5, 0, 0),
        reason="weekend closure",
    )
    manifest = _manifest(dataset_gap_allowlist=(entry,))
    assert manifest.dataset_gap_allowlist == (entry,)


def test_gap_allowlist_entry_is_frozen():
    entry = GapAllowlistEntry(
        instrument="EURUSDm", granularity="15M",
        gap_start=datetime(2026, 1, 2, 23, 45), gap_end=datetime(2026, 1, 5, 0, 0),
        reason="weekend closure",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.reason = "mutated after the fact"
