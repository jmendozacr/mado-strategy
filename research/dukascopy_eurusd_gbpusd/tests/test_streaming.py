from pathlib import Path

import pytest

from research.dukascopy_eurusd_gbpusd.adapter import DUKASCOPY_M1_COLUMNS
from research.dukascopy_eurusd_gbpusd.streaming import write_aggregated_csv


def write_raw(path: Path, rows: list[str]) -> None:
    path.write_text(
        ",".join(DUKASCOPY_M1_COLUMNS) + "\n" + "\n".join(rows) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def test_streaming_aggregation_writes_deterministic_m15_csv(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    destination = tmp_path / "out.csv"
    write_raw(
        source,
        [
            "2024.01.15 01:00:00,1,2,0.5,1.5,3",
            "2024.01.15 01:01:00,1.5,3,1,2,4",
            "2024.01.15 01:15:00,2,2.5,1.5,2.25,5",
        ],
    )

    receipt = write_aggregated_csv(source, destination, timeframe_minutes=15)

    assert receipt.row_count == 2
    assert destination.read_text(encoding="utf-8") == (
        "timestamp_utc,open,high,low,close,volume\n"
        "2024-01-14T23:00:00Z,1,3,0.5,2,7\n"
        "2024-01-14T23:15:00Z,2,2.5,1.5,2.25,5\n"
    )


def test_streaming_aggregation_rejects_non_monotonic_rows(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    write_raw(
        source,
        [
            "2024.01.15 01:01:00,1,1,1,1,1",
            "2024.01.15 01:00:00,1,1,1,1,1",
        ],
    )

    with pytest.raises(ValueError, match="non-monotonic"):
        write_aggregated_csv(source, tmp_path / "out.csv", timeframe_minutes=15)


def test_streaming_aggregation_rejects_invalid_header(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    source.write_text("wrong\n", encoding="utf-8")

    with pytest.raises(ValueError, match="unexpected CSV header"):
        write_aggregated_csv(source, tmp_path / "out.csv", timeframe_minutes=15)
