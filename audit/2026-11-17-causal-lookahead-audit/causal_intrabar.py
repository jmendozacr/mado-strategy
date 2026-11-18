"""Arms C1/C2 — intrabar causal detector. Design: design-c1-c2.md (rounds
1-3). Reuses detector internals UNMODIFIED wherever already causally
correct (imported, never copied/edited): `_purge_wick_extremes`,
`confirm_in_ltf_window`, `confirmation_window_utc`, `ltf_window_indices`,
`detect_crt_ranges`, `detect_swings`, `build_stage6_population`,
`_fill_sides`, `two_heap_sweep`, `_resolve_exits`. New code is limited to:
(1) the sweep+Key-Level trigger itself (replacing the close-based
`find_turtle_soup_triggers`, per the user's confirmed operative rule --
no H4-close/no-reentry requirement); (2) `key_level_credited`, a
timestamp-space restatement of `_key_level_credit_map`'s exact rule
(needed because C1's broker grid and C2's NY-anchored grid are not
index-comparable); (3) `fill_pass_c`, floored at `first_fillable_index`
(the bar strictly after Model-1's own confirmation bar), not
`retest_index` or `confirmation_index`.

Nothing under detector/ or scanner/ is modified.
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from alignment.htf_ltf import AlignedSignal, _purge_wick_extremes
from backtest.candidate import Candidate
from backtest.simulate import _fill_sides
from causal.htf_trigger import (
    MODEL_1AM,
    MODEL_9AM,
    FeederModel,
    confirm_in_ltf_window,
    confirmation_window_utc,
    ltf_window_indices,
)
from core.candle import Candle, OHLCSeries
from core.key_level import KeyLevel
from core.results import DetectionStatus
from core.sweep import two_heap_sweep
from primitives.crt_range import CRTRange

M15_DURATION = timedelta(minutes=15)
H4_DURATION = timedelta(hours=4)
_NY = ZoneInfo("America/New_York")
_UTC = ZoneInfo("UTC")

MODELS: tuple[FeederModel, ...] = (MODEL_1AM, MODEL_9AM)
# Which NY-local hour is "the reference candle" for each model's "core model"
# two-consecutive-feeder-candle variant (design §0 scope lock): 1AM's
# reference is 9PM (previous calendar day), 9AM's is 5AM (same day).
REFERENCE_HOUR_NY = {"1am": 21, "9am": 5}
CURRENT_HOUR_NY = {"1am": 1, "9am": 9}
REFERENCE_IS_PREVIOUS_DAY = {"1am": True, "9am": False}


# ---------------------------------------------------------------------------
# Bar contract (design §3)
# ---------------------------------------------------------------------------

def available_at(candle: Candle, duration: timedelta) -> datetime:
    """The only field ever read for "is this known yet" -- a bar's own
    close, never its open."""
    return candle.timestamp + duration


# ---------------------------------------------------------------------------
# Feeder candle construction (design §3/§4)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CompleteFeederCandle:
    high: float
    low: float
    open_ts: datetime
    close_ts: datetime


@dataclass(frozen=True)
class ProvisionalFeederCandle:
    """No `close` field -- a final value of an open candle cannot exist
    here, by construction, not by convention."""
    running_high: float
    running_low: float
    open_ts: datetime
    as_of_ts: datetime


def ny_anchored_open_utc(date_ny, hour_ny: int) -> datetime:
    local = datetime(date_ny.year, date_ny.month, date_ny.day, hour_ny, tzinfo=_NY)
    return local.astimezone(_UTC).replace(tzinfo=None)


def validate_complete_feeder_bucket(
    bucket: tuple[Candle, ...], expected_open_ts: datetime, expected_count: int = 16
) -> bool:
    if len(bucket) != expected_count:
        return False
    if bucket[0].timestamp != expected_open_ts:
        return False
    return all(
        bucket[i + 1].timestamp - bucket[i].timestamp == M15_DURATION
        for i in range(len(bucket) - 1)
    )


def complete_feeder_candle_ny(
    m15_timestamps: list[datetime], m15_candles: tuple[Candle, ...], open_ts: datetime
) -> CompleteFeederCandle | None:
    """None (never a synthesized candle) when the bucket fails §4's
    completeness check -- holidays/gaps/DST-affected days are skipped,
    never filled in."""
    close_ts = open_ts + H4_DURATION
    start = bisect.bisect_left(m15_timestamps, open_ts)
    end = bisect.bisect_left(m15_timestamps, close_ts)
    bucket = m15_candles[start:end]
    if not validate_complete_feeder_bucket(bucket, open_ts):
        return None
    return CompleteFeederCandle(
        high=max(c.high for c in bucket), low=min(c.low for c in bucket),
        open_ts=open_ts, close_ts=close_ts,
    )


def complete_feeder_candle_broker(h4_broker: OHLCSeries, index: int) -> CompleteFeederCandle:
    """C1's reference candle is simply the broker's own H4 bar at
    `index` -- already complete, already real data; no M15 reconstruction
    needed for the PREVIOUS candle (only the CURRENT, forming one needs
    the incremental, provisional view)."""
    candle = h4_broker.candles[index]
    return CompleteFeederCandle(
        high=candle.high, low=candle.low,
        open_ts=candle.timestamp, close_ts=candle.timestamp + H4_DURATION,
    )


# ---------------------------------------------------------------------------
# Key Level causal handling (design §2)
# ---------------------------------------------------------------------------

def key_level_credited(
    purge_extremes: tuple[float, ...], purge_observed_at: datetime,
    key_levels: list[KeyLevel], h4_broker: OHLCSeries,
) -> KeyLevel | None:
    """Restates `_key_level_credit_map`'s exact rule (origin strictly
    before the purge, unexpired, extreme inside the zone, highest-
    origin-index tiebreak) in TIMESTAMPS, because C1's broker-grid index
    and C2's NY-feeder index are not the same index space. KeyLevel
    SOURCE stays identical between C1 and C2 (same objects, same
    build_key_levels call) -- only this comparison changed."""

    def level_available_at(idx: int) -> datetime | None:
        # _ceiling_htf_index (alignment/htf_ltf.py) can return
        # len(htf_timestamps) as a "not yet knowable" sentinel -- indexing
        # at that value would raise IndexError.
        if idx >= len(h4_broker.candles):
            return None
        return available_at(h4_broker.candles[idx], H4_DURATION)

    def credited(level: KeyLevel) -> bool:
        origin_at = level_available_at(level.origin_index)
        if origin_at is None or origin_at >= purge_observed_at:
            return False
        if level.expiry_index is not None:
            expiry_at = level_available_at(level.expiry_index)
            if expiry_at is not None and purge_observed_at > expiry_at:
                return False
        return True

    qualifying = [
        level for extreme in purge_extremes for level in key_levels
        if credited(level) and level.bottom <= extreme <= level.top
    ]
    return max(qualifying, key=lambda lv: lv.origin_index) if qualifying else None


# ---------------------------------------------------------------------------
# The causal trigger itself: sweep + Key Level, observed incrementally
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CausalTrigger:
    direction: str  # "bullish" | "bearish"
    activation_instant_ts: datetime
    swept_extreme: float
    credited_level: KeyLevel


@dataclass(frozen=True)
class SweepOutcome:
    """Separates "the range was swept at all" from "...and a Key Level
    credited it" (validation point 6/7: register single- vs. both-sided
    sweeps, and which extreme/direction ultimately produced a signal,
    separately from whether it was ever usable)."""
    swept: bool
    trigger: CausalTrigger | None


def detect_sweep_and_key_level(
    m15_timestamps: list[datetime], m15_candles: tuple[Candle, ...],
    reference: CompleteFeederCandle, window_open_ts: datetime, window_close_ts: datetime,
    key_levels: list[KeyLevel], h4_broker: OHLCSeries,
) -> dict[str, SweepOutcome]:
    """Walks forward, M15 bar by M15 bar, through the CURRENT (forming)
    feeder candle's span, maintaining only the running high/low of bars
    ALREADY CLOSED -- never the candle's eventual final close. Returns at
    most one outcome per direction ("bearish"/"bullish" -- both can be
    present, ~14% of real purges breach both sides per
    `_purge_wick_extremes`'s own docstring): whether that side ever swept
    `reference`'s range at all, and, if so, the first instant a Key Level
    also credited it (`trigger=None` means swept but never credited
    within this window). `_purge_wick_extremes` is reused unmodified via
    a lightweight (high, low)-only proxy for both the running candle and
    the reference range."""
    start = bisect.bisect_left(m15_timestamps, window_open_ts)
    end = bisect.bisect_left(m15_timestamps, window_close_ts)
    candles = m15_candles[start:end]

    swept = {"bearish": False, "bullish": False}
    triggers: dict[str, CausalTrigger] = {}
    running_high: float | None = None
    running_low: float | None = None
    crt_range = SimpleNamespace(high=reference.high, low=reference.low)

    for candle in candles:
        running_high = candle.high if running_high is None else max(running_high, candle.high)
        running_low = candle.low if running_low is None else min(running_low, candle.low)
        observed_at = available_at(candle, M15_DURATION)

        provisional = SimpleNamespace(high=running_high, low=running_low)
        extremes = _purge_wick_extremes(provisional, crt_range)
        if not extremes:
            continue

        if running_high > reference.high:
            swept["bearish"] = True
            if "bearish" not in triggers:
                level = key_level_credited((running_high,), observed_at, key_levels, h4_broker)
                if level is not None:
                    triggers["bearish"] = CausalTrigger("bearish", observed_at, running_high, level)
        if running_low < reference.low:
            swept["bullish"] = True
            if "bullish" not in triggers:
                level = key_level_credited((running_low,), observed_at, key_levels, h4_broker)
                if level is not None:
                    triggers["bullish"] = CausalTrigger("bullish", observed_at, running_low, level)
        if "bearish" in triggers and "bullish" in triggers:
            break

    return {
        direction: SweepOutcome(swept=swept[direction], trigger=triggers.get(direction))
        for direction in ("bearish", "bullish")
    }


# ---------------------------------------------------------------------------
# Signal assembly: hands off to the UNMODIFIED Model-1 search
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CausalSignalRecord:
    """Carries every state-machine timestamp (design §5/§10) alongside the
    resulting AlignedSignal, for the reconciliation file and for tests."""
    aligned: AlignedSignal
    model_name: str
    direction: str
    feeder_ref_available_ts: datetime
    activation_instant_ts: datetime
    model1_available_ts: datetime
    confirmation_index: int
    order_placed_ts: datetime
    zero_signal_reason: str | None = None


def build_causal_signal(
    model: FeederModel, model_name: str, trigger: CausalTrigger,
    window_open_ts: datetime, m15_series: OHLCSeries, ltf_ranges: list[CRTRange],
    model1_config, reference: CompleteFeederCandle,
) -> CausalSignalRecord | None:
    """Reuses `confirmation_window_utc`/`ltf_window_indices`/
    `confirm_in_ltf_window` UNMODIFIED. The only new rule: the window is
    floored at `max(window_start, activation_instant)`, never at the H4
    close (that was B2's mistake) and never unbounded (the user's
    explicit, retained policy)."""
    trigger_proxy = SimpleNamespace(timestamp=window_open_ts)
    window_start, window_end = confirmation_window_utc(trigger_proxy, model)
    eligible_start = max(window_start, trigger.activation_instant_ts)
    if eligible_start >= window_end:
        return CausalSignalRecord(
            aligned=None, model_name=model_name, direction=trigger.direction,
            feeder_ref_available_ts=reference.close_ts,
            activation_instant_ts=trigger.activation_instant_ts,
            model1_available_ts=None, confirmation_index=None, order_placed_ts=None,
            zero_signal_reason=(
                f"window [{window_start.isoformat()}, {window_end.isoformat()}) ends at or "
                f"before activation {trigger.activation_instant_ts.isoformat()} -- no causally "
                f"valid portion of the window remains to search."
            ),
        )
    window = ltf_window_indices(m15_series.candles, eligible_start, window_end)
    if window is None:
        return CausalSignalRecord(
            aligned=None, model_name=model_name, direction=trigger.direction,
            feeder_ref_available_ts=reference.close_ts,
            activation_instant_ts=trigger.activation_instant_ts,
            model1_available_ts=None, confirmation_index=None, order_placed_ts=None,
            zero_signal_reason=f"no M15 candle falls inside [{eligible_start.isoformat()}, {window_end.isoformat()}).",
        )
    signal = confirm_in_ltf_window(m15_series.candles, ltf_ranges, window, trigger.direction, model1_config)
    if signal is None or signal.status != DetectionStatus.CONFIRMED:
        reason = (
            "no anchor/confirmation/retest completed inside the causally-valid window"
            if signal is None else
            f"Model-1 resolved {signal.status.name}, not CONFIRMED -- excluded per design S1.3's stricter filter"
        )
        return CausalSignalRecord(
            aligned=None, model_name=model_name, direction=trigger.direction,
            feeder_ref_available_ts=reference.close_ts,
            activation_instant_ts=trigger.activation_instant_ts,
            model1_available_ts=None, confirmation_index=None, order_placed_ts=None,
            zero_signal_reason=reason,
        )

    model1_available_ts = available_at(m15_series.candles[signal.confirmation_index], M15_DURATION)
    htf_context = CRTRange(
        model="2-candle", high=reference.high, low=reference.low,
        start_index=0, end_index=0, resolution="false_break", resolved_at_index=0,
    )
    aligned = AlignedSignal(
        ltf_signal=signal, htf_context=htf_context, aligned="aligned",
        key_level=trigger.credited_level, key_level_reaction=None,
    )
    return CausalSignalRecord(
        aligned=aligned, model_name=model_name, direction=trigger.direction,
        feeder_ref_available_ts=reference.close_ts,
        activation_instant_ts=trigger.activation_instant_ts,
        model1_available_ts=model1_available_ts,
        confirmation_index=signal.confirmation_index,
        order_placed_ts=model1_available_ts,
    )


# ---------------------------------------------------------------------------
# fill_pass_c (design §1.4, round-3 corrected)
# ---------------------------------------------------------------------------

def fill_pass_c(
    candidates: list[Candidate], candles: tuple[Candle, ...], m15_timestamps: list[datetime],
    max_fill_wait: int, order_placed_ts_by_signal_id: dict[str, datetime],
    confirmation_index_by_signal_id: dict[str, int],
):
    first_fillable: dict[str, int] = {}
    for sid, ts in order_placed_ts_by_signal_id.items():
        idx = bisect.bisect_left(m15_timestamps, ts)
        if idx < len(candles):
            assert idx > confirmation_index_by_signal_id[sid], (
                f"{sid}: first_fillable_index {idx} must be strictly after "
                f"confirmation_index {confirmation_index_by_signal_id[sid]}"
            )
        first_fillable[sid] = idx

    eligible = [c for c in candidates if first_fillable.get(c.signal_id, len(candles)) < len(candles)]
    skipped = len(candidates) - len(eligible)
    fill_order = sorted(eligible, key=lambda c: first_fillable[c.signal_id])
    fill_results = two_heap_sweep(
        candles, fill_order, eligible_at=lambda c: first_fillable[c.signal_id],
        sides=_fill_sides(), default=None,
    )
    filled = [
        (candidate, fill_index) for candidate, fill_index in zip(fill_order, fill_results)
        if fill_index is not None and fill_index - first_fillable[candidate.signal_id] <= max_fill_wait
    ]
    never_filled = len(fill_order) - len(filled)
    return filled, never_filled, skipped
