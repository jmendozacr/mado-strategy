"""Research-only execution seam: bridges OHLCVBar lists from the Dukascopy
adapter into the canonical read-only EST-B evaluation path.

Not imported by any production module.

Timezone note: OHLCVBar.timestamp is UTC-aware (timezone.utc) as returned by
aggregate_ohlcv.  Candle.timestamp is naive-UTC throughout the production repo
(adapter/cutoff.py documents this convention explicitly).  ohlcvbar_to_series
strips tzinfo before constructing each Candle — the value is already UTC, so
the strip is lossless.  The caller must supply naive-UTC datetimes for
candidate_cutoff_end_utc and outcome_followup_end_utc.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from core.candle import Candle, OHLCSeries
from core.config import DetectorConfig
from runner.statistics_bridge import StatisticsResult, compute_all_statistics
from selection.model import DirectionPolicyObservation

from research.dukascopy_eurusd_gbpusd.adapter import APPROVED_TIMEFRAMES, OHLCVBar
from research.dukascopy_eurusd_gbpusd.manifest import (
    RunManifest,
    validate_execution_boundaries,
)

# Production pipeline — read-only calls; no production module is modified
from adapter.build import build_direction_policy_observations
from adapter.bundle import InstrumentRunBundle
from backtest.population import build_stage6_population
from backtest.simulate import simulate
from causal.generate import generate_causal_aligned_signals
from composite.order_flow import detect_order_flow_events
from evaluation.direction import DirectionEvidence, evaluate_direction_policies
from primitives.bias import detect_bias_evidence
from primitives.fvg import detect_fvgs, to_key_levels as fvg_to_key_levels
from primitives.ict_order_block import (
    detect_ict_order_blocks,
    to_key_levels as ob_to_key_levels,
)
from primitives.swing import detect_swings
from runner.candidate_fingerprint import compute_candidate_fingerprint
from runner.errors import AuthorizationError

# These are detector-core labels.  Provider-facing artifact labels remain H4/D1.
_TIMEFRAME_LABELS: dict[int, str] = {15: "15M", 240: "4H", 1440: "D"}


@dataclass(frozen=True)
class SeamInstrumentResult:
    """Return value of run_instrument_seam — mirrors InstrumentResult in
    detector/runner/instrument_pipeline.py without the filesystem fields."""

    observations: tuple[DirectionPolicyObservation, ...]
    candidate_count: int
    candidate_fingerprint: str


APPROVED_STRATEGY_INSTRUMENTS: frozenset[str] = frozenset({
    "DUKASCOPY_EURUSD",
    "DUKASCOPY_GBPUSD",
})

EXCLUSION_THRESHOLD = 0.30


class ExclusionThresholdError(Exception):
    """Raised when the excluded fraction of instrument-days exceeds the
    protocol-approved 30% threshold (fail-closed)."""


def ohlcvbar_to_series(
    bars: list[OHLCVBar],
    instrument: str,
    timeframe_minutes: int,
) -> OHLCSeries:
    """Convert a list of OHLCVBar objects into a production OHLCSeries.

    instrument must be a strategy identity from APPROVED_STRATEGY_INSTRUMENTS.
    timeframe_minutes must be in APPROVED_TIMEFRAMES ({15, 240, 1440}).
    Volume is not carried by Candle and is silently dropped.
    """
    if instrument not in APPROVED_STRATEGY_INSTRUMENTS:
        raise ValueError(
            f"instrument {instrument!r} not in approved set"
            f" {sorted(APPROVED_STRATEGY_INSTRUMENTS)}"
        )
    if timeframe_minutes not in APPROVED_TIMEFRAMES:
        raise ValueError(
            f"timeframe_minutes {timeframe_minutes} not in approved set"
            f" {sorted(APPROVED_TIMEFRAMES)}"
        )
    timeframe_label = _TIMEFRAME_LABELS[timeframe_minutes]
    candles = tuple(
        Candle(
            # OHLCVBar.timestamp is UTC-aware; Candle.timestamp must be
            # naive-UTC per the production convention (adapter/cutoff.py).
            timestamp=bar.timestamp.replace(tzinfo=None),
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
        )
        for bar in bars
    )
    return OHLCSeries(candles=candles, instrument=instrument, timeframe=timeframe_label)


def check_exclusion_threshold(
    total_eligible_instrument_days: int,
    excluded_instrument_days: int,
) -> None:
    """Fail-closed gate: raise when the excluded fraction exceeds 30%.

    A zero-eligible population always raises — no population means no run.
    Exactly 30% is allowed (the threshold is exclusive on the upper end).
    """
    if total_eligible_instrument_days == 0:
        raise ExclusionThresholdError(
            "total_eligible_instrument_days is zero — no population to evaluate"
        )
    fraction = excluded_instrument_days / total_eligible_instrument_days
    if fraction > EXCLUSION_THRESHOLD:
        raise ExclusionThresholdError(
            f"excluded {excluded_instrument_days}/{total_eligible_instrument_days}"
            f" instrument-days ({fraction:.1%}) exceeds the approved"
            f" {EXCLUSION_THRESHOLD:.0%} threshold"
        )


def run_instrument_seam(
    ltf_series: OHLCSeries,
    htf_series: OHLCSeries,
    daily_series: OHLCSeries,
    config: DetectorConfig,
    candidate_cutoff_end_utc: datetime,
    outcome_followup_end_utc: datetime,
    *,
    manifest: RunManifest | None = None,
) -> SeamInstrumentResult:
    """Run the production CRT detection and evaluation pipeline on pre-loaded
    OHLCSeries objects and return a SeamInstrumentResult.

    This mirrors detector/runner/instrument_pipeline.process_instrument without
    the filesystem-loading and manifest-hash-validation steps, which the research
    adapter handles before calling this function.

    candidate_cutoff_end_utc and outcome_followup_end_utc must be naive-UTC
    datetimes per the production convention (adapter/cutoff.py).
    """
    if manifest is not None:
        validate_execution_boundaries(
            manifest, candidate_cutoff_end_utc, outcome_followup_end_utc
        )
    htf_fvgs = detect_fvgs(htf_series, config.fvg)
    htf_key_levels = list(fvg_to_key_levels(htf_fvgs))

    daily_obs = detect_ict_order_blocks(daily_series)
    daily_key_levels = list(ob_to_key_levels(daily_obs))

    causal_signals = generate_causal_aligned_signals(
        ltf_series,
        htf_series,
        config.crt_range,
        config.model1,
        htf_key_levels=htf_key_levels,
        daily_series=daily_series,
        daily_key_levels=daily_key_levels,
    )

    admitted = [
        s for s in causal_signals
        if ltf_series.candles[s.ltf_signal.retest_index].timestamp < candidate_cutoff_end_utc
    ]

    swings = detect_swings(ltf_series, config.swing)
    population = build_stage6_population(admitted, ltf_series, config, swings)

    # Fingerprint BEFORE simulate — candidate universe must be outcome-free
    candidate_fp = compute_candidate_fingerprint(population.candidates)

    trades, reconciliation = simulate(admitted, ltf_series, config, swings)

    # Every candidate must map to exactly one trade or excluded_never_filled
    expected_total = len(trades) + reconciliation.excluded_never_filled
    if len(population.candidates) != expected_total:
        raise AuthorizationError(
            f"cardinality mismatch for {ltf_series.instrument}: "
            f"population has {len(population.candidates)} candidates but "
            f"trades({len(trades)}) + excluded_never_filled"
            f"({reconciliation.excluded_never_filled}) = {expected_total}"
        )

    order_flow_events = tuple(detect_order_flow_events(ltf_series))
    bias_evidence = tuple(detect_bias_evidence(ltf_series))
    evidence = DirectionEvidence(
        series=ltf_series,
        order_flow_events=order_flow_events,
        bias_evidence=bias_evidence,
    )
    evaluations = evaluate_direction_policies(population, evidence)

    bundle = InstrumentRunBundle(
        instrument=ltf_series.instrument,
        population=population,
        evaluations=evaluations,
        trades=tuple(trades),
        reconciliation=reconciliation,
        aligned_signals=tuple(admitted),
        candidate_cutoff_end_utc=candidate_cutoff_end_utc,
        outcome_followup_end_utc=outcome_followup_end_utc,
    )
    observations = build_direction_policy_observations(bundle)
    return SeamInstrumentResult(
        observations=observations,
        candidate_count=len(population.candidates),
        candidate_fingerprint=candidate_fp,
    )


def run_statistics(
    observations: Sequence[DirectionPolicyObservation],
    instruments: tuple[str, ...],
) -> StatisticsResult:
    """Thread pooled observations through the canonical read-only EST-B path.

    instruments must list every strategy instrument whose observations appear
    in the sequence (e.g., ("DUKASCOPY_EURUSD", "DUKASCOPY_GBPUSD")).
    """
    return compute_all_statistics(list(observations), instruments)
