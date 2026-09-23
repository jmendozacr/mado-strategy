"""Research-only gap and exclusion ledger primitives for Dukascopy inputs."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Sequence

from research.dukascopy_eurusd_gbpusd.adapter import (
    GapStatus,
    MinuteRow,
    OfflineDomain,
    PROVIDER_TO_STRATEGY,
    classify_gap,
    parse_eet_timestamp,
)

_ONE_MINUTE = timedelta(minutes=1)


@dataclass(frozen=True)
class GapLedgerEntry:
    """One non-contiguous transition in a validated minute series."""

    instrument: str
    interval_start_utc: datetime
    interval_end_utc: datetime
    duration_minutes: int
    classification: str
    covering_domain: str
    affected_artifact: str
    action: str
    reason: str


def build_gap_ledger(
    rows: Sequence[MinuteRow],
    *,
    instrument: str,
    offline_domains: Sequence[OfflineDomain],
    affected_artifact: str = "raw-minute-series",
) -> tuple[GapLedgerEntry, ...]:
    """Return deterministic entries for every gap in a validated minute series.

    The function does not infer weekends or holidays.  A gap is explained only
    by a domain that fully covers the missing interval; all other gaps are
    recorded as unresolved and excluded.
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
                        interval_start_utc=expected,
                        interval_end_utc=current,
                        duration_minutes=int((current - expected).total_seconds() // 60),
                        classification="EXPLAINED" if explained else "UNRESOLVED",
                        covering_domain=(
                            f"{covering.start.isoformat()}->{covering.end.isoformat()}"
                            if covering is not None
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
    """Serialize a ledger deterministically with UTC timestamps."""
    payload = []
    for entry in entries:
        item = asdict(entry)
        item["interval_start_utc"] = _utc_iso(entry.interval_start_utc)
        item["interval_end_utc"] = _utc_iso(entry.interval_end_utc)
        payload.append(item)
    return json.dumps(payload, indent=2, sort_keys=True)


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
