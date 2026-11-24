# Deliverable D — Data Quality & Limitations (Phase 2)

## Causality

- Every eligible event's exit is causally grounded in `detector/backtest/simulate.py`'s own
  exit-resolution code (see `docs/07-phase2-stop-eligibility-and-atlas.md`), not assumed from column
  names. 1262 of 1265 losses (99.4%) are `confirmed_stop_event` with 0.98 classifier confidence; the
  remaining 3 are `ambiguous_stop_event` (intrabar SL/TP tie, 0.5 confidence) and kept out of the main
  Atlas.
- Post-stop measurement never uses the exit bar's own M15 range retrospectively — the first bar
  considered is strictly after `exit_ts` (`first_actionable_ts = exit_ts + 15min`).
- The control group's reference instant is chosen using only pre-instant information (instrument,
  session, direction, period bucket, and the control point's OWN pre-instant ATR) — never the
  control's own future trajectory.

## M15 resolution limits

- A single M15 bar cannot resolve true intrabar order when both an adverse and a favorable level are
  touched within it. This affects eligibility (`ambiguous_bar`, 0.2% of the loss population) and, in
  principle, the post-stop `first_move_direction` detection the same way — a bar whose range crosses
  BOTH the 0.25R continuation and reversal thresholds in the SAME bar resolves to `"continuation"`
  (adverse checked first in `behavior/post_stop_metrics.py`), deliberately mirroring this project's
  existing pessimistic tie-break convention (the production engine's own SL-wins-ties rule; Phase 1's
  MFE/MAE "conservative call") so an unresolvable intrabar tie never overstates reversal evidence —
  still a convention, not certain knowledge, exactly like `ambiguous_bar` itself.
- Gaps (weekend/holiday closures) are detected (`weekend_gap_spanned`, >20 minutes between consecutive
  available bars) and reported, never interpolated.

## Censoring

- 4 of 1265 losses are `open_censored` (still running when the source ledger was generated) and are
  excluded from trajectory measurement entirely — there is no `exit_ts` to measure from.
- Within the eligible population, a horizon can still be individually censored if the M15 series runs
  out before reaching it (near the data's own end, 2026-11-12/13) — reported per horizon as
  `pct_censored`, never filled in.

## Partial exits

- 0 of 1262 eligible events have `has_partial_exit=True` in the loss population (see Unit A's finding:
  the breakeven-after-partial reward structure makes a net loss on a partial-exit trade arithmetically
  near-impossible here). `stop_after_partial_exit` is consequently an empty category for THIS source —
  not evidence that partial exits never matter, only that they don't produce losses under this specific
  config.

## Statistical constraints

- Near-in-time events are not independent: every CI in this phase uses a block bootstrap, block =
  `(instrument, ISO calendar week)`, declared once in `stats/bootstrap.py` and used for every metric.
- `MIN_HEADLINE_N = 30`: any stratum cell below this is still reported in full but flagged
  `small_sample=True` — read its CI width accordingly.
- One-way stratification only (never the full instrument x session x direction x period cross-product)
  — see `docs/07-...`'s Unit D section for why.
- No genuine out-of-sample period exists in this dataset for ANY of this phase's findings — 2015-2026
  has already been used by this repo's prior research (Phase 1's L5, unchanged). Phase 2's descriptive
  findings are about what price historically did after these specific SL events, not a forward-tested
  claim.
- The control group's match quality depends on a 400-candidate random pool per stratum; see Phase 1/2's
  decision log L9 for its caveats.
