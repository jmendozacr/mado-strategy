"""Artifacts + publication.

Atomic write, existing directory refused, failure artifact has no
statistical fields, run_manifest schema complete, observation fingerprint
present. All tests use synthetic temporary files."""

import json
import os
import hashlib
from pathlib import Path

import pytest


def test_existing_directory_refused(tmp_path):
    from runner.publication import publish, PublicationInputs

    inputs = PublicationInputs(
        experiment_id="exp-001",
        manifest_dict={"experiment_id": "exp-001"},
        policy_summary_dict={"policies": {}},
        bootstrap_summary_dict={"bootstrap": {}},
        nomination_trace_dict={"nomination": {}},
        run_started_utc="2026-01-01T00:00:00",
        run_finished_utc="2026-01-01T01:00:00",
    )
    out_dir = str(tmp_path / "output")
    os.makedirs(out_dir)
    publish(inputs, out_dir)
    with pytest.raises(Exception, match="already exists"):
        publish(inputs, out_dir)


def test_publish_creates_five_files(tmp_path):
    from runner.publication import publish, PublicationInputs

    inputs = PublicationInputs(
        experiment_id="exp-002",
        manifest_dict={"experiment_id": "exp-002"},
        policy_summary_dict={"policies": {}},
        bootstrap_summary_dict={"bootstrap": {}},
        nomination_trace_dict={"nomination": {}},
        run_started_utc="2026-01-01T00:00:00",
        run_finished_utc="2026-01-01T01:00:00",
    )
    out_dir = str(tmp_path / "output")
    os.makedirs(out_dir)
    result_path = publish(inputs, out_dir)
    files = os.listdir(result_path)
    expected = {
        "run_manifest.json",
        "policy_summary.json",
        "bootstrap_summary.json",
        "nomination_trace.json",
        "run_status.json",
    }
    assert set(files) == expected


def test_run_status_written_last_and_references_others(tmp_path):
    from runner.publication import publish, PublicationInputs

    inputs = PublicationInputs(
        experiment_id="exp-003",
        manifest_dict={"experiment_id": "exp-003"},
        policy_summary_dict={"policies": {}},
        bootstrap_summary_dict={"bootstrap": {}},
        nomination_trace_dict={"nomination": {}},
        run_started_utc="2026-01-01T00:00:00",
        run_finished_utc="2026-01-01T01:00:00",
    )
    out_dir = str(tmp_path / "output")
    os.makedirs(out_dir)
    result_path = publish(inputs, out_dir)
    status_path = os.path.join(result_path, "run_status.json")
    with open(status_path, "r") as f:
        status = json.load(f)
    assert status["status"] == "COMPLETED"
    assert "artifacts" in status
    assert len(status["artifacts"]) == 4


def test_publication_uses_canonical_bytes_and_hashes(tmp_path):
    from runner.publication import publish, PublicationInputs
    from runner.serialization import canonical_json

    inputs = PublicationInputs(
        experiment_id="exp-canonical",
        manifest_dict={"z": 1, "a": "é"},
        policy_summary_dict={"policies": {"P1": {"point": 0.1 + 0.2}}},
        bootstrap_summary_dict={"bootstrap": {"replicates": 0}},
        nomination_trace_dict={"nomination": {"nominee": "NO POLICY NOMINATED"}},
        run_started_utc="2026-01-01T00:00:00",
        run_finished_utc="2026-01-01T01:00:00",
    )
    result_path = Path(publish(inputs, str(tmp_path)))
    expected = {
        "run_manifest.json": inputs.manifest_dict,
        "policy_summary.json": inputs.policy_summary_dict,
        "bootstrap_summary.json": inputs.bootstrap_summary_dict,
        "nomination_trace.json": inputs.nomination_trace_dict,
    }
    status = json.loads((result_path / "run_status.json").read_text(encoding="utf-8"))

    for filename, artifact in expected.items():
        written = (result_path / filename).read_bytes()
        assert written == canonical_json(artifact)
        assert status["artifacts"][filename] == hashlib.sha256(written).hexdigest()


def test_publication_writes_status_before_real_atomic_replacement(tmp_path, monkeypatch):
    import runner.publication as publication

    inputs = publication.PublicationInputs(
        experiment_id="exp-atomic",
        manifest_dict={"experiment_id": "exp-atomic"},
        policy_summary_dict={"policies": {}},
        bootstrap_summary_dict={"bootstrap": {}},
        nomination_trace_dict={"nomination": {}},
        run_started_utc="2026-01-01T00:00:00",
        run_finished_utc="2026-01-01T01:00:00",
    )
    original_replace = publication.os.replace
    replacements = []

    def checked_replace(source, destination):
        source_path = Path(source)
        assert source_path.parent == tmp_path
        assert source_path.name.startswith(".tmp-exp-atomic-")
        assert not Path(destination).exists()
        status = json.loads((source_path / "run_status.json").read_text(encoding="utf-8"))
        assert set(status["artifacts"]) == {
            "run_manifest.json",
            "policy_summary.json",
            "bootstrap_summary.json",
            "nomination_trace.json",
        }
        replacements.append((source_path, Path(destination)))
        return original_replace(source, destination)

    monkeypatch.setattr(publication.os, "replace", checked_replace)
    result_path = Path(publication.publish(inputs, str(tmp_path)))

    assert replacements == [(replacements[0][0], result_path)]
    assert not replacements[0][0].exists()
    assert {path.name for path in result_path.iterdir()} == {
        "run_manifest.json",
        "policy_summary.json",
        "bootstrap_summary.json",
        "nomination_trace.json",
        "run_status.json",
    }


def test_failure_artifact_no_statistical_fields(tmp_path):
    from runner.publication import write_failure_artifact

    out_dir = str(tmp_path / "output")
    os.makedirs(out_dir)
    write_failure_artifact(
        experiment_id="exp-fail",
        output_dir=out_dir,
        status="FAILED_VALIDATION",
        failing_check="check_3",
        error_class="AuthorizationError",
        error_message="baseline not ancestor",
        manifest_sha256="abc123",
        run_started_utc="2026-01-01T00:00:00",
    )
    failed_dir = os.path.join(out_dir, "failed")
    assert os.path.isdir(failed_dir)
    sub = os.listdir(failed_dir)
    assert len(sub) == 1
    failure_file = os.path.join(failed_dir, sub[0], "failure.json")
    with open(failure_file, "r") as f:
        data = json.load(f)
    assert data["status"] == "FAILED_VALIDATION"
    forbidden = [
        "realized_r", "closed_outcome", "mean_r", "wr", "est_b",
        "ci_lower", "ci_upper", "instrument_delta", "nomination_result",
    ]
    for field in forbidden:
        assert field not in data, f"failure artifact contains forbidden field: {field}"


def test_failure_artifact_includes_environment(tmp_path):
    from runner.publication import write_failure_artifact

    out_dir = str(tmp_path / "output")
    os.makedirs(out_dir)
    write_failure_artifact(
        experiment_id="exp-fail-env",
        output_dir=out_dir,
        status="FAILED_SOFTWARE",
        failing_check="instrument_processing",
        error_class="RuntimeError",
        error_message="test error",
        manifest_sha256="abc123",
        run_started_utc="2026-01-01T00:00:00",
        environment_record={"python_version": "3.12.14"},
        completed_checks=["schema_parse", "protocol_hash"],
    )
    failed_dir = os.path.join(out_dir, "failed")
    sub = os.listdir(failed_dir)
    failure_file = os.path.join(failed_dir, sub[0], "failure.json")
    with open(failure_file, "r") as f:
        data = json.load(f)
    assert "environment" in data
    assert data["environment"]["python_version"] == "3.12.14"
    assert "completed_checks" in data
    assert len(data["completed_checks"]) == 2


def test_publication_inputs_type():
    from runner.publication import PublicationInputs

    fields = set(PublicationInputs.__dataclass_fields__)
    assert "experiment_id" in fields
    assert "manifest_dict" in fields
    assert "run_started_utc" in fields
