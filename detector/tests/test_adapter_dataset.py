"""Section M dataset conditions Layer-2 owns (#4/#5/#6/#8/#12). Synthetic
temp files via `tempfile`/`tmp_path` only — no real dataset CSV."""

import dataclasses
from datetime import datetime, timedelta

import pytest

from adapter.dataset import (
    load_and_validate_dataset_file,
    sha256_of_file,
    validate_no_gaps,
    validate_no_gaps_against_manifest,
)
from adapter.errors import DatasetIntegrityError
from adapter.manifest import GapAllowlistEntry, Manifest
from core.candle import Candle, OHLCSeries
from evaluation.direction import FROZEN_POLICY_IDS
from fixtures.mt5_csv import write_series_csv


def _manifest(dataset_gap_allowlist: tuple = ()) -> Manifest:
    return Manifest(
        experiment_id="direction-policy-discovery-v1",
        protocol_artifact_path="detector/research/direction_policy_discovery_v1_amendment_1.json",
        protocol_artifact_sha256="47b17d7891f6f9a2d2d30f83df88b060840a895484a78e763c8f46da1ea8de4d",
        direction_policy_implementation_commit="7b09c31877a5e5978e10b6832f5b7f3010276f1d",
        evaluation_seam_spec_commit="6104343488cc0dd6df7b4d311dc2cdf6893f2ccb",
        evaluation_seam_implementation_commit="26d94be6eed49d1883f1454d2ceea0bc0e80b4ac",
        evaluation_seam_closeout_commit="7775a25c011254555c74021e83a4dad044700d83",
        statistical_spec_v3_commit="86c91506132292d5c9076462118cb5d32efe5807",
        layer1_implementation_commit="75d9c37ac08a314a6518484b7e62ee3c7eb798c1",
        policy_ids=tuple(FROZEN_POLICY_IDS),
        dataset_identity="EURUSDm-15M-discovery-window",
        dataset_file_hashes=(("EURUSDm.csv", "aaa"),),
        population_definition_ref="backtest.population.build_stage6_population",
        candidate_identity_fields=("instrument", "timeframe", "signal_id", "retest_index"),
        trade_join_key_fields=("instrument", "signal_id"),
        outcome_fields=("realized_r", "closed_outcome"),
        est_b_definition="mean(realized_r|ALIGNED,CLOSED) - mean(realized_r|OPPOSED,CLOSED)",
        mei_r=0.20,
        cluster_definition_ref="alignment.htf_ltf.tag_alignment",
        bootstrap_config=(("replicates", 10000), ("seed", 20260910)),
        nomination_rule_ref="selection.rule",
        cost_assumptions=(("trading_cost_price", 0.0),),
        protected_paths=("detector/policy/", "detector/evaluation/", "detector/selection/"),
        protected_paths_version="v1",
        dataset_gap_allowlist=dataset_gap_allowlist,
    )


def _series(size: int = 6, interval_minutes: int = 15) -> OHLCSeries:
    candles = tuple(
        Candle(
            timestamp=datetime(2026, 1, 1) + timedelta(minutes=interval_minutes * i),
            open=1.0, high=1.1, low=0.9, close=1.05,
        )
        for i in range(size)
    )
    return OHLCSeries(candles=candles, instrument="EURUSDm", timeframe="15M")


# --- #5 missing files ----------------------------------------------------


def test_missing_dataset_file_fails_closed(tmp_path):
    missing_path = tmp_path / "does_not_exist.csv"
    with pytest.raises(DatasetIntegrityError):
        load_and_validate_dataset_file(missing_path, "EURUSDm", expected_sha256="deadbeef")


# --- #8 hash drift ----------------------------------------------------------


def test_correct_hash_loads_successfully(tmp_path):
    series = _series()
    path = tmp_path / "eurusdm.csv"
    write_series_csv(series, path)
    expected_hash = sha256_of_file(path)

    loaded = load_and_validate_dataset_file(path, "EURUSDm", expected_sha256=expected_hash)
    assert len(loaded.candles) == len(series.candles)


def test_hash_drift_fails_closed(tmp_path):
    series = _series()
    path = tmp_path / "eurusdm.csv"
    write_series_csv(series, path)

    with pytest.raises(DatasetIntegrityError):
        load_and_validate_dataset_file(path, "EURUSDm", expected_sha256="0" * 64)


def test_hash_computed_over_real_file_bytes_changes_on_edit(tmp_path):
    series = _series()
    path = tmp_path / "eurusdm.csv"
    write_series_csv(series, path)
    original_hash = sha256_of_file(path)

    path.write_text(path.read_text() + "\n")  # mutate the file
    assert sha256_of_file(path) != original_hash


# --- #4 duplicate timestamps (delegated to ingestion.loader) ----------------


def test_duplicate_timestamps_fail_closed_as_dataset_integrity_error(tmp_path):
    from fixtures.mt5_csv import MT5_HEADER, _row

    path = tmp_path / "dup.csv"
    rows = [
        MT5_HEADER,
        _row("2026.01.01", "00:00:00", 1.0, 1.1, 0.9, 1.05),
        _row("2026.01.01", "00:00:00", 1.0, 1.1, 0.9, 1.05),  # duplicate timestamp
    ]
    path.write_text("\n".join(rows))
    expected_hash = sha256_of_file(path)

    with pytest.raises(DatasetIntegrityError):
        load_and_validate_dataset_file(path, "EURUSDm", expected_sha256=expected_hash)


# --- #6/#12 boundary gaps / incomplete-session dropping ---------------------


def test_regularly_spaced_series_has_no_gaps():
    validate_no_gaps(_series(size=5, interval_minutes=15), timedelta(minutes=15))  # must not raise


def test_undeclared_gap_fails_closed():
    candles = (
        Candle(timestamp=datetime(2026, 1, 1, 0, 0), open=1.0, high=1.1, low=0.9, close=1.05),
        Candle(timestamp=datetime(2026, 1, 1, 0, 15), open=1.0, high=1.1, low=0.9, close=1.05),
        Candle(timestamp=datetime(2026, 1, 1, 1, 0), open=1.0, high=1.1, low=0.9, close=1.05),  # dropped 2 candles
    )
    series = OHLCSeries(candles=candles, instrument="EURUSDm", timeframe="15M")
    with pytest.raises(DatasetIntegrityError):
        validate_no_gaps(series, timedelta(minutes=15))


def test_declared_gap_start_is_allowed():
    """A pre-registered gap (e.g. a known weekend closure) is not flagged."""
    candles = (
        Candle(timestamp=datetime(2026, 1, 2, 23, 45), open=1.0, high=1.1, low=0.9, close=1.05),  # Friday
        Candle(timestamp=datetime(2026, 1, 5, 0, 0), open=1.0, high=1.1, low=0.9, close=1.05),  # Monday
    )
    series = OHLCSeries(candles=candles, instrument="EURUSDm", timeframe="15M")
    allowed = frozenset({datetime(2026, 1, 2, 23, 45)})
    validate_no_gaps(series, timedelta(minutes=15), allowed_gap_starts=allowed)  # must not raise


def test_missing_candle_without_declared_gap_is_indistinguishable_from_dropped_session():
    """#12: a silently dropped candle IS a gap unless explicitly declared —
    Layer-2 must not distinguish "gap" from "dropped session" without a
    caller-provided allowance."""
    candles = (
        Candle(timestamp=datetime(2026, 1, 2, 23, 45), open=1.0, high=1.1, low=0.9, close=1.05),
        Candle(timestamp=datetime(2026, 1, 5, 0, 0), open=1.0, high=1.1, low=0.9, close=1.05),
    )
    series = OHLCSeries(candles=candles, instrument="EURUSDm", timeframe="15M")
    with pytest.raises(DatasetIntegrityError):
        validate_no_gaps(series, timedelta(minutes=15))  # no allowance supplied


# --- REQ-STAT-34 (V4): manifest-frozen gap allowlist is the ONLY production
# --- authority — validate_no_gaps' allowed_gap_starts stays test-only. -----

_WEEKEND_GAP_SERIES = OHLCSeries(
    candles=(
        Candle(timestamp=datetime(2026, 1, 2, 23, 45), open=1.0, high=1.1, low=0.9, close=1.05),  # Friday
        Candle(timestamp=datetime(2026, 1, 5, 0, 0), open=1.0, high=1.1, low=0.9, close=1.05),  # Monday
    ),
    instrument="EURUSDm",
    timeframe="15M",
)


def test_gap_declared_in_frozen_manifest_allowlist_passes():
    manifest = _manifest(
        dataset_gap_allowlist=(
            GapAllowlistEntry(
                instrument="EURUSDm", granularity="15M",
                gap_start=datetime(2026, 1, 2, 23, 45), gap_end=datetime(2026, 1, 5, 0, 0),
                reason="weekend closure",
            ),
        )
    )
    validate_no_gaps_against_manifest(_WEEKEND_GAP_SERIES, timedelta(minutes=15), manifest)  # must not raise


def test_gap_not_in_frozen_allowlist_fails_closed():
    manifest = _manifest(dataset_gap_allowlist=())  # same gap, but NOT declared
    with pytest.raises(DatasetIntegrityError):
        validate_no_gaps_against_manifest(_WEEKEND_GAP_SERIES, timedelta(minutes=15), manifest)


def test_gap_declared_for_a_different_instrument_does_not_apply():
    manifest = _manifest(
        dataset_gap_allowlist=(
            GapAllowlistEntry(
                instrument="GBPUSDm", granularity="15M",  # wrong instrument
                gap_start=datetime(2026, 1, 2, 23, 45), gap_end=datetime(2026, 1, 5, 0, 0),
                reason="weekend closure",
            ),
        )
    )
    with pytest.raises(DatasetIntegrityError):
        validate_no_gaps_against_manifest(_WEEKEND_GAP_SERIES, timedelta(minutes=15), manifest)


def test_extra_undeclared_gap_still_fails_even_with_one_gap_allowlisted():
    manifest = _manifest(
        dataset_gap_allowlist=(
            GapAllowlistEntry(
                instrument="EURUSDm", granularity="15M",
                gap_start=datetime(2026, 1, 2, 23, 45), gap_end=datetime(2026, 1, 5, 0, 0),
                reason="weekend closure",
            ),
        )
    )
    candles = (
        Candle(timestamp=datetime(2026, 1, 2, 23, 45), open=1.0, high=1.1, low=0.9, close=1.05),
        Candle(timestamp=datetime(2026, 1, 5, 0, 0), open=1.0, high=1.1, low=0.9, close=1.05),
        Candle(timestamp=datetime(2026, 1, 5, 1, 0), open=1.0, high=1.1, low=0.9, close=1.05),  # undeclared gap
    )
    series = OHLCSeries(candles=candles, instrument="EURUSDm", timeframe="15M")
    with pytest.raises(DatasetIntegrityError):
        validate_no_gaps_against_manifest(series, timedelta(minutes=15), manifest)


def test_manifest_dataset_gap_allowlist_cannot_be_mutated_at_runtime():
    """Runtime attempt to augment the immutable allowlist -> impossible:
    Manifest is a frozen dataclass."""
    manifest = _manifest(dataset_gap_allowlist=())
    with pytest.raises(dataclasses.FrozenInstanceError):
        manifest.dataset_gap_allowlist = (
            GapAllowlistEntry(
                instrument="EURUSDm", granularity="15M",
                gap_start=datetime(2026, 1, 2, 23, 45), gap_end=datetime(2026, 1, 5, 0, 0),
                reason="added after observing the gap — must be impossible",
            ),
        )


def test_manifest_driven_validator_has_no_parameter_to_add_gaps_beyond_the_manifest():
    """The distinction between the two functions is visible in the public
    API: validate_no_gaps_against_manifest takes (series, expected_interval,
    manifest) only — no allowed_gap_starts-shaped escape hatch."""
    import inspect

    params = list(inspect.signature(validate_no_gaps_against_manifest).parameters)
    assert params == ["series", "expected_interval", "manifest"]
