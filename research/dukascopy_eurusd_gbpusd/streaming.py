"""Streaming JForex CSV aggregation for the Dukascopy research experiment."""
from __future__ import annotations

import csv
import hashlib
import math
from dataclasses import dataclass
from pathlib import Path

from research.dukascopy_eurusd_gbpusd.adapter import (
    APPROVED_TIMEFRAMES,
    DUKASCOPY_M1_COLUMNS,
    _local_bucket_start,
    parse_eet_timestamp,
)


@dataclass(frozen=True)
class AggregationReceipt:
    source_path: Path
    destination_path: Path
    timeframe_minutes: int
    row_count: int
    sha256: str


def write_aggregated_csv(
    source_path: Path,
    destination_path: Path,
    *,
    timeframe_minutes: int,
) -> AggregationReceipt:
    """Aggregate a validated raw CSV without loading all minute rows into memory."""
    if timeframe_minutes not in APPROVED_TIMEFRAMES:
        raise ValueError(f"unapproved timeframe: {timeframe_minutes}")

    row_count = 0
    previous = None
    bucket_start = None
    open_ = high = low = close = volume = None

    with source_path.open("r", encoding="utf-8", newline="") as source, destination_path.open(
        "w", encoding="utf-8", newline=""
    ) as destination:
        reader = csv.reader(source)
        try:
            header = tuple(column.strip() for column in next(reader))
        except StopIteration as exc:
            raise ValueError("empty CSV: no header line") from exc
        if header != DUKASCOPY_M1_COLUMNS:
            raise ValueError(
                f"unexpected CSV header: expected {DUKASCOPY_M1_COLUMNS}, got {header}"
            )

        writer = csv.writer(destination, lineterminator="\n")
        writer.writerow(["timestamp_utc", "open", "high", "low", "close", "volume"])

        def flush() -> None:
            nonlocal row_count
            if bucket_start is None:
                return
            writer.writerow(
                [
                    bucket_start.isoformat().replace("+00:00", "Z"),
                    _format(open_),
                    _format(high),
                    _format(low),
                    _format(close),
                    _format(volume),
                ]
            )
            row_count += 1

        for line_no, parts in enumerate(reader, start=2):
            if not parts or all(not part.strip() for part in parts):
                continue
            if len(parts) != len(DUKASCOPY_M1_COLUMNS):
                raise ValueError(
                    f"line {line_no}: expected {len(DUKASCOPY_M1_COLUMNS)} columns, got {len(parts)}"
                )
            timestamp = parse_eet_timestamp(parts[0].strip())
            if previous is not None and timestamp <= previous:
                raise ValueError(f"non-monotonic timestamp at line {line_no}")
            previous = timestamp

            values = tuple(float(part) for part in parts[1:])
            if not all(math.isfinite(value) for value in values):
                raise ValueError(f"non-finite value at line {line_no}")
            current_bucket = _local_bucket_start(timestamp, timeframe_minutes)
            if bucket_start is None:
                bucket_start = current_bucket
                open_, high, low, close, volume = values
            elif current_bucket != bucket_start:
                flush()
                bucket_start = current_bucket
                open_, high, low, close, volume = values
            else:
                high = max(high, values[1])
                low = min(low, values[2])
                close = values[3]
                volume += values[4]

        flush()

    return AggregationReceipt(
        source_path=source_path,
        destination_path=destination_path,
        timeframe_minutes=timeframe_minutes,
        row_count=row_count,
        sha256=_sha256(destination_path),
    )


def _format(value: float | None) -> str:
    if value is None:
        raise RuntimeError("attempted to write an empty aggregation bucket")
    return format(value, ".15g")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
