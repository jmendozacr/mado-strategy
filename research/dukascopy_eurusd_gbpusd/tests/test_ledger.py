from datetime import datetime, timezone

import pytest

from research.dukascopy_eurusd_gbpusd.adapter import MinuteRow, OfflineDomain, parse_eet_timestamp
from research.dukascopy_eurusd_gbpusd.ledger import (
    CauseClassification,
    GapLedgerEntry,
    build_gap_ledger,
    serialize_gap_ledger,
)


def row(stamp: str) -> MinuteRow:
    return MinuteRow(stamp, 1.0, 1.1, 0.9, 1.05, 1.0)


def utc(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# Existing behaviour — must remain unchanged
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# CauseClassification schema
# ---------------------------------------------------------------------------


def test_cause_classification_has_both_variants() -> None:
    assert CauseClassification.DATA_INTEGRITY.value == "DATA_INTEGRITY"
    assert CauseClassification.MARKET_UNAVAILABILITY.value == "MARKET_UNAVAILABILITY"
    assert CauseClassification.DATA_INTEGRITY is not CauseClassification.MARKET_UNAVAILABILITY


def test_gap_entry_cause_is_market_unavailability() -> None:
    entries = build_gap_ledger(
        [row("2024.01.15 12:00:00"), row("2024.01.15 12:03:00")],
        instrument="DUKASCOPY_EURUSD",
        offline_domains=(),
    )
    assert entries[0].cause is CauseClassification.MARKET_UNAVAILABILITY


def test_data_integrity_cause_can_be_set_on_direct_construction() -> None:
    # GapLedgerEntry is a plain dataclass; callers at the signal-exclusion level
    # can construct DATA_INTEGRITY entries when an input file fails validation.
    entry = GapLedgerEntry(
        instrument="DUKASCOPY_EURUSD",
        date_eet="2024-01-15",
        interval_start_utc=utc("2024-01-15T10:01:00Z"),
        interval_end_utc=utc("2024-01-15T10:03:00Z"),
        duration_minutes=2,
        setup="raw-minute-gap",
        classification="UNRESOLVED",
        cause=CauseClassification.DATA_INTEGRITY,
        covering_domain="none",
        source_evidence="none",
        affected_artifact="raw-minute-series",
        action="excluded",
        reason="duplicate timestamp detected",
    )
    assert entry.cause is CauseClassification.DATA_INTEGRITY
    text = serialize_gap_ledger([entry])
    assert '"cause": "DATA_INTEGRITY"' in text


def test_gap_entry_rejects_an_invalid_cause_at_construction() -> None:
    with pytest.raises(ValueError, match="cause"):
        GapLedgerEntry(
            instrument="DUKASCOPY_EURUSD",
            date_eet="2024-01-15",
            interval_start_utc=utc("2024-01-15T10:01:00Z"),
            interval_end_utc=utc("2024-01-15T10:03:00Z"),
            duration_minutes=2,
            setup="raw-minute-gap",
            classification="UNRESOLVED",
            cause="not-a-cause",  # type: ignore[arg-type]
            covering_domain="none",
            source_evidence="none",
            affected_artifact="raw-minute-series",
            action="excluded",
            reason="probe",
        )


# ---------------------------------------------------------------------------
# date_eet derivation
# ---------------------------------------------------------------------------


def test_date_eet_reflects_eet_calendar_date_of_gap_start() -> None:
    # "2024.01.15 12:00:00" EET (UTC+2 winter) → 2024-01-15T10:00:00Z
    # gap start (expected next minute) = 2024-01-15T10:01:00Z
    # in EET (UTC+2): 2024-01-15 12:01:00 → date "2024-01-15"
    entries = build_gap_ledger(
        [row("2024.01.15 12:00:00"), row("2024.01.15 12:03:00")],
        instrument="DUKASCOPY_EURUSD",
        offline_domains=(),
    )
    assert entries[0].date_eet == "2024-01-15"


def test_date_eet_crosses_midnight_in_eet_correctly() -> None:
    # "2024.07.15 23:59:00" EEST (UTC+3 summer) → 2024-07-15T20:59:00Z
    # gap start = 2024-07-15T21:00:00Z
    # in EEST (UTC+3): 2024-07-16 00:00:00 → date "2024-07-16"
    entries = build_gap_ledger(
        [row("2024.07.15 23:59:00"), row("2024.07.16 00:05:00")],
        instrument="DUKASCOPY_EURUSD",
        offline_domains=(),
    )
    assert entries[0].date_eet == "2024-07-16"


# ---------------------------------------------------------------------------
# setup field propagation
# ---------------------------------------------------------------------------


def test_setup_defaults_to_raw_minute_gap() -> None:
    entries = build_gap_ledger(
        [row("2024.01.15 12:00:00"), row("2024.01.15 12:03:00")],
        instrument="DUKASCOPY_EURUSD",
        offline_domains=(),
    )
    assert entries[0].setup == "raw-minute-gap"


def test_setup_is_propagated_to_all_entries() -> None:
    entries = build_gap_ledger(
        [
            row("2024.01.15 12:00:00"),
            row("2024.01.15 12:03:00"),
            row("2024.01.15 12:10:00"),
        ],
        instrument="DUKASCOPY_EURUSD",
        offline_domains=(),
        setup="1AM",
    )
    assert all(e.setup == "1AM" for e in entries)


# ---------------------------------------------------------------------------
# source_evidence
# ---------------------------------------------------------------------------


def test_source_evidence_is_none_for_unresolved_gap() -> None:
    entries = build_gap_ledger(
        [row("2024.01.15 12:00:00"), row("2024.01.15 12:03:00")],
        instrument="DUKASCOPY_EURUSD",
        offline_domains=(),
        offline_domain_receipt_reference="openspec/explore/dukascopy-offline-domains-receipt-2026-09-22.md",
    )
    assert entries[0].source_evidence == "none"


def test_source_evidence_is_none_when_no_reference_provided() -> None:
    entries = build_gap_ledger(
        [row("2024.01.15 12:00:00"), row("2024.01.15 12:03:00")],
        instrument="DUKASCOPY_EURUSD",
        offline_domains=(),
    )
    assert entries[0].source_evidence == "none"


def test_source_evidence_populated_for_explained_gap() -> None:
    receipt = "openspec/explore/dukascopy-offline-domains-receipt-2026-09-22.md"
    entries = build_gap_ledger(
        [row("2024.01.15 12:00:00"), row("2024.01.15 12:03:00")],
        instrument="DUKASCOPY_GBPUSD",
        offline_domains=[
            OfflineDomain(
                start=parse_eet_timestamp("2024.01.15 12:01:00"),
                end=parse_eet_timestamp("2024.01.15 12:03:00"),
            )
        ],
        offline_domain_receipt_reference=receipt,
    )
    assert entries[0].source_evidence == receipt


# ---------------------------------------------------------------------------
# Deterministic ordering
# ---------------------------------------------------------------------------


def test_multiple_gaps_are_ordered_chronologically() -> None:
    entries = build_gap_ledger(
        [
            row("2024.01.15 12:00:00"),
            row("2024.01.15 12:04:00"),  # gap 12:01→12:04
            row("2024.01.15 12:05:00"),  # contiguous
            row("2024.01.15 12:10:00"),  # gap 12:06→12:10
        ],
        instrument="DUKASCOPY_EURUSD",
        offline_domains=(),
    )
    assert len(entries) == 2
    assert entries[0].interval_start_utc < entries[1].interval_start_utc


def test_serialization_order_is_deterministic_across_calls() -> None:
    entries = build_gap_ledger(
        [
            row("2024.01.15 12:00:00"),
            row("2024.01.15 12:04:00"),
            row("2024.01.15 12:10:00"),
        ],
        instrument="DUKASCOPY_EURUSD",
        offline_domains=(),
    )
    assert serialize_gap_ledger(entries) == serialize_gap_ledger(entries)


def test_serialization_rejects_duplicate_gap_identity() -> None:
    entry = build_gap_ledger(
        [row("2024.01.15 12:00:00"), row("2024.01.15 12:03:00")],
        instrument="DUKASCOPY_EURUSD",
        offline_domains=(),
    )[0]

    with pytest.raises(ValueError, match="duplicate gap identity"):
        serialize_gap_ledger([entry, entry])


# ---------------------------------------------------------------------------
# Duplicate instrument/window handling
# ---------------------------------------------------------------------------


def test_duplicate_offline_domain_does_not_create_duplicate_entries() -> None:
    # Supplying the same domain twice must not produce two EXPLAINED entries
    # for the same gap — one gap → one ledger entry regardless of domain list.
    domain = OfflineDomain(
        start=parse_eet_timestamp("2024.01.15 12:01:00"),
        end=parse_eet_timestamp("2024.01.15 12:03:00"),
    )
    entries = build_gap_ledger(
        [row("2024.01.15 12:00:00"), row("2024.01.15 12:03:00")],
        instrument="DUKASCOPY_GBPUSD",
        offline_domains=[domain, domain],
    )
    assert len(entries) == 1
    assert entries[0].classification == "EXPLAINED"


def test_same_window_different_instruments_have_no_cross_contamination() -> None:
    # Both instruments scan the same gap window; each entry must carry only
    # its own instrument identity without overwriting the other's.
    rows = [row("2024.01.15 12:00:00"), row("2024.01.15 12:03:00")]
    entries_eur = build_gap_ledger(rows, instrument="DUKASCOPY_EURUSD", offline_domains=())
    entries_gbp = build_gap_ledger(rows, instrument="DUKASCOPY_GBPUSD", offline_domains=())
    assert entries_eur[0].instrument == "DUKASCOPY_EURUSD"
    assert entries_gbp[0].instrument == "DUKASCOPY_GBPUSD"
    assert entries_eur[0].interval_start_utc == entries_gbp[0].interval_start_utc


# ---------------------------------------------------------------------------
# Serialization of new fields
# ---------------------------------------------------------------------------


def test_serialization_includes_all_new_audit_fields() -> None:
    entry = build_gap_ledger(
        [row("2024.01.15 12:00:00"), row("2024.01.15 12:03:00")],
        instrument="DUKASCOPY_EURUSD",
        offline_domains=(),
    )[0]
    text = serialize_gap_ledger([entry])
    assert '"cause": "MARKET_UNAVAILABILITY"' in text
    assert '"date_eet": "2024-01-15"' in text
    assert '"setup": "raw-minute-gap"' in text
    assert '"source_evidence": "none"' in text
