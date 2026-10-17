from dataclasses import replace
from datetime import datetime, timedelta

from alignment.htf_ltf import AlignedSignal
from backtest import simulate as simulation
from backtest.population import build_stage6_population
from core.candle import Candle, OHLCSeries
from core.config import DetectorConfig
from core.key_level import KeyLevel
from core.results import DetectionStatus
from entries.model1 import Model1Signal
from evaluation.direction import DirectionEvidence, evaluate_direction_policies
from primitives.bias import BiasEvidence
from primitives.crt_range import CRTRange


def _series() -> OHLCSeries:
    start = datetime(2026, 1, 1, 12)
    return OHLCSeries(
        candles=tuple(
            Candle(
                timestamp=start + timedelta(minutes=15 * index),
                open=open_,
                high=high,
                low=low,
                close=close,
            )
            for index, (open_, high, low, close) in enumerate(
                (
                    (1.1000, 1.1010, 1.0990, 1.1005),
                    (1.1005, 1.1010, 1.1000, 1.1005),
                    (1.1002, 1.1008, 1.1001, 1.1004),
                    (1.1003, 1.1006, 1.1001, 1.1002),
                    (1.1020, 1.1025, 1.0995, 1.1010),
                    (1.1000, 1.1010, 1.0995, 1.1002),
                )
            )
        ),
        instrument="EURUSDm",
        timeframe="15M",
    )


def _aligned_signal() -> AlignedSignal:
    signal = Model1Signal(
        anchor_index=0,
        direction="bullish",
        purge_target=0.0,
        confirmation_type="purge_engulf",
        entry_type="body",
        entry_price=0.0,
        retest_index=3,
        status=DetectionStatus.CONFIRMED,
        confirmation_index=3,
        origin_index=0,
    )
    return AlignedSignal(
        ltf_signal=signal,
        htf_context=CRTRange(
            model="2-candle",
            high=1.1050,
            low=1.0950,
            start_index=0,
            end_index=1,
            resolution="true_break",
            resolved_at_index=1,
        ),
        aligned="aligned",
        key_level=KeyLevel(kind="fvg", top=1.1050, bottom=1.0950, origin_index=0, expiry_index=None),
    )


def _evidence(series: OHLCSeries) -> DirectionEvidence:
    return DirectionEvidence(
        series=series,
        order_flow_events=(),
        bias_evidence=tuple(
            BiasEvidence(
                observation_index=index,
                close_relation="above",
                close_signal="bullish",
                wick_signal="bullish",
            )
            for index in range(1, len(series.candles))
        ),
    )


def test_stage6_population_is_consumed_unchanged_by_fill_and_evaluation(monkeypatch):
    series = _series()
    signals = [_aligned_signal()]
    observed = {}
    real_producer = build_stage6_population
    real_fill_pass = simulation._fill_pass

    def capture_population(*args, **kwargs):
        population = real_producer(*args, **kwargs)
        observed["population"] = population
        return population

    def capture_fill(candidates, *args, **kwargs):
        observed["fill_candidates"] = candidates
        return real_fill_pass(candidates, *args, **kwargs)

    monkeypatch.setattr(simulation, "build_stage6_population", capture_population)
    monkeypatch.setattr(simulation, "_fill_pass", capture_fill)

    trades, report = simulation.simulate(signals, series, DetectorConfig())
    rows = evaluate_direction_policies(observed["population"], _evidence(series))

    assert observed["fill_candidates"] is observed["population"].candidates
    assert [(candidate.signal_id, candidate.direction, candidate.retest_index) for candidate in observed["population"].candidates] == [
        ("0-0-bullish-purge_engulf-body", "bullish", 3)
    ]
    assert len(rows) == 4
    assert report.trades_opened == len(trades) == 1
    assert (
        report.excluded_no_crt_range,
        report.excluded_unaligned,
        report.excluded_confirmed_no_retest,
        report.excluded_never_confirmed,
        report.excluded_no_key_level,
        report.excluded_duplicate,
        report.excluded_kill_zone,
        report.excluded_rr_floor,
        report.excluded_never_filled,
    ) == (0, 0, 0, 0, 0, 0, 0, 0, 0)


def test_stage6_population_preserves_duplicate_and_rr_exclusion_counts():
    series = _series()
    duplicate = _aligned_signal()
    low_reward = _aligned_signal()
    low_reward = AlignedSignal(
        ltf_signal=replace(low_reward.ltf_signal, anchor_index=1, origin_index=1),
        htf_context=CRTRange(
            model="2-candle",
            high=1.1010,
            low=1.0950,
            start_index=0,
            end_index=1,
            resolution="true_break",
            resolved_at_index=1,
        ),
        aligned=low_reward.aligned,
        key_level=low_reward.key_level,
    )

    population = build_stage6_population([_aligned_signal(), duplicate, low_reward], series, DetectorConfig())

    assert len(population.candidates) == 1
    assert population.series is series
    assert population.excluded_duplicate == 1
    assert population.excluded_rr_floor == 1


def test_simulate_keeps_the_existing_fill_and_report_result():
    trades, report = simulation.simulate([_aligned_signal()], _series(), DetectorConfig())

    assert [(trade.signal_id, trade.entry_index, trade.outcome) for trade in trades] == [
        ("0-0-bullish-purge_engulf-body", 4, "open")
    ]
    assert report == simulation.ReconciliationReport(
        signals_considered=1,
        trades_opened=1,
        excluded_no_crt_range=0,
        excluded_unaligned=0,
        excluded_confirmed_no_retest=0,
        excluded_never_confirmed=0,
        excluded_no_key_level=0,
        excluded_duplicate=0,
        excluded_kill_zone=0,
        excluded_rr_floor=0,
        excluded_never_filled=0,
    )


def test_confirmed_signal_without_retest_is_distinct_from_never_confirmed():
    """REQ-30.3/40.5/40.6: retest_index is None splits by status -- a
    signal that reached confirmation (status PENDING: the anchor's body was
    engulfed but the retest sequence never completed) is
    excluded_confirmed_no_retest, while a signal invalidated before ever
    confirming (status INVALIDATED) is excluded_never_confirmed. Neither
    produces a candidate."""
    series = _series()
    base = _aligned_signal()
    confirmed_no_retest = AlignedSignal(
        ltf_signal=replace(base.ltf_signal, retest_index=None, status=DetectionStatus.PENDING, origin_index=1),
        htf_context=base.htf_context, aligned=base.aligned, key_level=base.key_level,
    )
    never_confirmed = AlignedSignal(
        ltf_signal=replace(base.ltf_signal, retest_index=None, status=DetectionStatus.INVALIDATED, origin_index=2),
        htf_context=base.htf_context, aligned=base.aligned, key_level=base.key_level,
    )

    population = build_stage6_population([confirmed_no_retest, never_confirmed], series, DetectorConfig())

    assert population.candidates == []
    assert population.excluded_confirmed_no_retest == 1
    assert population.excluded_never_confirmed == 1
