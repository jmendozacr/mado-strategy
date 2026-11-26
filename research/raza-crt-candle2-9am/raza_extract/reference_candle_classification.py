"""Raza close-back-inside-rule classification for the 9AM D3/C2 baseline.

Reuses, read-only and byte-for-byte unmodified: `causal_intrabar.
complete_feeder_candle_ny` (reference candle high/low reconstruction),
`run_d1_d2_d3.run_d_c2` (via the sibling lab's own
`model1_rejection_diagnostics.run_d_c2_instrumented`, for the
authoritative trigger population), `backtest.population.
build_stage6_population`, `causal_intrabar.fill_pass_c`, `backtest.
simulate._resolve_exits` -- the SAME functions, called in the SAME
order, Phase 8-10 already proved equivalent to the real pipeline. This
module mirrors `research/loss-pattern-discovery/extract/
funnel_reconstruction.py::reconstruct_for_symbol`'s own call sequence
(that function's own return value does not expose per-signal
candidate/fill membership, only aggregate counts) -- it is NOT a
reimplementation of any decision: every classification this module
adds (close-position, sweep-side, Raza direction) is a NEW, read-only
computation over the CURRENT H4 candle's own complete 09:00-13:00 NY
span, which the real pipeline never needed to reconstruct (it only
tracks a provisional running high/low during the shorter activation
window).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

LAB_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = LAB_ROOT.parent.parent
DETECTOR_ROOT = REPO_ROOT / "detector"
AUDIT_ROOT = REPO_ROOT / "audit" / "2026-11-17-causal-lookahead-audit"
LPD_ROOT = REPO_ROOT / "research" / "loss-pattern-discovery"
for _path in (LAB_ROOT, DETECTOR_ROOT, AUDIT_ROOT, LPD_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import causal_intrabar as ci  # noqa: E402
from backtest.population import build_stage6_population  # noqa: E402
from backtest.simulate import _resolve_exits  # noqa: E402
from causal_lib import build_key_levels  # noqa: E402
from core.config import DetectorConfig  # noqa: E402
from experimental.htf_trigger_1am_9am_backtest import SYMBOL_CONFIG  # noqa: E402
from primitives.swing import detect_swings  # noqa: E402

from extract.funnel_reconstruction import ARM_NAME, START_DATE, WINDOWS_9AM, _load_symbol_data  # noqa: E402
from extract.model1_rejection_diagnostics import (  # noqa: E402
    _window_open_ts_from_stable_id, run_d_c2_instrumented,
)

_NY = ZoneInfo("America/New_York")
_UTC = ZoneInfo("UTC")
_TOL = 1e-9
H4_DURATION = timedelta(hours=4)
REF_HOUR_NY = 5  # "9am" model's reference-candle open, same NY calendar day (causal_intrabar.REFERENCE_HOUR_NY)


@dataclass(frozen=True)
class CandleClassification:
    stable_id: str
    symbol: str
    direction: str
    current_open_ts: datetime
    h4_close_available_ts: datetime
    reference_low: float | None
    reference_high: float | None
    current_high: float | None
    current_low: float | None
    current_close: float | None
    close_position: str  # INSIDE / OUTSIDE / EXACT_BOUNDARY / MISSING_OR_INCOMPLETE
    sweep_side: str  # HIGH_ONLY / LOW_ONLY / BOTH / MISSING_OR_INCOMPLETE / NEITHER_ANOMALY
    raza_direction: str  # "bearish" / "bullish" / "DOUBLE_SWEEP_AMBIGUOUS" / "MISSING_OR_INCOMPLETE"


def _reference_open_ts_for(current_open_ts: datetime) -> datetime:
    """09:00 NY and 05:00 NY are the SAME NY calendar day for the 9AM
    model (`causal_intrabar.REFERENCE_IS_PREVIOUS_DAY["9am"] is False`)
    -- recovers that day from `current_open_ts` (a UTC instant) via the
    same DST-aware `zoneinfo` conversion `ny_anchored_open_utc` itself
    uses, never naive UTC arithmetic."""
    day = current_open_ts.replace(tzinfo=_UTC).astimezone(_NY).date()
    local = datetime(day.year, day.month, day.day, REF_HOUR_NY, tzinfo=_NY)
    return local.astimezone(_UTC).replace(tzinfo=None)


def _complete_feeder_candle_with_close(m15_timestamps, m15_candles, open_ts):
    """Identical bucket-building to `causal_intrabar.
    complete_feeder_candle_ny` (same bisect calls, same completeness
    check) -- adds the bucket's own last M15 candle's `close`, which
    that function's own `CompleteFeederCandle` never exposes, since the
    real pipeline never needs the current candle's final close (only
    its high/low, for the reference side)."""
    import bisect

    close_ts = open_ts + H4_DURATION
    start = bisect.bisect_left(m15_timestamps, open_ts)
    end = bisect.bisect_left(m15_timestamps, close_ts)
    bucket = m15_candles[start:end]
    if not ci.validate_complete_feeder_bucket(bucket, open_ts):
        return None
    return {
        "high": max(c.high for c in bucket), "low": min(c.low for c in bucket),
        "close": bucket[-1].close, "open_ts": open_ts, "close_ts": close_ts,
    }


def classify_one(symbol: str, direction: str, stable_id: str, current_open_ts: datetime, m15_timestamps, m15_candles) -> CandleClassification:
    h4_close_available_ts = current_open_ts + H4_DURATION
    reference_open_ts = _reference_open_ts_for(current_open_ts)
    reference = ci.complete_feeder_candle_ny(m15_timestamps, m15_candles, reference_open_ts)
    current = _complete_feeder_candle_with_close(m15_timestamps, m15_candles, current_open_ts)

    if reference is None or current is None:
        return CandleClassification(
            stable_id, symbol, direction, current_open_ts, h4_close_available_ts,
            reference.high if reference else None, reference.low if reference else None,
            current["high"] if current else None, current["low"] if current else None,
            current["close"] if current else None,
            "MISSING_OR_INCOMPLETE", "MISSING_OR_INCOMPLETE", "MISSING_OR_INCOMPLETE",
        )

    ref_low, ref_high = reference.low, reference.high
    cur_high, cur_low, cur_close = current["high"], current["low"], current["close"]

    high_swept = (cur_high - ref_high) > _TOL
    low_swept = (ref_low - cur_low) > _TOL
    if high_swept and low_swept:
        sweep_side, raza_direction = "BOTH", "DOUBLE_SWEEP_AMBIGUOUS"
    elif high_swept:
        sweep_side, raza_direction = "HIGH_ONLY", "bearish"
    elif low_swept:
        sweep_side, raza_direction = "LOW_ONLY", "bullish"
    else:
        sweep_side, raza_direction = "NEITHER_ANOMALY", "NEITHER_ANOMALY"

    if abs(cur_close - ref_low) <= _TOL or abs(cur_close - ref_high) <= _TOL:
        close_position = "EXACT_BOUNDARY"
    elif ref_low < cur_close < ref_high:
        close_position = "INSIDE"
    else:
        close_position = "OUTSIDE"

    return CandleClassification(
        stable_id, symbol, direction, current_open_ts, h4_close_available_ts,
        ref_low, ref_high, cur_high, cur_low, cur_close, close_position, sweep_side, raza_direction,
    )


def build_funnel_for_symbol(symbol: str, start_date=START_DATE, end_date=None) -> dict:
    """Full per-trigger reconstruction for one symbol's 9AM triggers:
    close-position classification (every trigger) + confirmed/candidate/
    filled/executed stage flags (via the same real functions Phase 8-10
    verified), + original trade outcome (via the real, unmodified
    ledger-producing `_resolve_exits`, never a resimulation)."""
    h4, m15, daily = _load_symbol_data(symbol)
    config = DetectorConfig(backtest=SYMBOL_CONFIG[symbol])
    m15_timestamps = [c.timestamp for c in m15.candles]
    swings = detect_swings(m15, config.swing)
    key_levels = build_key_levels(h4, daily, config.fvg)

    records_with_ids, counters, _diag = run_d_c2_instrumented(
        symbol, h4, m15, daily, config, m15_timestamps, key_levels,
        WINDOWS_9AM, ARM_NAME, start_date=start_date, end_date=end_date,
    )
    nine_am = [(r, sid) for r, sid in records_with_ids if r.model_name == "9am"]

    classifications: dict[str, CandleClassification] = {}
    for record, sid in nine_am:
        current_open_ts = _window_open_ts_from_stable_id(sid)
        classifications[sid] = classify_one(
            symbol, record.direction, sid, current_open_ts, m15_timestamps, m15.candles,
        )

    aligned_records = [(r, sid) for r, sid in nine_am if r.aligned is not None]
    aligned_signals = [r.aligned for r, _sid in aligned_records]
    stable_by_sig = {r.aligned.ltf_signal.signal_id: sid for r, sid in aligned_records}
    order_placed_by_sig = {r.aligned.ltf_signal.signal_id: r.order_placed_ts for r, _sid in aligned_records}
    confirmation_idx_by_sig = {r.aligned.ltf_signal.signal_id: r.confirmation_index for r, _sid in aligned_records}

    population = build_stage6_population(aligned_signals, m15, config, swings=swings)
    candidate_sids = {stable_by_sig[c.signal_id] for c in population.candidates}

    filled, _never_filled_count, _skipped_count = ci.fill_pass_c(
        population.candidates, m15.candles, m15_timestamps, config.backtest.max_fill_wait,
        order_placed_by_sig, confirmation_idx_by_sig,
    )
    filled_sids = {stable_by_sig[c.signal_id] for c, _fill_idx in filled}

    trades = _resolve_exits(
        filled, m15.candles, config.backtest.trading_cost_price, config.backtest.partial_fraction,
        breakeven_after_partial=config.backtest.breakeven_after_partial,
    )
    executed_by_sid = {stable_by_sig[t.signal_id]: t for t in trades if t.signal_id in stable_by_sig}

    confirmed_sids = {sid for _r, sid in aligned_records}

    return {
        "symbol": symbol,
        "classifications": classifications,
        "confirmed_sids": confirmed_sids,
        "candidate_sids": candidate_sids,
        "filled_sids": filled_sids,
        "executed_by_sid": executed_by_sid,
        "n_triggers": len(nine_am),
    }
