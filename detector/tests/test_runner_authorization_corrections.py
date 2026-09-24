import json
import hashlib
from dataclasses import fields, replace
from pathlib import Path
from unittest.mock import call, patch

import pytest

from adapter.manifest import DatasetFileRecord, Manifest
from runner.artifacts import build_run_manifest
from runner.manifest_builder import build_manifest
from runner.preflight import _validate_cross_consistency, run_preflight
from runner.serialization import manifest_sha256
from runner.run_discovery import AuthorizationReceipt


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DETECTOR_ROOT = PROJECT_ROOT / "detector"
PROTOCOL_PATH = DETECTOR_ROOT / "research" / "direction_policy_discovery_v1_amendment_1.json"
CANONICAL_PROTOCOL_PATH = "detector/research/direction_policy_discovery_v1_amendment_1.json"
STATISTICAL_SPEC_PATH = "openspec/changes/crt-detector-direction-policy-statistical-runner/spec.md"


def _manifest() -> Manifest:
    return build_manifest(
        protocol_path=str(PROTOCOL_PATH),
        repo_root=str(DETECTOR_ROOT),
        baseline_commit="b" * 40,
        layer2_commit="1dd0acc",
        layer3_commit="c" * 40,
    )


def test_builder_consumes_canonical_amendment_shape_without_dataset_access():
    manifest = _manifest()
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    protocol_bootstrap = protocol["bootstrap"]

    assert manifest.experiment_id == "direction_policy_discovery_v1_amendment_1"
    assert manifest.instrument_order == ("EURUSDm", "GBPUSDm", "DXYm")
    assert manifest.dataset_records is not None
    assert len(manifest.dataset_records) == 9
    assert {record.granularity for record in manifest.dataset_records} == {"M15", "H4", "D1"}
    assert manifest.dataset_records[0] == DatasetFileRecord(
        instrument="DXYm",
        granularity="D1",
        relative_path="../pairs/_discovery_snapshot/D1/DXYm_Daily_202110270000_202608190000.csv",
        byte_size=80376,
        sha256="2224944e3fe28504c84c0a8206a9cea4098d067b9beb9b78efe3228db3554db0",
        start_utc=manifest.dataset_records[0].start_utc,
        end_utc=manifest.dataset_records[0].end_utc,
    )
    assert manifest.policy_ids == tuple(protocol["policy_ids"])
    assert manifest.mei_r == 0.2
    assert dict(manifest.bootstrap_config)["replicates"] == 10000
    assert dict(manifest.bootstrap_config)["ci"] == protocol_bootstrap["ci"]
    assert manifest.detector_config_fingerprint
    assert manifest.causal_source_inputs is not None
    assert len(manifest.causal_source_inputs) == 9
    assert manifest.outcome_fields == ("realized_r", "closed_outcome")


@pytest.mark.parametrize(
    ("field_name", "replacement", "match"),
    [
        ("policy_ids", lambda m: tuple(reversed(m.policy_ids)), "policy_ids"),
        ("candidate_cutoff_end_utc", lambda m: m.outcome_followup_end_utc, "candidate_cutoff"),
        ("instrument_order", lambda m: tuple(reversed(m.instrument_order)), "instrument_order"),
        ("dataset_records", lambda m: m.dataset_records[:-1], "dataset_records"),
        ("bootstrap_config", lambda m: (("replicates", 9999), ("seed", (20260910,))), "bootstrap_config"),
        ("detector_config_fingerprint", lambda m: "0" * 64, "population.config"),
    ],
)
def test_protocol_manifest_mismatch_fails_independently(field_name, replacement, match):
    manifest = _manifest()
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    drifted = replace(manifest, **{field_name: replacement(manifest)})

    with pytest.raises(Exception, match=match):
        _validate_cross_consistency(drifted, protocol)


def test_protocol_mei_drift_fails_independently():
    manifest = _manifest()
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    protocol["selection"]["mei_r"] = 0.21

    with pytest.raises(Exception, match="mei_r"):
        _validate_cross_consistency(manifest, protocol)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("ci",), "different CI"),
        (("undefined",), "different undefined rule"),
        (("prng", "implementation"), "different implementation"),
        (("prng", "paired"), "different pairing"),
    ],
)
def test_nested_bootstrap_drift_fails(path, value):
    manifest = _manifest()
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    target = protocol["bootstrap"]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    with pytest.raises(Exception, match="bootstrap_config"):
        _validate_cross_consistency(manifest, protocol)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("stream_order", "replicate 0..9999; XEURUSDm,GBPUSDm,DXYm; policies consume no RNG"),
        ("seed", "one SeedSequence entropy sequence [7,20260910]; no per-policy stream"),
    ],
)
def test_bootstrap_order_and_entropy_are_parsed_exactly(field, value):
    manifest = _manifest()
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    protocol["bootstrap"]["prng"][field] = value

    with pytest.raises(Exception, match="bootstrap_config|instrument_order|seed"):
        _validate_cross_consistency(manifest, protocol)


def test_run_manifest_contains_every_frozen_manifest_field_verbatim():
    manifest = _manifest()
    receipt = AuthorizationReceipt(
        baseline_commit=manifest.measurement_execution_baseline_commit,
        head_commit="h" * 40,
        manifest_sha256=manifest_sha256(manifest),
        protocol_sha256=manifest.protocol_artifact_sha256,
        authorization_commit="a" * 40,
        checks_passed=("all",),
        instrument_results=(),
    )

    artifact = build_run_manifest(manifest, receipt, "start", "finish", "observation-fingerprint")

    assert {field.name for field in fields(Manifest)} <= artifact.keys()
    assert artifact["dataset_identity"] == manifest.dataset_identity
    assert artifact["dataset_file_hashes"] == [list(item) for item in manifest.dataset_file_hashes]
    assert artifact["causal_source_inputs"][0]["instrument"] == "EURUSDm"


def test_manifest_fingerprint_changes_independently_of_protocol_hash():
    manifest = _manifest()
    changed = replace(manifest, protected_paths_version="v2")

    assert manifest_sha256(changed) != manifest_sha256(manifest)
    assert changed.protocol_artifact_sha256 == manifest.protocol_artifact_sha256


def test_protocol_byte_length_fails_with_internally_consistent_hash(tmp_path):
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    changed_path = tmp_path / CANONICAL_PROTOCOL_PATH
    changed_path.parent.mkdir(parents=True)
    changed_bytes = json.dumps(protocol, separators=(",", ":")).encode("utf-8")
    changed_path.write_bytes(changed_bytes)

    with patch("runner.preflight.environment_record", return_value={}):
        with pytest.raises(Exception, match="byte length"):
            run_preflight(_manifest(), str(changed_path), str(tmp_path), authorization_commit="a" * 40)


def test_preflight_rejects_same_length_self_hashed_alternate_protocol(tmp_path):
    canonical_bytes = PROTOCOL_PATH.read_bytes()
    changed_bytes = canonical_bytes.replace(b'"version":1', b'"version":2', 1)
    assert len(changed_bytes) == len(canonical_bytes)
    protocol_path = tmp_path / CANONICAL_PROTOCOL_PATH
    protocol_path.parent.mkdir(parents=True)
    protocol_path.write_bytes(changed_bytes)
    manifest = replace(
        _manifest(),
        protocol_artifact_path=CANONICAL_PROTOCOL_PATH,
        protocol_artifact_sha256=hashlib.sha256(changed_bytes).hexdigest(),
    )

    with (
        patch("runner.preflight.environment_record", return_value={}),
        patch("runner.preflight.verify_commit_exists"),
        patch("runner.preflight.verify_is_ancestor"),
        patch("runner.preflight.verify_no_diff"),
        patch("runner.preflight.verify_no_working_tree_diff"),
        patch("runner.preflight.verify_no_staged_diff"),
        patch("runner.preflight.verify_no_untracked"),
        patch("runner.preflight.verify_environment", return_value={}),
        patch("runner.preflight._validate_datasets"),
        patch("runner.preflight.get_head_commit", return_value="h" * 40),
    ):
        with pytest.raises(Exception, match="protocol SHA-256"):
            run_preflight(manifest, str(protocol_path), str(tmp_path), authorization_commit="a" * 40)


@pytest.mark.parametrize(
    "field_name",
    (
        "direction_policy_implementation_commit",
        "evaluation_seam_spec_commit",
        "evaluation_seam_implementation_commit",
        "evaluation_seam_closeout_commit",
        "statistical_spec_v3_commit",
        "layer1_implementation_commit",
        "layer2_implementation_commit",
        "causal_spec_commit",
        "causal_spec_amendment_commit",
        "causal_implementation_commit",
    ),
)
def test_preflight_rejects_false_frozen_lineage(field_name):
    manifest = replace(_manifest(), **{field_name: "0" * 40})

    with patch("runner.preflight.environment_record", return_value={}):
        with pytest.raises(Exception, match="frozen lineage"):
            run_preflight(manifest, str(PROTOCOL_PATH), str(DETECTOR_ROOT), authorization_commit="a" * 40)


def test_preflight_rejects_false_statistical_spec_chain_and_hash():
    manifest = _manifest()

    with patch("runner.preflight.environment_record", return_value={}):
        with pytest.raises(Exception, match="statistical spec commit chain"):
            run_preflight(
                replace(
                    manifest,
                    statistical_spec_commit_chain=tuple(
                        reversed(manifest.statistical_spec_commit_chain)
                    ),
                ),
                str(PROTOCOL_PATH),
                str(DETECTOR_ROOT),
                authorization_commit="a" * 40,
            )
        with pytest.raises(Exception, match="spec SHA-256"):
            run_preflight(
                replace(manifest, spec_sha256="0" * 64),
                str(PROTOCOL_PATH),
                str(DETECTOR_ROOT),
                authorization_commit="a" * 40,
            )


def test_preflight_recomputes_canonical_statistical_spec_hash(tmp_path):
    protocol_path = tmp_path / CANONICAL_PROTOCOL_PATH
    protocol_path.parent.mkdir(parents=True)
    protocol_path.write_bytes(PROTOCOL_PATH.read_bytes())
    spec_path = tmp_path / STATISTICAL_SPEC_PATH
    spec_path.parent.mkdir(parents=True)
    spec_path.write_bytes((PROJECT_ROOT / STATISTICAL_SPEC_PATH).read_bytes() + b"\n")

    with patch("runner.preflight.environment_record", return_value={}):
        with pytest.raises(Exception, match="canonical statistical spec SHA-256"):
            run_preflight(_manifest(), str(protocol_path), str(tmp_path), authorization_commit="a" * 40)


def test_preflight_validates_supplied_layer_commit_existence_and_order():
    from runner.serialization import canonical_json, to_json_value

    manifest = _manifest()
    project_root = str(PROJECT_ROOT)
    auth_commit = "a" * 40
    # Compute bytes that exactly match the runtime serialization so the binding check passes.
    runtime_bytes = canonical_json(to_json_value(manifest))
    with (
        patch("runner.preflight.environment_record", return_value={}),
        patch("runner.preflight.verify_commit_exists") as commit_exists,
        patch("runner.preflight.verify_is_ancestor") as is_ancestor,
        patch("runner.preflight.read_committed_blob", return_value=runtime_bytes),
        patch("runner.preflight.verify_no_diff"),
        patch("runner.preflight.verify_no_working_tree_diff"),
        patch("runner.preflight.verify_no_staged_diff"),
        patch("runner.preflight.verify_no_untracked"),
        patch("runner.preflight.verify_environment", return_value={}),
        patch("runner.preflight._validate_datasets"),
        patch("runner.preflight.get_head_commit", return_value="h" * 40),
    ):
        run_preflight(manifest, str(PROTOCOL_PATH), str(DETECTOR_ROOT), authorization_commit=auth_commit)

    assert commit_exists.call_args_list == [
        call(auth_commit, project_root),
        call(manifest.layer2_implementation_commit, project_root),
        call(manifest.layer3_implementation_commit, project_root),
        call(manifest.measurement_execution_baseline_commit, project_root),
    ]
    assert is_ancestor.call_args_list == [
        call(manifest.measurement_execution_baseline_commit, project_root, auth_commit),
        call(auth_commit, project_root),
        call(
            manifest.layer2_implementation_commit,
            project_root,
            manifest.layer3_implementation_commit,
        ),
        call(
            manifest.layer3_implementation_commit,
            project_root,
            manifest.measurement_execution_baseline_commit,
        ),
        call(manifest.measurement_execution_baseline_commit, project_root),
    ]


@pytest.mark.parametrize(
    "overrides",
    (
        {"layer3_implementation_commit": "1dd0acc"},
        {
            "layer3_implementation_commit": "b" * 40,
            "measurement_execution_baseline_commit": "b" * 40,
        },
    ),
)
def test_preflight_requires_distinct_ordered_layer_and_baseline_commits(overrides):
    from runner.serialization import canonical_json, to_json_value
    manifest = replace(_manifest(), **overrides)
    runtime_bytes = canonical_json(to_json_value(manifest))
    with (
        patch("runner.preflight.environment_record", return_value={}),
        patch("runner.preflight.verify_commit_exists"),
        patch("runner.preflight.verify_is_ancestor"),
        patch("runner.preflight.read_committed_blob", return_value=runtime_bytes),
        patch("runner.preflight.verify_no_diff"),
        patch("runner.preflight.verify_no_working_tree_diff"),
        patch("runner.preflight.verify_no_staged_diff"),
        patch("runner.preflight.verify_no_untracked"),
    ):
        with pytest.raises(Exception, match="distinct"):
            run_preflight(
                manifest,
                str(PROTOCOL_PATH),
                str(DETECTOR_ROOT),
                authorization_commit="a" * 40,
            )
