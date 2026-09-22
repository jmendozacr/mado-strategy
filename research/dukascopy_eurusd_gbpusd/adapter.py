"""
Research-only Dukascopy ingestion adapter for the EURUSD + GBPUSD experiment.

Boundary contract:
- Not imported by any production module.
- Raw provider CSVs are never copied into the repository.
- All derived intermediates go to the approved external run root.
"""
from __future__ import annotations

import hashlib
import math
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


# Approved strategy timeframes (minutes).  D1=1440, H4=240, M15=15.
APPROVED_TIMEFRAMES: frozenset[int] = frozenset({15, 240, 1440})


@dataclass(frozen=True)
class OfflineDomain:
    """UTC-bounded offline interval from a retained getOfflineTimeDomains receipt."""

    start: datetime  # UTC-aware
    end: datetime    # UTC-aware


class GapStatus(Enum):
    """Gap classification result — fail-closed by default."""

    UNRESOLVED = auto()
    EXPLAINED = auto()


# ---------------------------------------------------------------------------
# Identity contract
# ---------------------------------------------------------------------------

# Maps raw Dukascopy provider labels to experiment-local strategy identities.
# The provider label is never silently substituted for the strategy identity.
PROVIDER_TO_STRATEGY: dict[str, str] = {
    "EURUSD": "DUKASCOPY_EURUSD",
    "GBPUSD": "DUKASCOPY_GBPUSD",
}

EXPECTED_OFFER_SIDE = "Bid"
EXPECTED_TIMEZONE_LABEL = "EET"

# Exact Dukascopy JForex 1-minute CSV column order.
# The real export header is: Time (EET),Open,High,Low,Close,Volume<trailing-space>
# parse_csv_bytes strips each column before comparison, so the trailing space is absorbed.
DUKASCOPY_M1_COLUMNS: tuple[str, ...] = (
    "Time (EET)",
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
)


@dataclass(frozen=True)
class InputIdentity:
    """Validated provenance for a single Dukascopy CSV input.

    source_path and source_sha256 are metadata only; no file I/O is performed
    by this module.  The SHA-256 is verified by the caller via verify_sha256()
    before any parsing occurs.
    """

    provider_instrument: str  # raw Dukascopy label: "EURUSD" or "GBPUSD"
    strategy_instrument: str  # experiment-local identity, never silently substituted
    source_path: str          # external absolute path, recorded in the run manifest
    source_sha256: str        # hex digest to be verified before parsing
    timezone_label: str       # must be "EET"
    offer_side: str           # must be "Bid"


def resolve_identity(
    provider_instrument: str,
    timezone_label: str,
    offer_side: str,
    source_path: str,
    source_sha256: str,
) -> InputIdentity:
    """Validate provider metadata and return a typed InputIdentity.

    Rejects unknown instruments, wrong offer side, and wrong timezone label.
    strategy_instrument is derived from PROVIDER_TO_STRATEGY; it is never
    derived by guessing or substituting the provider label directly.
    """
    if provider_instrument not in PROVIDER_TO_STRATEGY:
        raise ValueError(
            f"unknown provider_instrument {provider_instrument!r};"
            f" approved: {sorted(PROVIDER_TO_STRATEGY)}"
        )
    if offer_side != EXPECTED_OFFER_SIDE:
        raise ValueError(
            f"offer_side must be {EXPECTED_OFFER_SIDE!r}, got {offer_side!r}"
        )
    if timezone_label != EXPECTED_TIMEZONE_LABEL:
        raise ValueError(
            f"timezone_label must be {EXPECTED_TIMEZONE_LABEL!r}, got {timezone_label!r}"
        )
    return InputIdentity(
        provider_instrument=provider_instrument,
        strategy_instrument=PROVIDER_TO_STRATEGY[provider_instrument],
        source_path=source_path,
        source_sha256=source_sha256,
        timezone_label=timezone_label,
        offer_side=offer_side,
    )


def verify_sha256(data: bytes, expected_hex: str) -> None:
    """Raise ValueError when the SHA-256 digest of data does not match expected_hex."""
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected_hex:
        raise ValueError(
            f"SHA-256 mismatch: expected {expected_hex!r}, got {actual!r}"
        )


def parse_csv_bytes(data: bytes, identity: InputIdentity) -> list[MinuteRow]:
    """Parse Dukascopy 1-minute CSV bytes into a list of MinuteRow values.

    Validates the exact DUKASCOPY_M1_COLUMNS header before reading any data
    row.  Rejects malformed rows (wrong column count, non-numeric fields).
    Zero-volume rows are preserved as observations; they are never dropped.
    No file I/O occurs; source_path and source_sha256 on identity are metadata.
    """
    lines = data.decode("utf-8").splitlines()
    if not lines:
        raise ValueError("empty CSV: no header line")

    header_cols = tuple(col.strip() for col in lines[0].split(","))
    if header_cols != DUKASCOPY_M1_COLUMNS:
        raise ValueError(
            f"unexpected CSV header: expected {DUKASCOPY_M1_COLUMNS},"
            f" got {header_cols}"
        )

    rows: list[MinuteRow] = []
    for line_no, raw_line in enumerate(lines[1:], start=2):
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split(",")
        if len(parts) != len(DUKASCOPY_M1_COLUMNS):
            raise ValueError(
                f"line {line_no}: expected {len(DUKASCOPY_M1_COLUMNS)} columns,"
                f" got {len(parts)}"
            )
        timestamp = parts[0].strip()
        try:
            open_ = float(parts[1])
            high = float(parts[2])
            low = float(parts[3])
            close = float(parts[4])
            volume = float(parts[5])
        except ValueError as exc:
            raise ValueError(f"line {line_no}: non-numeric field — {exc}") from exc
        rows.append(
            MinuteRow(
                timestamp=timestamp,
                open=open_,
                high=high,
                low=low,
                close=close,
                volume=volume,
            )
        )
    return validate_rows(rows)


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
    - Raises ValueError on duplicate timestamps, non-finite price/volume values,
      or non-monotonic (backwards / equal) UTC timestamps.
    """
    seen: set[str] = set()
    prev_utc: datetime | None = None
    for r in rows:
        for name, value in (
            ("open", r.open),
            ("high", r.high),
            ("low", r.low),
            ("close", r.close),
            ("volume", r.volume),
        ):
            if not math.isfinite(value):
                raise ValueError(f"non-finite {name} in row {r.timestamp}: {value}")
        if r.timestamp in seen:
            raise ValueError(f"duplicate timestamp: {r.timestamp}")
        seen.add(r.timestamp)
        utc = parse_eet_timestamp(r.timestamp)
        if prev_utc is not None and utc <= prev_utc:
            raise ValueError(f"non-monotonic timestamp: {r.timestamp}")
        prev_utc = utc
    return rows


def aggregate_ohlcv(
    rows: Sequence[MinuteRow],
    timeframe_minutes: int,
) -> list[OHLCVBar]:
    """Aggregate minute rows into fixed-width OHLCV bars.

    ``timeframe_minutes`` must be one of the approved strategy timeframes
    (15=M15, 240=H4, 1440=D1). The first bar's timestamp is anchored to the
    EET session boundary of the first row (converted to UTC). Subsequent bucket
    boundaries advance by exactly ``timeframe_minutes`` from that anchor.
    """
    if timeframe_minutes not in APPROVED_TIMEFRAMES:
        raise ValueError(
            f"timeframe {timeframe_minutes} not in approved set"
            f" {sorted(APPROVED_TIMEFRAMES)}"
        )
    if not rows:
        return []

    bars: list[OHLCVBar] = []
    bucket_start_utc: datetime | None = None
    bucket: list[MinuteRow] = []

    for r in rows:
        ts = parse_eet_timestamp(r.timestamp)
        current_bucket_start = _local_bucket_start(ts, timeframe_minutes)
        if bucket_start_utc != current_bucket_start:
            if bucket and bucket_start_utc is not None:
                bars.append(_close_bucket(bucket_start_utc, bucket))
            bucket_start_utc = current_bucket_start
            bucket = [r]
        else:
            bucket.append(r)

    if bucket and bucket_start_utc is not None:
        bars.append(_close_bucket(bucket_start_utc, bucket))

    return bars


def _local_bucket_start(timestamp_utc: datetime, timeframe_minutes: int) -> datetime:
    """Return a UTC bucket boundary derived from Europe/Helsinki wall time."""
    local = timestamp_utc.astimezone(_EET)
    midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
    elapsed_minutes = (
        local.replace(tzinfo=None) - midnight.replace(tzinfo=None)
    ).total_seconds() // 60
    bucket_minutes = int(elapsed_minutes // timeframe_minutes * timeframe_minutes)
    local_start = midnight + timedelta(minutes=bucket_minutes)
    return local_start.astimezone(timezone.utc)


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
    offline_domains: Sequence[OfflineDomain],
) -> GapStatus:
    """Classify the gap between two consecutive UTC timestamps.

    Fail-closed: an unexplained gap (no matching offline-domain evidence) is
    always UNRESOLVED. Zero-volume rows are not evidence of closure.
    """
    expected_next = previous + _ONE_MINUTE
    if current <= expected_next:
        return GapStatus.EXPLAINED

    for domain in offline_domains:
        if _domain_covers(domain, expected_next, current):
            return GapStatus.EXPLAINED

    return GapStatus.UNRESOLVED


def _domain_covers(domain: OfflineDomain, gap_start: datetime, gap_end: datetime) -> bool:
    """Return True when the offline domain interval fully covers the gap."""
    return domain.start <= gap_start and domain.end >= gap_end
