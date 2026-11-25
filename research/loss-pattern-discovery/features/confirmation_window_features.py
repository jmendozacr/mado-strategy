"""Phase 7 Unit B: Confirmation Window Reconstruction + Temporal Feature Dataset.

Reconstructs, for every executed trade, the Model-1 confirmation window
ACTUALLY used to generate its signal (`window_start_at`/`window_end_at`),
and the trade's own position within it -- in absolute minutes AND relative
position, kept distinct (docs/47 section 9: 1AM's window is 120min, 9AM's
is 240min -- not directly comparable without care).

CORRECTION discovered during this phase's own Unit A audit (docs/46):
`detector/causal/htf_trigger.py::MODEL_9AM.window_duration` (90 minutes,
09:00-10:30 NY) is NOT the window that generated this lab's ledger. The
source CSV (`trades_d3_c2_2015plus_run2.csv`) comes from
`audit/.../run_d1_d2_d3.py`'s "D3" config
(`CONFIGS["d3"] = ("new", "new", "agreed 9AM operative design")`), which
routes 9AM through `causal_anchor_v2.py::new_9am_window_fns()` -- a WIDENED
window, true 09:00-13:00 NY (240 minutes), with a separate, narrower
09:00-11:00 NY activation sub-window gating only when the HTF sweep/
Key-Level trigger itself may fire (`activation_window_open_ts`/
`activation_window_close_ts`), not the Model-1 confirmation deadline.
1AM's window is untouched by D3 (`causal_anchor_v2.py`'s own comment:
"1AM's windows are never touched, design S19 S5") -- unchanged from
Phase 6's docs/41, which remains correct for 1AM specifically. This
module therefore calls `causal_anchor_v2.old_window_fns`/`new_9am_window_fns`
directly (never a hand-rolled duration constant) so it cannot silently
drift from whichever window logic actually generated the ledger.

Sources (read-only reuse, nothing reimplemented a second time):
  - `audit/2026-11-17-causal-lookahead-audit/causal_anchor_v2.py::old_window_fns`,
    `::new_9am_window_fns` -- the EXACT window-boundary functions D3 used
    (1AM: old/unchanged; 9AM: new/widened).
  - `audit/2026-11-17-causal-lookahead-audit/causal_intrabar.py::ny_anchored_open_utc`,
    `::CURRENT_HOUR_NY` -- the SAME DST-aware NY<->UTC conversion and the
    SAME "current hour" (1AM->01:00 NY, 9AM->09:00 NY) the C2 population
    grid itself used to build each `window_open_ts`.
  - `detector/causal/htf_trigger.py::MODEL_1AM`/`MODEL_9AM` -- only for
    1AM's (unchanged) `window_start_hour_ny`, never for 9AM's duration.
  - `EventRecord.features_pre_entry.model1_available_ts`/`order_placed_ts`
    -- already present verbatim in the source ledger (Phase 1's extractor),
    never re-derived from the "1am"/"9am" label alone.

Never confused (brief section 4):
  `confirmation_bar_open` (the M15 bar's own OPEN -- when the anchor/
  confirmation/retest sequence actually resolved) vs.
  `confirmation_available_at` (that bar's CLOSE -- when the fact becomes
  causally knowable; `model1_available_ts` in this pipeline) vs.
  `order_placed_at` (when the order was placed -- equals
  `confirmation_available_at` in this pipeline, verified, not assumed) vs.
  `entry_filled_at` (when price actually touched the entry level, which
  the fill sweep can place anywhere from the first eligible M15 bar
  onward -- `confirmation_available_at` is NEVER treated as the fill
  instant).

`confirmation_bar_open` is recovered as `model1_available_ts - 15min` --
an exact identity (`available_at`'s own definition is `candle.timestamp +
15min`), not an approximation. `window_start_at`/`window_end_at` are
recovered from the confirmation bar's OWN NY-local calendar date fed back
into the ACTUAL window-boundary function for that model: neither model's
window (1AM 02:00-04:00 NY; 9AM 09:00-13:00 NY) crosses NY local midnight,
so the confirming bar's NY date always equals the window's own NY date --
verified by test against real data, not assumed (Unit A: 0 violations
after this correction, vs. 1080/2043 before it, using the stale 90-minute
9AM duration).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = LAB_ROOT.parent.parent
AUDIT_ROOT = REPO_ROOT / "audit" / "2026-11-17-causal-lookahead-audit"
for _path in (LAB_ROOT, REPO_ROOT / "detector", AUDIT_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from causal.htf_trigger import MODEL_1AM  # noqa: E402
from causal_anchor_v2 import new_9am_window_fns, old_window_fns  # noqa: E402
from causal_intrabar import ny_anchored_open_utc  # noqa: E402
from common.ny_time import to_ny  # noqa: E402
from schema.events import EventRecord  # noqa: E402

M15_DURATION = timedelta(minutes=15)
# D3's actual choice per model (see module docstring correction): 1AM keeps
# its original window; 9AM uses the widened one. Never hand-roll a duration
# here -- always call the real boundary functions below.
WINDOW_FNS_BY_LABEL = {
    "1am": old_window_fns(MODEL_1AM),
    "9am": new_9am_window_fns(),
}
# The "current hour" each model's own window_open_ts is anchored to on the
# C2 (NY-anchored) population grid (`causal_intrabar.CURRENT_HOUR_NY`) --
# used only to reconstruct a self-consistent `window_open_ts` to feed the
# boundary functions above; both functions re-derive the true window hour
# from this via the same NY-day midpoint convention, so a `window_open_ts`
# that is not itself the window's own start hour still yields the correct
# boundaries (verified against real data: 0 self-consistency violations).
WINDOW_OPEN_HOUR_NY = {"1am": 1, "9am": 9}


@dataclass(frozen=True)
class ConfirmationWindowFeatures:
    event_id: str
    origin_model: str
    window_start_at: datetime | None
    window_end_at: datetime | None
    window_duration_minutes: float | None
    confirmation_bar_open: datetime | None
    confirmation_available_at: datetime | None
    order_placed_at: datetime | None
    entry_filled_at: datetime | None
    confirmation_elapsed_minutes: float | None
    confirmation_remaining_minutes: float | None
    confirmation_relative_position: float | None
    confirmation_bar_position: float | None
    order_to_fill_minutes: float | None
    missing_reasons: tuple[str, ...]


def compute_confirmation_window_features(record: EventRecord) -> ConfirmationWindowFeatures:
    event_id = record.identification.event_id
    model_label = record.identification.session_label
    window_fns = WINDOW_FNS_BY_LABEL.get(model_label)
    open_hour_ny = WINDOW_OPEN_HOUR_NY.get(model_label)
    pre = record.features_pre_entry
    order_placed_at = pre.order_placed_ts
    entry_filled_at = record.operation.entry_ts
    missing: list[str] = []

    if window_fns is None:
        missing.append(f"unknown_origin_model:{model_label}")
    if pre.model1_available_ts is None:
        missing.append("model1_available_ts_missing")

    if window_fns is None or pre.model1_available_ts is None:
        return ConfirmationWindowFeatures(
            event_id=event_id, origin_model=model_label,
            window_start_at=None, window_end_at=None, window_duration_minutes=None,
            confirmation_bar_open=None, confirmation_available_at=None,
            order_placed_at=order_placed_at, entry_filled_at=entry_filled_at,
            confirmation_elapsed_minutes=None, confirmation_remaining_minutes=None,
            confirmation_relative_position=None, confirmation_bar_position=None,
            order_to_fill_minutes=None, missing_reasons=tuple(missing),
        )

    confirmation_available_at = pre.model1_available_ts
    confirmation_bar_open = confirmation_available_at - M15_DURATION

    ny_date = to_ny(confirmation_bar_open).date()
    window_open_ts_guess = ny_anchored_open_utc(ny_date, open_hour_ny)
    window_start_fn, window_end_fn = window_fns
    window_start_at = window_start_fn(window_open_ts_guess)
    window_end_at = window_end_fn(window_open_ts_guess)
    window_duration_minutes = (window_end_at - window_start_at).total_seconds() / 60.0

    elapsed_minutes = (confirmation_bar_open - window_start_at).total_seconds() / 60.0
    remaining_minutes = window_duration_minutes - elapsed_minutes
    relative_position = elapsed_minutes / window_duration_minutes if window_duration_minutes else None
    bar_position = elapsed_minutes / 15.0

    order_to_fill_minutes = (
        (entry_filled_at - order_placed_at).total_seconds() / 60.0
        if (order_placed_at is not None and entry_filled_at is not None) else None
    )
    if order_to_fill_minutes is None:
        missing.append("order_to_fill_minutes_unavailable")

    return ConfirmationWindowFeatures(
        event_id=event_id, origin_model=model_label,
        window_start_at=window_start_at, window_end_at=window_end_at,
        window_duration_minutes=window_duration_minutes,
        confirmation_bar_open=confirmation_bar_open, confirmation_available_at=confirmation_available_at,
        order_placed_at=order_placed_at, entry_filled_at=entry_filled_at,
        confirmation_elapsed_minutes=elapsed_minutes, confirmation_remaining_minutes=remaining_minutes,
        confirmation_relative_position=relative_position, confirmation_bar_position=bar_position,
        order_to_fill_minutes=order_to_fill_minutes, missing_reasons=tuple(missing),
    )


def compute_all_confirmation_window_features(
    records: list[EventRecord],
) -> dict[str, ConfirmationWindowFeatures]:
    return {r.identification.event_id: compute_confirmation_window_features(r) for r in records}
