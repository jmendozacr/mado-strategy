"""Generic candle-bucket reconstruction and sweep/close classification,
shared by the daily-bias check (Step 1) and the H4 decision (Step 3) --
same arithmetic, different durations. Reuses `causal_intrabar.
validate_complete_feeder_bucket` unmodified for the completeness check;
never a second, divergent implementation of it.
"""
from __future__ import annotations

import bisect
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = LAB_ROOT.parent.parent
AUDIT_ROOT = REPO_ROOT / "audit" / "2026-11-17-causal-lookahead-audit"
for _path in (AUDIT_ROOT,):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import causal_intrabar as ci  # noqa: E402

_TOL = 1e-9


@dataclass(frozen=True)
class CompleteCandle:
    open_ts: datetime
    close_ts: datetime
    high: float
    low: float
    close: float


def complete_candle_with_close(
    m15_timestamps: list[datetime], m15_candles: tuple, open_ts: datetime, duration: timedelta,
    expected_count: int,
) -> CompleteCandle | None:
    """Generalizes `causal_intrabar.complete_feeder_candle_ny`'s own
    bucket-building to an arbitrary span (H4: 4h/16 bars; daily: 24h/96
    bars) -- same bisect calls, same completeness check
    (`validate_complete_feeder_bucket`, reused unmodified), plus the
    bucket's own last candle's `close` (needed for the close-back-
    inside check; the original function never exposes it since the
    production pipeline only ever needs a reference candle's high/low)."""
    close_ts = open_ts + duration
    start = bisect.bisect_left(m15_timestamps, open_ts)
    end = bisect.bisect_left(m15_timestamps, close_ts)
    bucket = m15_candles[start:end]
    if not ci.validate_complete_feeder_bucket(bucket, open_ts, expected_count=expected_count):
        return None
    return CompleteCandle(
        open_ts=open_ts, close_ts=close_ts,
        high=max(c.high for c in bucket), low=min(c.low for c in bucket), close=bucket[-1].close,
    )


def classify_sweep_and_close(
    reference_high: float, reference_low: float,
    current_high: float, current_low: float, current_close: float,
) -> tuple[str, str]:
    """Pure arithmetic, shared by the daily-bias check and the H4
    decision. Returns (close_position, sweep_side).

    close_position: INSIDE / OUTSIDE / EXACT_BOUNDARY (strict, 1e-9
    tolerance -- same convention as `raza-crt-candle2-9am`).
    sweep_side: HIGH_ONLY / LOW_ONLY / BOTH / NEITHER.
    """
    high_swept = (current_high - reference_high) > _TOL
    low_swept = (reference_low - current_low) > _TOL
    if high_swept and low_swept:
        sweep_side = "BOTH"
    elif high_swept:
        sweep_side = "HIGH_ONLY"
    elif low_swept:
        sweep_side = "LOW_ONLY"
    else:
        sweep_side = "NEITHER"

    if abs(current_close - reference_low) <= _TOL or abs(current_close - reference_high) <= _TOL:
        close_position = "EXACT_BOUNDARY"
    elif reference_low < current_close < reference_high:
        close_position = "INSIDE"
    else:
        close_position = "OUTSIDE"

    return close_position, sweep_side
