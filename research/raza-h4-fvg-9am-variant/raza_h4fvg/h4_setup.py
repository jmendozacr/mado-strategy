"""Steps 2/3: the reference candle, the known-at-09:00 FVG key level,
and the 13:00 H4 decision.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
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
H4_DURATION = timedelta(hours=4)
H4_EXPECTED_COUNT = 16
_TOL = 1e-9


@dataclass(frozen=True)
class H4SetupResult:
    qualifies: bool
    reason: str
    reference_high: float | None = None
    reference_low: float | None = None
    swept_extreme: float | None = None
    target_edge: float | None = None
    sweep_side: str | None = None
    close_position: str | None = None


def known_fvgs_at(fvgs: list, h4_candles: tuple, instant_utc: datetime) -> list:
    """An FVG is "known" at `instant_utc` if its own origin (`end_index`,
    the 3rd H4 candle completing the gap -- `fvgs` are detected on the
    H4 series, so `end_index` indexes INTO `h4_candles`, never M15)
    closes strictly before it -- `available_at`, reused unmodified.
    Fill status is never checked (the EXISTING `fvg_to_key_levels`
    never tracks FVG expiry either -- this follows that same
    convention, not a new one)."""
    out = []
    for fvg in fvgs:
        origin_candle = h4_candles[fvg.end_index]
        if ci.available_at(origin_candle, ci.H4_DURATION) < instant_utc:
            out.append(fvg)
    return out


def h4_decision(
    m15_timestamps: list[datetime], m15_candles: tuple, current_open_ts: datetime,
    daily_bias: str, fvgs_known_at_0900: list,
) -> H4SetupResult:
    reference_open = current_open_ts - H4_DURATION
    reference = complete_candle_with_close(m15_timestamps, m15_candles, reference_open, H4_DURATION, H4_EXPECTED_COUNT)
    current = complete_candle_with_close(m15_timestamps, m15_candles, current_open_ts, H4_DURATION, H4_EXPECTED_COUNT)
    if reference is None or current is None:
        return H4SetupResult(False, "MISSING_DATA")

    close_position, sweep_side = classify_sweep_and_close(
        reference.high, reference.low, current.high, current.low, current.close,
    )
    if close_position != "INSIDE":
        return H4SetupResult(False, "NOT_INSIDE", reference.high, reference.low, None, None, sweep_side, close_position)
    if sweep_side == "BOTH":
        return H4SetupResult(False, "DOUBLE_SWEEP", reference.high, reference.low, None, None, sweep_side, close_position)
    if sweep_side == "NEITHER":
        return H4SetupResult(False, "NO_SWEEP", reference.high, reference.low, None, None, sweep_side, close_position)

    if daily_bias == "bullish" and sweep_side != "LOW_ONLY":
        return H4SetupResult(False, "DISAGREES_WITH_DAILY_BIAS", reference.high, reference.low, None, None, sweep_side, close_position)
    if daily_bias == "bearish" and sweep_side != "HIGH_ONLY":
        return H4SetupResult(False, "DISAGREES_WITH_DAILY_BIAS", reference.high, reference.low, None, None, sweep_side, close_position)

    if daily_bias == "bullish":
        swept_extreme, target_edge = current.low, reference.high
        gap_matches = any(
            fvg.direction == "bullish" and fvg.bottom - _TOL <= current.low <= fvg.top + _TOL
            for fvg in fvgs_known_at_0900
        )
    else:
        swept_extreme, target_edge = current.high, reference.low
        gap_matches = any(
            fvg.direction == "bearish" and fvg.bottom - _TOL <= current.high <= fvg.top + _TOL
            for fvg in fvgs_known_at_0900
        )

    if not gap_matches:
        return H4SetupResult(
            False, "NO_MATCHING_GAP", reference.high, reference.low, swept_extreme, target_edge,
            sweep_side, close_position,
        )

    return H4SetupResult(
        True, "OK", reference.high, reference.low, swept_extreme, target_edge, sweep_side, close_position,
    )
