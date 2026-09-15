"""Instrument pipeline.

Behavioral: process_instrument with synthetic objects proves:
- one causal generation, one cutoff filter
- same-object discipline (identical bindings reach population + simulate)
- fingerprint before simulate
- cardinality check
- no tag_alignment import
- duplicate dataset records rejected"""

import inspect
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, call

import pytest

from adapter.manifest import DatasetFileRecord, Manifest
from alignment.htf_ltf import AlignedSignal
from backtest.population import build_stage6_population
from backtest.simulate import simulate
from core.candle import Candle, OHLCSeries
from core.config import DetectorConfig
from core.key_level import KeyLevel
from core.results import DetectionStatus
from entries.model1 import Model1Signal
from primitives.crt_range import CRTRange


def test_no_tag_alignment_import():
    """runner/ must not import tag_alignment or detect_model1_signals."""
    import runner.instrument_pipeline as mod
    source = inspect.getsource(mod)
    assert "tag_alignment" not in source
    assert "detect_model1_signals" not in source


def test_no_tag_alignment_in_any_runner_module():
    """Structural fitness: no runner/ module imports tag_alignment."""
    import importlib
    import pkgutil
    import runner

    for importer, modname, ispkg in pkgutil.walk_packages(runner.__path__, runner.__name__ + "."):
        mod = importlib.import_module(modname)
        source = inspect.getsource(mod)
        assert "tag_alignment" not in source, f"{modname} imports tag_alignment"
        assert "detect_model1_signals" not in source, f"{modname} imports detect_model1_signals"


def test_instrument_result_type_exists():
    from runner.instrument_pipeline import InstrumentResult
    fields = set(InstrumentResult.__dataclass_fields__)
    assert "instrument" in fields
    assert "observations" in fields
    assert "candidate_count" in fields
    assert "candidate_fingerprint" in fields


def test_process_instrument_function_exists():
    from runner.instrument_pipeline import process_instrument
    assert callable(process_instrument)


def test_duplicate_dataset_record_rejected():
    """Duplicate dataset records for same instrument+granularity are rejected."""
    from datetime import datetime
    from adapter.manifest import DatasetFileRecord
    from runner.instrument_pipeline import _find_dataset_record
    from runner.errors import AuthorizationError

    records = [
        DatasetFileRecord("EURUSDm", "M15", "a.csv", 100, "h1", datetime(2025, 1, 1), datetime(2026, 1, 1)),
        DatasetFileRecord("EURUSDm", "M15", "b.csv", 200, "h2", datetime(2025, 1, 1), datetime(2026, 1, 1)),
    ]
    with pytest.raises(AuthorizationError, match="duplicate"):
        _find_dataset_record(records, "EURUSDm", "M15")


def test_process_instrument_same_object_discipline():
    """Proves identical bindings reach build_stage6_population and simulate."""
    from datetime import datetime
    from unittest.mock import ANY

    from adapter.manifest import DatasetFileRecord, Manifest
    from core.config import DetectorConfig
    from evaluation.direction import FROZEN_POLICY_IDS

    captured_pop_args = {}
    captured_sim_args = {}
    mock_population = MagicMock()
    mock_population.candidates = []
    mock_population.series = MagicMock()

    def capture_build(*args, **kwargs):
        captured_pop_args["args"] = args
        return mock_population

    def capture_simulate(*args, **kwargs):
        captured_sim_args["args"] = args
        mock_recon = MagicMock()
        mock_recon.excluded_never_filled = 0
        return ([], mock_recon)

    mock_evaluations = tuple(MagicMock() for _ in FROZEN_POLICY_IDS)

    with (
        patch("runner.instrument_pipeline._load_and_validate_series") as mock_load,
        patch("runner.instrument_pipeline.generate_causal_aligned_signals", return_value=[]),
        patch("runner.instrument_pipeline.detect_swings", return_value=[]),
        patch("runner.instrument_pipeline.build_stage6_population", side_effect=capture_build) as mock_pop,
        patch("runner.instrument_pipeline.simulate", side_effect=capture_simulate) as mock_sim,
        patch("runner.instrument_pipeline.detect_order_flow_events", return_value=[]),
        patch("runner.instrument_pipeline.detect_bias_evidence", return_value=[]),
        patch("runner.instrument_pipeline.evaluate_direction_policies", return_value=mock_evaluations),
        patch("runner.instrument_pipeline.build_direction_policy_observations", return_value=()),
        patch("runner.instrument_pipeline.compute_candidate_fingerprint", return_value="fp"),
        patch("runner.instrument_pipeline.detect_fvgs", return_value=[]),
        patch("runner.instrument_pipeline.fvg_to_key_levels", return_value=[]),
        patch("runner.instrument_pipeline.detect_ict_order_blocks", return_value=[]),
        patch("runner.instrument_pipeline.ob_to_key_levels", return_value=[]),
    ):
        mock_series = MagicMock()
        mock_series.candles = []
        mock_series.instrument = "EURUSDm"
        mock_load.return_value = mock_series
        mock_population.series = mock_series

        from runner.instrument_pipeline import process_instrument

        records = tuple(
            DatasetFileRecord(
                "EURUSDm", g, f"data/EURUSDm_{g}.csv", 100, f"hash_{g}",
                datetime(2025, 1, 1), datetime(2026, 1, 1),
            )
            for g in ("M15", "H4", "D1")
        )
        manifest = MagicMock(spec=Manifest)
        manifest.dataset_records = records
        manifest.candidate_cutoff_end_utc = datetime(2026, 6, 1)
        manifest.outcome_followup_end_utc = datetime(2026, 9, 1)
        manifest.instrument_order = ("EURUSDm",)
        manifest.dataset_gap_allowlist = ()

        config = DetectorConfig()
        process_instrument("EURUSDm", manifest, config, ".")

        pop_admitted = captured_pop_args["args"][0]
        sim_admitted = captured_sim_args["args"][0]
        assert pop_admitted is sim_admitted

        pop_series = captured_pop_args["args"][1]
        sim_series = captured_sim_args["args"][1]
        assert pop_series is sim_series

        pop_config = captured_pop_args["args"][2]
        sim_config = captured_sim_args["args"][2]
        assert pop_config is sim_config

        pop_swings = captured_pop_args["args"][3]
        sim_swings = captured_sim_args["args"][3]
        assert pop_swings is sim_swings
        assert pop_swings is not None


def test_fingerprint_computed_before_simulate():
    """Candidate fingerprint is computed BEFORE simulate runs."""
    call_order = []

    def track_pop(*a, **kw):
        call_order.append("build_population")
        pop = MagicMock()
        pop.candidates = []
        series_mock = MagicMock()
        series_mock.instrument = "EURUSDm"
        pop.series = series_mock
        return pop

    def track_fp(*a, **kw):
        call_order.append("fingerprint")
        return "fp"

    def track_sim(*a, **kw):
        call_order.append("simulate")
        recon = MagicMock()
        recon.excluded_never_filled = 0
        return ([], recon)

    from datetime import datetime
    from adapter.manifest import DatasetFileRecord, Manifest
    from core.config import DetectorConfig
    from evaluation.direction import FROZEN_POLICY_IDS

    with (
        patch("runner.instrument_pipeline._load_and_validate_series") as mock_load,
        patch("runner.instrument_pipeline.generate_causal_aligned_signals", return_value=[]),
        patch("runner.instrument_pipeline.detect_swings", return_value=[]),
        patch("runner.instrument_pipeline.build_stage6_population", side_effect=track_pop),
        patch("runner.instrument_pipeline.simulate", side_effect=track_sim),
        patch("runner.instrument_pipeline.compute_candidate_fingerprint", side_effect=track_fp),
        patch("runner.instrument_pipeline.detect_order_flow_events", return_value=[]),
        patch("runner.instrument_pipeline.detect_bias_evidence", return_value=[]),
        patch("runner.instrument_pipeline.evaluate_direction_policies", return_value=()),
        patch("runner.instrument_pipeline.build_direction_policy_observations", return_value=()),
        patch("runner.instrument_pipeline.detect_fvgs", return_value=[]),
        patch("runner.instrument_pipeline.fvg_to_key_levels", return_value=[]),
        patch("runner.instrument_pipeline.detect_ict_order_blocks", return_value=[]),
        patch("runner.instrument_pipeline.ob_to_key_levels", return_value=[]),
    ):
        mock_series = MagicMock()
        mock_series.candles = []
        mock_series.instrument = "EURUSDm"
        mock_load.return_value = mock_series

        from runner.instrument_pipeline import process_instrument

        records = tuple(
            DatasetFileRecord(
                "EURUSDm", g, f"data/EURUSDm_{g}.csv", 100, f"hash_{g}",
                datetime(2025, 1, 1), datetime(2026, 1, 1),
            )
            for g in ("M15", "H4", "D1")
        )
        manifest = MagicMock(spec=Manifest)
        manifest.dataset_records = records
        manifest.candidate_cutoff_end_utc = datetime(2026, 6, 1)
        manifest.outcome_followup_end_utc = datetime(2026, 9, 1)
        manifest.instrument_order = ("EURUSDm",)
        manifest.dataset_gap_allowlist = ()

        process_instrument("EURUSDm", manifest, DetectorConfig(), ".")

    fp_idx = call_order.index("fingerprint")
    sim_idx = call_order.index("simulate")
    assert fp_idx < sim_idx


def test_cardinality_mismatch_aborts():
    """Cardinality mismatch aborts the run."""
    from datetime import datetime
    from adapter.manifest import DatasetFileRecord, Manifest
    from core.config import DetectorConfig
    from runner.errors import AuthorizationError

    mock_pop = MagicMock()
    mock_pop.candidates = [MagicMock(), MagicMock()]
    mock_pop.series = MagicMock()

    mock_recon = MagicMock()
    mock_recon.excluded_never_filled = 99

    with (
        patch("runner.instrument_pipeline._load_and_validate_series") as mock_load,
        patch("runner.instrument_pipeline.generate_causal_aligned_signals", return_value=[]),
        patch("runner.instrument_pipeline.detect_swings", return_value=[]),
        patch("runner.instrument_pipeline.build_stage6_population", return_value=mock_pop),
        patch("runner.instrument_pipeline.simulate", return_value=([], mock_recon)),
        patch("runner.instrument_pipeline.compute_candidate_fingerprint", return_value="fp"),
        patch("runner.instrument_pipeline.detect_fvgs", return_value=[]),
        patch("runner.instrument_pipeline.fvg_to_key_levels", return_value=[]),
        patch("runner.instrument_pipeline.detect_ict_order_blocks", return_value=[]),
        patch("runner.instrument_pipeline.ob_to_key_levels", return_value=[]),
    ):
        mock_series = MagicMock()
        mock_series.candles = []
        mock_series.instrument = "EURUSDm"
        mock_load.return_value = mock_series

        from runner.instrument_pipeline import process_instrument

        records = tuple(
            DatasetFileRecord(
                "EURUSDm", g, f"data/EURUSDm_{g}.csv", 100, f"hash_{g}",
                datetime(2025, 1, 1), datetime(2026, 1, 1),
            )
            for g in ("M15", "H4", "D1")
        )
        manifest = MagicMock(spec=Manifest)
        manifest.dataset_records = records
        manifest.candidate_cutoff_end_utc = datetime(2026, 6, 1)
        manifest.outcome_followup_end_utc = datetime(2026, 9, 1)
        manifest.instrument_order = ("EURUSDm",)
        manifest.dataset_gap_allowlist = ()

        with pytest.raises(AuthorizationError, match="cardinality"):
            process_instrument("EURUSDm", manifest, DetectorConfig(), ".")


def test_dataset_callback_runs_after_three_loads_before_causal_generation():
    from datetime import datetime

    from adapter.manifest import DatasetFileRecord, Manifest
    from core.config import DetectorConfig
    from runner.instrument_pipeline import process_instrument

    records = tuple(
        DatasetFileRecord(
            "EURUSDm", granularity, f"data/{granularity}.csv", 1, "hash",
            datetime(2025, 1, 1), datetime(2026, 1, 1),
        )
        for granularity in ("M15", "H4", "D1")
    )
    manifest = MagicMock(spec=Manifest)
    manifest.dataset_records = records
    manifest.candidate_cutoff_end_utc = datetime(2026, 6, 1)
    manifest.outcome_followup_end_utc = datetime(2026, 9, 1)
    order = []

    def loaded(*args):
        order.append("load")
        return MagicMock()

    def causal(*args, **kwargs):
        order.append("causal")
        raise RuntimeError("stop after boundary")

    with (
        patch("runner.instrument_pipeline._load_and_validate_series", side_effect=loaded),
        patch("runner.instrument_pipeline.generate_causal_aligned_signals", side_effect=causal),
        patch("runner.instrument_pipeline.detect_fvgs", return_value=[]),
        patch("runner.instrument_pipeline.fvg_to_key_levels", return_value=[]),
        patch("runner.instrument_pipeline.detect_ict_order_blocks", return_value=[]),
        patch("runner.instrument_pipeline.ob_to_key_levels", return_value=[]),
    ):
        with pytest.raises(RuntimeError, match="stop after boundary"):
            process_instrument(
                "EURUSDm", manifest, DetectorConfig(), ".",
                on_dataset_validated=lambda instrument: order.append(f"validated:{instrument}"),
            )

    assert order == ["load", "load", "load", "validated:EURUSDm", "causal"]


def _nonempty_series() -> OHLCSeries:
    start = datetime(2026, 1, 1, 12)
    prices = (
        (1.1000, 1.1010, 1.0990, 1.1005),
        (1.1005, 1.1010, 1.1000, 1.1005),
        (1.1002, 1.1008, 1.1001, 1.1004),
        (1.1003, 1.1006, 1.1001, 1.1002),
        (1.1020, 1.1025, 1.0995, 1.1010),
        (1.1000, 1.1010, 1.0995, 1.1002),
    )
    return OHLCSeries(
        tuple(
            Candle(start + timedelta(minutes=15 * index), open_, high, low, close)
            for index, (open_, high, low, close) in enumerate(prices)
        ),
        "EURUSDm",
        "15M",
    )


def _causal_signal(retest_index: int, anchor_index: int = 0) -> AlignedSignal:
    signal = Model1Signal(
        anchor_index=anchor_index,
        direction="bullish",
        purge_target=1.0990,
        confirmation_type="purge_engulf",
        entry_type="body",
        entry_price=1.1000,
        retest_index=retest_index,
        status=DetectionStatus.CONFIRMED,
        confirmation_index=retest_index,
        origin_index=anchor_index,
    )
    context = CRTRange(
        "2-candle", 1.1050, 1.0950, 0, 1, "true_break", 1
    )
    key_level = KeyLevel("fvg", 1.1050, 1.0950, 0)
    return AlignedSignal(signal, context, "aligned", key_level)


def test_strict_cutoff_keeps_one_nonempty_list_for_population_and_simulation():
    from runner.instrument_pipeline import process_instrument

    series = _nonempty_series()
    cutoff = series.candles[4].timestamp
    retained = _causal_signal(3)
    boundary = _causal_signal(4, anchor_index=1)
    records = tuple(
        DatasetFileRecord(
            "EURUSDm", granularity, f"data/{granularity}.csv", 1, "hash",
            series.candles[0].timestamp, series.candles[-1].timestamp,
        )
        for granularity in ("M15", "H4", "D1")
    )
    manifest = MagicMock(spec=Manifest)
    manifest.dataset_records = records
    manifest.candidate_cutoff_end_utc = cutoff
    manifest.outcome_followup_end_utc = series.candles[-1].timestamp
    manifest.dataset_gap_allowlist = ()

    with (
        patch(
            "runner.instrument_pipeline._load_and_validate_series",
            side_effect=(series, series, series),
        ),
        patch(
            "runner.instrument_pipeline.generate_causal_aligned_signals",
            return_value=[retained, boundary],
        ) as causal,
        patch("runner.instrument_pipeline.detect_fvgs", return_value=[]),
        patch("runner.instrument_pipeline.fvg_to_key_levels", return_value=[]),
        patch("runner.instrument_pipeline.detect_ict_order_blocks", return_value=[]),
        patch("runner.instrument_pipeline.ob_to_key_levels", return_value=[]),
        patch(
            "runner.instrument_pipeline.build_stage6_population",
            wraps=build_stage6_population,
        ) as population_call,
        patch("runner.instrument_pipeline.simulate", wraps=simulate) as simulate_call,
    ):
        result = process_instrument("EURUSDm", manifest, DetectorConfig(), ".")

    causal.assert_called_once()
    population_call.assert_called_once()
    simulate_call.assert_called_once()
    admitted = population_call.call_args.args[0]
    assert admitted is simulate_call.call_args.args[0]
    assert admitted == [retained]
    assert admitted[0] is retained
    assert result.candidate_count == 1
    assert len(result.observations) == 4
    assert {row.candidate_id.signal_id for row in result.observations} == {
        retained.ltf_signal.signal_id
    }
    assert all(row.candidate_id.retest_index == 3 for row in result.observations)
