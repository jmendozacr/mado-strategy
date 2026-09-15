"""Tests for discovery orchestration and failure boundaries."""

import json
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from adapter.manifest import (
    CausalSourceInputRecord,
    DatasetFileRecord,
    Manifest,
)
from core.config import DetectorConfig
from evaluation.direction import FROZEN_POLICY_IDS
from runner.errors import AuthorizationError
from runner.instrument_pipeline import InstrumentResult
from runner.preflight import PreflightResult
from runner.manifest_builder import PROTECTED_PATHS
from selection.model import (
    CandidateIdentity,
    ClosedTradeOutcome,
    DirectionPolicyObservation,
    OutcomeState,
    Relation,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DETECTOR_ROOT = PROJECT_ROOT / "detector"
_ARG_TO_PRODUCER = {
    "htf_key_levels": "primitives.fvg.detect_fvgs->primitives.fvg.to_key_levels",
    "daily_series": "ingestion.loader.load_mt5_csv",
    "daily_key_levels": "primitives.ict_order_block.detect_ict_order_blocks->primitives.ict_order_block.to_key_levels",
}
_ARG_TO_GRANULARITY = {"htf_key_levels": "H4", "daily_series": "D1", "daily_key_levels": "D1"}


def _make_causal_source_inputs():
    inputs = []
    for inst in ("EURUSDm", "GBPUSDm", "DXYm"):
        for arg in ("htf_key_levels", "daily_series", "daily_key_levels"):
            inputs.append(CausalSourceInputRecord(
                instrument=inst,
                argument_name=arg,
                producer_id=_ARG_TO_PRODUCER[arg],
                dataset_relative_path=f"data/{inst}_{_ARG_TO_GRANULARITY[arg]}.csv",
            ))
    return tuple(inputs)


def _make_manifest(**overrides):
    defaults = dict(
        experiment_id="test-exp-001",
        protocol_artifact_path="protocol.json",
        protocol_artifact_sha256="abc123",
        direction_policy_implementation_commit="aaa",
        evaluation_seam_spec_commit="bbb",
        evaluation_seam_implementation_commit="ccc",
        evaluation_seam_closeout_commit="ddd",
        statistical_spec_v3_commit="eee",
        layer1_implementation_commit="fff",
        policy_ids=FROZEN_POLICY_IDS,
        dataset_identity="3x15M",
        dataset_file_hashes=(("file1.csv", "hash1"),),
        population_definition_ref="backtest/population.py",
        candidate_identity_fields=("instrument", "timeframe", "signal_id", "retest_index"),
        trade_join_key_fields=("instrument", "signal_id"),
        outcome_fields=("realized_r", "closed_outcome"),
        est_b_definition="mean(ALIGNED) - mean(OPPOSED)",
        mei_r=0.20,
        cluster_definition_ref="alignment/htf_ltf.py",
        bootstrap_config=(("replicates", 10000), ("seed", (20260910,))),
        nomination_rule_ref="selection/nomination.py",
        cost_assumptions=(("trading_cost_price", 0.0),),
        protected_paths=PROTECTED_PATHS,
        protected_paths_version="v1",
        layer2_implementation_commit="l2commit",
        layer3_implementation_commit="l3commit",
        measurement_execution_baseline_commit="baselinecommit",
        instrument_order=("EURUSDm", "GBPUSDm", "DXYm"),
        dataset_records=tuple(
            DatasetFileRecord(inst, gran, f"data/{inst}_{gran}.csv", 100, f"hash_{inst}_{gran}",
                              datetime(2025, 1, 1), datetime(2026, 1, 1))
            for inst in ("EURUSDm", "GBPUSDm", "DXYm")
            for gran in ("M15", "H4", "D1")
        ),
        candidate_cutoff_end_utc=datetime(2026, 6, 1),
        outcome_followup_end_utc=datetime(2026, 9, 1),
        spec_sha256="spec_hash",
        statistical_spec_commit_chain=("dc8af7d", "6b48374", "86c9150"),
        detector_config_fingerprint="config_fp",
        uv_lock_sha256="uvlock_hash",
        causal_spec_commit="1f412e3",
        causal_spec_amendment_commit="8f1906e",
        causal_implementation_commit="2419381",
        causal_source_inputs=_make_causal_source_inputs(),
    )
    defaults.update(overrides)
    return Manifest(**defaults)


def _make_synthetic_observations(instrument: str, n: int = 2):
    obs = []
    for i in range(n):
        cid = CandidateIdentity(instrument, "M15", f"sig_{instrument}_{i}", 10 + i)
        cluster_id = (instrument, 0, 5, 4)
        for pid in FROZEN_POLICY_IDS:
            obs.append(DirectionPolicyObservation(
                candidate_id=cid,
                context_cluster_id=cluster_id,
                policy_id=pid,
                relation=Relation.ALIGNED,
                outcome_state=OutcomeState.CLOSED,
                closed_outcome=ClosedTradeOutcome.WIN,
                realized_r=0.5,
            ))
    return tuple(obs)


def _make_instrument_result(instrument: str) -> InstrumentResult:
    return InstrumentResult(
        instrument=instrument,
        observations=_make_synthetic_observations(instrument),
        candidate_count=2,
        candidate_fingerprint="fp_" + instrument,
    )


def _make_preflight():
    return PreflightResult(
        baseline_commit="baselinecommit",
        head_commit="headcommit123",
        manifest_sha256="manifest_hash_abc",
        protocol_sha256="abc123",
        checks_passed=(
            "schema_parse", "schema_completeness", "protocol_hash",
            "policy_ids_match", "mei_r_match", "bootstrap_config_match",
            "cutoff_match", "population_config_match", "config_reconstruction",
            "authorization_manifest_binding",
            "environment_verification", "dataset_validation",
        ),
        authorization_commit="a" * 40,
        reconstructed_config=DetectorConfig(),
    )


def _assert_only_failure(output_dir: str, experiment_id: str) -> dict:
    output = Path(output_dir)
    assert not (output / experiment_id).exists()
    reports = list((output / "failed").glob("*/failure.json"))
    assert len(reports) == 1
    return json.loads(reports[0].read_text(encoding="utf-8"))


def test_successful_run_one_statistics_call(tmp_path):
    """Mocked orchestration invokes statistics once and publishes five files."""
    from runner.run_discovery import run_discovery

    manifest = _make_manifest()
    config = DetectorConfig()
    out_dir = str(tmp_path / "output")
    os.makedirs(out_dir)

    mock_results = {
        inst: _make_instrument_result(inst)
        for inst in ("EURUSDm", "GBPUSDm", "DXYm")
    }

    with (
        patch("runner.run_discovery.run_preflight") as mock_preflight,
        patch("runner.run_discovery.process_instrument") as mock_proc,
        patch("runner.run_discovery.compute_all_statistics") as mock_stats,
    ):
        mock_preflight.return_value = _make_preflight()
        mock_proc.side_effect = lambda inst, m, c, r, **kwargs: mock_results[inst]

        from runner.statistics_bridge import StatisticsResult
        from selection.bootstrap import BootstrapResult, CIComputability, ResamplePlan
        from selection.estimators import Computability, ESTBResult, InstrumentDelta
        from selection.nomination import NominationResult, PolicyEligibility
        from selection.stratify import PolicyStrata, RelationStratum

        dummy_stratum = RelationStratum(Relation.ALIGNED, 2, 0.5, 0.3, Computability.ESTIMABLE, 0.5)
        dummy_strata = PolicyStrata("p", 8, 4, 2, 2,
                                    dummy_stratum, dummy_stratum, dummy_stratum)
        dummy_est_b = ESTBResult(Computability.ESTIMABLE, 0.3)
        dummy_bootstrap = BootstrapResult(CIComputability.COMPUTABLE, 0.1, 0.5)
        dummy_delta = (InstrumentDelta("EURUSDm", Computability.ESTIMABLE, 0.2),)
        dummy_elig = PolicyEligibility("p", True, (), 0.3, 0.1, 0.5)
        dummy_nom = NominationResult(None, (dummy_elig,))
        dummy_plan = ResamplePlan(("EURUSDm",), {"EURUSDm": ()}, ())

        stats = StatisticsResult(
            strata={pid: dummy_strata for pid in FROZEN_POLICY_IDS},
            est_b_results={pid: dummy_est_b for pid in FROZEN_POLICY_IDS},
            bootstrap_results={pid: dummy_bootstrap for pid in FROZEN_POLICY_IDS},
            instrument_deltas={pid: dummy_delta for pid in FROZEN_POLICY_IDS},
            eligibilities=tuple(
                PolicyEligibility(pid, True, (), 0.3, 0.1, 0.5) for pid in FROZEN_POLICY_IDS
            ),
            nomination=dummy_nom,
            plan=dummy_plan,
        )
        mock_stats.return_value = stats

        result_path = run_discovery(manifest, config, "protocol.json", ".", out_dir, authorization_commit="a" * 40)

    assert mock_proc.call_count == 3
    mock_stats.assert_called_once()
    files = os.listdir(result_path)
    assert len(files) == 5
    run_manifest = json.loads(Path(result_path, "run_manifest.json").read_text(encoding="utf-8"))
    assert run_manifest["authorization_commit"] == "a" * 40


def test_instrument_failure_aborts_no_statistics(tmp_path):
    """Single instrument failure -> no compute_all_statistics call.
    Failure artifact is written."""
    from runner.run_discovery import run_discovery

    manifest = _make_manifest()
    config = DetectorConfig()
    out_dir = str(tmp_path / "output")
    os.makedirs(out_dir)

    def mock_proc(inst, m, c, r, **kwargs):
        if inst == "DXYm":
            raise RuntimeError("DXYm dataset corrupt")
        return _make_instrument_result(inst)

    with (
        patch("runner.run_discovery.run_preflight") as mock_preflight,
        patch("runner.run_discovery.process_instrument", side_effect=mock_proc),
        patch("runner.run_discovery.compute_all_statistics") as mock_stats,
    ):
        mock_preflight.return_value = _make_preflight()
        with pytest.raises(RuntimeError, match="DXYm"):
            run_discovery(manifest, config, "protocol.json", ".", out_dir, authorization_commit="a" * 40)

    mock_stats.assert_not_called()

    report = _assert_only_failure(out_dir, manifest.experiment_id)
    assert report["failing_check"] == "instrument_processing"


@pytest.mark.parametrize("repo_root", (PROJECT_ROOT, DETECTOR_ROOT))
def test_discovery_normalizes_project_and_detector_roots_for_instrument_loading(
    tmp_path, repo_root
):
    from runner.run_discovery import run_discovery

    manifest = _make_manifest()
    output = str(tmp_path / "output")
    with (
        patch("runner.run_discovery.run_preflight", return_value=_make_preflight()) as preflight,
        patch(
            "runner.run_discovery.process_instrument", side_effect=RuntimeError("opaque")
        ) as instrument,
    ):
        with pytest.raises(RuntimeError, match="opaque"):
            run_discovery(
                manifest, DetectorConfig(), "protocol.json", str(repo_root), output,
                authorization_commit="a" * 40,
            )

    assert Path(preflight.call_args.args[2]) == PROJECT_ROOT
    assert Path(instrument.call_args.args[3]) == DETECTOR_ROOT


def test_preflight_failure_no_instrument_processing(tmp_path):
    """Preflight failure -> no instrument processing, no statistics.
    Failure artifact is written."""
    from runner.run_discovery import run_discovery

    manifest = _make_manifest()
    config = DetectorConfig()
    out_dir = str(tmp_path / "output")
    os.makedirs(out_dir)

    with (
        patch("runner.run_discovery.run_preflight", side_effect=AuthorizationError("schema fail")),
        patch("runner.run_discovery.process_instrument") as mock_proc,
        patch("runner.run_discovery.compute_all_statistics") as mock_stats,
    ):
        with pytest.raises(AuthorizationError):
            run_discovery(manifest, config, "protocol.json", ".", out_dir, authorization_commit="a" * 40)

    mock_proc.assert_not_called()
    mock_stats.assert_not_called()

    failed_dir = os.path.join(out_dir, "failed")
    assert os.path.isdir(failed_dir)


def test_failure_artifact_has_environment_and_checks(tmp_path):
    """Failure artifact includes environment record and completed checks."""
    from runner.run_discovery import run_discovery

    manifest = _make_manifest()
    config = DetectorConfig()
    out_dir = str(tmp_path / "output")
    os.makedirs(out_dir)

    def mock_proc(inst, m, c, r, **kwargs):
        raise RuntimeError("instrument failure")

    with (
        patch("runner.run_discovery.run_preflight") as mock_preflight,
        patch("runner.run_discovery.process_instrument", side_effect=mock_proc),
    ):
        mock_preflight.return_value = _make_preflight()
        with pytest.raises(RuntimeError):
            run_discovery(manifest, config, "protocol.json", ".", out_dir, authorization_commit="a" * 40)

    failed_dir = os.path.join(out_dir, "failed")
    sub = os.listdir(failed_dir)
    assert len(sub) == 1
    failure_file = os.path.join(failed_dir, sub[0], "failure.json")
    with open(failure_file, "r") as f:
        data = json.load(f)
    assert "environment" in data
    assert "completed_checks" in data
    assert len(data["completed_checks"]) == len(_make_preflight().checks_passed)


def test_failure_artifact_no_statistical_fields_recursive(tmp_path):
    """Failure artifact NEVER contains statistical fields, checked recursively."""
    from runner.run_discovery import run_discovery

    manifest = _make_manifest()
    config = DetectorConfig()
    out_dir = str(tmp_path / "output")
    os.makedirs(out_dir)

    with (
        patch("runner.run_discovery.run_preflight", side_effect=AuthorizationError("fail")),
    ):
        with pytest.raises(AuthorizationError):
            run_discovery(manifest, config, "protocol.json", ".", out_dir, authorization_commit="a" * 40)

    failed_dir = os.path.join(out_dir, "failed")
    sub = os.listdir(failed_dir)
    failure_file = os.path.join(failed_dir, sub[0], "failure.json")
    with open(failure_file, "r") as f:
        raw = f.read()

    forbidden = [
        "realized_r", "closed_outcome", "mean_r", "est_b",
        "ci_lower", "ci_upper", "instrument_delta", "nomination_result",
        "relation_distribution", "wr_value",
    ]
    for field in forbidden:
        assert field not in raw, f"failure artifact contains forbidden term: {field}"


def test_4n_cardinality_check(tmp_path):
    """Cross-validation rejects wrong observation count."""
    from runner.run_discovery import run_discovery

    manifest = _make_manifest()
    config = DetectorConfig()
    out_dir = str(tmp_path / "output")
    os.makedirs(out_dir)

    bad_result = InstrumentResult(
        instrument="EURUSDm",
        observations=_make_synthetic_observations("EURUSDm", 2),
        candidate_count=99,
        candidate_fingerprint="fp",
    )
    good_results = {
        "GBPUSDm": _make_instrument_result("GBPUSDm"),
        "DXYm": _make_instrument_result("DXYm"),
    }

    with (
        patch("runner.run_discovery.run_preflight") as mock_preflight,
        patch("runner.run_discovery.process_instrument") as mock_proc,
        patch("runner.run_discovery.compute_all_statistics") as mock_stats,
    ):
        mock_preflight.return_value = _make_preflight()
        def _mock(inst, m, c, r, **kwargs):
            if inst == "EURUSDm":
                return bad_result
            return good_results[inst]
        mock_proc.side_effect = _mock
        with pytest.raises(AuthorizationError, match="4N cardinality"):
            run_discovery(manifest, config, "protocol.json", ".", out_dir, authorization_commit="a" * 40)
    mock_stats.assert_not_called()
    report = _assert_only_failure(out_dir, manifest.experiment_id)
    assert report["failing_check"] == "instrument_bundle_validation"


def test_statistics_failure_writes_only_failure_report(tmp_path):
    from runner.run_discovery import run_discovery

    manifest = _make_manifest()
    output = str(tmp_path / "output")
    with (
        patch("runner.run_discovery.run_preflight", return_value=_make_preflight()),
        patch("runner.run_discovery.process_instrument", side_effect=lambda inst, *_, **__: _make_instrument_result(inst)),
        patch("runner.run_discovery.compute_all_statistics", side_effect=RuntimeError("opaque")),
    ):
        with pytest.raises(RuntimeError, match="opaque"):
            run_discovery(manifest, DetectorConfig(), "protocol.json", ".", output, authorization_commit="a" * 40)

    report = _assert_only_failure(output, manifest.experiment_id)
    assert report["failing_check"] == "statistics_computation"


def test_artifact_construction_failure_writes_only_failure_report(tmp_path):
    from runner.run_discovery import run_discovery

    manifest = _make_manifest()
    output = str(tmp_path / "output")
    with (
        patch("runner.run_discovery.run_preflight", return_value=_make_preflight()),
        patch("runner.run_discovery.process_instrument", side_effect=lambda inst, *_, **__: _make_instrument_result(inst)),
        patch("runner.run_discovery.compute_all_statistics", return_value=MagicMock()),
        patch("runner.run_discovery.build_run_manifest", side_effect=RuntimeError("opaque")),
    ):
        with pytest.raises(RuntimeError, match="opaque"):
            run_discovery(manifest, DetectorConfig(), "protocol.json", ".", output, authorization_commit="a" * 40)

    report = _assert_only_failure(output, manifest.experiment_id)
    assert report["failing_check"] == "artifact_construction"


def test_publication_failure_writes_only_failure_report(tmp_path):
    from runner.run_discovery import run_discovery

    manifest = _make_manifest()
    output = str(tmp_path / "output")
    with (
        patch("runner.run_discovery.run_preflight", return_value=_make_preflight()),
        patch("runner.run_discovery.process_instrument", side_effect=lambda inst, *_, **__: _make_instrument_result(inst)),
        patch("runner.run_discovery.compute_all_statistics", return_value=MagicMock()),
        patch("runner.run_discovery.build_run_manifest", return_value={}),
        patch("runner.run_discovery.build_policy_summary", return_value={}),
        patch("runner.run_discovery.build_bootstrap_summary", return_value={}),
        patch("runner.run_discovery.build_nomination_trace", return_value={}),
        patch("runner.run_discovery.publish", side_effect=RuntimeError("opaque")),
    ):
        with pytest.raises(RuntimeError, match="opaque"):
            run_discovery(manifest, DetectorConfig(), "protocol.json", ".", output, authorization_commit="a" * 40)

    report = _assert_only_failure(output, manifest.experiment_id)
    assert report["failing_check"] == "publication"


def test_failure_report_error_does_not_mask_original_exception(tmp_path):
    from runner.run_discovery import run_discovery

    manifest = _make_manifest()
    with (
        patch("runner.run_discovery.run_preflight", return_value=_make_preflight()),
        patch("runner.run_discovery.process_instrument", side_effect=RuntimeError("original failure")),
        patch("runner.run_discovery.write_failure_artifact", side_effect=OSError("report failure")),
    ):
        with pytest.raises(RuntimeError, match="original failure"):
            run_discovery(
                manifest, DetectorConfig(), "protocol.json", ".", str(tmp_path / "output"),
                authorization_commit="a" * 40,
            )
