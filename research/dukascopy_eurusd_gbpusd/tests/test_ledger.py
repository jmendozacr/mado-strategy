from datetime import datetime, timezone

import pytest

from research.dukascopy_eurusd_gbpusd.adapter import MinuteRow, OfflineDomain, parse_eet_timestamp
from research.dukascopy_eurusd_gbpusd.ledger import build_gap_ledger, serialize_gap_ledger


def row(stamp: str) -> MinuteRow:
    return MinuteRow(stamp, 1.0, 1.1, 0.9, 1.05, 1.0)


def utc(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def test_unresolved_gap_is_excluded() -> None:
    entries = build_gap_ledger(
        [row("2024.01.15 12:00:00"), row("2024.01.15 12:03:00")],
        instrument="DUKASCOPY_EURUSD",
        offline_domains=(),
    )
    assert len(entries) == 1
    assert entries[0].classification == "UNRESOLVED"
    assert entries[0].action == "excluded"
    assert entries[0].duration_minutes == 2
    assert entries[0].covering_domain == "none"


def test_fully_covered_gap_is_eligible() -> None:
    entries = build_gap_ledger(
        [row("2024.01.15 12:00:00"), row("2024.01.15 12:03:00")],
        instrument="DUKASCOPY_GBPUSD",
        offline_domains=[
            OfflineDomain(
                start=parse_eet_timestamp("2024.01.15 12:01:00"),
                end=parse_eet_timestamp("2024.01.15 12:03:00"),
            )
        ],
    )
    assert entries[0].classification == "EXPLAINED"
    assert entries[0].action == "eligible"


def test_partial_domain_remains_unresolved() -> None:
    entries = build_gap_ledger(
        [row("2024.01.15 12:00:00"), row("2024.01.15 12:04:00")],
        instrument="DUKASCOPY_EURUSD",
        offline_domains=[
            OfflineDomain(
                start=parse_eet_timestamp("2024.01.15 12:01:00"),
                end=parse_eet_timestamp("2024.01.15 12:03:00"),
            )
        ],
    )
    assert entries[0].classification == "UNRESOLVED"
    assert entries[0].covering_domain == "none"


def test_contiguous_series_has_empty_ledger() -> None:
    assert build_gap_ledger(
        [row("2024.01.15 12:00:00"), row("2024.01.15 12:01:00")],
        instrument="DUKASCOPY_EURUSD",
        offline_domains=(),
    ) == ()


def test_non_monotonic_rows_are_rejected() -> None:
    with pytest.raises(ValueError, match="non-monotonic"):
        build_gap_ledger(
            [row("2024.01.15 12:01:00"), row("2024.01.15 12:00:00")],
            instrument="DUKASCOPY_EURUSD",
            offline_domains=(),
        )


def test_invalid_domain_timezone_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        build_gap_ledger(
            [row("2024.01.15 12:00:00")],
            instrument="DUKASCOPY_EURUSD",
            offline_domains=[
                OfflineDomain(
                    start=datetime(2024, 1, 15, 12, 1),
                    end=datetime(2024, 1, 15, 12, 2),
                )
            ],
        )


def test_serialization_is_stable_and_uses_z_suffix() -> None:
    entry = build_gap_ledger(
        [row("2024.01.15 12:00:00"), row("2024.01.15 12:03:00")],
        instrument="DUKASCOPY_EURUSD",
        offline_domains=(),
    )[0]
    text = serialize_gap_ledger([entry])
    assert '"interval_start_utc": "2024-01-15T10:01:00Z"' in text
    assert serialize_gap_ledger([entry]) == serialize_gap_ledger([entry])
