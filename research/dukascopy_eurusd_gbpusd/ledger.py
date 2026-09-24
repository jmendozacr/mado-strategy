"""Research-only gap and exclusion ledger primitives for Dukascopy inputs."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Sequence
from zoneinfo import ZoneInfo

from research.dukascopy_eurusd_gbpusd.adapter import (
    GapStatus,
    MinuteRow,
    OfflineDomain,
    PROVIDER_TO_STRATEGY,
    classify_gap,
    parse_eet_timestamp,
)

_ONE_MINUTE = timedelta(minutes=1)
_EET = ZoneInfo("Europe/Helsinki")


class CauseClassification(str, Enum):
    """Top-level cause category for a ledger entry.

    DATA_INTEGRITY covers input failures that are independent of market hours:
        malformed rows, hash mismatches, duplicate timestamps, non-monotonic
        ordering, and non-finite values.  These reach the ledger when a caller
        explicitly records a rejection rather than raising an exception.

    MARKET_UNAVAILABILITY covers missing-minute intervals that may represent
        market closures.  Each such interval is either explained by retained
        offline-domain evidence (EXPLAINED) or remains unresolved because no
        retained evidence fully covers it (UNRESOLVED).  Fail-closed: the
        absence of evidence never converts an unresolved interval to "open".
    """

    DATA_INTEGRITY = "DATA_INTEGRITY"
    MARKET_UNAVAILABILITY = "MARKET_UNAVAILABILITY"


@dataclass(frozen=True)
class GapLedgerEntry:
    """One non-contiguous transition in a validated minute series.

    Fields satisfy the signed statistical protocol's requirement that the
    exclusion ledger retains: instrument, date, setup, reason, source evidence,
    and a cause classification distinguishing data-integrity failures from
    market unavailability.
    """

    instrument: str
    date_eet: str                   # EET calendar date (YYYY-MM-DD) of interval_start_utc
    interval_start_utc: datetime
    interval_end_utc: datetime
    duration_minutes: int
    setup: str                      # strategy setup identifier, or "raw-minute-gap" at scan level
    classification: str             # "EXPLAINED" or "UNRESOLVED"
    cause: CauseClassification      # DATA_INTEGRITY or MARKET_UNAVAILABILITY
    covering_domain: str            # UTC range "{start}->{end}" or "none"
    source_evidence: str            # offline-domain receipt reference used, or "none"
    affected_artifact: str
    action: str                     # "eligible" (explained) or "excluded" (unresolved)
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.cause, CauseClassification):
            raise ValueError("cause must be a CauseClassification")


def build_gap_ledger(
    rows: Sequence[MinuteRow],
    *,
    instrument: str,
    offline_domains: Sequence[OfflineDomain],
    affected_artifact: str = "raw-minute-series",
    setup: str = "raw-minute-gap",
    offline_domain_receipt_reference: str | None = None,
) -> tuple[GapLedgerEntry, ...]:
    """Return deterministic entries for every gap in a validated minute series.

    The function does not infer weekends or holidays.  A gap is explained only
    by a domain that fully covers the missing interval; all other gaps are
    recorded as unresolved and excluded.

    Args:
        rows: validated minute rows in ascending chronological order.
        instrument: approved strategy identity ("DUKASCOPY_EURUSD" or
            "DUKASCOPY_GBPUSD").
        offline_domains: retained getOfflineTimeDomains evidence, UTC-bounded.
        affected_artifact: identifier of the artifact whose continuity is being
            validated (default "raw-minute-series").
        setup: strategy setup identifier propagated to every entry.  Use the
            default "raw-minute-gap" at the raw scan level and a specific
            identifier (e.g. "1AM", "5AM") at the signal-exclusion level.
        offline_domain_receipt_reference: path or reference to the retained
            offline-domain receipt used for classification.  Populated in
            source_evidence only when the gap is explained; "none" otherwise.
    """
    if instrument not in PROVIDER_TO_STRATEGY.values():
        raise ValueError(f"unapproved instrument: {instrument!r}")
    if not affected_artifact:
        raise ValueError("affected_artifact must not be empty")
    _validate_domains(offline_domains)

    entries: list[GapLedgerEntry] = []
    previous: datetime | None = None
    for row in rows:
        current = parse_eet_timestamp(row.timestamp)
        if previous is not None:
            expected = previous + _ONE_MINUTE
            if current > expected:
                covering = next(
                    (
                        domain
                        for domain in offline_domains
                        if domain.start <= expected and domain.end >= current
                    ),
                    None,
                )
                status = classify_gap(previous, current, offline_domains)
                explained = status is GapStatus.EXPLAINED
                entries.append(
                    GapLedgerEntry(
                        instrument=instrument,
                        date_eet=_eet_date(expected),
                        interval_start_utc=expected,
                        interval_end_utc=current,
                        duration_minutes=int((current - expected).total_seconds() // 60),
                        setup=setup,
                        classification="EXPLAINED" if explained else "UNRESOLVED",
                        cause=CauseClassification.MARKET_UNAVAILABILITY,
                        covering_domain=(
                            f"{covering.start.isoformat()}->{covering.end.isoformat()}"
                            if covering is not None
                            else "none"
                        ),
                        source_evidence=(
                            offline_domain_receipt_reference
                            if explained and offline_domain_receipt_reference is not None
                            else "none"
                        ),
                        affected_artifact=affected_artifact,
                        action="eligible" if explained else "excluded",
                        reason=(
                            "fully covered by retained offline domain"
                            if explained
                            else "no retained offline domain fully covers the gap"
                        ),
                    )
                )
            elif current <= previous:
                raise ValueError(f"non-monotonic timestamp: {row.timestamp}")
        previous = current
    return tuple(entries)


def serialize_gap_ledger(entries: Sequence[GapLedgerEntry]) -> str:
    """Serialize a ledger deterministically with UTC timestamps.

    ``cause`` is serialized as its string value (e.g. "MARKET_UNAVAILABILITY").
    ``interval_start_utc`` and ``interval_end_utc`` use the Z-suffix UTC form.
    """
    payload = []
    identities: set[tuple[str, str, datetime, datetime]] = set()
    for entry in entries:
        identity = (
            entry.instrument,
            entry.setup,
            entry.interval_start_utc,
            entry.interval_end_utc,
        )
        if identity in identities:
            raise ValueError(f"duplicate gap identity: {identity!r}")
        identities.add(identity)
        item = asdict(entry)
        item["interval_start_utc"] = _utc_iso(entry.interval_start_utc)
        item["interval_end_utc"] = _utc_iso(entry.interval_end_utc)
        # CauseClassification(str, Enum) serializes correctly via json.dumps as-is,
        # but asdict returns the enum instance; replace with its plain string value
        # so the output is not dependent on json encoder's str-subclass handling.
        item["cause"] = entry.cause.value
        payload.append(item)
    return json.dumps(payload, indent=2, sort_keys=True)


def _eet_date(utc: datetime) -> str:
    """Return the Europe/Helsinki calendar date of a UTC-aware datetime as YYYY-MM-DD."""
    return utc.astimezone(_EET).date().isoformat()


def _validate_domains(domains: Sequence[OfflineDomain]) -> None:
    for domain in domains:
        if domain.start.tzinfo is None or domain.end.tzinfo is None:
            raise ValueError("offline domain timestamps must be timezone-aware")
        if domain.start.utcoffset() != timedelta(0) or domain.end.utcoffset() != timedelta(0):
            raise ValueError("offline domain timestamps must be UTC")
        if domain.end <= domain.start:
            raise ValueError("offline domain end must be after start")


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("ledger timestamps must be UTC")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
