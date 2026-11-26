"""Per-symbol, per-session orchestration: Steps 1-5 in sequence, for
every NY calendar date the M15 series covers.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

LAB_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = LAB_ROOT.parent.parent
DETECTOR_ROOT = REPO_ROOT / "detector"
AUDIT_ROOT = REPO_ROOT / "audit" / "2026-11-17-causal-lookahead-audit"
LPD_ROOT = REPO_ROOT / "research" / "loss-pattern-discovery"
for _path in (DETECTOR_ROOT, AUDIT_ROOT, LPD_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import causal_intrabar as ci  # noqa: E402
from core.config import DetectorConfig  # noqa: E402
from experimental.htf_trigger_1am_9am_backtest import SYMBOL_CONFIG  # noqa: E402
from primitives.fvg import detect_fvgs  # noqa: E402
from primitives.swing import detect_swings  # noqa: E402

from extract.funnel_reconstruction import START_DATE, _load_symbol_data  # noqa: E402

from raza_h4fvg.candidate_and_fill import resolve_candidate  # noqa: E402
from raza_h4fvg.daily_bias import daily_bias_for_session  # noqa: E402
from raza_h4fvg.h4_setup import h4_decision, known_fvgs_at  # noqa: E402
from raza_h4fvg.m15_entry import search_entry  # noqa: E402

_NY = ZoneInfo("America/New_York")
_UTC = ZoneInfo("UTC")
ONE_DAY = timedelta(days=1)

QUALIFYING_H4_REASONS = {"OK"}
NOT_QUALIFYING_H4_REASONS = {
    "MISSING_DATA", "NOT_INSIDE", "DOUBLE_SWEEP", "NO_SWEEP", "DISAGREES_WITH_DAILY_BIAS", "NO_MATCHING_GAP",
}


def run_symbol(symbol: str, start_date=START_DATE, end_date=None) -> dict:
    h4, m15, daily = _load_symbol_data(symbol)
    config = DetectorConfig(backtest=SYMBOL_CONFIG[symbol])
    m15_timestamps = [c.timestamp for c in m15.candles]
    swings = detect_swings(m15, config.swing)
    indices = [s.index for s in swings]
    fvgs = detect_fvgs(h4, config.fvg)

    first_day = m15.candles[0].timestamp.replace(tzinfo=_UTC).astimezone(_NY).date()
    last_day = m15.candles[-1].timestamp.replace(tzinfo=_UTC).astimezone(_NY).date()

    sessions: dict[str, dict] = {}
    day = first_day
    while day <= last_day:
        current_open_ts = ci.ny_anchored_open_utc(day, 9)
        day_key = day.isoformat()
        day_next = day + ONE_DAY
        day = day_next

        if start_date is not None and current_open_ts < start_date:
            continue
        if end_date is not None and current_open_ts > end_date:
            continue

        bias_result = daily_bias_for_session(m15_timestamps, m15.candles, date.fromisoformat(day_key))
        if bias_result.bias is None:
            sessions[day_key] = {"outcome": "NO_DAILY_BIAS", "reason": bias_result.reason, "qualifying_h4_setup": False}
            continue

        nine_am_ny_instant = ci.ny_anchored_open_utc(date.fromisoformat(day_key), 9)
        fvgs_known = known_fvgs_at(fvgs, h4.candles, nine_am_ny_instant)
        h4_result = h4_decision(m15_timestamps, m15.candles, current_open_ts, bias_result.bias, fvgs_known)
        if not h4_result.qualifies:
            sessions[day_key] = {
                "outcome": h4_result.reason, "reason": h4_result.reason, "qualifying_h4_setup": False,
                "daily_bias": bias_result.bias,
            }
            continue

        entry_result = search_entry(
            m15_timestamps, m15.candles, current_open_ts, bias_result.bias,
            h4_result.swept_extreme, h4_result.target_edge, config.model1,
        )
        base_record = {
            "qualifying_h4_setup": True, "daily_bias": bias_result.bias,
            "sweep_side": h4_result.sweep_side, "swept_extreme": h4_result.swept_extreme,
            "target_edge": h4_result.target_edge,
        }
        if entry_result.outcome != "ENTER_CANDIDATE":
            sessions[day_key] = {**base_record, "outcome": entry_result.outcome}
            continue

        resolution = resolve_candidate(
            entry_result.signal, m15, config, swings, indices,
            h4_result.reference_high, h4_result.reference_low, current_open_ts, m15_timestamps,
        )
        r_multiple = resolution.trade.r_multiple if resolution.outcome == "ENTERED" and resolution.trade.outcome != "open" else None
        sessions[day_key] = {
            **base_record, "outcome": resolution.outcome, "risk_reward": resolution.risk_reward,
            "r_multiple": r_multiple,
            "trade_outcome": resolution.trade.outcome if resolution.outcome == "ENTERED" else None,
        }

    return {"symbol": symbol, "sessions": sessions}
