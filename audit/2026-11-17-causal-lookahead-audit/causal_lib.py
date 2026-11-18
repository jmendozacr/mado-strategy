"""Phase 2 causal-reproduction library. Reuses detector internals UNMODIFIED
(imported, never copied/edited) wherever the existing logic is already
causally correct; builds new orchestration only where it is not (B2's
confirmation-window intersection; B1's placement-floored fill pass).

Nothing under detector/ or scanner/ is modified. This module only imports
and calls what already exists.

Shared, expensive detection (CRT ranges on M15, swings, FVG/Order-Block
key levels, H4 Turtle Soup triggers) is computed ONCE per symbol and reused
across Arm A, B1, and B2 -- only the per-trigger confirmation window and the
fill-eligibility floor differ between arms. See run_experiment.py.
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass
from datetime import datetime, timedelta

from alignment.htf_ltf import AlignedSignal, _reindex_daily_key_levels
from causal.htf_trigger import (
    MODEL_1AM,
    MODEL_9AM,
    FeederModel,
    confirm_in_ltf_window,
    confirmation_window_utc,
    find_turtle_soup_triggers,
    ltf_window_indices,
)
from composite.ict_order_block import detect_order_blocks, to_key_levels as ob_to_key_levels
from core.candle import OHLCSeries
from core.config import DetectorConfig
from core.key_level import KeyLevel
from primitives.crt_range import CRTRange, detect_crt_ranges
from primitives.fvg import detect_fvgs, to_key_levels as fvg_to_key_levels
from primitives.swing import SwingPoint, detect_swings

MODELS: tuple[FeederModel, ...] = (MODEL_1AM, MODEL_9AM)


def build_key_levels(htf_series: OHLCSeries, daily_series: OHLCSeries, fvg_config) -> list[KeyLevel]:
    """Byte-for-byte copy of experimental.htf_trigger_1am_9am_backtest.build_key_levels
    / scanner.main._build_key_levels -- replicated (not imported) for the
    same reason that module states: scanner.main pulls in MT5-only deps this
    suite cannot load, and importing the experimental module would re-run
    its own module-level SYMBOL_CONFIG construction unnecessarily. Logic is
    unchanged from both."""
    htf_fvg_levels = fvg_to_key_levels(detect_fvgs(htf_series, fvg_config))
    daily_ob_levels = ob_to_key_levels(detect_order_blocks(daily_series))
    htf_timestamps = [c.timestamp for c in htf_series.candles]
    reindexed_daily = _reindex_daily_key_levels(
        daily_ob_levels, daily_series.candles, htf_series.candles, htf_timestamps
    )
    return htf_fvg_levels + reindexed_daily


@dataclass(frozen=True)
class SharedDetection:
    """Everything expensive, computed ONCE per symbol and shared by every arm."""

    m15: OHLCSeries
    h4: OHLCSeries
    config: DetectorConfig
    ltf_ranges: list[CRTRange]
    swings: list[SwingPoint]
    triggers_by_model: dict[str, list]  # model.name -> list[HTFTrigger]
    m15_timestamps: list[datetime]


def compute_shared_detection(m15: OHLCSeries, h4: OHLCSeries, daily: OHLCSeries, config: DetectorConfig) -> SharedDetection:
    key_levels = build_key_levels(h4, daily, config.fvg)
    ltf_ranges = detect_crt_ranges(m15, config.crt_range)
    swings = detect_swings(m15, config.swing)
    triggers_by_model = {
        model.name: find_turtle_soup_triggers(h4.candles, key_levels, model) for model in MODELS
    }
    return SharedDetection(
        m15=m15, h4=h4, config=config, ltf_ranges=ltf_ranges, swings=swings,
        triggers_by_model=triggers_by_model, m15_timestamps=[c.timestamp for c in m15.candles],
    )


def trigger_h4_close(shared: SharedDetection, candle_index: int) -> datetime:
    """The triggering H4 candle's true, real-world close -- open time + 4h
    (H4 bars are 4 hours; Candle.timestamp is the bar's OPEN, confirmed via
    detector/ingestion/loader.py and the fixed 00/04/08/12/16/20 UTC grid
    causal/htf_trigger.py's own module docstring documents)."""
    return shared.h4.candles[candle_index].timestamp + timedelta(hours=4)


def m15_index_at_or_after(shared: SharedDetection, when: datetime) -> int | None:
    """First M15 candle index whose timestamp >= `when`, or None past the end."""
    idx = bisect.bisect_left(shared.m15_timestamps, when)
    if idx >= len(shared.m15_timestamps):
        return None
    return idx


def _assemble_aligned(trig, model: FeederModel, signal, shared: SharedDetection) -> AlignedSignal:
    prev_candle = shared.h4.candles[trig.candle_index - 1]
    htf_context = CRTRange(
        model="2-candle", high=prev_candle.high, low=prev_candle.low,
        start_index=trig.candle_index - 1, end_index=trig.candle_index,
        resolution="false_break", resolved_at_index=trig.candle_index,
    )
    return AlignedSignal(
        ltf_signal=signal, htf_context=htf_context, aligned="aligned",
        key_level=trig.key_level, key_level_reaction=trig.key_level_reaction,
    )


def stable_trigger_id(symbol: str, model_name: str, candle_index: int, direction: str) -> str:
    """Reconciliation key shared by every arm: identifies the H4 TRIGGER
    (shared, unmodified `find_turtle_soup_triggers` output), not the
    resulting LTF signal_id -- B2 can pick a different anchor than A/B1
    for the SAME trigger (its window differs), so signal_id alone cannot
    be used to match a trigger across arms."""
    return f"{symbol}|{model_name}|h4idx={candle_index}|{direction}"


def arm_a_signals(shared: SharedDetection, symbol: str):
    """Reproduces find_1am_9am_aligned_signals's exact logic (same window,
    same confirm_in_ltf_window call) but reusing the shared triggers/ranges
    and additionally returning the signal_id<->stable_id and
    signal_id->h4-close maps, so the caller doesn't need a second, separate
    causal.htf_trigger call. Not a copy for its own sake: it is the same
    control flow because Arm A's window IS the production window -- only
    instrumented to expose the trigger linkage the production function's
    return type doesn't carry.

    Returns (results[(aligned, model_name, stable_id)], signal_id_to_stable_id, signal_id_to_h4_close).
    """
    results: list[tuple[AlignedSignal, str, str]] = []
    signal_id_to_stable_id: dict[str, str] = {}
    signal_id_to_h4_close: dict[str, datetime] = {}
    for model in MODELS:
        for trig in shared.triggers_by_model[model.name]:
            trigger_candle = shared.h4.candles[trig.candle_index]
            window_start, window_end = confirmation_window_utc(trigger_candle, model)
            window = ltf_window_indices(shared.m15.candles, window_start, window_end)
            if window is None:
                continue
            signal = confirm_in_ltf_window(
                shared.m15.candles, shared.ltf_ranges, window, trig.direction, shared.config.model1
            )
            if signal is None:
                continue
            aligned = _assemble_aligned(trig, model, signal, shared)
            sid = stable_trigger_id(symbol, model.name, trig.candle_index, trig.direction)
            results.append((aligned, model.name, sid))
            signal_id_to_stable_id[signal.signal_id] = sid
            signal_id_to_h4_close[signal.signal_id] = trigger_h4_close(shared, trig.candle_index)
    return results, signal_id_to_stable_id, signal_id_to_h4_close


def arm_b2_signals(shared: SharedDetection, symbol: str):
    """Strict-causality variant (S3 Arm B2): identical to arm_a_signals
    EXCEPT the confirmation window is intersected with
    [trigger_h4_close, window_end) before being handed to the UNMODIFIED
    `confirm_in_ltf_window` -- so no anchor/confirm/retest this function
    returns can ever have been found using information that, causally, did
    not yet exist (the H4 candle's own close). A confirmation that existed
    only before the close is never retroactively relabeled as "after" --
    it is simply never searched for in that already-passed portion of the
    window; confirm_in_ltf_window itself is reused byte-for-byte.

    Returns (results[(aligned, model_name, stable_id)], signal_id_to_h4_close,
    zero_signal_reason[stable_id -> why]) -- the third dict records, per
    trigger, WHY no B2 signal exists when the window-intersect leaves
    nothing to search (so a "0 trades for 9am" outcome is reported as a
    legitimate, explained result, not silently dropped). Every trigger
    gets EXACTLY one of: an entry in `results`, or an entry in
    `zero_signal_reason` -- never neither, never both."""
    results: list[tuple[AlignedSignal, str, str]] = []
    signal_id_to_h4_close: dict[str, datetime] = {}
    zero_signal_reason: dict[str, str] = {}
    for model in MODELS:
        for trig in shared.triggers_by_model[model.name]:
            trigger_candle = shared.h4.candles[trig.candle_index]
            window_start, window_end = confirmation_window_utc(trigger_candle, model)
            h4_close = trigger_h4_close(shared, trig.candle_index)
            sid = stable_trigger_id(symbol, model.name, trig.candle_index, trig.direction)
            b2_start = max(window_start, h4_close)
            if b2_start >= window_end:
                zero_signal_reason[sid] = (
                    f"confirmation window [{window_start.isoformat()}, {window_end.isoformat()}) "
                    f"ends at or before the H4 close {h4_close.isoformat()} -- no causally valid "
                    f"portion of the window remains to search."
                )
                continue
            window = ltf_window_indices(shared.m15.candles, b2_start, window_end)
            if window is None:
                zero_signal_reason[sid] = (
                    f"no M15 candle falls inside the causally-valid sub-window "
                    f"[{b2_start.isoformat()}, {window_end.isoformat()})."
                )
                continue
            signal = confirm_in_ltf_window(
                shared.m15.candles, shared.ltf_ranges, window, trig.direction, shared.config.model1
            )
            if signal is None:
                zero_signal_reason[sid] = (
                    "no anchor/confirmation/retest completed inside the causally-valid "
                    f"sub-window [{b2_start.isoformat()}, {window_end.isoformat()})."
                )
                continue
            aligned = _assemble_aligned(trig, model, signal, shared)
            results.append((aligned, model.name, sid))
            signal_id_to_h4_close[signal.signal_id] = h4_close
    return results, signal_id_to_h4_close, zero_signal_reason
