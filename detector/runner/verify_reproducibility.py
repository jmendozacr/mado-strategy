"""Offline reproducibility verifier for two completed result directories.

REQ-STAT-56: a successful rerun of the same authorized experiment MUST be
deterministic except permitted operational metadata (timestamps); core result
hashes matching is required, or the rerun is a REPRODUCIBILITY FAILURE.

This is the approved Option 1 implementation: an offline verifier that accepts
two already-published result directories and detects any divergence outside the
explicitly permitted operational metadata. The normal discovery runner remains
one-shot and continues refusing an existing <out>/<experiment_id>/ directory.

Comparison contract (explicit engineering decisions consistent with REQ-STAT-56):

  DETERMINISTIC artifacts (must be byte-identical — no timestamps):
    policy_summary.json, bootstrap_summary.json, nomination_trace.json
    Comparison: SHA-256 hashes recorded in run_status.json, cross-verified
    against actual file bytes to detect corruption.

  MANIFEST (run_manifest.json):
    Contains run_started_utc and run_finished_utc which are explicitly permitted
    to differ. Every other field must produce identical canonical JSON after
    those two keys are stripped. Any other field difference — including
    candidate_universe_fingerprint, observation_table_fingerprint, manifest
    lineage (causal_spec_commit, etc.), instrument_order, or any other
    provenance field — is a REPRODUCIBILITY FAILURE.

  run_status.json:
    experiment_id must be non-empty and status="COMPLETED". The artifacts map
    must contain exactly the four published artifact names. SHA-256 of every
    artifact is verified against the per-directory recorded hash before use.
    The run_manifest.json hash is verified per-directory for integrity but is
    not compared across directories because timestamps change it legitimately;
    run_manifest.json is compared field-by-field instead. run_started_utc and
    run_finished_utc in run_status.json are permitted to differ.

Does not execute detection, simulation, statistics, network access, or any
real-data loading. Operates only on the five published JSON artifact files.
"""

import hashlib
import json
import os
import re
from dataclasses import dataclass

from runner.errors import ReproducibilityError
from runner.serialization import canonical_json

# Exact set of artifact names every completed result directory must publish.
_REQUIRED_ARTIFACTS = frozenset({
    "run_manifest.json",
    "policy_summary.json",
    "bootstrap_summary.json",
    "nomination_trace.json",
})

# Artifacts that carry no timestamps and must be byte-identical between runs.
_DETERMINISTIC_ARTIFACTS = (
    "policy_summary.json",
    "bootstrap_summary.json",
    "nomination_trace.json",
)

# Keys in run_manifest.json that are permitted to differ between runs (REQ-STAT-56).
_MANIFEST_VARIABLE_KEYS = frozenset({"run_started_utc", "run_finished_utc"})

# Valid SHA-256 hex digest: exactly 64 lowercase hexadecimal characters.
_SHA256_RE = re.compile(r'^[0-9a-f]{64}$')


@dataclass(frozen=True)
class VerificationSuccess:
    """Returned when two result directories are confirmed reproducible."""

    experiment_id: str
    dir_a: str
    dir_b: str


def verify_reproducibility(dir_a: str, dir_b: str) -> VerificationSuccess:
    """Verify that two completed result directories are reproducible.

    Accepts two completed experiment result directories (each containing the
    five artifacts published by the discovery runner). Returns VerificationSuccess
    when reproducible; raises ReproducibilityError with a precise mismatch
    explanation on any divergence outside the permitted operational metadata.
    """
    status_a = _read_run_status(dir_a)
    status_b = _read_run_status(dir_b)

    _require_completed(status_a, "dir_a", dir_a)
    _require_completed(status_b, "dir_b", dir_b)

    exp_a: str = status_a["experiment_id"]  # non-empty guaranteed by _require_completed
    exp_b: str = status_b["experiment_id"]
    if exp_a != exp_b:
        raise ReproducibilityError(
            f"experiment_id mismatch: {exp_a!r} (dir_a) vs {exp_b!r} (dir_b)"
        )
    experiment_id = exp_a

    hashes_a = _validate_artifact_inventory(status_a, "dir_a")
    hashes_b = _validate_artifact_inventory(status_b, "dir_b")

    for filename in _DETERMINISTIC_ARTIFACTS:
        _compare_deterministic_artifact(dir_a, dir_b, filename, hashes_a, hashes_b)

    _compare_manifests(
        dir_a, dir_b,
        hashes_a["run_manifest.json"],
        hashes_b["run_manifest.json"],
        experiment_id,
    )

    return VerificationSuccess(
        experiment_id=experiment_id,
        dir_a=dir_a,
        dir_b=dir_b,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _read_run_status(result_dir: str) -> dict:
    path = os.path.join(result_dir, "run_status.json")
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError as e:
        raise ReproducibilityError(
            f"cannot read run_status.json from {result_dir}: {e}"
        ) from e
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ReproducibilityError(
            f"malformed run_status.json in {result_dir}: {e}"
        ) from e


def _require_completed(status: dict, label: str, result_dir: str) -> None:
    s = status.get("status")
    if s != "COMPLETED":
        raise ReproducibilityError(
            f"{label} ({result_dir}) is not COMPLETED: status={s!r}"
        )
    exp_id = status.get("experiment_id")
    if not exp_id:
        raise ReproducibilityError(
            f"{label} ({result_dir}) has missing or empty experiment_id"
        )


def _validate_artifact_inventory(status: dict, label: str) -> dict:
    """Return the artifacts dict after verifying it contains exactly the four required keys
    and that every hash value is a valid 64-character lowercase SHA-256 hex string."""
    artifacts = status.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ReproducibilityError(
            f"{label}: artifacts field is missing or not an object in run_status.json"
        )
    actual = frozenset(artifacts.keys())
    if actual != _REQUIRED_ARTIFACTS:
        missing = sorted(_REQUIRED_ARTIFACTS - actual)
        extra = sorted(actual - _REQUIRED_ARTIFACTS)
        parts = []
        if missing:
            parts.append(f"missing={missing}")
        if extra:
            parts.append(f"extra={extra}")
        raise ReproducibilityError(
            f"{label}: artifact inventory invalid ({', '.join(parts)})"
        )
    for fname in _REQUIRED_ARTIFACTS:
        h = artifacts[fname]
        if not isinstance(h, str) or not _SHA256_RE.match(h):
            raise ReproducibilityError(
                f"{label}: artifact hash for {fname!r} is not a valid SHA-256 hex string: {h!r}"
            )
    return artifacts


def _load_artifact(result_dir: str, filename: str, expected_sha256: str | None = None) -> bytes:
    """Load an artifact file; optionally verify its bytes against a recorded hash."""
    path = os.path.join(result_dir, filename)
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        raise ReproducibilityError(
            f"cannot read {filename} from {result_dir}: {e}"
        ) from e
    if expected_sha256 is not None:
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected_sha256:
            raise ReproducibilityError(
                f"artifact integrity failure for {filename} in {result_dir}: "
                f"recorded hash {expected_sha256!r} but actual is {actual!r}"
            )
    return data


def _compare_deterministic_artifact(
    dir_a: str,
    dir_b: str,
    filename: str,
    hashes_a: dict,
    hashes_b: dict,
) -> None:
    """Verify a timestamp-free artifact is byte-identical across two runs."""
    sha_a = hashes_a.get(filename)
    sha_b = hashes_b.get(filename)

    # Load and cross-verify each file against its recorded hash.
    _load_artifact(dir_a, filename, sha_a)
    _load_artifact(dir_b, filename, sha_b)

    if sha_a is None or sha_b is None:
        raise ReproducibilityError(
            f"artifact hash missing in run_status.json for {filename}"
        )
    if sha_a != sha_b:
        raise ReproducibilityError(
            f"core artifact hash mismatch for {filename}: "
            f"{sha_a!r} (dir_a) vs {sha_b!r} (dir_b)"
        )


def _compare_manifests(
    dir_a: str,
    dir_b: str,
    sha_a: str,
    sha_b: str,
    expected_experiment_id: str,
) -> None:
    """Compare run_manifest.json after stripping permitted operational fields.

    Raw bytes are verified per-directory against the recorded SHA-256 before
    parsing. The hashes are NOT compared across directories because permitted
    timestamps make them legitimately different.
    """
    raw_a = _load_artifact(dir_a, "run_manifest.json", sha_a)
    raw_b = _load_artifact(dir_b, "run_manifest.json", sha_b)

    try:
        obj_a: dict = json.loads(raw_a)
    except json.JSONDecodeError as e:
        raise ReproducibilityError(
            f"malformed run_manifest.json in {dir_a}: {e}"
        ) from e
    try:
        obj_b: dict = json.loads(raw_b)
    except json.JSONDecodeError as e:
        raise ReproducibilityError(
            f"malformed run_manifest.json in {dir_b}: {e}"
        ) from e

    for obj, label in ((obj_a, "dir_a"), (obj_b, "dir_b")):
        manifest_exp = obj.get("experiment_id")
        if not manifest_exp:
            raise ReproducibilityError(
                f"{label}: run_manifest.json has missing or empty experiment_id"
            )
        if manifest_exp != expected_experiment_id:
            raise ReproducibilityError(
                f"{label}: run_manifest.json experiment_id {manifest_exp!r} does not match "
                f"run_status.json experiment_id {expected_experiment_id!r}"
            )

    for key in _MANIFEST_VARIABLE_KEYS:
        obj_a.pop(key, None)
        obj_b.pop(key, None)

    canonical_a = canonical_json(obj_a)
    canonical_b = canonical_json(obj_b)

    if canonical_a != canonical_b:
        differing = sorted(
            k for k in set(obj_a) | set(obj_b) if obj_a.get(k) != obj_b.get(k)
        )
        raise ReproducibilityError(
            f"run_manifest.json content mismatch in fields: {differing}"
        )
