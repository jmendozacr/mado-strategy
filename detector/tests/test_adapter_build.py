"""The transactional facade (spec.md Section O, REQ-STAT-01/03/19-30): one
end-to-end synthetic run (real detection/alignment/backtest pipeline calls,
fabricated OHLC fixture values — never real MT5/discovery data) proving
Group K (same economic outcome across P1-P4), 4N cardinality, deterministic
ordering, and fail-before-statistics/no-partial-output."""

from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from adapter.build import build_direction_policy_observations
from adapter.bundle import InstrumentRunBundle
from adapter.errors import AdapterIntegrityError
from alignment.htf_ltf import tag_alignment
from backtest.population import build_stage6_population
from backtest.simulate import ReconciliationReport, Trade, simulate
from composite.order_flow import OrderFlowEvent
from core.candle import Candle, OHLCSeries
from core.config import BacktestConfig, DetectorConfig
from evaluation.direction import DirectionEvidence, FROZEN_POLICY_IDS, evaluate_direction_policies
from primitives.bias import BiasEvidence
from primitives.fvg import detect_fvgs, to_key_levels
from primitives.swing import SwingPoint
from selection.model import OutcomeState, Relation

# Synthetic fixture (fabricated OHLC values, no real MT5/discovery data):
# one CONFIRMED bearish Model-1 signal, purging an HTF Daily CRT range
# credited with an FVG-sourced Key Level, filling and closing as a WIN.
_LTF_CANDLES = [
    (1.1000, 1.1020, 1.0980, 1.1010),
    (1.1010, 1.1035, 1.1000, 1.1015),  # anchor
    (1.1000, 1.1005, 1.0950, 1.0960),  # confirms
    (1.0960, 1.1012, 1.0955, 1.0965),  # retest + fills (retest_index=3)
    (1.0965, 1.1010, 1.0790, 1.0910),  # expansion -> CONFIRMED; closes the trade
]
_HTF_DAILY = [
    ("2026.07.02", 1.1060, 1.1065, 1.1040, 1.1045),
    ("2026.07.03", 1.1042, 1.1044, 1.1034, 1.1036),
    ("2026.07.04", 1.1028, 1.1030, 1.1020, 1.1022),
    ("2026.07.05", 1.1020, 1.1028, 1.0900, 1.0910),
    ("2026.07.06", 1.0915, 1.1035, 1.0905, 1.0920),
    ("2026.07.07", 1.0920, 1.0930, 1.0910, 1.0925),
]
_SWING_LOW = SwingPoint(index=0, price=1.0, kind="low")
_SWING_HIGH = SwingPoint(index=1, price=2.0, kind="high")


def _build_synthetic_bundle() -> InstrumentRunBundle:
    config = DetectorConfig(backtest=BacktestConfig(kill_zone_gated=False))
    ltf_candles = tuple(
        Candle(timestamp=datetime(2026, 7, 6, 10, 0) + timedelta(minutes=15 * i), open=o, high=h, low=l, close=c)
        for i, (o, h, l, c) in enumerate(_LTF_CANDLES)
    )
    ltf_series = OHLCSeries(candles=ltf_candles, instrument="EURUSDm", timeframe="15M")
    htf_candles = tuple(
        Candle(timestamp=datetime(2026, 7, 2) + timedelta(days=i), open=o, high=h, low=l, close=c)
        for i, (_, o, h, l, c) in enumerate(_HTF_DAILY)
    )
    htf_series = OHLCSeries(candles=htf_candles, instrument="EURUSDm", timeframe="D")

    htf_key_levels = to_key_levels(detect_fvgs(htf_series, config.fvg))
    tagged = tag_alignment(
        htf_series, ltf_series, config.crt_range, config.fvg, config.model1, htf_key_levels=htf_key_levels
    )
    population = build_stage6_population(tagged, ltf_series, config)
    assert len(population.candidates) == 1  # fixture sanity, not the adapter under test

    trades, report = simulate(tagged, ltf_series, config)
    candidate = population.candidates[0]

    evidence = DirectionEvidence(
        series=ltf_series,
        order_flow_events=(
            OrderFlowEvent(
                direction=candidate.direction, rejection_reference=_SWING_LOW,
                break_reference=_SWING_HIGH, rejection_index=0, confirmation_index=1,
            ),
        ),
        bias_evidence=tuple(
            BiasEvidence(observation_index=i, close_relation="inside", close_signal=None, wick_signal=None)
            for i in range(1, len(ltf_candles))
        ),
    )
    evaluations = evaluate_direction_policies(population, evidence)

    return InstrumentRunBundle(
        instrument="EURUSDm", population=population, evaluations=evaluations, trades=tuple(trades),
        reconciliation=report, aligned_signals=tuple(tagged),
        candidate_cutoff_end_utc=ltf_candles[-1].timestamp + timedelta(days=1),
        outcome_followup_end_utc=ltf_candles[-1].timestamp + timedelta(days=2),
    )


def test_end_to_end_produces_4n_observations_for_one_candidate():
    bundle = _build_synthetic_bundle()
    observations = build_direction_policy_observations(bundle)
    assert len(observations) == 4 == 4 * len(bundle.population.candidates)


def test_group_k_same_economic_outcome_across_all_four_policies():
    bundle = _build_synthetic_bundle()
    observations = build_direction_policy_observations(bundle)
    assert len({o.candidate_id for o in observations}) == 1
    first = observations[0]
    for obs in observations:
        assert obs.candidate_id == first.candidate_id
        assert obs.context_cluster_id == first.context_cluster_id
        assert obs.outcome_state == first.outcome_state
        assert obs.closed_outcome == first.closed_outcome
        assert obs.realized_r == first.realized_r
    # only relation/policy_id vary
    assert {o.policy_id for o in observations} == set(FROZEN_POLICY_IDS)
    assert first.outcome_state is OutcomeState.CLOSED
    assert first.realized_r == pytest.approx(1.6216216216216535)


def test_relations_are_not_all_identical_real_mapped_values():
    """Confirms the mapping is real (not a stub returning one constant) —
    this fixture's evidence deliberately produces a mix of ALIGNED/UNRESOLVED
    across the 4 policies."""
    bundle = _build_synthetic_bundle()
    observations = build_direction_policy_observations(bundle)
    relations = {o.relation for o in observations}
    assert relations <= {Relation.ALIGNED, Relation.OPPOSED, Relation.UNRESOLVED}
    assert len(relations) > 1


def test_deterministic_ordering_candidate_then_policy_p1_to_p4():
    bundle = _build_synthetic_bundle()
    observations = build_direction_policy_observations(bundle)
    assert [o.policy_id for o in observations] == list(FROZEN_POLICY_IDS)


def test_output_is_an_immutable_tuple():
    bundle = _build_synthetic_bundle()
    observations = build_direction_policy_observations(bundle)
    assert isinstance(observations, tuple)
    with pytest.raises(TypeError):
        observations[0] = observations[1]


def test_broken_aggregate_accounting_raises_before_any_output():
    bundle = _build_synthetic_bundle()
    corrupted = replace(bundle, reconciliation=replace(bundle.reconciliation, excluded_never_filled=999))
    with pytest.raises(AdapterIntegrityError):
        build_direction_policy_observations(corrupted)


def test_orphan_trade_raises_before_any_output():
    bundle = _build_synthetic_bundle()
    orphan_trade = replace(bundle.trades[0], signal_id="no-such-signal")
    corrupted = replace(bundle, trades=(orphan_trade,))
    with pytest.raises(AdapterIntegrityError):
        build_direction_policy_observations(corrupted)


def test_candidate_cutoff_violation_raises_before_any_output():
    bundle = _build_synthetic_bundle()
    # candidate's retest timestamp already >= this cutoff -> ineligible
    retest_timestamp = bundle.population.series.candles[3].timestamp
    corrupted = replace(bundle, candidate_cutoff_end_utc=retest_timestamp)
    with pytest.raises(AdapterIntegrityError):
        build_direction_policy_observations(corrupted)


def test_missing_evaluation_row_raises_before_any_output():
    bundle = _build_synthetic_bundle()
    corrupted = replace(bundle, evaluations=bundle.evaluations[:-1])  # drop the 4th policy row
    with pytest.raises(AdapterIntegrityError):
        build_direction_policy_observations(corrupted)


def test_no_recomputation_adapter_never_imports_policy_direction_functions():
    """REQ-STAT-21: Layer-2 must use frozen DirectionEvaluation rows as-is —
    it must never import policy.direction's decision functions to recompute
    a relation itself."""
    import ast
    from pathlib import Path

    adapter_dir = Path(__file__).resolve().parent.parent / "adapter"
    for path in adapter_dir.glob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("policy"):
                pytest.fail(f"{path.name} imports from {node.module!r} — Layer-2 must never recompute policy decisions")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("policy"):
                        pytest.fail(f"{path.name} imports {alias.name!r} — Layer-2 must never recompute policy decisions")


def test_context_cluster_id_uses_supplied_aligned_signal_context():
    """context_cluster_id reflects the htf_context on the supplied AlignedSignal,
    not any independently computed value. Verified by injecting start_index=99."""
    from dataclasses import replace as dc_replace
    from primitives.crt_range import CRTRange

    bundle = _build_synthetic_bundle()
    candidate_signal_id = bundle.population.candidates[0].signal_id

    original = next(
        s for s in bundle.aligned_signals if s.ltf_signal.signal_id == candidate_signal_id
    )
    assert original.htf_context is not None

    synthetic_context = CRTRange(
        model="2-candle", high=1.5, low=0.5,
        start_index=99, end_index=100, resolution="true_break", resolved_at_index=100,
    )
    amended_signal = dc_replace(original, htf_context=synthetic_context)
    amended_signals = tuple(
        amended_signal if s.ltf_signal.signal_id == candidate_signal_id else s
        for s in bundle.aligned_signals
    )
    amended_bundle = dc_replace(bundle, aligned_signals=amended_signals)

    observations = build_direction_policy_observations(amended_bundle)
    assert len(observations) == 4
    assert all(obs.context_cluster_id[1] == 99 for obs in observations)


def test_no_statistics_adapter_never_imports_layer1_estimator_modules():
    """Layer-2 must never compute MeanR/WR/EST-B/bootstrap/CI/SEL-A itself —
    only `selection.model` (the shared record type + its own construction
    invariant) may be imported, never `selection.{stratify,estimators,
    bootstrap,nomination}`."""
    import ast
    from pathlib import Path

    forbidden = {"selection.stratify", "selection.estimators", "selection.bootstrap", "selection.nomination"}
    adapter_dir = Path(__file__).resolve().parent.parent / "adapter"
    for path in adapter_dir.glob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in forbidden:
                pytest.fail(f"{path.name} imports {node.module!r} — Layer-2 must never compute statistics")
