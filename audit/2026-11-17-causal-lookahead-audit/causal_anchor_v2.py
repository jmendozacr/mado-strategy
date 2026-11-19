"""Shared causal M15 anchor-source mechanism (Modificación 1) and
widened-9AM-window helpers (Modificación 2), authorized by the user's
conditional approval of design-causal-anchor-source.md (commit
86a1e58), corrected per that same review before this file was written
(see design doc's "Cierre de diseño -- ronda 3" + its corrections).

D1/D2/D3 (run_d1_d2_d3.py) share this module. Neither C1/C2
(causal_intrabar.py/run_c1_c2.py) nor anything under detector/scanner/
docs is modified -- this module only ADDS the new alternatives as
separate, explicit functions, so C1/C2 stay byte-for-byte reproducible.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Callable
from zoneinfo import ZoneInfo

from causal.htf_trigger import FeederModel, confirmation_window_utc, ltf_window_indices
from core.candle import Candle, OHLCSeries
from core.config import Model1Config
from core.results import DetectionStatus
from entries.model1 import Direction, Model1Signal, _track_anchor

import causal_intrabar as ci

_NY = ZoneInfo("America/New_York")
_UTC = ZoneInfo("UTC")

FOUR_HOURS = timedelta(hours=4)
NINE_AM_ACTIVATION_DURATION = timedelta(hours=2)              # design S19 S1: activation window 09:00-11:00 NY
NINE_AM_CONFIRMATION_DEADLINE_DURATION = timedelta(hours=4)   # design S19 S1: until the feeder's own close (13:00 NY)

# M15 bars are a fixed >=15min grid (never finer) -- `age` real hours can
# never span more than this many bars, data gaps included (a gap only
# ever makes real time per bar LARGER, never smaller). This is a safe,
# generous bound used only to limit the inner scan below; the actual
# expiry decision always re-checks real `available_at` timestamps, so an
# overly-generous margin can only cost a little extra compute, never
# correctness.
_MAX_CANDLES_IN_AGE_WINDOW = 20


# ---------------------------------------------------------------------------
# Modificación 1: fuente causal del anchor M15 (design S19 S2, corrected)
# ---------------------------------------------------------------------------

def is_broken_by(candle: Candle, level_price: float, direction: Direction) -> bool:
    return candle.high > level_price if direction == "bearish" else candle.low < level_price


def _side_value(candles: tuple[Candle, ...], i: int, direction: Direction) -> float:
    return candles[i].high if direction == "bearish" else candles[i].low


def find_first_valid_anchor(
    candles: tuple[Candle, ...], search_start_idx: int, search_end_idx: int,
    direction: Direction, age: timedelta = FOUR_HOURS,
) -> tuple[int, int] | None:
    """Design S19 S2, corrected per the user's review of commit 86a1e58:
    for candle `j` to be a valid anchor, NO candle `k` with `i < k < j`
    may have already broken candle `i`'s level (that is what "still open
    just before j" means) -- `j` itself is explicitly EXCLUDED from that
    check, unlike the design's first (buggy) draft, since `j` is
    precisely the candle required TO break it. High and Low sides of the
    same origin candle `i` are independent: this function only ever
    inspects ONE side per call (per `direction`), exactly like
    `first_breach_index` is already called today (`high=` XOR `low=`,
    never both) -- breaking one side never disqualifies the other.

    Age is checked via `available_at` timestamps, never bar-count, so a
    data gap can never make this see more or less than `age` of real
    elapsed time (design S19 S2's gap-safety requirement).

    Returns `(origin_index, anchor_index)` for the first (earliest
    `anchor_index`, tie-break lowest `origin_index`) valid breach inside
    `[search_start_idx, search_end_idx]`, or `None`.
    """
    for j in range(search_start_idx, search_end_idx + 1):
        winners = []
        lo = max(0, j - _MAX_CANDLES_IN_AGE_WINDOW)
        for i in range(lo, j):
            if ci.available_at(candles[j], ci.M15_DURATION) - ci.available_at(candles[i], ci.M15_DURATION) > age:
                continue  # expired by timestamp -- never by index/bar-count
            level_price = _side_value(candles, i, direction)
            if any(is_broken_by(candles[k], level_price, direction) for k in range(i + 1, j)):
                continue  # someone strictly BEFORE j already broke it -- no longer "open" at j
            if is_broken_by(candles[j], level_price, direction):
                winners.append(i)  # j itself breaks it -- j is a valid anchor for origin i
        if winners:
            return (min(winners), j)  # existing tie-break: lowest origin/start_index among simultaneous breaks
    return None


def confirm_in_ltf_window_v2(
    ltf_candles: tuple[Candle, ...], window: tuple[int, int], direction: Direction,
    config: Model1Config, age: timedelta = FOUR_HOURS,
) -> Model1Signal | None:
    """New-anchor-source counterpart to `causal.htf_trigger.
    confirm_in_ltf_window` -- identical in every way except how the
    winning (origin_index, anchor_index) pair is found
    (`find_first_valid_anchor` above, instead of a search over
    `detect_crt_ranges`' pre-filtered, resolution-gated `ltf_ranges`).
    `_track_anchor`'s retry-on-invalidation loop is reused UNMODIFIED,
    exactly like the original function.
    """
    start_idx, end_idx = window
    truncated = ltf_candles[: end_idx + 1]

    result = find_first_valid_anchor(truncated, start_idx, end_idx, direction, age)
    if result is None:
        return None
    origin_index, current_anchor = result
    purge_target = truncated[origin_index].high if direction == "bearish" else truncated[origin_index].low

    while True:
        result = _track_anchor(
            truncated, current_anchor, direction, purge_target, "purge_engulf", config, origin_index
        )
        if result is None or result.status != DetectionStatus.INVALIDATED:
            return result
        current_anchor = result.confirmation_index


# ---------------------------------------------------------------------------
# Window-boundary providers (old vs. new 9AM), for build_causal_signal_v2
# ---------------------------------------------------------------------------

WindowBoundaryFn = Callable[[datetime], datetime]


def old_window_fns(model: FeederModel) -> tuple[WindowBoundaryFn, WindowBoundaryFn]:
    """Reproduces `confirmation_window_utc(trigger_proxy, model)` exactly
    -- used for D1 (both models) and for 1AM in every config (1AM's
    windows are never touched, design S19 S5)."""
    def start_fn(window_open_ts: datetime) -> datetime:
        return confirmation_window_utc(SimpleNamespace(timestamp=window_open_ts), model)[0]

    def end_fn(window_open_ts: datetime) -> datetime:
        return confirmation_window_utc(SimpleNamespace(timestamp=window_open_ts), model)[1]

    return start_fn, end_fn


def _ny_instant_on_trigger_day(window_open_ts: datetime, hour_ny: int) -> datetime:
    """Design S19/correction round 4 (user's review of commit 4e36b1a):
    `window_open_ts` must NEVER be assumed to itself be 09:00 NY. In C2
    (NY-anchored grid) it genuinely is; in C1 (broker H4 grid) the "9am"
    trigger candle opens at 12:00 UTC, which is 07:00 NY in EST or
    08:00 NY in EDT -- 2-3 hours before true 09:00 NY, never equal to
    it. This mirrors `confirmation_window_utc`'s own, already-correct
    mechanism exactly (same midpoint-based NY-day derivation, same
    DST-aware `zoneinfo` wall-clock construction) rather than doing
    naive UTC arithmetic on `window_open_ts` -- that naive arithmetic
    was the bug. The broker candle's own UTC open is used ONLY to find
    which NY calendar day this trigger belongs to (via the same +2h
    midpoint convention, to correctly handle the day-boundary edge case
    that convention exists for) -- never as a stand-in for NY wall-clock
    time itself. The broker-grid geometry feeding `reference` (which H4
    candle supplies the swept high/low) stays completely independent of
    this and is never touched here."""
    midpoint = window_open_ts + timedelta(hours=2)
    ny_day = midpoint.replace(tzinfo=_UTC).astimezone(_NY).date()
    instant_ny = datetime(ny_day.year, ny_day.month, ny_day.day, hour_ny, tzinfo=_NY)
    return instant_ny.astimezone(_UTC).replace(tzinfo=None)


def new_9am_window_fns() -> tuple[WindowBoundaryFn, WindowBoundaryFn]:
    """Design S19 S1, corrected: the Model-1 search window is
    [true 09:00 NY, true 13:00 NY] -- both derived via
    `_ny_instant_on_trigger_day`, never via naive arithmetic on
    `window_open_ts` (which is only a true 09:00 NY instant for C2,
    not for C1 -- see that function's docstring)."""
    def start_fn(window_open_ts: datetime) -> datetime:
        return _ny_instant_on_trigger_day(window_open_ts, 9)

    def end_fn(window_open_ts: datetime) -> datetime:
        return _ny_instant_on_trigger_day(window_open_ts, 13)

    return start_fn, end_fn


def activation_window_open_ts(window_open_ts: datetime, model_name: str, windows_9am: str) -> datetime:
    """What to pass as `window_open_ts` (the scan START) to
    `detect_sweep_and_key_level` -- design S19/correction round 4: for
    the new 9AM windows, this must be true 09:00 NY, so the sweep+Key-
    Level scan itself never even looks at candles before 09:00 NY (a
    post-hoc filter on the returned `activation_instant_ts` would not
    be enough -- `detect_sweep_and_key_level` locks in the FIRST
    qualifying instant per direction and never looks further once
    found, so an early, pre-09:00 match would need to be re-searched
    for a later one, not just discarded). For every other case (1AM
    always; 9AM with old windows), the scan starts at `window_open_ts`
    itself, unchanged from today."""
    if model_name == "9am" and windows_9am == "new":
        return _ny_instant_on_trigger_day(window_open_ts, 9)
    return window_open_ts


def activation_window_close_ts(window_open_ts: datetime, model_name: str, windows_9am: str) -> datetime:
    """What to pass as `window_close_ts` to `detect_sweep_and_key_level`
    (design S19 S0's correction): today (and 1AM always), the activation
    search spans the FULL feeder candle (no explicit activation deadline
    of its own -- the effective ~10:30 cutoff comes indirectly from the
    Model-1 window closing there, not from this parameter). The new 9AM
    rule makes the activation deadline EXPLICIT and INDEPENDENT at true
    11:00 NY -- derived the same DST-aware way as the other new 9AM
    boundaries, never as `window_open_ts + 2h` (that naive arithmetic
    was round 4's bug: correct only for C2, wrong by 2-3h for C1)."""
    if model_name == "9am" and windows_9am == "new":
        return _ny_instant_on_trigger_day(window_open_ts, 11)
    return window_open_ts + ci.H4_DURATION


# ---------------------------------------------------------------------------
# Shared orchestration step: generalizes causal_intrabar.build_causal_signal
# ---------------------------------------------------------------------------

ConfirmFn = Callable[[tuple[Candle, ...], tuple[int, int], Direction, Model1Config], Model1Signal | None]


def build_causal_signal_v2(
    model_name: str, trigger, window_open_ts: datetime, m15_series: OHLCSeries,
    model1_config: Model1Config, reference,
    window_start_fn: WindowBoundaryFn, window_end_fn: WindowBoundaryFn,
    confirm_fn: ConfirmFn,
) -> ci.CausalSignalRecord:
    """Generalizes `causal_intrabar.build_causal_signal` with two
    injected choices, so D1/D2/D3 share ONE function instead of three
    near-copies: `confirm_fn` picks the anchor-source mechanism (old
    `confirm_in_ltf_window` bound to `ltf_ranges`, or the new
    `confirm_in_ltf_window_v2`); `window_start_fn`/`window_end_fn` pick
    the search-window boundaries (old `confirmation_window_utc`-derived
    values, or the new widened 9AM ones). A deliberate fork, not a
    silent reimplementation: kept separate from
    `causal_intrabar.build_causal_signal` itself so C1/C2 (which call
    that function directly) stay byte-for-byte unchanged and
    reproducible. Every other step below is copied verbatim from that
    function -- intentionally, so the two stay comparable line-by-line.
    """
    window_start = window_start_fn(window_open_ts)
    window_end = window_end_fn(window_open_ts)
    eligible_start = max(window_start, trigger.activation_instant_ts)
    if eligible_start >= window_end:
        return ci.CausalSignalRecord(
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
        return ci.CausalSignalRecord(
            aligned=None, model_name=model_name, direction=trigger.direction,
            feeder_ref_available_ts=reference.close_ts,
            activation_instant_ts=trigger.activation_instant_ts,
            model1_available_ts=None, confirmation_index=None, order_placed_ts=None,
            zero_signal_reason=f"no M15 candle falls inside [{eligible_start.isoformat()}, {window_end.isoformat()}).",
        )
    signal = confirm_fn(m15_series.candles, window, trigger.direction, model1_config)
    if signal is None or signal.status != DetectionStatus.CONFIRMED:
        reason = (
            "no anchor/confirmation/retest completed inside the causally-valid window"
            if signal is None else
            f"Model-1 resolved {signal.status.name}, not CONFIRMED -- excluded per design S1.3's stricter filter"
        )
        return ci.CausalSignalRecord(
            aligned=None, model_name=model_name, direction=trigger.direction,
            feeder_ref_available_ts=reference.close_ts,
            activation_instant_ts=trigger.activation_instant_ts,
            model1_available_ts=None, confirmation_index=None, order_placed_ts=None,
            zero_signal_reason=reason,
        )

    model1_available_ts = ci.available_at(m15_series.candles[signal.confirmation_index], ci.M15_DURATION)
    htf_context = ci.CRTRange(
        model="2-candle", high=reference.high, low=reference.low,
        start_index=0, end_index=0, resolution="false_break", resolved_at_index=0,
    )
    aligned = ci.AlignedSignal(
        ltf_signal=signal, htf_context=htf_context, aligned="aligned",
        key_level=trigger.credited_level, key_level_reaction=None,
    )
    return ci.CausalSignalRecord(
        aligned=aligned, model_name=model_name, direction=trigger.direction,
        feeder_ref_available_ts=reference.close_ts,
        activation_instant_ts=trigger.activation_instant_ts,
        model1_available_ts=model1_available_ts,
        confirmation_index=signal.confirmation_index,
        order_placed_ts=model1_available_ts,
    )


def old_confirm_fn(ltf_ranges) -> ConfirmFn:
    """D2, and 1AM in every config: the OLD, `detect_crt_ranges`-based
    anchor mechanism, reused UNMODIFIED -- only re-shaped to match
    `build_causal_signal_v2`'s `confirm_fn` call signature (candles,
    window, direction, config), since the original function's own
    signature takes `ltf_ranges` as its second positional argument."""
    from causal.htf_trigger import confirm_in_ltf_window

    def fn(candles, window, direction, model1_config):
        return confirm_in_ltf_window(candles, ltf_ranges, window, direction, model1_config)

    return fn


def new_confirm_fn(age: timedelta = FOUR_HOURS) -> ConfirmFn:
    """D1/D3: the new, age-gated, gap-safe anchor mechanism (above)."""
    def fn(candles, window, direction, model1_config):
        return confirm_in_ltf_window_v2(candles, window, direction, model1_config, age)

    return fn
