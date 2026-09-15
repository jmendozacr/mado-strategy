"""Discovery authorization, execution, and atomic publication."""

import itertools
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from adapter.manifest import Manifest
from core.config import DetectorConfig
from evaluation.direction import FROZEN_POLICY_IDS
from runner.artifacts import (
    build_bootstrap_summary,
    build_nomination_trace,
    build_policy_summary,
    build_run_manifest,
)
from runner.candidate_fingerprint import compute_observation_table_fingerprint
from runner.environment import environment_record
from runner.errors import AuthorizationError, PreflightFailure, ReproducibilityError
from runner.instrument_pipeline import InstrumentResult, process_instrument
from runner.manifest_builder import _project_root
from runner.preflight import PreflightResult, run_preflight
from runner.progress import ProgressEvent
from runner.publication import PublicationInputs, publish, write_failure_artifact
from runner.serialization import manifest_sha256
from runner.statistics_bridge import compute_all_statistics
from selection.model import DirectionPolicyObservation


_N_POLICIES = len(FROZEN_POLICY_IDS)


@dataclass(frozen=True)
class AuthorizationReceipt:
    baseline_commit: str
    head_commit: str
    manifest_sha256: str
    protocol_sha256: str
    checks_passed: tuple[str, ...]
    instrument_results: tuple[InstrumentResult, ...]


def run_discovery(
    manifest: Manifest,
    config: DetectorConfig,
    protocol_path: str,
    repo_root: str,
    output_dir: str,
    on_progress: Callable[[ProgressEvent, dict], None] | None = None,
) -> str:
    run_started_utc = datetime.now(timezone.utc).isoformat()
    preflight: PreflightResult | None = None
    project_root = _project_root(repo_root)
    detector_root = project_root / "detector"
    failing_check = "reproducibility"

    def emit(event: ProgressEvent, **payload: str) -> None:
        if on_progress is not None:
            on_progress(event, payload)

    try:
        final_path = os.path.join(output_dir, manifest.experiment_id)
        if os.path.exists(final_path):
            raise ReproducibilityError(f"output directory already exists: {final_path}")

        failing_check = "preflight"
        preflight = run_preflight(manifest, protocol_path, str(project_root))
        failing_check = "runtime_config"
        if config != preflight.reconstructed_config:
            raise AuthorizationError("runtime DetectorConfig differs from authorized population.config")
        emit(ProgressEvent.PREFLIGHT_PASSED)

        failing_check = "instrument_processing"
        instrument_results = []
        for instrument in manifest.instrument_order or ():
            result = process_instrument(
                instrument,
                manifest,
                config,
                str(detector_root),
                on_dataset_validated=lambda validated: emit(
                    ProgressEvent.INSTRUMENT_DATASET_VALIDATED, instrument=validated
                ),
            )
            instrument_results.append(result)
            emit(ProgressEvent.INSTRUMENT_BUNDLE_VALIDATED, instrument=instrument)

        failing_check = "instrument_bundle_validation"
        all_observations: list[DirectionPolicyObservation] = list(
            itertools.chain.from_iterable(result.observations for result in instrument_results)
        )
        total_candidates = sum(result.candidate_count for result in instrument_results)
        expected_observations = total_candidates * _N_POLICIES
        if len(all_observations) != expected_observations:
            raise AuthorizationError(
                f"4N cardinality check failed: expected {expected_observations}, "
                f"got {len(all_observations)}"
            )

        receipt = AuthorizationReceipt(
            baseline_commit=preflight.baseline_commit,
            head_commit=preflight.head_commit,
            manifest_sha256=preflight.manifest_sha256,
            protocol_sha256=preflight.protocol_sha256,
            checks_passed=preflight.checks_passed + ("instrument_bundle_validation",),
            instrument_results=tuple(instrument_results),
        )
        emit(ProgressEvent.ALL_INSTRUMENTS_VALIDATED)

        failing_check = "statistics_computation"
        stats = compute_all_statistics(all_observations, manifest.instrument_order or ())
        emit(ProgressEvent.STATISTICS_COMPLETE)
        failing_check = "artifact_construction"
        observation_fingerprint = compute_observation_table_fingerprint(all_observations)
        run_finished_utc = datetime.now(timezone.utc).isoformat()
        inputs = PublicationInputs(
            experiment_id=manifest.experiment_id,
            manifest_dict=build_run_manifest(
                manifest, receipt, run_started_utc, run_finished_utc, observation_fingerprint
            ),
            policy_summary_dict=build_policy_summary(stats),
            bootstrap_summary_dict=build_bootstrap_summary(stats),
            nomination_trace_dict=build_nomination_trace(stats),
            run_started_utc=run_started_utc,
            run_finished_utc=run_finished_utc,
        )
        failing_check = "publication"
        result_path = publish(inputs, output_dir)
        emit(ProgressEvent.PUBLISHED, path=result_path)
        return result_path
    except Exception as exc:
        try:
            _write_failure(
                manifest,
                project_root,
                output_dir,
                run_started_utc,
                exc,
                preflight,
                failing_check,
            )
        except Exception:
            pass
        raise


def _write_failure(
    manifest: Manifest,
    project_root: Path,
    output_dir: str,
    run_started_utc: str,
    exc: Exception,
    preflight: PreflightResult | None,
    failing_check: str,
) -> None:
    if isinstance(exc, PreflightFailure):
        failing_check = exc.failing_check
        completed_checks = list(exc.completed_checks)
        digest = exc.manifest_sha256
        env = exc.environment_record
    else:
        completed_checks = list(preflight.checks_passed) if preflight else []
        digest = preflight.manifest_sha256 if preflight else manifest_sha256(manifest)
        if preflight and preflight.environment_record:
            env = preflight.environment_record
        else:
            env = environment_record(str(project_root / "detector" / "uv.lock"))

    write_failure_artifact(
        experiment_id=manifest.experiment_id,
        output_dir=output_dir,
        status="FAILED_VALIDATION" if isinstance(exc, AuthorizationError) else "FAILED_SOFTWARE",
        failing_check=failing_check,
        error_class=type(exc).__name__,
        error_message=str(exc),
        manifest_sha256=digest,
        run_started_utc=run_started_utc,
        environment_record=env,
        completed_checks=completed_checks,
    )
