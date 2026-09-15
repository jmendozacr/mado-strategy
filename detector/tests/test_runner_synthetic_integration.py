from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from alignment.htf_ltf import AlignedSignal
from backtest.population import build_stage6_population
from backtest.simulate import simulate
from core.candle import Candle, OHLCSeries
from core.config import DetectorConfig
from core.key_level import KeyLevel
from core.results import DetectionStatus
from entries.model1 import Model1Signal
from evaluation.direction import FROZEN_POLICY_IDS
from primitives.crt_range import CRTRange
from runner import artifacts as artifact_module
from runner import statistics_bridge
from runner.manifest_builder import build_manifest
from runner.progress import ProgressEvent
from runner.run_discovery import run_discovery
from selection.model import OutcomeState


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DETECTOR_ROOT = PROJECT_ROOT / "detector"
CANONICAL_PROTOCOL = DETECTOR_ROOT / "research" / "direction_policy_discovery_v1_amendment_1.json"


def _series_for(path: str, instrument: str) -> OHLCSeries:
    granularity = next(
        item for item in ("M15", "H4", "D1") if item in Path(path).parts
    )
    interval = {"M15": timedelta(minutes=15), "H4": timedelta(hours=4), "D1": timedelta(days=1)}[granularity]
    start = datetime(2026, 1, 1, 12)
    if granularity == "M15":
        prices = (
            (1.1000, 1.1010, 1.0990, 1.1005),
            (1.1005, 1.1010, 1.1000, 1.1005),
            (1.1002, 1.1008, 1.1001, 1.1004),
            (1.1003, 1.1006, 1.1001, 1.1002),
            (1.1020, 1.1025, 1.0995, 1.1010),
            (1.1000, 1.1010, 1.0995, 1.1002),
        )
        candles = tuple(
            Candle(start + interval * index, open_, high, low, close)
            for index, (open_, high, low, close) in enumerate(prices)
        )
    else:
        candles = tuple(
            Candle(start + interval * index, 1.0, 1.1, 0.9, 1.0)
            for index in range(6)
        )
    internal_timeframe = "15M" if granularity == "M15" else granularity
    return OHLCSeries(candles, instrument, internal_timeframe)


def _causal_signal() -> AlignedSignal:
    signal = Model1Signal(
        anchor_index=0,
        direction="bullish",
        purge_target=1.0990,
        confirmation_type="purge_engulf",
        entry_type="body",
        entry_price=1.1000,
        retest_index=3,
        status=DetectionStatus.CONFIRMED,
        confirmation_index=3,
        origin_index=0,
    )
    return AlignedSignal(
        signal,
        CRTRange("2-candle", 1.1050, 1.0950, 0, 1, "true_break", 1),
        "aligned",
        KeyLevel("fvg", 1.1050, 1.0950, 0),
    )


def test_synthetic_run_executes_real_preflight_and_publishes_once(tmp_path):
    manifest = build_manifest(
        str(CANONICAL_PROTOCOL), str(DETECTOR_ROOT), "b" * 40, "1dd0acc", "c" * 40
    )
    records_by_path = {
        str((DETECTOR_ROOT / record.relative_path).resolve()): record
        for record in manifest.dataset_records
    }
    output = tmp_path / "output"
    events = []
    populations = []
    simulations = []

    def record_for(path):
        return records_by_path[str(Path(path).resolve())]

    def capture_population(*args):
        population = build_stage6_population(*args)
        populations.append((args, population))
        return population

    def capture_simulation(*args):
        result = simulate(*args)
        simulations.append((args, result))
        return result

    with (
        patch("runner.preflight.verify_commit_exists"),
        patch("runner.preflight.verify_is_ancestor"),
        patch("runner.preflight.verify_no_diff"),
        patch("runner.preflight.verify_no_working_tree_diff"),
        patch("runner.preflight.verify_no_staged_diff"),
        patch("runner.preflight.verify_no_untracked"),
        patch("runner.preflight.get_head_commit", return_value="h" * 40),
        patch("runner.preflight.os.path.isfile", return_value=True),
        patch(
            "runner.preflight.os.path.getsize",
            side_effect=lambda path: record_for(path).byte_size,
        ),
        patch(
            "runner.preflight.sha256_of_file",
            side_effect=lambda path: (
                manifest.spec_sha256
                if Path(path).resolve() == (PROJECT_ROOT / "openspec/changes/crt-detector-direction-policy-statistical-runner/spec.md").resolve()
                else record_for(path).sha256
            ),
        ),
        patch("runner.preflight.load_mt5_csv", side_effect=_series_for),
        patch(
            "runner.instrument_pipeline.sha256_of_file",
            side_effect=lambda path: record_for(path).sha256,
        ),
        patch("runner.instrument_pipeline.load_mt5_csv", side_effect=_series_for),
        patch(
            "runner.instrument_pipeline.generate_causal_aligned_signals",
            side_effect=lambda *args, **kwargs: [_causal_signal()],
        ) as causal_call,
        patch(
            "runner.instrument_pipeline.build_stage6_population",
            side_effect=capture_population,
        ) as population_call,
        patch(
            "runner.instrument_pipeline.simulate",
            side_effect=capture_simulation,
        ) as simulation_call,
        patch(
            "runner.run_discovery.compute_all_statistics",
            wraps=statistics_bridge.compute_all_statistics,
        ) as statistics_call,
        patch(
            "runner.run_discovery.build_run_manifest",
            wraps=artifact_module.build_run_manifest,
        ) as manifest_call,
    ):
        result = run_discovery(
            manifest,
            DetectorConfig(),
            str(CANONICAL_PROTOCOL),
            str(DETECTOR_ROOT),
            str(output),
            lambda event, payload: events.append((event, payload)),
        )

    statistics_call.assert_called_once()
    assert causal_call.call_count == 3
    assert population_call.call_count == simulation_call.call_count == 3
    loaded_series = _series_for("synthetic/M15/EURUSDm.csv", "EURUSDm")
    assert loaded_series.timeframe == "15M"
    assert next(record for record in manifest.dataset_records if record.granularity == "M15").granularity == "M15"
    receipt = manifest_call.call_args.args[1]
    assert receipt.checks_passed[-1] == "instrument_bundle_validation"
    assert len(receipt.instrument_results) == 3
    assert [item.candidate_count for item in receipt.instrument_results] == [1, 1, 1]
    assert [len(item.observations) for item in receipt.instrument_results] == [4, 4, 4]
    assert sum(len(item.observations) for item in receipt.instrument_results) == (
        len(FROZEN_POLICY_IDS) * sum(item.candidate_count for item in receipt.instrument_results)
    )
    for instrument_result, (population_args, population), (simulation_args, simulation_result) in zip(
        receipt.instrument_results, populations, simulations
    ):
        assert population_args[0] is simulation_args[0]
        assert len(population_args[0]) == 1
        assert population_args[1] is simulation_args[1]
        assert population_args[2] is simulation_args[2]
        assert population_args[3] is simulation_args[3]
        candidate = population.candidates[0]
        trade = simulation_result[0][0]
        assert (trade.signal_id, trade.entry_price, trade.stop_loss, trade.take_profit) == (
            candidate.signal_id,
            candidate.entry_price,
            candidate.stop_loss,
            candidate.take_profit,
        )
        assert {row.policy_id for row in instrument_result.observations} == set(
            FROZEN_POLICY_IDS
        )
        assert all(
            row.candidate_id.instrument == instrument_result.instrument
            and row.candidate_id.signal_id == candidate.signal_id
            and row.candidate_id.retest_index == candidate.retest_index
            and row.context_cluster_id[0] == instrument_result.instrument
            and row.outcome_state == OutcomeState.OPEN
            and row.realized_r is None
            for row in instrument_result.observations
        )
    assert [event for event, _ in events] == [
        ProgressEvent.PREFLIGHT_PASSED,
        ProgressEvent.INSTRUMENT_DATASET_VALIDATED,
        ProgressEvent.INSTRUMENT_BUNDLE_VALIDATED,
        ProgressEvent.INSTRUMENT_DATASET_VALIDATED,
        ProgressEvent.INSTRUMENT_BUNDLE_VALIDATED,
        ProgressEvent.INSTRUMENT_DATASET_VALIDATED,
        ProgressEvent.INSTRUMENT_BUNDLE_VALIDATED,
        ProgressEvent.ALL_INSTRUMENTS_VALIDATED,
        ProgressEvent.STATISTICS_COMPLETE,
        ProgressEvent.PUBLISHED,
    ]
    assert {path.name for path in Path(result).iterdir()} == {
        "run_manifest.json", "policy_summary.json", "bootstrap_summary.json",
        "nomination_trace.json", "run_status.json",
    }
