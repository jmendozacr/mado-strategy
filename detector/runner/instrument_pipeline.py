"""Per-instrument sequential pipeline: causal generation, cutoff filtering,
swing detection, population build, simulation, evaluation, observation
construction. One function, one set of local bindings -- same-object
discipline enforced by scope."""

import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import timedelta

from adapter.build import build_direction_policy_observations
from adapter.bundle import InstrumentRunBundle
from adapter.dataset import sha256_of_file, validate_no_gaps_against_manifest
from adapter.manifest import DatasetFileRecord, Manifest
from backtest.population import Stage6Population, build_stage6_population
from backtest.simulate import simulate
from causal.generate import generate_causal_aligned_signals
from composite.order_flow import detect_order_flow_events
from core.candle import OHLCSeries
from core.config import DetectorConfig
from core.key_level import KeyLevel
from evaluation.direction import DirectionEvidence, evaluate_direction_policies
from ingestion.loader import load_mt5_csv
from primitives.bias import detect_bias_evidence
from primitives.fvg import detect_fvgs, to_key_levels as fvg_to_key_levels
from primitives.ict_order_block import (
    detect_ict_order_blocks,
    to_key_levels as ob_to_key_levels,
)
from primitives.swing import detect_swings
from runner.candidate_fingerprint import compute_candidate_fingerprint
from runner.errors import AuthorizationError
from selection.model import DirectionPolicyObservation


@dataclass(frozen=True)
class InstrumentResult:
    instrument: str
    observations: tuple[DirectionPolicyObservation, ...]
    candidate_count: int
    candidate_fingerprint: str


def _find_dataset_record(
    records: Sequence[DatasetFileRecord], instrument: str, granularity: str
) -> DatasetFileRecord:
    matches = [
        r for r in records
        if r.instrument == instrument and r.granularity == granularity
    ]
    if len(matches) == 0:
        raise ValueError(
            f"no dataset record for instrument={instrument!r}, granularity={granularity!r}"
        )
    if len(matches) > 1:
        raise AuthorizationError(
            f"duplicate dataset records for instrument={instrument!r}, "
            f"granularity={granularity!r}: found {len(matches)}"
        )
    return matches[0]


def _load_and_validate_series(
    record: DatasetFileRecord, repo_root: str, manifest: Manifest,
) -> OHLCSeries:
    """Load a series and validate its integrity against the manifest."""
    path = os.path.join(repo_root, record.relative_path)

    actual_size = os.path.getsize(path)
    if actual_size != record.byte_size:
        raise AuthorizationError(
            f"dataset file size mismatch for {path}: "
            f"expected {record.byte_size}, got {actual_size}"
        )

    actual_hash = sha256_of_file(path)
    if actual_hash != record.sha256:
        raise AuthorizationError(
            f"dataset file hash mismatch for {path}: "
            f"expected {record.sha256}, got {actual_hash}"
        )

    series = load_mt5_csv(path, record.instrument)

    _GRANULARITY_TO_INTERVAL = {
        "M15": timedelta(minutes=15),
        "H4": timedelta(hours=4),
        "D1": timedelta(days=1),
    }
    try:
        interval = _GRANULARITY_TO_INTERVAL[record.granularity]
    except KeyError as exc:
        raise AuthorizationError(f"unsupported dataset granularity: {record.granularity}") from exc
    validate_no_gaps_against_manifest(series, interval, manifest)

    return series


def process_instrument(
    instrument: str,
    manifest: Manifest,
    config: DetectorConfig,
    repo_root: str,
    on_dataset_validated: Callable[[str], None] | None = None,
) -> InstrumentResult:
    """Execute the full per-instrument pipeline. Same-object discipline:
    admitted, ltf_series, config, and swings are the IDENTICAL Python objects
    passed to both build_stage6_population and simulate."""
    assert manifest.dataset_records is not None
    assert manifest.candidate_cutoff_end_utc is not None
    assert manifest.outcome_followup_end_utc is not None

    ltf_record = _find_dataset_record(manifest.dataset_records, instrument, "M15")
    htf_record = _find_dataset_record(manifest.dataset_records, instrument, "H4")
    daily_record = _find_dataset_record(manifest.dataset_records, instrument, "D1")

    ltf_series = _load_and_validate_series(ltf_record, repo_root, manifest)
    htf_series = _load_and_validate_series(htf_record, repo_root, manifest)
    daily_series = _load_and_validate_series(daily_record, repo_root, manifest)
    if on_dataset_validated is not None:
        on_dataset_validated(instrument)

    htf_fvgs = detect_fvgs(htf_series, config.fvg)
    htf_key_levels: list[KeyLevel] = list(fvg_to_key_levels(htf_fvgs))

    daily_obs = detect_ict_order_blocks(daily_series)
    daily_key_levels: list[KeyLevel] = list(ob_to_key_levels(daily_obs))

    causal_signals = generate_causal_aligned_signals(
        ltf_series,
        htf_series,
        config.crt_range,
        config.model1,
        htf_key_levels=htf_key_levels,
        daily_series=daily_series,
        daily_key_levels=daily_key_levels,
    )

    candidate_cutoff_end_utc = manifest.candidate_cutoff_end_utc
    admitted = [
        s for s in causal_signals
        if ltf_series.candles[s.ltf_signal.retest_index].timestamp < candidate_cutoff_end_utc
    ]

    swings = detect_swings(ltf_series, config.swing)

    population = build_stage6_population(admitted, ltf_series, config, swings)

    # Fingerprint BEFORE simulate -- candidate universe must be outcome-free
    candidate_fp = compute_candidate_fingerprint(population.candidates)

    assert swings is not None
    trades, reconciliation = simulate(admitted, ltf_series, config, swings)

    # Every candidate must map to exactly one trade or excluded_never_filled
    expected_total = len(trades) + reconciliation.excluded_never_filled
    if len(population.candidates) != expected_total:
        raise AuthorizationError(
            f"cardinality mismatch for {instrument}: "
            f"population has {len(population.candidates)} candidates but "
            f"trades({len(trades)}) + excluded_never_filled({reconciliation.excluded_never_filled}) = {expected_total}"
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
        instrument=instrument,
        population=population,
        evaluations=evaluations,
        trades=tuple(trades),
        reconciliation=reconciliation,
        aligned_signals=tuple(admitted),
        candidate_cutoff_end_utc=manifest.candidate_cutoff_end_utc,
        outcome_followup_end_utc=manifest.outcome_followup_end_utc,
    )
    observations = build_direction_policy_observations(bundle)

    return InstrumentResult(
        instrument=instrument,
        observations=observations,
        candidate_count=len(population.candidates),
        candidate_fingerprint=candidate_fp,
    )
