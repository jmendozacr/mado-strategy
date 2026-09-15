"""Authorization manifest binding tests — REQ-STAT-44/46."""

import contextlib
import dataclasses
import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from runner.errors import AuthorizationError, PreflightFailure
from runner.git_ops import read_committed_blob
from runner.manifest_builder import CANONICAL_MANIFEST_ARTIFACT_PATH, PROTECTED_PATHS
from runner.serialization import canonical_json


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True, capture_output=True)
    return repo


def _make_commit(repo: Path, files: dict[str, bytes], msg: str = "commit") -> str:
    for path, content in files.items():
        p = repo / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
        subprocess.run(["git", "add", path], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", msg], cwd=repo, check=True, capture_output=True)
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


_SENTINEL_BYTES = b'{"sentinel":true}\n'


class _FakeManifest:
    def __init__(self, **overrides):
        self.experiment_id = "test-binding-001"
        self.protocol_artifact_path = "detector/research/protocol.json"
        self.protocol_artifact_sha256 = "abc123"
        self.measurement_execution_baseline_commit = "b" * 40
        self.layer2_implementation_commit = "l2" + "0" * 38
        self.layer3_implementation_commit = "l3" + "0" * 38
        self.protected_paths = ()
        self.uv_lock_sha256 = "uv" + "0" * 62
        for k, v in overrides.items():
            setattr(self, k, v)

    def __getattr__(self, name):
        return None


def _build_minimal_manifest(**overrides):
    from adapter.manifest import CausalSourceInputRecord, DatasetFileRecord, Manifest
    from datetime import datetime
    from evaluation.direction import FROZEN_POLICY_IDS

    _prod = {
        "htf_key_levels": "primitives.fvg.detect_fvgs->primitives.fvg.to_key_levels",
        "daily_series": "ingestion.loader.load_mt5_csv",
        "daily_key_levels": (
            "primitives.ict_order_block.detect_ict_order_blocks"
            "->primitives.ict_order_block.to_key_levels"
        ),
    }
    _gran = {"htf_key_levels": "H4", "daily_series": "D1", "daily_key_levels": "D1"}
    instruments = ("EURUSDm", "GBPUSDm", "DXYm")
    args = ("htf_key_levels", "daily_series", "daily_key_levels")
    defaults = dict(
        experiment_id="test-field-001",
        protocol_artifact_path="detector/research/protocol.json",
        protocol_artifact_sha256="abc123",
        direction_policy_implementation_commit="aaa",
        evaluation_seam_spec_commit="bbb",
        evaluation_seam_implementation_commit="ccc",
        evaluation_seam_closeout_commit="ddd",
        statistical_spec_v3_commit="eee",
        layer1_implementation_commit="fff",
        policy_ids=FROZEN_POLICY_IDS,
        dataset_identity="3x15M",
        dataset_file_hashes=(("f.csv", "hashval"),),
        population_definition_ref="pop.py",
        candidate_identity_fields=("instrument", "timeframe", "signal_id", "retest_index"),
        trade_join_key_fields=("instrument", "signal_id"),
        outcome_fields=("realized_r", "closed_outcome"),
        est_b_definition="mean(ALIGNED) - mean(OPPOSED)",
        mei_r=0.20,
        cluster_definition_ref="cluster.py",
        bootstrap_config=(("replicates", 10000), ("seed", (20260910,))),
        nomination_rule_ref="nom.py",
        cost_assumptions=(("trading_cost_price", 0.0),),
        protected_paths=PROTECTED_PATHS,
        protected_paths_version="v1",
        layer2_implementation_commit="l2" + "0" * 38,
        layer3_implementation_commit="l3" + "0" * 38,
        measurement_execution_baseline_commit="b" * 40,
        instrument_order=instruments,
        dataset_records=tuple(
            DatasetFileRecord(
                inst, gran, f"data/{inst}_{gran}.csv", 100, f"h_{inst}_{gran}",
                datetime(2025, 1, 1), datetime(2026, 1, 1),
            )
            for inst in instruments for gran in ("M15", "H4", "D1")
        ),
        candidate_cutoff_end_utc=datetime(2026, 6, 1),
        outcome_followup_end_utc=datetime(2026, 9, 1),
        spec_sha256="sphash",
        statistical_spec_commit_chain=("dc8af7d", "6b48374", "86c9150"),
        detector_config_fingerprint="fp",
        uv_lock_sha256="uvhash",
        causal_spec_commit="1f412e3",
        causal_spec_amendment_commit="8f1906e",
        causal_implementation_commit="2419381",
        causal_source_inputs=tuple(
            CausalSourceInputRecord(
                instrument=inst, argument_name=arg,
                producer_id=_prod[arg],
                dataset_relative_path=f"data/{inst}_{_gran[arg]}.csv",
            )
            for inst in instruments for arg in args
        ),
    )
    defaults.update(overrides)
    return Manifest(**defaults)


def _run_preflight(manifest_obj, repo_root, authorization_commit, *,
                   mock_git_ancestry=True, mock_serial=True):
    """Run run_preflight with heavy IO/validation stages mocked.

    mock_git_ancestry=True  — mocks verify_commit_exists/verify_is_ancestor; routes
                               verify_no_diff/worktree/staged/untracked for the
                               authorization artifact only through real git ops.
    mock_git_ancestry=False — keeps verify_commit_exists/verify_is_ancestor real;
                               all diff/clean checks are mocked (irrelevant for
                               ancestry-failure tests).
    mock_serial=True        — mocks canonical_json/to_json_value (returns sentinel);
                               committed artifact must equal _SENTINEL_BYTES to pass.
    mock_serial=False       — real serialization; use with real Manifest objects to
                               test field-level byte mismatches.
    """
    import runner.git_ops as _g
    from runner.preflight import run_preflight

    proto_path = getattr(manifest_obj, "protocol_artifact_path", "protocol.json")
    proto_sha = getattr(manifest_obj, "protocol_artifact_sha256", "abc123")
    _M = [CANONICAL_MANIFEST_ARTIFACT_PATH]

    with contextlib.ExitStack() as stack:
        enter = stack.enter_context
        enter(patch("runner.preflight.manifest_sha256", return_value="fake-digest"))
        enter(patch("runner.preflight.environment_record", return_value={}))
        enter(patch("runner.preflight._validate_schema"))
        enter(patch("runner.preflight._validate_causal_source_inputs"))
        enter(patch("runner.preflight._load_canonical_protocol", return_value={}))
        enter(patch("runner.preflight.validate_protocol_hash"))
        enter(patch("runner.preflight._validate_cross_consistency", return_value=None))
        enter(patch("runner.preflight._validate_frozen_lineage"))
        enter(patch("runner.preflight.verify_environment", return_value={}))
        enter(patch("runner.preflight._validate_datasets"))
        enter(patch("runner.preflight.get_head_commit", return_value="h" * 40))
        enter(patch("runner.preflight.CANONICAL_PROTOCOL_RELATIVE_PATH", proto_path))
        enter(patch("runner.preflight.CANONICAL_PROTOCOL_SHA256", proto_sha))
        if mock_serial:
            enter(patch("runner.preflight.canonical_json", return_value=_SENTINEL_BYTES))
            enter(patch("runner.preflight.to_json_value", return_value={}))
        if mock_git_ancestry:
            enter(patch("runner.preflight.verify_no_diff",
                        side_effect=lambda c, p, cwd: _g.verify_no_diff(c, p, cwd) if p == _M else None))
            enter(patch("runner.preflight.verify_no_working_tree_diff",
                        side_effect=lambda c, p, cwd: _g.verify_no_working_tree_diff(c, p, cwd) if p == _M else None))
            enter(patch("runner.preflight.verify_no_staged_diff",
                        side_effect=lambda c, p, cwd: _g.verify_no_staged_diff(c, p, cwd) if p == _M else None))
            enter(patch("runner.preflight.verify_no_untracked",
                        side_effect=lambda p, cwd: _g.verify_no_untracked(p, cwd) if p == _M else None))
            enter(patch("runner.preflight.verify_commit_exists"))
            enter(patch("runner.preflight.verify_is_ancestor"))
        else:
            enter(patch("runner.preflight.verify_no_diff"))
            enter(patch("runner.preflight.verify_no_working_tree_diff"))
            enter(patch("runner.preflight.verify_no_staged_diff"))
            enter(patch("runner.preflight.verify_no_untracked"))
        return run_preflight(
            manifest_obj, "protocol.json", repo_root, authorization_commit=authorization_commit
        )


def test_read_committed_blob_returns_exact_bytes(tmp_path):
    expected = canonical_json({"experiment_id": "t", "path": "p.json", "sha256": "abc"})
    repo = _init_repo(tmp_path)
    _make_commit(repo, {"placeholder.txt": b"init"}, "B")
    a_sha = _make_commit(repo, {CANONICAL_MANIFEST_ARTIFACT_PATH: expected}, "A")
    assert read_committed_blob(a_sha, CANONICAL_MANIFEST_ARTIFACT_PATH, str(repo)) == expected


def test_read_committed_blob_missing_path_raises(tmp_path):
    repo = _init_repo(tmp_path)
    sha = _make_commit(repo, {"other.txt": b"content"}, "init")
    with pytest.raises(AuthorizationError, match="cannot read"):
        read_committed_blob(sha, CANONICAL_MANIFEST_ARTIFACT_PATH, str(repo))


def test_read_committed_blob_invalid_commit_raises(tmp_path):
    repo = _init_repo(tmp_path)
    _make_commit(repo, {"x.txt": b"y"}, "init")
    with pytest.raises(AuthorizationError, match="cannot read"):
        read_committed_blob("0" * 40, CANONICAL_MANIFEST_ARTIFACT_PATH, str(repo))


def test_read_committed_blob_respects_allowlist(tmp_path):
    # Removing 'show' from _ALLOWED_SUBCOMMANDS must reject the call, proving that
    # read_committed_blob routes through _check_subcommand rather than bypassing it.
    import runner.git_ops as git_ops
    repo = _init_repo(tmp_path)
    sha = _make_commit(repo, {"file.txt": b"content"}, "init")
    restricted = git_ops._ALLOWED_SUBCOMMANDS - {"show"}
    with patch.object(git_ops, "_ALLOWED_SUBCOMMANDS", restricted):
        with pytest.raises(AuthorizationError):
            git_ops.read_committed_blob(sha, "file.txt", str(repo))


def test_exact_bytes_pass(tmp_path):
    repo = _init_repo(tmp_path)
    l2 = _make_commit(repo, {"l2.txt": b"l2"}, "l2")
    l3 = _make_commit(repo, {"l3.txt": b"l3"}, "l3")
    b = _make_commit(repo, {"baseline.txt": b"B"}, "B")
    manifest_obj = _FakeManifest(
        measurement_execution_baseline_commit=b,
        layer2_implementation_commit=l2,
        layer3_implementation_commit=l3,
    )
    a = _make_commit(repo, {CANONICAL_MANIFEST_ARTIFACT_PATH: _SENTINEL_BYTES}, "A")
    result = _run_preflight(manifest_obj, str(repo), a)
    assert result.authorization_commit == a
    assert "authorization_manifest_binding" in result.checks_passed


def test_one_field_differs_fails(tmp_path):
    from runner.serialization import canonical_json as _cj, to_json_value
    repo = _init_repo(tmp_path)
    l2 = _make_commit(repo, {"l2.txt": b"l2"}, "l2")
    l3 = _make_commit(repo, {"l3.txt": b"l3"}, "l3")
    b = _make_commit(repo, {"baseline.txt": b"B"}, "B")
    manifest = _build_minimal_manifest(
        measurement_execution_baseline_commit=b,
        layer2_implementation_commit=l2,
        layer3_implementation_commit=l3,
    )
    a = _make_commit(repo, {CANONICAL_MANIFEST_ARTIFACT_PATH: _cj(to_json_value(manifest))}, "A")
    modified = dataclasses.replace(manifest, experiment_id="test-field-CHANGED")
    with pytest.raises((PreflightFailure, AuthorizationError)):
        _run_preflight(modified, str(repo), a, mock_serial=False)


def test_nonexistent_authorization_commit_fails(tmp_path):
    repo = _init_repo(tmp_path)
    b = _make_commit(repo, {"x.txt": b"x"}, "init")
    with pytest.raises((PreflightFailure, AuthorizationError)):
        _run_preflight(
            _FakeManifest(measurement_execution_baseline_commit=b),
            str(repo), "d" * 40, mock_git_ancestry=False,
        )


def test_a_not_descendant_of_b_fails(tmp_path):
    repo = _init_repo(tmp_path)
    a_sha = _make_commit(repo, {"a.txt": b"a"}, "A")
    # B lives on an orphan branch, so B→A ancestry cannot hold.
    subprocess.run(["git", "checkout", "--orphan", "orphan"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "rm", "-rf", "."], cwd=repo, capture_output=True)
    b_sha = _make_commit(repo, {"b.txt": b"b"}, "B")
    subprocess.run(["git", "checkout", "main"], cwd=repo, check=True, capture_output=True)
    with pytest.raises((PreflightFailure, AuthorizationError)):
        _run_preflight(
            _FakeManifest(measurement_execution_baseline_commit=b_sha),
            str(repo), a_sha, mock_git_ancestry=False,
        )


def test_a_not_ancestor_of_head_fails(tmp_path):
    repo = _init_repo(tmp_path)
    b = _make_commit(repo, {"x.txt": b"x"}, "B")
    subprocess.run(["git", "checkout", "-b", "side"], cwd=repo, check=True, capture_output=True)
    a = _make_commit(repo, {CANONICAL_MANIFEST_ARTIFACT_PATH: _SENTINEL_BYTES}, "A")
    # HEAD returns to main, which diverged before A and is not a descendant of it.
    subprocess.run(["git", "checkout", "main"], cwd=repo, check=True, capture_output=True)
    with pytest.raises((PreflightFailure, AuthorizationError)):
        _run_preflight(
            _FakeManifest(measurement_execution_baseline_commit=b),
            str(repo), a, mock_git_ancestry=False,
        )


def test_missing_blob_in_a_fails(tmp_path):
    repo = _init_repo(tmp_path)
    b = _make_commit(repo, {"placeholder.txt": b"B"}, "B")
    a = _make_commit(repo, {"unrelated.txt": b"no manifest here"}, "A")
    with pytest.raises((PreflightFailure, AuthorizationError)):
        _run_preflight(_FakeManifest(measurement_execution_baseline_commit=b), str(repo), a)


def test_committed_rewrite_after_a_fails(tmp_path):
    repo = _init_repo(tmp_path)
    b = _make_commit(repo, {"placeholder.txt": b"B"}, "B")
    a = _make_commit(repo, {CANONICAL_MANIFEST_ARTIFACT_PATH: _SENTINEL_BYTES}, "A")
    _make_commit(repo, {CANONICAL_MANIFEST_ARTIFACT_PATH: b'{"rewritten":true}\n'}, "rewrite")
    with pytest.raises((PreflightFailure, AuthorizationError)):
        _run_preflight(_FakeManifest(measurement_execution_baseline_commit=b), str(repo), a)


def test_unstaged_edit_fails(tmp_path):
    repo = _init_repo(tmp_path)
    b = _make_commit(repo, {"placeholder.txt": b"B"}, "B")
    a = _make_commit(repo, {CANONICAL_MANIFEST_ARTIFACT_PATH: _SENTINEL_BYTES}, "A")
    (repo / CANONICAL_MANIFEST_ARTIFACT_PATH).write_bytes(b'{"unstaged":true}\n')
    with pytest.raises((PreflightFailure, AuthorizationError)):
        _run_preflight(_FakeManifest(measurement_execution_baseline_commit=b), str(repo), a)


def test_staged_edit_fails(tmp_path):
    repo = _init_repo(tmp_path)
    b = _make_commit(repo, {"placeholder.txt": b"B"}, "B")
    a = _make_commit(repo, {CANONICAL_MANIFEST_ARTIFACT_PATH: _SENTINEL_BYTES}, "A")
    (repo / CANONICAL_MANIFEST_ARTIFACT_PATH).write_bytes(b'{"staged":true}\n')
    subprocess.run(["git", "add", CANONICAL_MANIFEST_ARTIFACT_PATH], cwd=repo, check=True, capture_output=True)
    with pytest.raises((PreflightFailure, AuthorizationError)):
        _run_preflight(_FakeManifest(measurement_execution_baseline_commit=b), str(repo), a)


def test_untracked_replacement_after_deletion_fails(tmp_path):
    repo = _init_repo(tmp_path)
    b = _make_commit(repo, {"placeholder.txt": b"B"}, "B")
    a = _make_commit(repo, {CANONICAL_MANIFEST_ARTIFACT_PATH: _SENTINEL_BYTES}, "A")
    subprocess.run(["git", "rm", CANONICAL_MANIFEST_ARTIFACT_PATH], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "delete manifest"], cwd=repo, check=True, capture_output=True)
    (repo / CANONICAL_MANIFEST_ARTIFACT_PATH).write_bytes(b'{"untracked":true}\n')
    with pytest.raises((PreflightFailure, AuthorizationError)):
        _run_preflight(_FakeManifest(measurement_execution_baseline_commit=b), str(repo), a)


def test_run_discovery_aborts_before_instruments_on_binding_failure(tmp_path):
    from runner.run_discovery import run_discovery
    mock_process = MagicMock(name="process_instrument")
    binding_failure = PreflightFailure(
        "authorization_manifest_binding", AuthorizationError("bad_a"), (), "d", {}
    )
    with (
        patch("runner.run_discovery.run_preflight", side_effect=binding_failure),
        patch("runner.run_discovery.process_instrument", mock_process),
    ):
        with pytest.raises((AuthorizationError, PreflightFailure)):
            run_discovery(
                _FakeManifest(), None, "protocol.json", ".", str(tmp_path / "output"),
                authorization_commit="e" * 40,
            )
    mock_process.assert_not_called()


def test_preflight_result_authorization_commit_has_no_default():
    from runner.preflight import PreflightResult
    fields = {f.name: f for f in dataclasses.fields(PreflightResult)}
    auth_field = fields["authorization_commit"]
    assert auth_field.default is dataclasses.MISSING
    assert auth_field.default_factory is dataclasses.MISSING


def test_canonical_path_not_in_protected_paths():
    for p in PROTECTED_PATHS:
        assert not (
            CANONICAL_MANIFEST_ARTIFACT_PATH == p
            or CANONICAL_MANIFEST_ARTIFACT_PATH.startswith(p)
        ), f"{CANONICAL_MANIFEST_ARTIFACT_PATH!r} is covered by protected path {p!r}"
