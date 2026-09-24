"""Group D (spec.md REQ-STAT-23, Section L): instrument-scoped input bundle.
`Trade` carries no `instrument` field, so Layer-2 must never guess it from a
Trade — `instrument` is read from `Stage6Population.series.instrument`."""

from datetime import datetime, timedelta

import pytest

from adapter.bundle import InstrumentRunBundle
from adapter.errors import AdapterIntegrityError
from alignment.htf_ltf import AlignedSignal
from backtest.candidate import Candidate
from backtest.population import Stage6Population
from backtest.simulate import ReconciliationReport
from core.candle import Candle, OHLCSeries
from core.results import DetectionStatus
from entries.model1 import Model1Signal
from primitives.crt_range import CRTRange


def _series(instrument: str = "EURUSDm", timeframe: str = "15M", size: int = 6) -> OHLCSeries:
    candles = tuple(
        Candle(
            timestamp=datetime(2026, 1, 1) + timedelta(minutes=15 * i),
            open=1.0, high=1.1, low=0.9, close=1.05,
        )
        for i in range(size)
    )
    return OHLCSeries(candles=candles, instrument=instrument, timeframe=timeframe)


def _population(series: OHLCSeries, candidates=()) -> Stage6Population:
    return Stage6Population(
        series=series, candidates=list(candidates), excluded_no_crt_range=0, excluded_unaligned=0,
        excluded_never_confirmed=0, excluded_no_key_level=0, excluded_duplicate=0,
        excluded_kill_zone=0, excluded_rr_floor=0,
    )


def _reconciliation(excluded_never_filled: int = 0, trades_opened: int = 0) -> ReconciliationReport:
    return ReconciliationReport(
        signals_considered=0, trades_opened=trades_opened, excluded_no_crt_range=0, excluded_unaligned=0,
        excluded_never_confirmed=0, excluded_no_key_level=0, excluded_duplicate=0, excluded_kill_zone=0,
        excluded_rr_floor=0, excluded_never_filled=excluded_never_filled,
    )


def test_bundle_reads_instrument_from_population_series():
    series = _series(instrument="GBPUSDm")
    bundle = InstrumentRunBundle(
        instrument="GBPUSDm", population=_population(series), evaluations=(), trades=(),
        reconciliation=_reconciliation(), aligned_signals=(),
        candidate_cutoff_end_utc=datetime(2026, 1, 1),
        outcome_followup_end_utc=datetime(2026, 1, 2),
    )
    assert bundle.instrument == "GBPUSDm"


def test_bundle_rejects_instrument_mismatch_with_series():
    series = _series(instrument="EURUSDm")
    with pytest.raises(AdapterIntegrityError):
        InstrumentRunBundle(
            instrument="GBPUSDm", population=_population(series), evaluations=(), trades=(),
            reconciliation=_reconciliation(), aligned_signals=(),
            candidate_cutoff_end_utc=datetime(2026, 1, 1),
            outcome_followup_end_utc=datetime(2026, 1, 2),
        )


def test_bundle_is_immutable():
    series = _series()
    bundle = InstrumentRunBundle(
        instrument="EURUSDm", population=_population(series), evaluations=(), trades=(),
        reconciliation=_reconciliation(), aligned_signals=(),
        candidate_cutoff_end_utc=datetime(2026, 1, 1),
        outcome_followup_end_utc=datetime(2026, 1, 2),
    )
    with pytest.raises(Exception):
        bundle.instrument = "GBPUSDm"


def _make_aligned_signal() -> AlignedSignal:
    signal = Model1Signal(
        anchor_index=1, direction="bullish", purge_target=1.0,
        confirmation_type="purge_engulf", entry_type="wick", entry_price=1.0,
        retest_index=3, status=DetectionStatus.CONFIRMED,
        confirmation_index=2, origin_index=0,
    )
    crt = CRTRange(
        model="2-candle", high=1.2, low=0.8, start_index=0, end_index=1,
        resolution="true_break", resolved_at_index=1,
    )
    return AlignedSignal(ltf_signal=signal, htf_context=crt, aligned="aligned")


def _candidate_with_signal_id(signal_id: str) -> Candidate:
    return Candidate(
        signal_id=signal_id, anchor_index=1, origin_index=0, direction="bullish",
        entry_type="wick", retest_index=3, entry_price=1.0, stop_loss=0.9,
        take_profit=1.2, partial_price=1.1,
    )


def test_bundle_rejects_candidate_with_missing_signal_id():
    series = _series()
    candidate = _candidate_with_signal_id("sig-A")
    population = _population(series, candidates=(candidate,))
    with pytest.raises(AdapterIntegrityError):
        InstrumentRunBundle(
            instrument="EURUSDm", population=population, evaluations=(), trades=(),
            reconciliation=_reconciliation(), aligned_signals=(),
            candidate_cutoff_end_utc=datetime(2026, 1, 1),
            outcome_followup_end_utc=datetime(2026, 1, 2),
        )


def test_bundle_permits_extra_aligned_signals():
    series = _series()
    population = _population(series, candidates=())
    extra_signal = _make_aligned_signal()
    InstrumentRunBundle(
        instrument="EURUSDm", population=population, evaluations=(), trades=(),
        reconciliation=_reconciliation(), aligned_signals=(extra_signal,),
        candidate_cutoff_end_utc=datetime(2026, 1, 1),
        outcome_followup_end_utc=datetime(2026, 1, 2),
    )
