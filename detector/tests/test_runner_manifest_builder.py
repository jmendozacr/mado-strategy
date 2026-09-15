import json
from pathlib import Path

import pytest

from runner.errors import AuthorizationError
from runner.manifest_builder import PROTECTED_PATHS, build_manifest, validate_protected_paths


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DETECTOR_ROOT = PROJECT_ROOT / "detector"
PROTOCOL_PATH = DETECTOR_ROOT / "research" / "direction_policy_discovery_v1_amendment_1.json"


def test_build_manifest_requires_recorded_baseline():
    with pytest.raises(AuthorizationError, match="baseline_commit"):
        build_manifest(str(PROTOCOL_PATH), str(DETECTOR_ROOT), "", "layer2", "layer3")


def test_builder_rejects_rewritten_protocol_before_authorization(tmp_path):
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    protocol["population"]["config"]["model1"]["max_retest_lookback"] = 21
    drifted = tmp_path / "protocol.json"
    drifted.write_text(json.dumps(protocol), encoding="utf-8")

    with pytest.raises(AuthorizationError, match="protocol path must be canonical"):
        build_manifest(str(drifted), str(DETECTOR_ROOT), "b" * 40, "layer2", "layer3")


def test_protected_paths_require_exact_minimum_and_exclusions():
    validate_protected_paths(PROTECTED_PATHS)
    with pytest.raises(AuthorizationError, match="missing"):
        validate_protected_paths(PROTECTED_PATHS[:-1])
    with pytest.raises(AuthorizationError, match="excluded"):
        validate_protected_paths(PROTECTED_PATHS + ("detector/viz/",))


@pytest.mark.parametrize(
    "path",
    (
        ".",
        "detector/",
        "docs/runner.md",
        "openspec/",
        "openspec/changes/unrelated/spec.md",
        "tests/",
        "artifacts/run.json",
        "detector/results/run.json",
        "detector/output/run.json",
        "detector/cache/entry.json",
        "detector\\cache\\entry.json",
        "detector/research/other.py",
    ),
)
def test_protected_paths_reject_overinclusive_and_excluded_directories(path):
    with pytest.raises(AuthorizationError, match="excluded"):
        validate_protected_paths(PROTECTED_PATHS + (path,))
