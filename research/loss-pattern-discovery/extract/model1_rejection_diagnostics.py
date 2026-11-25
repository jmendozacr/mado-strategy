"""Phase 9 Units B/C/E: Model-1 rejection taxonomy, with a read-only
diagnostic probe for the one thing `causal_anchor_v2.build_causal_signal_v2`
does not expose: whether `find_first_valid_anchor` found ANY anchor on its
first pass, for triggers that did not confirm.

Structural fact, proven by reading `causal_anchor_v2.confirm_in_ltf_window_v2`
directly (never assumed from the "model1_pending_or_invalidated" label):

    while True:
        result = _track_anchor(...)
        if result is None or result.status != DetectionStatus.INVALIDATED:
            return result
        current_anchor = result.confirmation_index

INVALIDATED is NEVER the function's own terminal return value -- it always
triggers an internal retry (treating the invalidation point as a new
anchor). The only non-None statuses `confirm_in_ltf_window_v2` can ever
return to its caller are CONFIRMED or PENDING. **"model1_pending_or_invalidated"
is therefore a misnomer for D3 (`anchor_source="new"`): it is always PENDING,
never a terminal INVALIDATED, in this pipeline.** Verified both analytically
(this docstring) and by a regression test
(`tests/test_model1_rejection_diagnostics.py::test_confirm_in_ltf_window_v2_never_returns_invalidated_as_terminal`)
using the REAL, unmodified `_track_anchor`/`confirm_in_ltf_window_v2` on a
synthetic candle sequence engineered to invalidate at least once before
resolving.

The ONE thing this pipeline's persisted output cannot disambiguate without
re-probing: whether "no_model1_anchor_found" means zero anchors ever existed
in the window, or at least one anchor was found but the whole retry chain
was eventually exhausted without ever engulfing. `probe_first_anchor` adds
exactly that one extra, side-effect-free read of `find_first_valid_anchor`
-- never a different rule, never a second decision path. The authoritative
record itself is ALWAYS produced by calling the real, unmodified
`causal_anchor_v2.build_causal_signal_v2` -- this module never reimplements
that decision.
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

FOUR_HOURS = timedelta(hours=4)  # ca.find_first_valid_anchor's own default `age`


@dataclass(frozen=True)
class RejectionDiagnostic:
    """`anchor_probe` is `None` only when the real pipeline never even
    reached the anchor-search step (window empty before search, or no M15
    candle in the eligible range) -- the probe is never run on data the
    original pipeline itself never looked at."""
    model_name: str
    direction: str
    zero_signal_reason: str | None
    category: str  # matches run_c1_c2._categorize_reason exactly, reused
    anchor_probe: bool | None  # True = an anchor existed on the first pass; False = none did; None = not probed


def probe_first_anchor(candles, window: tuple[int, int], direction: str, age=FOUR_HOURS) -> bool:
    """A single, read-only call to the REAL `find_first_valid_anchor`
    (unmodified) -- reports only whether an anchor existed, never
    reimplements the retry chain that follows it."""
    start_idx, end_idx = window
    truncated = candles[: end_idx + 1]
    result = ca.find_first_valid_anchor(truncated, start_idx, end_idx, direction, age)
    return result is not None


def diagnose_rejection(
    model_name: str, window_open_ts, m15_series, window_start_fn, window_end_fn,
    record,  # the REAL, already-computed CausalSignalRecord from build_causal_signal_v2 -- never recomputed
) -> RejectionDiagnostic:
    """`record` must come from calling the real, unmodified
    `causal_anchor_v2.build_causal_signal_v2` -- this function never
    produces its own decision, only classifies and (for the no-anchor
    case) adds one extra probe on top of that already-authoritative
    result. `record.direction`/`record.activation_instant_ts` are already
    populated by the real pipeline for EVERY record, confirmed or not --
    no separate trigger object is needed."""
    category = _categorize_reason(record.zero_signal_reason) if record.zero_signal_reason else "confirmed"
    if category != "no_model1_anchor_found":
        return RejectionDiagnostic(model_name, record.direction, record.zero_signal_reason, category, None)

    window_start = window_start_fn(window_open_ts)
    window_end = window_end_fn(window_open_ts)
    eligible_start = max(window_start, record.activation_instant_ts)
    if eligible_start >= window_end:
        # The real pipeline would have returned "window_empty_before_search"
        # for this -- reaching here with category "no_model1_anchor_found"
        # would be an inconsistency between this probe and the real
        # decision; surfaced by this function's own equivalence test, never
        # silently reconciled.
        return RejectionDiagnostic(model_name, record.direction, record.zero_signal_reason, category, None)
    window = ltf_window_indices(m15_series.candles, eligible_start, window_end)
    if window is None:
        return RejectionDiagnostic(model_name, record.direction, record.zero_signal_reason, category, None)

    anchor_found = probe_first_anchor(m15_series.candles, window, record.direction)
    return RejectionDiagnostic(model_name, record.direction, record.zero_signal_reason, category, anchor_found)


def run_d_c2_instrumented(
    symbol, h4, m15, daily, config, m15_timestamps, key_levels,
    windows_9am, arm_name, start_date=None, end_date=None,
):
    """Faithful mirror of `run_d1_d2_d3.run_d_c2`, pinned to
    `anchor_source="new"` (D3's own value -- the only one this probe is
    meaningful for) -- every sub-call (`ca.new_confirm_fn`,
    `ca.new_9am_window_fns`/`ca.old_window_fns`, `ci.ny_anchored_open_utc`,
    `ci.complete_feeder_candle_ny`, `ca.activation_window_open_ts`/
    `close_ts`, `ci.detect_sweep_and_key_level`, `ca.build_causal_signal_v2`)
    is the SAME real, unmodified function, called in the SAME order, with
    the SAME config -- the only addition is one extra `diagnose_rejection`
    call per non-confirmed trigger. `records_with_ids`/`counters` returned
    here must be identical to `run_d_c2`'s own (asserted by
    `tests/test_model1_rejection_diagnostics.py`'s equivalence test, and by
    this function's own internal identity requirement, never assumed).
    """
    from run_d1_d2_d3 import run_d_c2  # noqa: E402 (imported here, not at module level, to avoid any import-order side effect on the real pipeline)

    records_with_ids, counters = run_d_c2(
        symbol, h4, m15, daily, config, m15_timestamps, None, None, key_levels,
        "new", windows_9am, arm_name, start_date=start_date, end_date=end_date,
    )

    diagnostics: dict[str, RejectionDiagnostic] = {}
    for model, model_name in ((ci.MODEL_1AM, "1am"), (ci.MODEL_9AM, "9am")):
        if model_name == "9am" and windows_9am == "new":
            window_start_fn, window_end_fn = ca.new_9am_window_fns()
        else:
            window_start_fn, window_end_fn = ca.old_window_fns(model)

        for record, sid in records_with_ids:
            if record.model_name != model_name or record.aligned is not None:
                continue
            # `window_open_ts` is not persisted on `CausalSignalRecord` --
            # recovered from `stable_trigger_id`'s own embedded timestamp,
            # the SAME value `stable_trigger_id(...)` was built from
            # (`run_c1_c2.stable_trigger_id`'s own 4th field), never a
            # freshly-guessed one.
            window_open_ts = _window_open_ts_from_stable_id(sid)
            diagnostics[sid] = diagnose_rejection(
                model_name, window_open_ts, m15, window_start_fn, window_end_fn, record,
            )

    return records_with_ids, counters, diagnostics


def _window_open_ts_from_stable_id(stable_id: str):
    """Inverse of `run_c1_c2.stable_trigger_id`
    (`f"{symbol}|{arm}|{model_name}|{window_open_ts.isoformat()}|{direction}"`)
    -- the exact same value the real loop used to build `sid`, read back,
    never recomputed from the model/day some other way."""
    from datetime import datetime

    parts = stable_id.split("|")
    return datetime.fromisoformat(parts[3])


def _categorize_reason(reason: str) -> str:
    """Byte-for-byte copy of `run_c1_c2._categorize_reason` -- reused here
    (not imported) only because `run_c1_c2.py` is a script, not a package,
    and this lab already duplicates it consistently with the production
    string contract it classifies; never a different rule."""
    if "window" in reason and "ends at or before" in reason:
        return "window_empty_before_search"
    if "no M15 candle falls inside" in reason:
        return "window_has_no_m15_data"
    if "resolved" in reason and "not CONFIRMED" in reason:
        return "model1_pending_or_invalidated"
    return "no_model1_anchor_found"
