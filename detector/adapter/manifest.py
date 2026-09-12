"""REQ-STAT-19/32/31: the Layer-2 manifest schema, protocol-artifact hash
validation, and execution-baseline OWNERSHIP — this module records the
schema and the pre-baseline dev-validation boundary; it does NOT fabricate
a baseline hash, and real-execution authorization stays impossible until
Layer-3 exists and a `measurement_execution_baseline_commit` is recorded
after its own closeout + full measurement-instrument verification."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from adapter.dataset import sha256_of_file
from adapter.errors import FrozenArtifactMismatchError
from evaluation.direction import FROZEN_POLICY_IDS

MEI_R = 0.20


@dataclass(frozen=True)
class GapAllowlistEntry:
    """REQ-STAT-34/32 (V4): one pre-frozen, manifest-declared dataset
    boundary gap (Section M #6/#12) — declared before any real outcome
    execution, never chosen or adjusted based on `Trade` outcome or any
    downstream statistic. `gap_start` is the timestamp of the candle
    immediately before the gap, matching `validate_no_gaps`'s own
    `allowed_gap_starts` convention."""

    instrument: str
    granularity: str
    gap_start: datetime
    gap_end: datetime
    reason: str


@dataclass(frozen=True)
class Manifest:
    """REQ-STAT-19 (+ REQ-STAT-32 V3/V4 extensions). `candidate_identity_fields`
    and `trade_join_key_fields` are named distinctly, never merged into one
    field (Section A) — `__post_init__` enforces they can never collide.
    `dataset_gap_allowlist` (V4, REQ-STAT-34) is the immutable, frozen
    production authority for acceptable dataset boundary gaps — a runtime
    caller cannot add to it after this dataclass is constructed (frozen) nor
    through any parameter of `adapter.dataset.validate_no_gaps_against_manifest`."""

    experiment_id: str
    protocol_artifact_path: str
    protocol_artifact_sha256: str
    direction_policy_implementation_commit: str
    evaluation_seam_spec_commit: str
    evaluation_seam_implementation_commit: str
    evaluation_seam_closeout_commit: str
    statistical_spec_v3_commit: str
    layer1_implementation_commit: str
    policy_ids: tuple[str, ...]
    dataset_identity: str
    dataset_file_hashes: tuple[tuple[str, str], ...]
    population_definition_ref: str
    candidate_identity_fields: tuple[str, ...]
    trade_join_key_fields: tuple[str, ...]
    outcome_fields: tuple[str, ...]
    est_b_definition: str
    mei_r: float
    cluster_definition_ref: str
    bootstrap_config: tuple[tuple[str, object], ...]
    nomination_rule_ref: str
    cost_assumptions: tuple[tuple[str, object], ...]
    protected_paths: tuple[str, ...]
    protected_paths_version: str
    layer2_implementation_commit: str | None = None
    layer3_implementation_commit: str | None = None
    measurement_execution_baseline_commit: str | None = None
    dataset_gap_allowlist: tuple[GapAllowlistEntry, ...] = ()

    def __post_init__(self) -> None:
        if set(self.policy_ids) != set(FROZEN_POLICY_IDS):
            raise FrozenArtifactMismatchError(
                f"manifest.policy_ids must be exactly the 4 frozen policy IDs, got {self.policy_ids}"
            )
        if self.candidate_identity_fields == self.trade_join_key_fields:
            raise FrozenArtifactMismatchError(
                "candidate_identity_fields and trade_join_key_fields must be named distinctly — "
                "never merged into one field (spec.md Section A / REQ-STAT-19)"
            )
        if self.mei_r != MEI_R:
            raise FrozenArtifactMismatchError(f"manifest.mei_r must be the frozen {MEI_R}, got {self.mei_r!r}")
        if self.measurement_execution_baseline_commit is not None and (
            self.layer2_implementation_commit is None or self.layer3_implementation_commit is None
        ):
            raise FrozenArtifactMismatchError(
                "measurement_execution_baseline_commit requires layer2_implementation_commit AND "
                "layer3_implementation_commit to already be recorded (REQ-STAT-31: the baseline commit "
                "is created AFTER Layer-2 and Layer-3 implementation, closeout, and full verification)"
            )


def validate_protocol_hash(manifest: Manifest, protocol_path: str) -> None:
    """REQ-STAT-19: the manifest's declared protocol SHA-256 MUST match the
    actual protocol artifact on disk."""
    actual = sha256_of_file(protocol_path)
    if actual != manifest.protocol_artifact_sha256:
        raise FrozenArtifactMismatchError(
            f"protocol artifact hash drift: {protocol_path} has sha256={actual}, "
            f"manifest declares {manifest.protocol_artifact_sha256}"
        )


def is_execution_authorized(manifest: Manifest) -> bool:
    """REQ-STAT-31: real-data execution is authorized ONLY once a
    `measurement_execution_baseline_commit` is recorded — which itself
    requires Layer-2 AND Layer-3 implementation commits to already exist
    (enforced in `__post_init__`). This module never sets that field itself;
    it only reports whether the manifest handed to it already carries one.
    At the current (Layer-2-only, pre-Layer-3) state of this repo, this is
    always `False` for any manifest this codebase could honestly construct."""
    return manifest.measurement_execution_baseline_commit is not None


def verify_protected_paths_clean(
    protected_paths: Sequence[str], changed_paths: Sequence[str], baseline_commit: str
) -> None:
    """REQ-STAT-31/Section N: given the set of paths with uncommitted
    modifications (as the caller determines — real `git status` invocation
    is Layer-3's runner concern, out of this spec's scope, Section I), raise
    if any changed path falls under a protected path. Unrelated working-tree
    changes outside protected paths need not abort (Section N)."""
    for changed in changed_paths:
        if any(changed == p or changed.startswith(p.rstrip("/") + "/") for p in protected_paths):
            raise FrozenArtifactMismatchError(
                f"protected path {changed!r} has an uncommitted modification relative to "
                f"execution-baseline commit {baseline_commit!r}"
            )
