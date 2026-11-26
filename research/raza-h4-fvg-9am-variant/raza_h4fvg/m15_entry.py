"""Step 4: the M15 entry search, scoped to bars opening at or after
13:00 NY, bounded by 15:00 NY -- Mado's own `causal_anchor_v2.
confirm_in_ltf_window_v2` (anchor + `entries.model1._track_anchor`
engulf/retest/retry), reused unmodified, direction FIXED to the daily
bias. A separate, independent invalidation scan over the same window
decides precedence against Model-1's own confirmation index.
"""
from __future__ import annotations

import bisect
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

LAB_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = LAB_ROOT.parent.parent
DETECTOR_ROOT = REPO_ROOT / "detector"
AUDIT_ROOT = REPO_ROOT / "audit" / "2026-11-17-causal-lookahead-audit"
for _path in (DETECTOR_ROOT, AUDIT_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import causal_anchor_v2 as ca  # noqa: E402
from core.config import Model1Config  # noqa: E402

_NY = ZoneInfo("America/New_York")
_UTC = ZoneInfo("UTC")
FOUR_HOURS = timedelta(hours=4)  # confirm_in_ltf_window_v2's own default anchor-age window


def _ny_instant_utc(ny_date, hour_ny: int) -> datetime:
    local = datetime(ny_date.year, ny_date.month, ny_date.day, hour_ny, tzinfo=_NY)
    return local.astimezone(_UTC).replace(tzinfo=None)


@dataclass(frozen=True)
class EntrySearchResult:
    outcome: str  # "ENTER_CANDIDATE" / "DISCARD_SWEPT_EXTREME_BREACH" / "DISCARD_TARGET_BEFORE_ENTRY" / "EXPIRED"
    signal: object | None  # the real, unmodified Model1Signal if ENTER_CANDIDATE
    invalidation_index: int | None


def _window_indices(m15_timestamps: list[datetime], current_open_ts: datetime) -> tuple[int, int]:
    session_date = current_open_ts.replace(tzinfo=_UTC).astimezone(_NY).date()
    start_ts = _ny_instant_utc(session_date, 13)
    end_ts = _ny_instant_utc(session_date, 15)
    start_idx = bisect.bisect_left(m15_timestamps, start_ts)
    end_idx = bisect.bisect_left(m15_timestamps, end_ts) - 1  # last bar strictly before 15:00
    return start_idx, end_idx


def _first_invalidation_index(
    m15_candles: tuple, window: tuple[int, int], direction: str, swept_extreme: float, target_edge: float,
) -> tuple[int | None, str | None]:
    start, end = window
    for j in range(start, end + 1):
        c = m15_candles[j]
        if direction == "bullish":
            extreme_breached = c.low <= swept_extreme
            target_reached = c.high >= target_edge
        else:
            extreme_breached = c.high >= swept_extreme
            target_reached = c.low <= target_edge
        if target_reached:
            return j, "DISCARD_TARGET_BEFORE_ENTRY"
        if extreme_breached:
            return j, "DISCARD_SWEPT_EXTREME_BREACH"
    return None, None


def search_entry(
    m15_timestamps: list[datetime], m15_candles: tuple, current_open_ts: datetime,
    direction: str, swept_extreme: float, target_edge: float, config: Model1Config = Model1Config(),
) -> EntrySearchResult:
    window = _window_indices(m15_timestamps, current_open_ts)
    start, end = window
    if start > end or start >= len(m15_candles):
        return EntrySearchResult("EXPIRED", None, None)

    signal = ca.confirm_in_ltf_window_v2(m15_candles, window, direction, config, age=FOUR_HOURS)
    confirmed = signal is not None and signal.status.name == "CONFIRMED"
    confirmation_index = signal.confirmation_index if confirmed else None

    inval_index, inval_reason = _first_invalidation_index(m15_candles, window, direction, swept_extreme, target_edge)

    if confirmed and (inval_index is None or inval_index > confirmation_index):
        return EntrySearchResult("ENTER_CANDIDATE", signal, inval_index)
    if inval_index is not None:
        return EntrySearchResult(inval_reason, None, inval_index)
    return EntrySearchResult("EXPIRED", None, None)
