"""Fail-closed authorization preflight for the discovery runner."""

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from adapter.dataset import sha256_of_file, validate_no_gaps_against_manifest
from adapter.manifest import Manifest, _ARGUMENT_TO_PRODUCER, validate_protocol_hash
from core.config import DetectorConfig
from ingestion.loader import load_mt5_csv
from runner.config_fingerprint import reconstruct_and_fingerprint
from runner.environment import environment_record, verify_environment
from runner.errors import AuthorizationError, PreflightFailure
from runner.git_ops import (
    get_head_commit,
    verify_commit_exists,
    verify_is_ancestor,
    verify_no_diff,
    verify_no_staged_diff,
    verify_no_untracked,
    verify_no_working_tree_diff,
)
from runner.manifest_builder import (
    CANONICAL_PROTOCOL_RELATIVE_PATH,
    CANONICAL_PROTOCOL_SHA256,
    CANONICAL_STATISTICAL_SPEC_SHA256,
    CAUSAL_IMPLEMENTATION_COMMIT,
    CAUSAL_SPEC_AMENDMENT_COMMIT,
    CAUSAL_SPEC_COMMIT,
    DIRECTION_POLICY_IMPLEMENTATION_COMMIT,
    EVALUATION_SEAM_CLOSEOUT_COMMIT,
    EVALUATION_SEAM_IMPLEMENTATION_COMMIT,
    EVALUATION_SEAM_SPEC_COMMIT,
    INSTRUMENT_ORDER,
    LAYER1_IMPLEMENTATION_COMMIT,
    LAYER2_IMPLEMENTATION_COMMIT,
    STATISTICAL_SPEC_COMMIT_CHAIN,
    STATISTICAL_SPEC_PATH,
    _dataset_records,
    _freeze_json,
    _instrument_order,
    _load_canonical_protocol,
    _project_root,
    _seed_entropy,
    validate_protected_paths,
)
from runner.serialization import manifest_sha256


@dataclass(frozen=True)
class PreflightResult:
    baseline_commit: str
    head_commit: str
    manifest_sha256: str
    protocol_sha256: str
    checks_passed: tuple[str, ...]
    environment_record: dict[str, str] = field(default_factory=dict)
    reconstructed_config: DetectorConfig | None = None


_GRANULARITY_TO_INTERVAL = {
    "M15": timedelta(minutes=15),
    "H4": timedelta(hours=4),
    "D1": timedelta(days=1),
}
_FROZEN_ARGUMENTS = ("htf_key_levels", "daily_series", "daily_key_levels")
_FROZEN_LINEAGE_FIELDS = (
    ("direction_policy_implementation_commit", DIRECTION_POLICY_IMPLEMENTATION_COMMIT),
    ("evaluation_seam_spec_commit", EVALUATION_SEAM_SPEC_COMMIT),
    ("evaluation_seam_implementation_commit", EVALUATION_SEAM_IMPLEMENTATION_COMMIT),
    ("evaluation_seam_closeout_commit", EVALUATION_SEAM_CLOSEOUT_COMMIT),
    ("statistical_spec_v3_commit", STATISTICAL_SPEC_COMMIT_CHAIN[2]),
    ("layer1_implementation_commit", LAYER1_IMPLEMENTATION_COMMIT),
    ("layer2_implementation_commit", LAYER2_IMPLEMENTATION_COMMIT),
    ("causal_spec_commit", CAUSAL_SPEC_COMMIT),
    ("causal_spec_amendment_commit", CAUSAL_SPEC_AMENDMENT_COMMIT),
    ("causal_implementation_commit", CAUSAL_IMPLEMENTATION_COMMIT),
)


def _validate_schema(manifest: Manifest) -> None:
    required_strings = (
        "experiment_id", "protocol_artifact_path", "protocol_artifact_sha256",
        "direction_policy_implementation_commit", "evaluation_seam_spec_commit",
        "evaluation_seam_implementation_commit", "evaluation_seam_closeout_commit",
        "statistical_spec_v3_commit", "layer1_implementation_commit",
        "dataset_identity", "population_definition_ref", "est_b_definition",
        "cluster_definition_ref", "nomination_rule_ref", "protected_paths_version",
        "layer2_implementation_commit", "layer3_implementation_commit",
        "measurement_execution_baseline_commit", "spec_sha256",
        "detector_config_fingerprint", "uv_lock_sha256", "causal_spec_commit",
        "causal_spec_amendment_commit", "causal_implementation_commit",
    )
    for name in required_strings:
        value = getattr(manifest, name)
        if not isinstance(value, str) or not value:
            raise AuthorizationError(f"manifest.{name} must be set and non-empty")

    required_collections = (
        "policy_ids", "dataset_file_hashes", "candidate_identity_fields",
        "trade_join_key_fields", "outcome_fields", "bootstrap_config",
        "cost_assumptions", "protected_paths", "instrument_order", "dataset_records",
        "statistical_spec_commit_chain", "causal_source_inputs",
    )
    for name in required_collections:
        value = getattr(manifest, name)
        if value is None or len(value) == 0:
            raise AuthorizationError(f"manifest.{name} must be set and non-empty")
    if manifest.candidate_cutoff_end_utc is None or manifest.outcome_followup_end_utc is None:
        raise AuthorizationError("manifest cutoff fields must be set")
    if any(not entry for entry in manifest.statistical_spec_commit_chain or ()):
        raise AuthorizationError("statistical_spec_commit_chain entries must be non-empty")
    validate_protected_paths(manifest.protected_paths)


def _validate_causal_source_inputs(manifest: Manifest) -> None:
    inputs = manifest.causal_source_inputs or ()
    if len(inputs) != len(INSTRUMENT_ORDER) * len(_FROZEN_ARGUMENTS):
        raise AuthorizationError("manifest.causal_source_inputs must have exactly 9 entries")
    expected_granularity = {
        "htf_key_levels": "H4", "daily_series": "D1", "daily_key_levels": "D1",
    }
    records = manifest.dataset_records or ()
    seen: set[tuple[str, str]] = set()
    for record in inputs:
        pair = (record.instrument, record.argument_name)
        if pair in seen:
            raise AuthorizationError(f"duplicate causal_source_inputs pair: {pair!r}")
        seen.add(pair)
        if record.instrument not in INSTRUMENT_ORDER:
            raise AuthorizationError(
                f"causal_source_inputs instrument {record.instrument!r} not in manifest.instrument_order"
            )
        if record.argument_name not in _FROZEN_ARGUMENTS:
            raise AuthorizationError(f"invalid causal_source_inputs argument: {record.argument_name!r}")
        if record.producer_id != _ARGUMENT_TO_PRODUCER[record.argument_name]:
            raise AuthorizationError(
                f"causal_source_inputs {record.argument_name!r} requires producer_id "
                f"{_ARGUMENT_TO_PRODUCER[record.argument_name]!r}"
            )
        granularity = expected_granularity[record.argument_name]
        if not any(
            item.instrument == record.instrument
            and item.granularity == granularity
            and item.relative_path == record.dataset_relative_path
            for item in records
        ):
            raise AuthorizationError(
                f"causal_source_inputs path not found in manifest.dataset_records for {pair!r}"
            )
    expected = {(instrument, argument) for instrument in INSTRUMENT_ORDER for argument in _FROZEN_ARGUMENTS}
    if seen != expected:
        raise AuthorizationError("causal_source_inputs does not cover the frozen 3x3 mapping")


def _validate_cross_consistency(manifest: Manifest, protocol: dict) -> DetectorConfig:
    if manifest.policy_ids != tuple(protocol["policy_ids"]):
        raise AuthorizationError("policy_ids mismatch between protocol and manifest")
    if manifest.mei_r != protocol["selection"]["mei_r"]:
        raise AuthorizationError("mei_r mismatch between protocol and manifest")

    dataset = protocol["dataset"]
    candidate_cutoff = datetime.fromisoformat(dataset["candidate_cutoff_end_utc"].removesuffix("Z"))
    outcome_followup = datetime.fromisoformat(dataset["outcome_followup_end_utc"].removesuffix("Z"))
    if manifest.candidate_cutoff_end_utc != candidate_cutoff:
        raise AuthorizationError("candidate_cutoff_end_utc mismatch between protocol and manifest")
    if manifest.outcome_followup_end_utc != outcome_followup:
        raise AuthorizationError("outcome_followup_end_utc mismatch between protocol and manifest")

    if manifest.instrument_order != _instrument_order(protocol):
        raise AuthorizationError("instrument_order mismatch between protocol and manifest")

    actual_records = manifest.dataset_records or ()
    expected_records = _dataset_records(protocol)
    if actual_records != expected_records:
        raise AuthorizationError("dataset_records mismatch between protocol and manifest")
    expected_hashes = tuple((record.relative_path, record.sha256) for record in expected_records)
    if manifest.dataset_file_hashes != expected_hashes:
        raise AuthorizationError("dataset_file_hashes mismatch between protocol and manifest")

    _seed_entropy(protocol)
    expected_bootstrap = _freeze_json(protocol["bootstrap"])
    if manifest.bootstrap_config != expected_bootstrap:
        raise AuthorizationError("bootstrap_config mismatch between protocol and manifest")

    config, fingerprint = reconstruct_and_fingerprint(protocol["population"]["config"])
    if config != DetectorConfig():
        raise AuthorizationError("population.config does not equal frozen DetectorConfig defaults")
    if manifest.detector_config_fingerprint != fingerprint:
        raise AuthorizationError("population.config fingerprint mismatch in manifest")
    return config


def _validate_frozen_lineage(manifest: Manifest, project_root: Path) -> None:
    for field_name, expected in _FROZEN_LINEAGE_FIELDS:
        if getattr(manifest, field_name) != expected:
            raise AuthorizationError(f"frozen lineage mismatch: manifest.{field_name}")
    if manifest.statistical_spec_commit_chain != STATISTICAL_SPEC_COMMIT_CHAIN:
        raise AuthorizationError("statistical spec commit chain mismatch")

    spec_digest = sha256_of_file(str(project_root / STATISTICAL_SPEC_PATH))
    if spec_digest != CANONICAL_STATISTICAL_SPEC_SHA256:
        raise AuthorizationError("canonical statistical spec SHA-256 mismatch")
    if manifest.spec_sha256 != spec_digest:
        raise AuthorizationError("manifest spec SHA-256 mismatch")


def _validate_datasets(manifest: Manifest, detector_root: str) -> None:
    for record in manifest.dataset_records or ():
        path = os.path.join(detector_root, record.relative_path)
        if not os.path.isfile(path):
            raise AuthorizationError(f"dataset file does not exist: {path}")
        if os.path.getsize(path) != record.byte_size:
            raise AuthorizationError(f"dataset file size mismatch: {path}")
        if sha256_of_file(path) != record.sha256:
            raise AuthorizationError(f"dataset file hash mismatch: {path}")
        try:
            interval = _GRANULARITY_TO_INTERVAL[record.granularity]
        except KeyError as exc:
            raise AuthorizationError(f"unsupported dataset granularity: {record.granularity}") from exc
        series = load_mt5_csv(path, record.instrument)
        validate_no_gaps_against_manifest(series, interval, manifest)


def run_preflight(manifest: Manifest, protocol_path: str, repo_root: str) -> PreflightResult:
    completed: list[str] = []
    digest = manifest_sha256(manifest)
    project_root = _project_root(repo_root)
    detector_root = project_root / "detector"
    uv_lock_path = detector_root / "uv.lock"
    env = environment_record(str(uv_lock_path))
    reconstructed_config: DetectorConfig | None = None
    stage = "baseline_declared"
    try:
        if not manifest.measurement_execution_baseline_commit:
            raise AuthorizationError("manifest.measurement_execution_baseline_commit must be set")
        completed.append(stage)

        stage = "schema_completeness"
        _validate_schema(manifest)
        _validate_causal_source_inputs(manifest)
        completed.append(stage)

        stage = "protocol_integrity"
        protocol = _load_canonical_protocol(protocol_path, project_root)
        if manifest.protocol_artifact_path != CANONICAL_PROTOCOL_RELATIVE_PATH:
            raise AuthorizationError("manifest protocol path is not canonical")
        if manifest.protocol_artifact_sha256 != CANONICAL_PROTOCOL_SHA256:
            raise AuthorizationError("manifest protocol SHA-256 is not canonical")
        validate_protocol_hash(manifest, protocol_path)
        completed.append(stage)

        stage = "protocol_manifest_consistency"
        reconstructed_config = _validate_cross_consistency(manifest, protocol)
        completed.append(stage)

        stage = "frozen_lineage"
        _validate_frozen_lineage(manifest, project_root)
        completed.append(stage)

        baseline = manifest.measurement_execution_baseline_commit
        layer2 = manifest.layer2_implementation_commit or ""
        layer3 = manifest.layer3_implementation_commit or ""
        if len({layer2, layer3, baseline}) != 3:
            raise AuthorizationError("Layer-2, Layer-3, and baseline commits must be distinct")
        protected = list(manifest.protected_paths)

        stage = "baseline_resolvable"
        for commit in (layer2, layer3, baseline):
            verify_commit_exists(commit, str(project_root))
        completed.append(stage)

        stage = "baseline_ancestor"
        verify_is_ancestor(layer2, str(project_root), layer3)
        verify_is_ancestor(layer3, str(project_root), baseline)
        verify_is_ancestor(baseline, str(project_root))
        completed.append(stage)

        for stage, operation in (
            ("protected_committed_clean", lambda: verify_no_diff(baseline, protected, str(project_root))),
            ("protected_worktree_clean", lambda: verify_no_working_tree_diff(baseline, protected, str(project_root))),
            ("protected_staged_clean", lambda: verify_no_staged_diff(baseline, protected, str(project_root))),
            ("protected_untracked_clean", lambda: verify_no_untracked(protected, str(project_root))),
        ):
            operation()
            completed.append(stage)

        stage = "environment_verification"
        env = verify_environment(
            manifest.uv_lock_sha256 or "", "2.5.2", str(uv_lock_path)
        )
        completed.append(stage)

        stage = "dataset_validation"
        _validate_datasets(manifest, str(detector_root))
        completed.append(stage)
        head_commit = get_head_commit(str(project_root))
    except Exception as exc:
        if isinstance(exc, PreflightFailure):
            raise
        raise PreflightFailure(stage, exc, tuple(completed), digest, env) from exc

    return PreflightResult(
        baseline_commit=manifest.measurement_execution_baseline_commit,
        head_commit=head_commit,
        manifest_sha256=digest,
        protocol_sha256=manifest.protocol_artifact_sha256,
        checks_passed=tuple(completed),
        environment_record=env,
        reconstructed_config=reconstructed_config,
    )
