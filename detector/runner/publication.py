"""Atomic temp-dir write + per-artifact hash + run_status.json written LAST +
single os.replace to final path."""

import hashlib
import os
import time
from dataclasses import dataclass

from runner.errors import ReproducibilityError
from runner.serialization import canonical_json


@dataclass(frozen=True)
class PublicationInputs:
    experiment_id: str
    manifest_dict: dict
    policy_summary_dict: dict
    bootstrap_summary_dict: dict
    nomination_trace_dict: dict
    run_started_utc: str
    run_finished_utc: str


def publish(inputs: PublicationInputs, output_dir: str) -> str:
    """Write the 5 result artifacts atomically. Returns the final path."""
    final_path = os.path.join(output_dir, inputs.experiment_id)
    if os.path.exists(final_path):
        raise ReproducibilityError(
            f"output directory already exists: {final_path}"
        )

    os.makedirs(output_dir, exist_ok=True)
    tmp_name = f".tmp-{inputs.experiment_id}-{os.getpid()}-{int(time.monotonic_ns())}"
    tmp_path = os.path.join(output_dir, tmp_name)
    os.makedirs(tmp_path)

    artifact_files = {
        "run_manifest.json": inputs.manifest_dict,
        "policy_summary.json": inputs.policy_summary_dict,
        "bootstrap_summary.json": inputs.bootstrap_summary_dict,
        "nomination_trace.json": inputs.nomination_trace_dict,
    }

    artifact_hashes: dict[str, str] = {}
    for filename, content in artifact_files.items():
        data = canonical_json(content)
        file_path = os.path.join(tmp_path, filename)
        with open(file_path, "wb") as f:
            f.write(data)
        with open(file_path, "rb") as f:
            written = f.read()
        if written != data:
            raise ReproducibilityError(f"artifact bytes changed while writing {filename}")
        artifact_hashes[filename] = hashlib.sha256(written).hexdigest()

    # run_status.json written LAST
    status = {
        "status": "COMPLETED",
        "experiment_id": inputs.experiment_id,
        "run_started_utc": inputs.run_started_utc,
        "run_finished_utc": inputs.run_finished_utc,
        "artifacts": {
            name: sha for name, sha in artifact_hashes.items()
        },
    }
    status_data = canonical_json(status)
    status_path = os.path.join(tmp_path, "run_status.json")
    with open(status_path, "wb") as f:
        f.write(status_data)

    os.replace(tmp_path, final_path)
    return final_path


def write_failure_artifact(
    experiment_id: str,
    output_dir: str,
    status: str,
    failing_check: str,
    error_class: str,
    error_message: str,
    manifest_sha256: str,
    run_started_utc: str,
    environment_record: dict | None = None,
    completed_checks: list[str] | None = None,
) -> str:
    """Write a failure artifact to <out>/failed/<id>-<started>/failure.json.
    Contains zero statistical fields."""
    failed_dir = os.path.join(output_dir, "failed")
    safe_timestamp = run_started_utc.replace(":", "-")
    run_dir = os.path.join(failed_dir, f"{experiment_id}-{safe_timestamp}")
    os.makedirs(run_dir, exist_ok=True)

    failure: dict = {
        "status": status,
        "failing_check": failing_check,
        "error_class": error_class,
        "error_message": error_message,
        "manifest_sha256": manifest_sha256,
        "run_started_utc": run_started_utc,
    }
    if environment_record is not None:
        failure["environment"] = environment_record
    if completed_checks is not None:
        failure["completed_checks"] = completed_checks

    data = canonical_json(failure)
    failure_path = os.path.join(run_dir, "failure.json")
    with open(failure_path, "wb") as f:
        f.write(data)
    return failure_path
