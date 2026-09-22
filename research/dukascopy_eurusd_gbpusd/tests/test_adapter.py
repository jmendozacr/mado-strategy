from datetime import datetime, timezone

import pytest

from research.dukascopy_eurusd_gbpusd.adapter import (
    GapStatus,
    MinuteRow,
    aggregate_ohlcv,
    classify_gap,
    parse_eet_timestamp,
    validate_rows,
)


def row(timestamp: str, volume: float = 1.0) -> MinuteRow:
    return MinuteRow(
        timestamp=timestamp,
        open=1.1,
        high=1.2,
        low=1.0,
        close=1.15,
        volume=volume,
    )


def test_parse_eet_uses_standard_offset() -> None:
    assert parse_eet_timestamp("2024.01.15 12:00:00") == datetime(
        2024, 1, 15, 10, 0, tzinfo=timezone.utc
    )


def test_parse_eet_uses_daylight_offset() -> None:
    assert parse_eet_timestamp("2024.07.15 12:00:00") == datetime(
        2024, 7, 15, 9, 0, tzinfo=timezone.utc
    )


def test_validate_rows_preserves_zero_volume_but_rejects_duplicates() -> None:
    rows = [row("2024.01.15 12:00:00", volume=0.0), row("2024.01.15 12:01:00")]
    assert validate_rows(rows) == rows

    with pytest.raises(ValueError, match="duplicate timestamp"):
        validate_rows(rows + [row("2024.01.15 12:01:00")])


def test_aggregate_uses_eet_session_boundary_and_preserves_ohlcv() -> None:
    rows = [
        row("2024.01.15 01:00:00"),
        row("2024.01.15 01:01:00", volume=2.0),
        row("2024.01.15 01:02:00"),
    ]
    bars = aggregate_ohlcv(rows, timeframe_minutes=3)
    assert len(bars) == 1
    assert bars[0].timestamp == parse_eet_timestamp("2024.01.15 01:00:00")
    assert bars[0].open == 1.1
    assert bars[0].high == 1.2
    assert bars[0].low == 1.0
    assert bars[0].close == 1.15
    assert bars[0].volume == 4.0


def test_unexplained_gap_is_fail_closed() -> None:
    previous = parse_eet_timestamp("2024.01.15 12:00:00")
    current = parse_eet_timestamp("2024.01.15 12:03:00")
    assert classify_gap(previous, current, offline_domains=()) is GapStatus.UNRESOLVED
