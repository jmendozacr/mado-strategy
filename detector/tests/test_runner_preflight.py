"""Preflight validation.

Tests that run_preflight executes real checks:
- schema/parse, protocol hash, cross-consistency, config reconstruction,
  git baseline, environment, dataset integrity.
- NEVER calls build_stage6_population or evaluate_direction_policies."""

import hashlib
import json
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from adapter.manifest import (
    CausalSourceInputRecord,
    DatasetFileRecord,
    GapAllowlistEntry,
    Manifest,
)
from evaluation.direction import FROZEN_POLICY_IDS
from core.candle import Candle, OHLCSeries
from runner.errors import AuthorizationError
from runner.preflight import (
    PreflightResult,
    _validate_causal_source_inputs,
    _validate_schema,
    run_preflight,
)
from runner.manifest_builder import PROTECTED_PATHS, build_manifest


_ARG_TO_PRODUCER = {
    "htf_key_levels": "primitives.fvg.detect_fvgs->primitives.fvg.to_key_levels",
    "daily_series": "ingestion.loader.load_mt5_csv",
    "daily_key_levels": "primitives.ict_order_block.detect_ict_order_blocks->primitives.ict_order_block.to_key_levels",
}
_ARG_TO_GRANULARITY = {
    "htf_key_levels": "H4",
    "daily_series": "D1",
    "daily_key_levels": "D1",
}


def _make_causal_source_inputs():
    inputs = []
    for inst in ("EURUSDm", "GBPUSDm", "DXYm"):
        for arg in ("htf_key_levels", "daily_series", "daily_key_levels"):
            granularity = _ARG_TO_GRANULARITY[arg]
            inputs.append(
                CausalSourceInputRecord(
                    instrument=inst,
                    argument_name=arg,
                    producer_id=_ARG_TO_PRODUCER[arg],
                    dataset_relative_path=f"data/{inst}_{granularity}.csv",
                )
            )
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
        dataset_records=(
            DatasetFileRecord("EURUSDm", "M15", "data/EURUSDm_M15.csv", 1000, "hash_eur15", datetime(2025, 1, 1), datetime(2026, 1, 1)),
            DatasetFileRecord("EURUSDm", "H4", "data/EURUSDm_H4.csv", 500, "hash_eurh4", datetime(2025, 1, 1), datetime(2026, 1, 1)),
            DatasetFileRecord("EURUSDm", "D1", "data/EURUSDm_D1.csv", 300, "hash_eurd1", datetime(2025, 1, 1), datetime(2026, 1, 1)),
            DatasetFileRecord("GBPUSDm", "M15", "data/GBPUSDm_M15.csv", 1000, "hash_gbp15", datetime(2025, 1, 1), datetime(2026, 1, 1)),
            DatasetFileRecord("GBPUSDm", "H4", "data/GBPUSDm_H4.csv", 500, "hash_gbph4", datetime(2025, 1, 1), datetime(2026, 1, 1)),
            DatasetFileRecord("GBPUSDm", "D1", "data/GBPUSDm_D1.csv", 300, "hash_gbpd1", datetime(2025, 1, 1), datetime(2026, 1, 1)),
            DatasetFileRecord("DXYm", "M15", "data/DXYm_M15.csv", 1000, "hash_dxy15", datetime(2025, 1, 1), datetime(2026, 1, 1)),
            DatasetFileRecord("DXYm", "H4", "data/DXYm_H4.csv", 500, "hash_dxyh4", datetime(2025, 1, 1), datetime(2026, 1, 1)),
            DatasetFileRecord("DXYm", "D1", "data/DXYm_D1.csv", 300, "hash_dxyd1", datetime(2025, 1, 1), datetime(2026, 1, 1)),
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


def test_validate_schema_all_fields_present():
    m = _make_manifest()
    _validate_schema(m)


def test_validate_schema_missing_instrument_order():
    m = _make_manifest(instrument_order=None)
    with pytest.raises(AuthorizationError, match="instrument_order"):
        _validate_schema(m)


def test_validate_schema_missing_dataset_records():
    m = _make_manifest(dataset_records=None)
    with pytest.raises(AuthorizationError, match="dataset_records"):
        _validate_schema(m)


def test_validate_schema_empty_spec_chain():
    m = _make_manifest(statistical_spec_commit_chain=())
    with pytest.raises(AuthorizationError, match="statistical_spec_commit_chain"):
        _validate_schema(m)


def test_validate_schema_missing_baseline():
    m = _make_manifest(measurement_execution_baseline_commit=None)
    with pytest.raises(AuthorizationError, match="measurement_execution_baseline_commit"):
        _validate_schema(m)


def test_causal_source_inputs_exactly_9():
    inputs = tuple(
        CausalSourceInputRecord(
            instrument="EURUSDm",
            argument_name="htf_key_levels",
            producer_id="primitives.fvg.detect_fvgs->primitives.fvg.to_key_levels",
            dataset_relative_path="data/EUR_H4.csv",
        )
        for _ in range(8)
    )
    m = _make_manifest(causal_source_inputs=inputs)
    with pytest.raises(AuthorizationError, match="9"):
        _validate_causal_source_inputs(m)


def test_causal_source_inputs_wrong_instrument():
    """An instrument not in manifest.instrument_order is rejected."""
    inputs = list(_make_causal_source_inputs())
    inputs[0] = CausalSourceInputRecord(
        instrument="XAUUSDm",
        argument_name="htf_key_levels",
        producer_id=_ARG_TO_PRODUCER["htf_key_levels"],
        dataset_relative_path="data/XAUUSDm_H4.csv",
    )
    m = _make_manifest(causal_source_inputs=tuple(inputs))
    with pytest.raises(AuthorizationError, match="not in manifest.instrument_order"):
        _validate_causal_source_inputs(m)


def test_causal_source_inputs_missing_pair():
    """A missing (instrument, argument) pair is detected."""
    inputs = list(_make_causal_source_inputs())
    inputs[0] = CausalSourceInputRecord(
        instrument="GBPUSDm",
        argument_name="htf_key_levels",
        producer_id=_ARG_TO_PRODUCER["htf_key_levels"],
        dataset_relative_path="data/GBPUSDm_H4.csv",
    )
    m = _make_manifest(causal_source_inputs=tuple(inputs))
    with pytest.raises(AuthorizationError, match="duplicate|missing"):
        _validate_causal_source_inputs(m)


def test_causal_source_inputs_wrong_producer():
    """Wrong producer_id for an argument_name is rejected."""
    inputs = list(_make_causal_source_inputs())
    inputs[0] = CausalSourceInputRecord(
        instrument="EURUSDm",
        argument_name="htf_key_levels",
        producer_id="ingestion.loader.load_mt5_csv",
        dataset_relative_path="data/EURUSDm_H4.csv",
    )
    m = _make_manifest(causal_source_inputs=tuple(inputs))
    with pytest.raises(AuthorizationError, match="requires producer_id"):
        _validate_causal_source_inputs(m)


def test_causal_source_inputs_cross_instrument_path():
    """A path referencing wrong instrument/granularity is rejected."""
    inputs = list(_make_causal_source_inputs())
    inputs[0] = CausalSourceInputRecord(
        instrument="EURUSDm",
        argument_name="htf_key_levels",
        producer_id=_ARG_TO_PRODUCER["htf_key_levels"],
        dataset_relative_path="data/GBPUSDm_D1.csv",
    )
    m = _make_manifest(causal_source_inputs=tuple(inputs))
    with pytest.raises(AuthorizationError, match="not found in manifest.dataset_records"):
        _validate_causal_source_inputs(m)


def test_causal_source_inputs_wrong_granularity():
    """A path with wrong granularity for the argument is rejected."""
    inputs = list(_make_causal_source_inputs())
    inputs[0] = CausalSourceInputRecord(
        instrument="EURUSDm",
        argument_name="htf_key_levels",
        producer_id=_ARG_TO_PRODUCER["htf_key_levels"],
        dataset_relative_path="data/EURUSDm_D1.csv",
    )
    m = _make_manifest(causal_source_inputs=tuple(inputs))
    with pytest.raises(AuthorizationError, match="not found in manifest.dataset_records"):
        _validate_causal_source_inputs(m)


def test_preflight_rejects_noncanonical_protocol_path(tmp_path):
    protocol_file = tmp_path / "protocol.json"
    protocol_file.write_text('{"population":{"config":{}}}')
    m = _make_manifest(
        protocol_artifact_sha256="wrong_hash",
        protocol_artifact_path=str(protocol_file),
    )
    with pytest.raises(Exception, match="canonical"):
        run_preflight(m, str(protocol_file), str(tmp_path), authorization_commit="a" * 40)


def test_successful_preflight_never_calls_population_or_evaluate():
    project_root = Path(__file__).resolve().parents[2]
    detector_root = project_root / "detector"
    protocol_path = (
        detector_root / "research" / "direction_policy_discovery_v1_amendment_1.json"
    )
    manifest = build_manifest(
        str(protocol_path), str(detector_root), "b" * 40, "1dd0acc", "c" * 40
    )
    records_by_path = {
        str((detector_root / record.relative_path).resolve()): record
        for record in manifest.dataset_records
    }

    def record_for(path):
        return records_by_path[str(Path(path).resolve())]

    def series_for(path, instrument):
        granularity = next(
            item for item in ("M15", "H4", "D1") if item in Path(path).parts
        )
        interval = {
            "M15": timedelta(minutes=15),
            "H4": timedelta(hours=4),
            "D1": timedelta(days=1),
        }[granularity]
        candles = tuple(
            Candle(datetime(2026, 1, 1) + interval * index, 1.0, 1.1, 0.9, 1.0)
            for index in range(4)
        )
        timeframe = "15M" if granularity == "M15" else granularity
        return OHLCSeries(candles, instrument, timeframe)

    from runner.serialization import canonical_json, to_json_value
    runtime_bytes = canonical_json(to_json_value(manifest))
    with (
        patch("runner.preflight.environment_record", return_value={}),
        patch("runner.preflight.verify_commit_exists"),
        patch("runner.preflight.verify_is_ancestor"),
        patch("runner.preflight.read_committed_blob", return_value=runtime_bytes),
        patch("runner.preflight.verify_no_diff"),
        patch("runner.preflight.verify_no_working_tree_diff"),
        patch("runner.preflight.verify_no_staged_diff"),
        patch("runner.preflight.verify_no_untracked"),
        patch("runner.preflight.get_head_commit", return_value="h" * 40),
        patch("runner.preflight.verify_environment", return_value={}),
        patch("runner.preflight.os.path.isfile", return_value=True),
        patch(
            "runner.preflight.os.path.getsize",
            side_effect=lambda path: record_for(path).byte_size,
        ),
        patch(
            "runner.preflight.sha256_of_file",
            side_effect=lambda path: (
                manifest.spec_sha256
                if Path(path).resolve()
                == (project_root / "openspec/changes/crt-detector-direction-policy-statistical-runner/spec.md").resolve()
                else record_for(path).sha256
            ),
        ),
        patch("runner.preflight.load_mt5_csv", side_effect=series_for),
        patch("backtest.population.build_stage6_population") as mock_pop,
        patch("evaluation.direction.evaluate_direction_policies") as mock_eval,
    ):
        result = run_preflight(
            manifest, str(protocol_path), str(detector_root), authorization_commit="a" * 40
        )

    mock_pop.assert_not_called()
    mock_eval.assert_not_called()
    assert result.checks_passed[-1] == "dataset_validation"


def test_manifest_with_all_layer3_fields():
    m = _make_manifest()
    assert m.instrument_order == ("EURUSDm", "GBPUSDm", "DXYm")
    assert m.dataset_records is not None
    assert len(m.dataset_records) == 9
    assert m.candidate_cutoff_end_utc is not None
    assert m.causal_source_inputs is not None
    assert len(m.causal_source_inputs) == 9


def test_manifest_layer3_fields_neutral_defaults():
    m = Manifest(
        experiment_id="test",
        protocol_artifact_path="p.json",
        protocol_artifact_sha256="hash",
        direction_policy_implementation_commit="a",
        evaluation_seam_spec_commit="b",
        evaluation_seam_implementation_commit="c",
        evaluation_seam_closeout_commit="d",
        statistical_spec_v3_commit="e",
        layer1_implementation_commit="f",
        policy_ids=FROZEN_POLICY_IDS,
        dataset_identity="id",
        dataset_file_hashes=(("f", "h"),),
        population_definition_ref="ref",
        candidate_identity_fields=("instrument", "timeframe", "signal_id", "retest_index"),
        trade_join_key_fields=("instrument", "signal_id"),
        outcome_fields=("outcome_state",),
        est_b_definition="def",
        mei_r=0.20,
        cluster_definition_ref="ref",
        bootstrap_config=(("k", "v"),),
        nomination_rule_ref="ref",
        cost_assumptions=(("k", "v"),),
        protected_paths=("p/",),
        protected_paths_version="v1",
    )
    assert m.instrument_order is None
    assert m.dataset_records is None
    assert m.causal_source_inputs is None
