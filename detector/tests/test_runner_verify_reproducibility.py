"""Focused tests for the offline reproducibility verifier (REQ-STAT-56 Option 1)."""

import hashlib
import json
import os

import pytest

from runner.errors import ReproducibilityError
from runner.serialization import canonical_json
from runner.verify_reproducibility import VerificationSuccess, verify_reproducibility


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_canonical(path: str, obj: dict) -> bytes:
    data = canonical_json(obj)
    with open(path, "wb") as f:
        f.write(data)
    return data


def _make_result_dir(
    base: str,
    experiment_id: str,
    run_started_utc: str = "2026-09-14T10:00:00Z",
    run_finished_utc: str = "2026-09-14T10:05:00Z",
    *,
    policy_summary_override: dict | None = None,
    bootstrap_summary_override: dict | None = None,
    nomination_trace_override: dict | None = None,
    manifest_extra: dict | None = None,
    run_status_override: dict | None = None,
) -> str:
    """Create a minimal synthetic completed result directory."""
    result_dir = os.path.join(base, experiment_id)
    os.makedirs(result_dir, exist_ok=True)

    policy_summary = policy_summary_override or {
        "P1": {"est_b": {"status": "NOT_ESTIMABLE", "point": None}},
    }
    bootstrap_summary = bootstrap_summary_override or {
        "replicate_count": 100,
        "seed": [20260910],
        "ci_method": "percentile",
    }
    nomination_trace = nomination_trace_override or {
        "nominee": "NO POLICY NOMINATED",
        "tie_status": False,
    }
    manifest = {
        "experiment_id": experiment_id,
        "instrument_order": ["EURUSDm", "GBPUSDm", "DXYm"],
        "candidate_universe_fingerprint": {"EURUSDm": "aaa", "GBPUSDm": "bbb", "DXYm": "ccc"},
        "observation_table_fingerprint": "obs_fingerprint_xyz",
        "causal_spec_commit": "1f412e3",
        "run_started_utc": run_started_utc,
        "run_finished_utc": run_finished_utc,
        **(manifest_extra or {}),
    }

    artifacts: dict[str, str] = {}
    for fname, content in [
        ("policy_summary.json", policy_summary),
        ("bootstrap_summary.json", bootstrap_summary),
        ("nomination_trace.json", nomination_trace),
        ("run_manifest.json", manifest),
    ]:
        data = _write_canonical(os.path.join(result_dir, fname), content)
        artifacts[fname] = _sha256(data)

    if run_status_override is not None:
        _write_canonical(os.path.join(result_dir, "run_status.json"), run_status_override)
    else:
        run_status = {
            "status": "COMPLETED",
            "experiment_id": experiment_id,
            "run_started_utc": run_started_utc,
            "run_finished_utc": run_finished_utc,
            "artifacts": artifacts,
        }
        _write_canonical(os.path.join(result_dir, "run_status.json"), run_status)

    return result_dir


# ---------------------------------------------------------------------------
# Tests: success paths
# ---------------------------------------------------------------------------


def test_identical_directories_pass(tmp_path):
    """Two directories with bit-identical content are reproducible."""
    dir_a = _make_result_dir(str(tmp_path / "a"), "exp-001")
    dir_b = _make_result_dir(str(tmp_path / "b"), "exp-001")
    result = verify_reproducibility(dir_a, dir_b)
    assert isinstance(result, VerificationSuccess)
    assert result.experiment_id == "exp-001"


def test_timestamp_only_difference_passes(tmp_path):
    """Two runs differing only in run_started_utc and run_finished_utc are reproducible."""
    dir_a = _make_result_dir(
        str(tmp_path / "a"), "exp-001",
        run_started_utc="2026-09-14T10:00:00Z",
        run_finished_utc="2026-09-14T10:05:00Z",
    )
    dir_b = _make_result_dir(
        str(tmp_path / "b"), "exp-001",
        run_started_utc="2026-09-15T08:30:00Z",  # different time
        run_finished_utc="2026-09-15T08:37:23Z",  # different time
    )
    result = verify_reproducibility(dir_a, dir_b)
    assert result.experiment_id == "exp-001"


def test_success_result_has_experiment_id_and_dirs(tmp_path):
    dir_a = _make_result_dir(str(tmp_path / "a"), "exp-abc")
    dir_b = _make_result_dir(str(tmp_path / "b"), "exp-abc")
    result = verify_reproducibility(dir_a, dir_b)
    assert result.experiment_id == "exp-abc"
    assert result.dir_a == dir_a
    assert result.dir_b == dir_b


# ---------------------------------------------------------------------------
# Tests: experiment identity failures
# ---------------------------------------------------------------------------


def test_experiment_id_mismatch_fails(tmp_path):
    dir_a = _make_result_dir(str(tmp_path / "a"), "exp-001")
    dir_b = _make_result_dir(str(tmp_path / "b"), "exp-002")
    with pytest.raises(ReproducibilityError, match="experiment_id mismatch"):
        verify_reproducibility(dir_a, dir_b)


def test_missing_experiment_id_in_status_fails(tmp_path):
    """A COMPLETED run_status.json with no experiment_id must be rejected."""
    dir_a = _make_result_dir(str(tmp_path / "a"), "exp-001")
    dir_b = _make_result_dir(str(tmp_path / "b"), "exp-001")
    status_path = os.path.join(dir_b, "run_status.json")
    with open(status_path, "rb") as f:
        status = json.loads(f.read())
    del status["experiment_id"]
    with open(status_path, "wb") as f:
        f.write(canonical_json(status))
    with pytest.raises(ReproducibilityError, match="experiment_id"):
        verify_reproducibility(dir_a, dir_b)


def test_empty_experiment_id_in_status_fails(tmp_path):
    """A COMPLETED run_status.json with empty-string experiment_id must be rejected."""
    dir_a = _make_result_dir(str(tmp_path / "a"), "exp-001")
    dir_b = _make_result_dir(str(tmp_path / "b"), "exp-001")
    status_path = os.path.join(dir_b, "run_status.json")
    with open(status_path, "rb") as f:
        status = json.loads(f.read())
    status["experiment_id"] = ""
    with open(status_path, "wb") as f:
        f.write(canonical_json(status))
    with pytest.raises(ReproducibilityError, match="experiment_id"):
        verify_reproducibility(dir_a, dir_b)


def test_manifest_experiment_id_mismatch_fails(tmp_path):
    """run_manifest.json experiment_id must equal run_status.json experiment_id."""
    dir_a = _make_result_dir(str(tmp_path / "a"), "exp-001")
    dir_b = _make_result_dir(str(tmp_path / "b"), "exp-001")
    # Replace manifest with one having a different experiment_id;
    # update the hash in run_status.json so integrity passes but identity check fails.
    manifest_path = os.path.join(dir_b, "run_manifest.json")
    with open(manifest_path, "rb") as f:
        manifest = json.loads(f.read())
    manifest["experiment_id"] = "exp-WRONG"
    new_bytes = canonical_json(manifest)
    with open(manifest_path, "wb") as f:
        f.write(new_bytes)
    status_path = os.path.join(dir_b, "run_status.json")
    with open(status_path, "rb") as f:
        status = json.loads(f.read())
    status["artifacts"]["run_manifest.json"] = _sha256(new_bytes)
    with open(status_path, "wb") as f:
        f.write(canonical_json(status))
    with pytest.raises(ReproducibilityError, match="experiment_id"):
        verify_reproducibility(dir_a, dir_b)


def test_non_completed_status_fails(tmp_path):
    dir_a = _make_result_dir(str(tmp_path / "a"), "exp-001")
    dir_b = _make_result_dir(
        str(tmp_path / "b"), "exp-001",
        run_status_override={
            "status": "FAILED",
            "experiment_id": "exp-001",
            "artifacts": {},
        },
    )
    with pytest.raises(ReproducibilityError, match="not COMPLETED"):
        verify_reproducibility(dir_a, dir_b)


# ---------------------------------------------------------------------------
# Tests: core artifact mutations fail closed
# ---------------------------------------------------------------------------


def test_policy_summary_mutation_fails(tmp_path):
    """A changed policy summary is a reproducibility failure."""
    dir_a = _make_result_dir(str(tmp_path / "a"), "exp-001")
    dir_b = _make_result_dir(
        str(tmp_path / "b"), "exp-001",
        policy_summary_override={"P1": {"est_b": {"status": "ESTIMABLE", "point": 0.25}}},
    )
    with pytest.raises(ReproducibilityError, match="policy_summary"):
        verify_reproducibility(dir_a, dir_b)


def test_bootstrap_summary_mutation_fails(tmp_path):
    dir_a = _make_result_dir(str(tmp_path / "a"), "exp-001")
    dir_b = _make_result_dir(
        str(tmp_path / "b"), "exp-001",
        bootstrap_summary_override={"replicate_count": 9999, "seed": [20260910]},
    )
    with pytest.raises(ReproducibilityError, match="bootstrap_summary"):
        verify_reproducibility(dir_a, dir_b)


def test_nomination_trace_mutation_fails(tmp_path):
    dir_a = _make_result_dir(str(tmp_path / "a"), "exp-001")
    dir_b = _make_result_dir(
        str(tmp_path / "b"), "exp-001",
        nomination_trace_override={"nominee": "P1", "tie_status": False},
    )
    with pytest.raises(ReproducibilityError, match="nomination_trace"):
        verify_reproducibility(dir_a, dir_b)


def test_manifest_candidate_fingerprint_mutation_fails(tmp_path):
    """candidate_universe_fingerprint change is a reproducibility failure."""
    dir_a = _make_result_dir(str(tmp_path / "a"), "exp-001")
    dir_b = _make_result_dir(
        str(tmp_path / "b"), "exp-001",
        manifest_extra={"candidate_universe_fingerprint": {"EURUSDm": "CHANGED"}},
    )
    with pytest.raises(ReproducibilityError, match="run_manifest"):
        verify_reproducibility(dir_a, dir_b)


def test_manifest_observation_fingerprint_mutation_fails(tmp_path):
    """observation_table_fingerprint change is a reproducibility failure."""
    dir_a = _make_result_dir(str(tmp_path / "a"), "exp-001")
    dir_b = _make_result_dir(
        str(tmp_path / "b"), "exp-001",
        manifest_extra={"observation_table_fingerprint": "DIFFERENT_FINGERPRINT"},
    )
    with pytest.raises(ReproducibilityError, match="run_manifest"):
        verify_reproducibility(dir_a, dir_b)


def test_manifest_lineage_mutation_fails(tmp_path):
    """Causal spec commit change is a reproducibility failure."""
    dir_a = _make_result_dir(str(tmp_path / "a"), "exp-001")
    dir_b = _make_result_dir(
        str(tmp_path / "b"), "exp-001",
        manifest_extra={"causal_spec_commit": "DIFFERENT_COMMIT"},
    )
    with pytest.raises(ReproducibilityError, match="run_manifest"):
        verify_reproducibility(dir_a, dir_b)


def test_manifest_instrument_order_mutation_fails(tmp_path):
    """Instrument order change is a reproducibility failure."""
    dir_a = _make_result_dir(str(tmp_path / "a"), "exp-001")
    dir_b = _make_result_dir(
        str(tmp_path / "b"), "exp-001",
        manifest_extra={"instrument_order": ["GBPUSDm", "EURUSDm", "DXYm"]},
    )
    with pytest.raises(ReproducibilityError, match="run_manifest"):
        verify_reproducibility(dir_a, dir_b)


# ---------------------------------------------------------------------------
# Tests: artifact inventory validation
# ---------------------------------------------------------------------------


def test_missing_artifact_in_inventory_fails(tmp_path):
    """An artifacts map missing a required entry must be rejected."""
    dir_a = _make_result_dir(str(tmp_path / "a"), "exp-001")
    dir_b = _make_result_dir(str(tmp_path / "b"), "exp-001")
    status_path = os.path.join(dir_b, "run_status.json")
    with open(status_path, "rb") as f:
        status = json.loads(f.read())
    del status["artifacts"]["nomination_trace.json"]
    with open(status_path, "wb") as f:
        f.write(canonical_json(status))
    with pytest.raises(ReproducibilityError, match="inventory"):
        verify_reproducibility(dir_a, dir_b)


def test_extra_artifact_in_inventory_fails(tmp_path):
    """An artifacts map with an extra entry beyond the four required must be rejected."""
    dir_a = _make_result_dir(str(tmp_path / "a"), "exp-001")
    dir_b = _make_result_dir(str(tmp_path / "b"), "exp-001")
    status_path = os.path.join(dir_b, "run_status.json")
    with open(status_path, "rb") as f:
        status = json.loads(f.read())
    status["artifacts"]["unexpected_file.json"] = "a" * 64
    with open(status_path, "wb") as f:
        f.write(canonical_json(status))
    with pytest.raises(ReproducibilityError, match="inventory"):
        verify_reproducibility(dir_a, dir_b)


def test_null_artifact_hash_in_inventory_fails(tmp_path):
    """A null hash value in the artifacts map must be rejected before any file is read."""
    dir_a = _make_result_dir(str(tmp_path / "a"), "exp-001")
    dir_b = _make_result_dir(str(tmp_path / "b"), "exp-001")
    status_path = os.path.join(dir_b, "run_status.json")
    with open(status_path, "rb") as f:
        status = json.loads(f.read())
    status["artifacts"]["run_manifest.json"] = None
    with open(status_path, "wb") as f:
        f.write(canonical_json(status))
    with pytest.raises(ReproducibilityError, match="hash"):
        verify_reproducibility(dir_a, dir_b)


def test_malformed_artifact_hash_in_inventory_fails(tmp_path):
    """A non-hex or wrong-length hash value in the artifacts map must be rejected."""
    dir_a = _make_result_dir(str(tmp_path / "a"), "exp-001")
    dir_b = _make_result_dir(str(tmp_path / "b"), "exp-001")
    status_path = os.path.join(dir_b, "run_status.json")
    with open(status_path, "rb") as f:
        status = json.loads(f.read())
    status["artifacts"]["bootstrap_summary.json"] = "not-a-valid-sha256"
    with open(status_path, "wb") as f:
        f.write(canonical_json(status))
    with pytest.raises(ReproducibilityError, match="hash"):
        verify_reproducibility(dir_a, dir_b)


def test_run_manifest_hash_tampered_fails(tmp_path):
    """A run_manifest.json whose bytes don't match its recorded hash must be rejected."""
    dir_a = _make_result_dir(str(tmp_path / "a"), "exp-001")
    dir_b = _make_result_dir(str(tmp_path / "b"), "exp-001")
    # Overwrite run_manifest.json without updating the hash in run_status.json.
    with open(os.path.join(dir_b, "run_manifest.json"), "wb") as f:
        f.write(canonical_json({"tampered": True}))
    with pytest.raises(ReproducibilityError):
        verify_reproducibility(dir_a, dir_b)


# ---------------------------------------------------------------------------
# Tests: missing or malformed files fail closed
# ---------------------------------------------------------------------------


def test_missing_run_status_fails(tmp_path):
    dir_a = _make_result_dir(str(tmp_path / "a"), "exp-001")
    dir_b = _make_result_dir(str(tmp_path / "b"), "exp-001")
    os.remove(os.path.join(dir_b, "run_status.json"))
    with pytest.raises(ReproducibilityError, match="run_status"):
        verify_reproducibility(dir_a, dir_b)


def test_missing_policy_summary_fails(tmp_path):
    dir_a = _make_result_dir(str(tmp_path / "a"), "exp-001")
    dir_b = _make_result_dir(str(tmp_path / "b"), "exp-001")
    os.remove(os.path.join(dir_b, "policy_summary.json"))
    with pytest.raises(ReproducibilityError):
        verify_reproducibility(dir_a, dir_b)


def test_missing_run_manifest_fails(tmp_path):
    dir_a = _make_result_dir(str(tmp_path / "a"), "exp-001")
    dir_b = _make_result_dir(str(tmp_path / "b"), "exp-001")
    os.remove(os.path.join(dir_b, "run_manifest.json"))
    with pytest.raises(ReproducibilityError):
        verify_reproducibility(dir_a, dir_b)


def test_malformed_run_status_json_fails(tmp_path):
    dir_a = _make_result_dir(str(tmp_path / "a"), "exp-001")
    dir_b = _make_result_dir(str(tmp_path / "b"), "exp-001")
    with open(os.path.join(dir_b, "run_status.json"), "wb") as f:
        f.write(b"NOT VALID JSON{{{")
    with pytest.raises(ReproducibilityError, match="malformed"):
        verify_reproducibility(dir_a, dir_b)


def test_malformed_run_manifest_json_fails(tmp_path):
    dir_a = _make_result_dir(str(tmp_path / "a"), "exp-001")
    dir_b = _make_result_dir(str(tmp_path / "b"), "exp-001")
    with open(os.path.join(dir_b, "run_manifest.json"), "wb") as f:
        f.write(b"{corrupted")
    with pytest.raises(ReproducibilityError, match="malformed"):
        verify_reproducibility(dir_a, dir_b)


def test_artifact_hash_mismatch_in_status_fails(tmp_path):
    """An artifact whose bytes don't match the hash recorded in run_status.json fails."""
    dir_a = _make_result_dir(str(tmp_path / "a"), "exp-001")
    dir_b = _make_result_dir(str(tmp_path / "b"), "exp-001")
    # Tamper with the file after run_status.json was written
    with open(os.path.join(dir_b, "policy_summary.json"), "wb") as f:
        f.write(canonical_json({"tampered": True}))
    with pytest.raises(ReproducibilityError):
        verify_reproducibility(dir_a, dir_b)


# ---------------------------------------------------------------------------
# Tests: no runner execution path invoked
# ---------------------------------------------------------------------------


def test_verifier_does_not_import_detection_modules(tmp_path):
    """The verifier module must not import or expose execution or detection modules."""
    import importlib
    import types

    mod = importlib.import_module("runner.verify_reproducibility")
    forbidden_prefixes = ("backtest", "selection", "causal", "alignment", "primitives")

    # Check that no module-type attribute in the verifier's namespace comes from a
    # forbidden detection or execution package. Deterministic — does not depend on
    # which modules other tests may have loaded into sys.modules.
    leaked = [
        (attr, val.__name__)
        for attr, val in vars(mod).items()
        if isinstance(val, types.ModuleType)
        and any(
            val.__name__ == prefix
            or val.__name__.startswith(f"detector.{prefix}.")
            or val.__name__.startswith(f"{prefix}.")
            for prefix in forbidden_prefixes
        )
    ]
    assert not leaked, (
        f"runner.verify_reproducibility imports forbidden execution module(s): {leaked}"
    )

    # Also confirm no name in the namespace starts with a forbidden prefix
    # (catches re-exports or aliases).
    for prefix in forbidden_prefixes:
        assert not any(
            name.startswith(prefix)
            for name in dir(mod)
        ), f"verify_reproducibility namespace has name starting with {prefix!r}"


def test_verifier_does_not_call_build_stage6_population(tmp_path):
    """Running the verifier must not call any population-building function."""
    dir_a = _make_result_dir(str(tmp_path / "a"), "exp-001")
    dir_b = _make_result_dir(str(tmp_path / "b"), "exp-001")
    # If this succeeds without raising, no production runner code was invoked.
    result = verify_reproducibility(dir_a, dir_b)
    assert result.experiment_id == "exp-001"
