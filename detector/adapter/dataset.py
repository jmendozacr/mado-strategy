"""Section M dataset-level fail-closed conditions Layer-2 owns: #4 duplicate
candles/timestamps (delegated to `ingestion.loader`'s own dense-timestamp
invariant), #5 missing files, #6 boundary gaps affecting prefix/setup/
outcome, #8 hash drift, #12 no incomplete-session dropping. Synthetic
temp-file fixtures only — never a real dataset CSV.

`validate_no_gaps`'s `allowed_gap_starts` parameter is a low-level,
synthetic-test-only convenience — it is explicitly NOT the production/
real-execution authority for gap tolerance (REQ-STAT-34, V4). That authority
is `validate_no_gaps_against_manifest`, which reads the immutable, frozen
`Manifest.dataset_gap_allowlist` alone; there is no way for a real caller to
declare an extra allowed gap through that path."""

import hashlib
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from adapter.errors import DatasetIntegrityError
from core.candle import OHLCSeries
from ingestion.loader import LoadError, load_mt5_csv

if TYPE_CHECKING:
    from adapter.manifest import Manifest


def sha256_of_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_and_validate_dataset_file(
    path: str | Path, symbol: str, expected_sha256: str
) -> OHLCSeries:
    """Section M #5 (missing files) / #8 (hash drift) / #4 (duplicate
    timestamps, via `ingestion.loader`'s own dense-order invariant,
    re-raised as `DatasetIntegrityError`)."""
    file_path = Path(path)
    if not file_path.exists():
        raise DatasetIntegrityError(f"missing dataset file: {file_path}")

    actual_sha256 = sha256_of_file(file_path)
    if actual_sha256 != expected_sha256:
        raise DatasetIntegrityError(
            f"hash drift: {file_path} has sha256={actual_sha256}, manifest declares {expected_sha256}"
        )

    try:
        return load_mt5_csv(str(file_path), symbol)
    except LoadError as error:
        raise DatasetIntegrityError(f"dataset integrity failure loading {file_path}: {error}") from error


def validate_no_gaps(
    series: OHLCSeries, expected_interval: timedelta, allowed_gap_starts: frozenset = frozenset()
) -> None:
    """Section M #6 (boundary gaps affecting prefix/setup/outcome) / #12 (no
    incomplete-session dropping): every consecutive candle pair MUST be
    spaced by exactly `expected_interval`, except a caller pre-declared,
    explicit set of gap-start timestamps (e.g. a known weekend closure) —
    Layer-2 validates internal contiguity; broader market-calendar semantics
    are the caller's declared expectation, never inferred here. An
    undeclared gap is indistinguishable from a silently dropped candle, so
    both conditions share this one check.

    LOW-LEVEL, SYNTHETIC-TEST CONVENIENCE ONLY (REQ-STAT-34, V4): the caller
    may supply any `allowed_gap_starts` it likes, which is exactly why this
    function MUST NOT be treated as the production/real-execution authority
    — use `validate_no_gaps_against_manifest` for that."""
    candles = series.candles
    for i in range(1, len(candles)):
        previous, current = candles[i - 1].timestamp, candles[i].timestamp
        delta = current - previous
        if delta != expected_interval and previous not in allowed_gap_starts:
            raise DatasetIntegrityError(
                f"unexpected gap of {delta} between {previous.isoformat()} and "
                f"{current.isoformat()} (expected {expected_interval}) — either an undisclosed "
                f"boundary gap or a silently dropped candle"
            )


def validate_no_gaps_against_manifest(
    series: OHLCSeries, expected_interval: timedelta, manifest: "Manifest"
) -> None:
    """REQ-STAT-34 (V4): the ONLY production/real-execution authority for
    dataset gap tolerance. Unlike `validate_no_gaps`'s caller-supplied
    `allowed_gap_starts`, this derives the allowed gap-start timestamps
    EXCLUSIVELY from the immutable `manifest.dataset_gap_allowlist` — frozen
    before any real outcome execution and never mutable afterward (`Manifest`
    is a frozen dataclass). This function accepts no parameter through which
    a caller could add an allowed gap beyond what the frozen manifest already
    declares; an observed gap absent from the allowlist raises
    `DatasetIntegrityError` unconditionally, exactly as `validate_no_gaps`
    does for any gap outside its own (here: manifest-derived) allowance."""
    allowed_gap_starts = frozenset(
        entry.gap_start
        for entry in manifest.dataset_gap_allowlist
        if entry.instrument == series.instrument and entry.granularity == series.timeframe
    )
    validate_no_gaps(series, expected_interval, allowed_gap_starts=allowed_gap_starts)
