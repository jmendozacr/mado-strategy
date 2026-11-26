"""Phase 10 Unit B: reconstruct the internal confirmation-attempt path
(anchor restarts, internal invalidations) for Model-1 signals that
CONFIRM, using the SAME real, unmodified `find_first_valid_anchor`/
`_track_anchor` functions `causal_anchor_v2.confirm_in_ltf_window_v2`
itself calls.

`confirm_in_ltf_window_v2` only returns its TERMINAL result -- it does
not expose how many attempts it made internally before returning.
`confirm_in_ltf_window_v2_traced` below is a line-by-line structural
mirror of that function's own retry loop (never a reimplementation of
`_track_anchor`'s own decision logic, which is imported and called
unmodified), with one addition: it records each attempt's own result
before deciding whether to retry. Its own terminal `Model1Signal` is
required, by a dedicated equivalence test, to be identical to calling
the real `confirm_in_ltf_window_v2` directly on the same inputs.

Per `docs/79-phase10-design-and-pre-registration.md` section 1's
structural finding: a "new anchor" on retry is never a fresh
`find_first_valid_anchor` call -- `find_first_valid_anchor` runs
EXACTLY ONCE per signal, right here, at the top. Every retry reuses
the INVALIDATING candle's own index as the next attempt's anchor,
carrying the same `origin_index`/`purge_target` forward. Internal
invalidations happen strictly before `order_placed_ts` -- they are
confirmation-process events, never Stop Loss exits, and this module
never assigns an outcome to one.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = LAB_ROOT.parent.parent
DETECTOR_ROOT = REPO_ROOT / "detector"
AUDIT_ROOT = REPO_ROOT / "audit" / "2026-11-17-causal-lookahead-audit"
for _path in (LAB_ROOT, DETECTOR_ROOT, AUDIT_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import causal_anchor_v2 as ca  # noqa: E402
import causal_intrabar as ci  # noqa: E402
from causal.htf_trigger import ltf_window_indices  # noqa: E402
from core.results import DetectionStatus  # noqa: E402
from entries.model1 import Model1Signal, _track_anchor  # noqa: E402

from extract.model1_rejection_diagnostics import _window_open_ts_from_stable_id  # noqa: E402,F401 (re-exported)

FOUR_HOURS = timedelta(hours=4)


@dataclass(frozen=True)
class ConfirmationAttempt:
    attempt_index: int
    anchor_index: int
    status: str  # "CONFIRMED" | "PENDING" | "INVALIDATED" | "NONE" (never engulfed)
    confirmation_index: int | None


@dataclass(frozen=True)
class ConfirmationPath:
    origin_index: int
    first_anchor_index: int
    attempts: tuple[ConfirmationAttempt, ...]
    terminal_status: str  # "CONFIRMED" | "PENDING" | "NONE"
    terminal_signal: Model1Signal | None

    @property
    def confirmation_attempt_count(self) -> int:
        return len(self.attempts)

    @property
    def internal_invalidation_count(self) -> int:
        return sum(1 for a in self.attempts if a.status == "INVALIDATED")

    @property
    def final_anchor_index(self) -> int:
        return self.attempts[-1].anchor_index


def confirm_in_ltf_window_v2_traced(
    ltf_candles: tuple, window: tuple[int, int], direction: str, config, age: timedelta = FOUR_HOURS,
) -> ConfirmationPath | None:
    """Structural mirror of `causal_anchor_v2.confirm_in_ltf_window_v2`.
    Returns `None` under the EXACT same condition the real function
    does (no anchor found at all) -- never a different decision."""
    start_idx, end_idx = window
    truncated = ltf_candles[: end_idx + 1]

    result = ca.find_first_valid_anchor(truncated, start_idx, end_idx, direction, age)
    if result is None:
        return None
    origin_index, current_anchor = result
    purge_target = truncated[origin_index].high if direction == "bearish" else truncated[origin_index].low
    first_anchor_index = current_anchor

    attempts: list[ConfirmationAttempt] = []
    attempt_index = 0
    while True:
        tracked = _track_anchor(
            truncated, current_anchor, direction, purge_target, "purge_engulf", config, origin_index,
        )
        if tracked is None:
            attempts.append(ConfirmationAttempt(attempt_index, current_anchor, "NONE", None))
            return ConfirmationPath(
                origin_index, first_anchor_index, tuple(attempts), "NONE", None,
            )
        attempts.append(
            ConfirmationAttempt(attempt_index, current_anchor, tracked.status.name, tracked.confirmation_index)
        )
        if tracked.status != DetectionStatus.INVALIDATED:
            return ConfirmationPath(
                origin_index, first_anchor_index, tuple(attempts), tracked.status.name, tracked,
            )
        current_anchor = tracked.confirmation_index
        attempt_index += 1


def trace_confirmation_path_for_record(
    record, window_open_ts, m15_series, window_start_fn, window_end_fn, config,
) -> ConfirmationPath | None:
    """Recomputes the exact same `window` tuple
    `causal_anchor_v2.build_causal_signal_v2` computed internally for
    this record -- `window_start_fn`/`window_end_fn`/`record.
    activation_instant_ts` are all pure, already-computed inputs, so
    recomputing them here is bit-identical to the real pipeline's own
    internal step, never a re-derivation that could drift from it."""
    window_start = window_start_fn(window_open_ts)
    window_end = window_end_fn(window_open_ts)
    eligible_start = max(window_start, record.activation_instant_ts)
    if eligible_start >= window_end:
        return None
    window = ltf_window_indices(m15_series.candles, eligible_start, window_end)
    if window is None:
        return None
    return confirm_in_ltf_window_v2_traced(m15_series.candles, window, record.direction, config)


def run_d_c2_with_confirmation_paths(
    symbol, h4, m15, daily, config, m15_timestamps, key_levels, windows_9am, arm_name,
    start_date=None, end_date=None,
):
    """Faithful mirror of Phase 9's `run_d_c2_instrumented`, for the
    CONFIRMED side instead of the rejected side: the real, unmodified
    `run_d_c2` supplies the authoritative `records_with_ids`/
    `counters` (never recomputed); this function ONLY adds one extra
    `trace_confirmation_path_for_record` call per CONFIRMED record."""
    from run_d1_d2_d3 import run_d_c2  # noqa: E402 (deferred import, same reason as Phase 9's module)

    records_with_ids, counters = run_d_c2(
        symbol, h4, m15, daily, config, m15_timestamps, None, None, key_levels,
        "new", windows_9am, arm_name, start_date=start_date, end_date=end_date,
    )

    paths: dict[str, ConfirmationPath | None] = {}
    for model, model_name in ((ci.MODEL_1AM, "1am"), (ci.MODEL_9AM, "9am")):
        if model_name == "9am" and windows_9am == "new":
            window_start_fn, window_end_fn = ca.new_9am_window_fns()
        else:
            window_start_fn, window_end_fn = ca.old_window_fns(model)

        for record, sid in records_with_ids:
            if record.model_name != model_name or record.aligned is None:
                continue
            window_open_ts = _window_open_ts_from_stable_id(sid)
            paths[sid] = trace_confirmation_path_for_record(
                record, window_open_ts, m15, window_start_fn, window_end_fn, config.model1,
            )

    return records_with_ids, counters, paths
