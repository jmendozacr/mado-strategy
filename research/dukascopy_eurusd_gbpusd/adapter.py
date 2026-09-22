"""
Research-only Dukascopy ingestion adapter for the EURUSD + GBPUSD experiment.

Boundary contract:
- Not imported by any production module.
- Raw provider CSVs are never copied into the repository.
- All derived intermediates go to the approved external run root.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum, auto
from typing import Sequence
from zoneinfo import ZoneInfo

# Europe/Helsinki: UTC+2 (EET standard) / UTC+3 (EEST daylight).
# This is the authoritative DST rule for the raw EET label in JForex exports.
_EET = ZoneInfo("Europe/Helsinki")

_ONE_MINUTE = timedelta(minutes=1)


@dataclass(frozen=True)
class MinuteRow:
    """One raw minute record as parsed from the JForex EET-labelled CSV."""

    timestamp: str  # raw EET string, preserved exactly as provided
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class OHLCVBar:
    """One aggregated OHLCV bar; timestamp is the UTC instant of the EET session boundary."""

    timestamp: datetime  # UTC-aware
    open: float
    high: float
    low: float
    close: float
    volume: float


class GapStatus(Enum):
    """Gap classification result — fail-closed by default."""

    UNRESOLVED = auto()
    EXPLAINED = auto()


def parse_eet_timestamp(timestamp_str: str) -> datetime:
    """Return a UTC-aware datetime from a Dukascopy EET timestamp string.

    The DST rule is Europe/Helsinki (UTC+2 standard, UTC+3 daylight).
    A fixed offset is never inferred from a single date.
    """
    naive = datetime.strptime(timestamp_str, "%Y.%m.%d %H:%M:%S")
    # replace() + ZoneInfo handles DST fold/gap via the fold attribute (default 0).
    localized = naive.replace(tzinfo=_EET)
    return localized.astimezone(timezone.utc)


def validate_rows(rows: list[MinuteRow]) -> list[MinuteRow]:
    """Validate a sequence of minute rows.

    - Zero-volume rows are preserved as observations.
    - Raises ValueError on duplicate timestamps.
    """
    seen: set[str] = set()
    for r in rows:
        if r.timestamp in seen:
            raise ValueError(f"duplicate timestamp: {r.timestamp}")
        seen.add(r.timestamp)
    return rows


def aggregate_ohlcv(
    rows: Sequence[MinuteRow],
    timeframe_minutes: int,
) -> list[OHLCVBar]:
    """Aggregate minute rows into fixed-width OHLCV bars.

    The first bar's timestamp is anchored to the EET session boundary of the
    first row (converted to UTC). Subsequent bucket boundaries advance by
    exactly ``timeframe_minutes`` from that anchor.
    """
    if not rows:
        return []

    td = timedelta(minutes=timeframe_minutes)
    anchor = parse_eet_timestamp(rows[0].timestamp)

    bars: list[OHLCVBar] = []
    bucket_start = anchor
    bucket: list[MinuteRow] = []

    for r in rows:
        ts = parse_eet_timestamp(r.timestamp)
        if ts >= bucket_start + td:
            if bucket:
                bars.append(_close_bucket(bucket_start, bucket))
            # Advance the bucket boundary past ts.
            while bucket_start + td <= ts:
                bucket_start += td
            bucket = [r]
        else:
            bucket.append(r)

    if bucket:
        bars.append(_close_bucket(bucket_start, bucket))

    return bars


def _close_bucket(timestamp: datetime, rows: list[MinuteRow]) -> OHLCVBar:
    return OHLCVBar(
        timestamp=timestamp,
        open=rows[0].open,
        high=max(r.high for r in rows),
        low=min(r.low for r in rows),
        close=rows[-1].close,
        volume=sum(r.volume for r in rows),
    )


def classify_gap(
    previous: datetime,
    current: datetime,
    offline_domains: tuple,
) -> GapStatus:
    """Classify the gap between two consecutive UTC timestamps.

    Fail-closed: an unexplained gap (no matching offline-domain evidence) is
    always UNRESOLVED. Zero-volume rows are not evidence of closure.

    ``offline_domains`` must be a tuple of objects with ``start`` and ``end``
    attributes (UTC-aware datetimes) covering the missing interval.
    """
    expected_next = previous + _ONE_MINUTE
    if current <= expected_next:
        return GapStatus.EXPLAINED

    for domain in offline_domains:
        if _domain_covers(domain, expected_next, current):
            return GapStatus.EXPLAINED

    return GapStatus.UNRESOLVED


def _domain_covers(domain: object, gap_start: datetime, gap_end: datetime) -> bool:
    """Return True when the offline domain interval fully covers the gap."""
    try:
        return domain.start <= gap_start and domain.end >= gap_end  # type: ignore[union-attr]
    except AttributeError:
        return False
