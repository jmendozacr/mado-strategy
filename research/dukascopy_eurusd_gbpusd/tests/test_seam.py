"""Synthetic tests for the Dukascopy research seam.

All tests use in-memory fixtures only — no filesystem I/O, no real CSVs,
no production modules are modified.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from core.candle import Candle, OHLCSeries
from core.config import DetectorConfig
from research.dukascopy_eurusd_gbpusd.adapter import OHLCVBar
from research.dukascopy_eurusd_gbpusd.seam import (
    APPROVED_STRATEGY_INSTRUMENTS,
    EXCLUSION_THRESHOLD,
    ExclusionThresholdError,
    SeamInstrumentResult,
    check_exclusion_threshold,
    ohlcvbar_to_series,
    run_instrument_seam,
    run_statistics,
)
from runner.errors import AuthorizationError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_UTC = timezone.utc

_EURUSD = "DUKASCOPY_EURUSD"
_GBPUSD = "DUKASCOPY_GBPUSD"


def _aware_bar(minutes_offset: int) -> OHLCVBar:
    """One UTC-aware OHLCVBar anchored at 2023-01-02 00:00Z + offset."""
    ts = datetime(2023, 1, 2, 0, 0, 0, tzinfo=_UTC) + timedelta(minutes=minutes_offset)
    return OHLCVBar(timestamp=ts, open=1.1000, high=1.1010, low=1.0990, close=1.1005, volume=100.0)


def _flat_bars(n: int, timeframe_minutes: int) -> list[OHLCVBar]:
    """n UTC-aware OHLCVBars with identical flat prices, spaced by timeframe."""
    return [
        OHLCVBar(
            timestamp=datetime(2023, 1, 2, 0, 0, 0, tzinfo=_UTC) + timedelta(minutes=i * timeframe_minutes),
            open=1.1000,
            high=1.1000,
            low=1.1000,
            close=1.1000,
            volume=1.0,
        )
        for i in range(n)
    ]


def _minimal_naive_series(instrument: str, timeframe: str, n: int = 60) -> OHLCSeries:
    """Flat-price naive-UTC OHLCSeries that generates no CRT signals."""
    step = {"15M": timedelta(minutes=15), "H4": timedelta(hours=4), "D1": timedelta(days=1)}[timeframe]
    base = datetime(2023, 1, 2, 0, 0, 0)  # naive-UTC
    candles = tuple(
        Candle(timestamp=base + i * step, open=1.1, high=1.1, low=1.1, close=1.1)
        for i in range(n)
    )
    return OHLCSeries(candles=candles, instrument=instrument, timeframe=timeframe)


# ---------------------------------------------------------------------------
# ohlcvbar_to_series — conversion and validation
# ---------------------------------------------------------------------------


def test_ohlcvbar_to_series_strips_timezone():
    """UTC-aware OHLCVBar timestamps become naive-UTC Candle timestamps."""
    bars = [_aware_bar(0)]
    series = ohlcvbar_to_series(bars, _EURUSD, 15)
    assert series.candles[0].timestamp.tzinfo is None


def test_ohlcvbar_to_series_preserves_utc_value():
    """Stripping tzinfo preserves the UTC datetime value, not local time."""
    ts_aware = datetime(2023, 6, 15, 3, 0, 0, tzinfo=_UTC)  # UTC+3 DST period
    bar = OHLCVBar(timestamp=ts_aware, open=1.1, high=1.2, low=1.0, close=1.15, volume=1.0)
    series = ohlcvbar_to_series([bar], _EURUSD, 15)
    assert series.candles[0].timestamp == datetime(2023, 6, 15, 3, 0, 0)


def test_ohlcvbar_to_series_preserves_ohlc():
    """OHLC values are passed through unchanged; volume is not carried."""
    bar = OHLCVBar(
        timestamp=datetime(2023, 1, 2, 0, 0, 0, tzinfo=_UTC),
        open=1.2345, high=1.2350, low=1.2340, close=1.2348, volume=999.0,
    )
    series = ohlcvbar_to_series([bar], _GBPUSD, 240)
    c = series.candles[0]
    assert c.open == 1.2345
    assert c.high == 1.2350
    assert c.low == 1.2340
    assert c.close == 1.2348


def test_ohlcvbar_to_series_sets_instrument_and_timeframe():
    bars = _flat_bars(3, 15)
    series = ohlcvbar_to_series(bars, _EURUSD, 15)
    assert series.instrument == _EURUSD
    assert series.timeframe == "15M"

    series_h4 = ohlcvbar_to_series(bars[:3], _GBPUSD, 240)
    assert series_h4.timeframe == "H4"

    series_d1 = ohlcvbar_to_series(bars[:3], _GBPUSD, 1440)
    assert series_d1.timeframe == "D1"


def test_ohlcvbar_to_series_rejects_unknown_instrument():
    with pytest.raises(ValueError, match="instrument"):
        ohlcvbar_to_series([_aware_bar(0)], "EURUSD", 15)  # raw provider label, not strategy id


def test_ohlcvbar_to_series_rejects_unapproved_timeframe():
    with pytest.raises(ValueError, match="timeframe_minutes"):
        ohlcvbar_to_series([_aware_bar(0)], _EURUSD, 60)  # H1 not in approved set


def test_ohlcvbar_to_series_empty_bars():
    series = ohlcvbar_to_series([], _EURUSD, 15)
    assert series.candles == ()
    assert series.instrument == _EURUSD


# ---------------------------------------------------------------------------
# check_exclusion_threshold — fail-closed gate
# ---------------------------------------------------------------------------


def test_exclusion_below_threshold_passes():
    """29% exclusion must not raise."""
    check_exclusion_threshold(100, 29)


def test_exclusion_at_threshold_passes():
    """Exactly 30% must not raise (the threshold is exclusive)."""
    check_exclusion_threshold(100, 30)


def test_exclusion_above_threshold_raises():
    """31% exclusion must raise."""
    with pytest.raises(ExclusionThresholdError, match="31"):
        check_exclusion_threshold(100, 31)


def test_exclusion_zero_eligible_raises():
    """Zero-eligible population must always raise — no population, no run."""
    with pytest.raises(ExclusionThresholdError, match="zero"):
        check_exclusion_threshold(0, 0)


def test_exclusion_threshold_constant_matches_protocol():
    """The 30% threshold is the one approved in the signed protocol."""
    assert EXCLUSION_THRESHOLD == 0.30


# ---------------------------------------------------------------------------
# run_statistics — threading to canonical EST-B path
# ---------------------------------------------------------------------------


def test_run_statistics_empty_observations_returns_result():
    """Empty observation list produces a StatisticsResult without error.

    All estimands are NOT_ESTIMABLE / NOT_COMPUTABLE; no nominee is returned.
    This confirms the seam correctly threads to compute_all_statistics.
    """
    from runner.statistics_bridge import StatisticsResult

    result = run_statistics([], (_EURUSD, _GBPUSD))
    assert isinstance(result, StatisticsResult)
    assert result.nomination.nominee is None


def test_run_statistics_respects_instruments_tuple():
    """The instruments tuple is passed through to the resample plan."""
    from runner.statistics_bridge import StatisticsResult

    result = run_statistics([], (_EURUSD,))
    assert isinstance(result, StatisticsResult)
    assert result.plan.instruments == (_EURUSD,)


# ---------------------------------------------------------------------------
# run_instrument_seam — pipeline plumbing with no-signal series
# ---------------------------------------------------------------------------


def test_run_instrument_seam_flat_series_returns_empty_observations():
    """A flat-price series generates no CRT signals; the seam must return
    a SeamInstrumentResult with an empty observations tuple.  This validates
    the pipeline plumbing end to end without executing against real data.
    """
    instrument = _EURUSD
    ltf = _minimal_naive_series(instrument, "15M", 60)
    htf = _minimal_naive_series(instrument, "H4", 30)
    daily = _minimal_naive_series(instrument, "D1", 20)

    config = DetectorConfig()
    cutoff = datetime(2030, 1, 1)          # naive-UTC, far future
    followup = datetime(2030, 12, 31)      # naive-UTC, far future

    result = run_instrument_seam(ltf, htf, daily, config, cutoff, followup)
    assert isinstance(result, SeamInstrumentResult)
    assert len(result.observations) == 0


def test_run_instrument_seam_works_for_gbpusd():
    """Seam is not instrument-specific; GBPUSD series yields the same empty result."""
    instrument = _GBPUSD
    ltf = _minimal_naive_series(instrument, "15M", 60)
    htf = _minimal_naive_series(instrument, "H4", 30)
    daily = _minimal_naive_series(instrument, "D1", 20)

    config = DetectorConfig()
    cutoff = datetime(2030, 1, 1)
    followup = datetime(2030, 12, 31)

    result = run_instrument_seam(ltf, htf, daily, config, cutoff, followup)
    assert isinstance(result, SeamInstrumentResult)
    assert len(result.observations) == 0


# ---------------------------------------------------------------------------
# run_instrument_seam — candidate fingerprint parity
# ---------------------------------------------------------------------------


def test_run_instrument_seam_result_carries_candidate_fingerprint():
    """SeamInstrumentResult.candidate_fingerprint must be a 64-char hex SHA-256."""
    instrument = _EURUSD
    ltf = _minimal_naive_series(instrument, "15M", 60)
    htf = _minimal_naive_series(instrument, "H4", 30)
    daily = _minimal_naive_series(instrument, "D1", 20)

    result = run_instrument_seam(ltf, htf, daily, DetectorConfig(), datetime(2030, 1, 1), datetime(2030, 12, 31))
    fp = result.candidate_fingerprint
    assert isinstance(fp, str)
    assert len(fp) == 64
    assert all(c in "0123456789abcdef" for c in fp)


def test_run_instrument_seam_candidate_count_zero_for_no_signal_series():
    """Flat series produces no candidates; candidate_count must be 0."""
    instrument = _GBPUSD
    ltf = _minimal_naive_series(instrument, "15M", 60)
    htf = _minimal_naive_series(instrument, "H4", 30)
    daily = _minimal_naive_series(instrument, "D1", 20)

    result = run_instrument_seam(ltf, htf, daily, DetectorConfig(), datetime(2030, 1, 1), datetime(2030, 12, 31))
    assert result.candidate_count == 0


def test_run_instrument_seam_fingerprint_deterministic():
    """Same flat series must produce the same fingerprint across two calls."""
    instrument = _EURUSD
    ltf = _minimal_naive_series(instrument, "15M", 60)
    htf = _minimal_naive_series(instrument, "H4", 30)
    daily = _minimal_naive_series(instrument, "D1", 20)

    r1 = run_instrument_seam(ltf, htf, daily, DetectorConfig(), datetime(2030, 1, 1), datetime(2030, 12, 31))
    r2 = run_instrument_seam(ltf, htf, daily, DetectorConfig(), datetime(2030, 1, 1), datetime(2030, 12, 31))
    assert r1.candidate_fingerprint == r2.candidate_fingerprint


# ---------------------------------------------------------------------------
# run_instrument_seam — candidate cardinality validation
# ---------------------------------------------------------------------------


def test_run_instrument_seam_cardinality_mismatch_raises_authorization_error():
    """Population-vs-simulation cardinality mismatch must raise AuthorizationError.

    Patches build_stage6_population to return 1 phantom candidate while simulate
    returns 0 trades and 0 excluded_never_filled — forcing a 1 != 0 mismatch.
    """
    from unittest.mock import MagicMock, patch

    instrument = _EURUSD
    ltf = _minimal_naive_series(instrument, "15M", 60)
    htf = _minimal_naive_series(instrument, "H4", 30)
    daily = _minimal_naive_series(instrument, "D1", 20)

    fake_candidate = MagicMock()
    fake_candidate.retest_index = 0
    fake_candidate.signal_id = "s0"
    fake_candidate.anchor_index = 0
    fake_candidate.origin_index = 0
    fake_candidate.direction = "long"
    fake_candidate.entry_type = "limit"
    fake_candidate.entry_price = 1.1
    fake_candidate.stop_loss = 1.0
    fake_candidate.take_profit = 1.2
    fake_candidate.partial_price = 1.15

    fake_population = MagicMock()
    fake_population.candidates = [fake_candidate]

    fake_reconciliation = MagicMock()
    fake_reconciliation.excluded_never_filled = 0

    with (
        patch("research.dukascopy_eurusd_gbpusd.seam.build_stage6_population", return_value=fake_population),
        patch("research.dukascopy_eurusd_gbpusd.seam.simulate", return_value=([], fake_reconciliation)),
    ):
        with pytest.raises(AuthorizationError, match="cardinality mismatch"):
            run_instrument_seam(ltf, htf, daily, DetectorConfig(), datetime(2030, 1, 1), datetime(2030, 12, 31))


def test_run_instrument_seam_cardinality_holds_for_zero_candidate_result():
    """Zero candidates + zero trades + zero excluded = cardinality satisfied (no raise)."""
    instrument = _EURUSD
    ltf = _minimal_naive_series(instrument, "15M", 60)
    htf = _minimal_naive_series(instrument, "H4", 30)
    daily = _minimal_naive_series(instrument, "D1", 20)

    # Flat series guarantees 0 candidates — this must not raise
    result = run_instrument_seam(ltf, htf, daily, DetectorConfig(), datetime(2030, 1, 1), datetime(2030, 12, 31))
    assert result.candidate_count == 0


# ---------------------------------------------------------------------------
# APPROVED_STRATEGY_INSTRUMENTS contract
# ---------------------------------------------------------------------------


def test_approved_strategy_instruments():
    assert _EURUSD in APPROVED_STRATEGY_INSTRUMENTS
    assert _GBPUSD in APPROVED_STRATEGY_INSTRUMENTS
    assert "EURUSD" not in APPROVED_STRATEGY_INSTRUMENTS  # raw provider label rejected
