"""Construct the frozen authorization manifest from recorded sources."""

import json
import re
from datetime import datetime
from pathlib import Path, PurePosixPath

from adapter.dataset import sha256_of_file
from adapter.manifest import CausalSourceInputRecord, DatasetFileRecord, Manifest
from core.config import DetectorConfig
from runner.config_fingerprint import reconstruct_and_fingerprint
from runner.errors import AuthorizationError


INSTRUMENT_ORDER = ("EURUSDm", "GBPUSDm", "DXYm")
FROZEN_SEED_ENTROPY = (20_260_910,)
CANONICAL_DATASET_RECORD_FIELD_COUNT = 7
CANONICAL_PROTOCOL_BYTE_SIZE = 7_737
CANONICAL_PROTOCOL_RELATIVE_PATH = (
    "detector/research/direction_policy_discovery_v1_amendment_1.json"
)
CANONICAL_PROTOCOL_SHA256 = "47b17d7891f6f9a2d2d30f83df88b060840a895484a78e763c8f46da1ea8de4d"
STATISTICAL_SPEC_PATH = "openspec/changes/crt-detector-direction-policy-statistical-runner/spec.md"
CANONICAL_STATISTICAL_SPEC_SHA256 = (
    "5e76d21d0f33112af52faf47e09168656ec5f3254469ee1a6763a9408d0b2ece"
)
STATISTICAL_SPEC_COMMIT_CHAIN = (
    "dc8af7daa6f8ff9f51abf2b94e7604f28ec53658",
    "6b48374ec9fa513897d050b7114a9f313f3d1b65",
    "86c91506132292d5c9076462118cb5d32efe5807",
    "8195ea913c2ed3f61c3d65f2552d9e94a05a7aa8",
    "edd6eef7e5a19d83570d76346c017e52cb828a91",
    "1915829da8511fc0095face1621922d95fb4879b",
)
DIRECTION_POLICY_IMPLEMENTATION_COMMIT = "7b09c31877a5e5978e10b6832f5b7f3010276f1d"
EVALUATION_SEAM_SPEC_COMMIT = "6104343488cc0dd6df7b4d311dc2cdf6893f2ccb"
EVALUATION_SEAM_IMPLEMENTATION_COMMIT = "26d94be6eed49d1883f1454d2ceea0bc0e80b4ac"
EVALUATION_SEAM_CLOSEOUT_COMMIT = "7775a25c011254555c74021e83a4dad044700d83"
LAYER1_IMPLEMENTATION_COMMIT = "75d9c37ac08a314a6518484b7e62ee3c7eb798c1"
LAYER2_IMPLEMENTATION_COMMIT = "1dd0acc"
CAUSAL_SPEC_COMMIT = "1f412e3675909a4da0046a1e72c45f6164acd232"
CAUSAL_SPEC_AMENDMENT_COMMIT = "8f1906e"
CAUSAL_IMPLEMENTATION_COMMIT = "2419381"
PROTECTED_PATHS = (
    "detector/ingestion/loader.py", "detector/ingestion/pairing.py",
    "detector/core/pairing_table.py", "detector/core/candle.py",
    "detector/primitives/crt_range.py", "detector/primitives/fvg.py",
    "detector/primitives/swing.py", "detector/primitives/ict_order_block.py",
    "detector/core/atr.py", "detector/core/key_level.py", "detector/core/sweep.py",
    "detector/core/results.py", "detector/core/config.py", "detector/entries/model1.py",
    "detector/causal/", "detector/alignment/htf_ltf.py", "detector/primitives/bias.py",
    "detector/composite/order_flow.py", "detector/backtest/candidate.py",
    "detector/backtest/population.py", "detector/backtest/simulate.py",
    "detector/backtest/levels.py", "detector/core/kill_zone.py",
    "detector/policy/direction.py", "detector/evaluation/direction.py",
    "detector/selection/", "detector/adapter/", "detector/runner/",
    CANONICAL_PROTOCOL_RELATIVE_PATH,
    STATISTICAL_SPEC_PATH,
    "openspec/changes/crt-detector-causal-candidate-generation/spec.md",
    "detector/uv.lock", "detector/pyproject.toml", "detector/.importlinter",
    "detector/tests/",
)
_EXCLUDED_PROTECTED_PATHS = (
    "detector/viz/", "detector/cli.py", "detector/composite/mss.py",
    "detector/primitives/liquidity.py", "detector/backtest/metrics.py",
    "detector/research/", "docs/",
)
_EXCLUDED_PROTECTED_DIRECTORY_NAMES = frozenset(
    ("artifacts", "cache", "docs", "openspec", "output", "results", "tests")
)
_ARGUMENT_SOURCE = {
    "htf_key_levels": ("H4", "primitives.fvg.detect_fvgs->primitives.fvg.to_key_levels"),
    "daily_series": ("D1", "ingestion.loader.load_mt5_csv"),
    "daily_key_levels": (
        "D1",
        "primitives.ict_order_block.detect_ict_order_blocks->primitives.ict_order_block.to_key_levels",
    ),
}


def _project_root(repo_root: str) -> Path:
    root = Path(repo_root).resolve()
    return root.parent if root.name == "detector" and (root / "uv.lock").exists() else root


def _load_canonical_protocol(protocol_path: str, project_root: Path) -> dict:
    path = Path(protocol_path).resolve()
    expected_path = (project_root / CANONICAL_PROTOCOL_RELATIVE_PATH).resolve()
    if path != expected_path:
        raise AuthorizationError(
            f"protocol path must be canonical: {CANONICAL_PROTOCOL_RELATIVE_PATH}"
        )
    payload = path.read_bytes()
    if len(payload) != CANONICAL_PROTOCOL_BYTE_SIZE:
        raise AuthorizationError(
            f"protocol artifact byte length mismatch: expected "
            f"{CANONICAL_PROTOCOL_BYTE_SIZE}, got {len(payload)}"
        )
    digest = sha256_of_file(str(path))
    if digest != CANONICAL_PROTOCOL_SHA256:
        raise AuthorizationError("canonical protocol SHA-256 mismatch")
    return json.loads(payload)


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.removesuffix("Z"))


def validate_protected_paths(paths: tuple[str, ...]) -> None:
    missing = tuple(path for path in PROTECTED_PATHS if path not in paths)
    required = frozenset(_normalize_protected_path(path) for path in PROTECTED_PATHS)
    excluded = tuple(
        path
        for path in paths
        if _is_excluded_protected_path(path, required)
    )
    if missing or excluded:
        raise AuthorizationError(
            f"protected_paths mismatch: missing={missing!r}, excluded={excluded!r}"
        )


def _normalize_protected_path(path: str) -> str:
    return PurePosixPath(path.replace("\\", "/")).as_posix().rstrip("/")


def _is_excluded_protected_path(path: str, required: frozenset[str]) -> bool:
    normalized = _normalize_protected_path(path)
    if normalized in required:
        return False
    if normalized in ("", ".") or PurePosixPath(normalized).is_absolute():
        return True

    parts = PurePosixPath(normalized).parts
    if ".." in parts or any(part in _EXCLUDED_PROTECTED_DIRECTORY_NAMES for part in parts):
        return True

    for excluded_path in _EXCLUDED_PROTECTED_PATHS:
        excluded = _normalize_protected_path(excluded_path)
        if normalized == excluded or (
            excluded_path.endswith("/") and normalized.startswith(f"{excluded}/")
        ):
            return True

    return any(required_path.startswith(f"{normalized}/") for required_path in required)


def _instrument_order(protocol: dict) -> tuple[str, ...]:
    stream_order = protocol["bootstrap"]["prng"]["stream_order"]
    segments = tuple(segment.strip() for segment in stream_order.split(";"))
    if len(segments) != 3 or segments[1] != ",".join(INSTRUMENT_ORDER):
        raise AuthorizationError("bootstrap.prng.stream_order does not declare exact instrument_order")
    return tuple(segments[1].split(","))


def _seed_entropy(protocol: dict) -> tuple[int, ...]:
    seed = protocol["bootstrap"]["prng"]["seed"]
    matches = re.findall(r"SeedSequence entropy sequence \[([0-9, ]+)\]", seed)
    if len(matches) != 1:
        raise AuthorizationError("bootstrap.prng.seed must declare one SeedSequence entropy sequence")
    entropy = tuple(int(value.strip()) for value in matches[0].split(",") if value.strip())
    if entropy != FROZEN_SEED_ENTROPY:
        raise AuthorizationError("bootstrap.prng.seed entropy must be exactly [20260910]")
    return entropy


def _freeze_json(value):
    if isinstance(value, dict):
        return tuple((key, _freeze_json(item)) for key, item in value.items())
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value


def _dataset_records(protocol: dict) -> tuple[DatasetFileRecord, ...]:
    records = []
    for entry in protocol["dataset"]["files"]:
        if not isinstance(entry, list) or len(entry) != CANONICAL_DATASET_RECORD_FIELD_COUNT:
            raise AuthorizationError("dataset.files entries must be 7-element arrays")
        instrument, granularity, relative_path, byte_size, digest, start_utc, end_utc = entry
        records.append(DatasetFileRecord(
            instrument, granularity, relative_path, byte_size, digest,
            _parse_utc(start_utc), _parse_utc(end_utc),
        ))
    return tuple(records)


def _causal_inputs(records: tuple[DatasetFileRecord, ...]) -> tuple[CausalSourceInputRecord, ...]:
    by_key = {(record.instrument, record.granularity): record for record in records}
    inputs = []
    for instrument in INSTRUMENT_ORDER:
        for argument_name, (granularity, producer_id) in _ARGUMENT_SOURCE.items():
            try:
                record = by_key[(instrument, granularity)]
            except KeyError as exc:
                raise AuthorizationError(
                    f"dataset.files lacks {instrument}/{granularity} for {argument_name}"
                ) from exc
            inputs.append(CausalSourceInputRecord(
                instrument=instrument,
                argument_name=argument_name,
                producer_id=producer_id,
                dataset_relative_path=record.relative_path,
            ))
    return tuple(inputs)


def build_manifest(
    protocol_path: str,
    repo_root: str,
    baseline_commit: str,
    layer2_commit: str,
    layer3_commit: str,
) -> Manifest:
    if not baseline_commit:
        raise AuthorizationError("baseline_commit must be provided (already recorded)")
    if not layer2_commit or not layer3_commit:
        raise AuthorizationError("layer2_commit and layer3_commit must be provided")

    project_root = _project_root(repo_root)
    protocol = _load_canonical_protocol(protocol_path, project_root)
    records = _dataset_records(protocol)
    instrument_order = _instrument_order(protocol)
    _seed_entropy(protocol)
    config, config_fingerprint = reconstruct_and_fingerprint(protocol["population"]["config"])
    if config != DetectorConfig():
        raise AuthorizationError("population.config does not equal frozen DetectorConfig defaults")

    detector_root = project_root / "detector"
    spec_path = project_root / STATISTICAL_SPEC_PATH
    uv_lock_path = detector_root / "uv.lock"
    if not spec_path.is_file() or not uv_lock_path.is_file():
        raise AuthorizationError("frozen spec or detector/uv.lock is missing")

    validate_protected_paths(PROTECTED_PATHS)
    dataset = protocol["dataset"]
    population = protocol["population"]
    selection = protocol["selection"]

    return Manifest(
        experiment_id=protocol["artifact"]["artifact_id"],
        protocol_artifact_path=CANONICAL_PROTOCOL_RELATIVE_PATH,
        protocol_artifact_sha256=CANONICAL_PROTOCOL_SHA256,
        direction_policy_implementation_commit=DIRECTION_POLICY_IMPLEMENTATION_COMMIT,
        evaluation_seam_spec_commit=EVALUATION_SEAM_SPEC_COMMIT,
        evaluation_seam_implementation_commit=EVALUATION_SEAM_IMPLEMENTATION_COMMIT,
        evaluation_seam_closeout_commit=EVALUATION_SEAM_CLOSEOUT_COMMIT,
        statistical_spec_v3_commit=STATISTICAL_SPEC_COMMIT_CHAIN[2],
        layer1_implementation_commit=LAYER1_IMPLEMENTATION_COMMIT,
        policy_ids=tuple(protocol["policy_ids"]),
        dataset_identity=dataset["identity"],
        dataset_file_hashes=tuple((record.relative_path, record.sha256) for record in records),
        population_definition_ref=population["id"],
        candidate_identity_fields=tuple(population["key"]),
        trade_join_key_fields=("instrument", "signal_id"),
        outcome_fields=("realized_r", "closed_outcome"),
        est_b_definition=selection["primary_estimand"],
        mei_r=selection["mei_r"],
        cluster_definition_ref="selection.cluster_key",
        bootstrap_config=_freeze_json(protocol["bootstrap"]),
        nomination_rule_ref=selection["rule"],
        cost_assumptions=(("trading_cost_price", population["config"]["backtest"]["trading_cost_price"]),),
        protected_paths=PROTECTED_PATHS,
        protected_paths_version="REQ-STAT-45-v6",
        layer2_implementation_commit=layer2_commit,
        layer3_implementation_commit=layer3_commit,
        measurement_execution_baseline_commit=baseline_commit,
        dataset_gap_allowlist=(),
        instrument_order=instrument_order,
        dataset_records=records,
        candidate_cutoff_end_utc=_parse_utc(dataset["candidate_cutoff_end_utc"]),
        outcome_followup_end_utc=_parse_utc(dataset["outcome_followup_end_utc"]),
        spec_sha256=sha256_of_file(str(spec_path)),
        statistical_spec_commit_chain=STATISTICAL_SPEC_COMMIT_CHAIN,
        detector_config_fingerprint=config_fingerprint,
        uv_lock_sha256=protocol["bootstrap"]["prng"]["lock_sha256"],
        causal_spec_commit=CAUSAL_SPEC_COMMIT,
        causal_spec_amendment_commit=CAUSAL_SPEC_AMENDMENT_COMMIT,
        causal_implementation_commit=CAUSAL_IMPLEMENTATION_COMMIT,
        causal_source_inputs=_causal_inputs(records),
    )
