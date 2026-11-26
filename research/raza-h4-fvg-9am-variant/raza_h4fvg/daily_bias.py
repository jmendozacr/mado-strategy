"""Step 1: daily bias, using daily candles closing at 17:00 NY --
reconstructed fresh from the M15 series (NOT the existing D1 CSV-loaded
`daily` OHLCSeries, which is UTC-midnight-anchored -- verified real
timestamps are `00:00:00`, not 17:00 NY; reusing it as-is would
silently misalign with this protocol's own stated convention).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

LAB_ROOT = Path(__file__).resolve().parent.parent
AUDIT_ROOT = LAB_ROOT.parent.parent / "audit" / "2026-11-17-causal-lookahead-audit"
for _path in (AUDIT_ROOT,):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import causal_intrabar as ci  # noqa: E402

from raza_h4fvg.candles import classify_sweep_and_close, complete_candle_with_close  # noqa: E402

_NY = ZoneInfo("America/New_York")
_UTC = ZoneInfo("UTC")
DAILY_DURATION = timedelta(hours=24)
DAILY_EXPECTED_COUNT = 96  # 24h / 15min


def _daily_open_utc(ny_date: date) -> datetime:
    local = datetime(ny_date.year, ny_date.month, ny_date.day, 17, tzinfo=_NY)
    return local.astimezone(_UTC).replace(tzinfo=None)


@dataclass(frozen=True)
class DailyBiasResult:
    bias: str | None  # "bullish" / "bearish" / None
    reason: str  # "OK" / "MISSING_DATA" / "NO_SWEEP" / "DOUBLE_SWEEP" / "NOT_INSIDE"
    sweep_side: str | None
    close_position: str | None


def daily_bias_for_session(
    m15_timestamps: list[datetime], m15_candles: tuple, session_date: date,
) -> DailyBiasResult:
    """`session_date` is the NY calendar date of the 9AM session being
    evaluated. The latest daily candle completed strictly before 09:00
    NY on that date spans [17:00 NY (session_date - 2), 17:00 NY
    (session_date - 1)]; the preceding one spans [17:00 NY
    (session_date - 3), 17:00 NY (session_date - 2)]."""
    today_open = _daily_open_utc(session_date - timedelta(days=2))
    yesterday_open = _daily_open_utc(session_date - timedelta(days=3))

    today = complete_candle_with_close(m15_timestamps, m15_candles, today_open, DAILY_DURATION, DAILY_EXPECTED_COUNT)
    yesterday = complete_candle_with_close(
        m15_timestamps, m15_candles, yesterday_open, DAILY_DURATION, DAILY_EXPECTED_COUNT,
    )
    if today is None or yesterday is None:
        return DailyBiasResult(None, "MISSING_DATA", None, None)

    close_position, sweep_side = classify_sweep_and_close(
        yesterday.high, yesterday.low, today.high, today.low, today.close,
    )
    if close_position != "INSIDE":
        return DailyBiasResult(None, "NOT_INSIDE", sweep_side, close_position)
    if sweep_side == "LOW_ONLY":
        return DailyBiasResult("bullish", "OK", sweep_side, close_position)
    if sweep_side == "HIGH_ONLY":
        return DailyBiasResult("bearish", "OK", sweep_side, close_position)
    if sweep_side == "BOTH":
        return DailyBiasResult(None, "DOUBLE_SWEEP", sweep_side, close_position)
    return DailyBiasResult(None, "NO_SWEEP", sweep_side, close_position)
