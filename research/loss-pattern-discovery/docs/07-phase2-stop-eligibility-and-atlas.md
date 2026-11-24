# Phase 2 — Stop-Event Eligibility + Post-Stop-Loss Behavior Atlas

Phase 2's premise, stated by the user before any code was written: "no hemos demostrado que las
1.265 pérdidas equivalgan a 1.265 Stop Loss ejecutados." This document records how that premise was
tested, and the pre-registered design decisions for the Atlas, the control group, and the statistics
layer -- all fixed before any Phase-2 result was inspected.

## Unit A — Stop eligibility

`eligibility/stop_eligibility.py` classifies every loss/open event into `confirmed_stop_event`,
`stop_after_partial_exit`, `other_negative_exit`, `ambiguous_stop_event`, or `open_censored`. The
classifier is grounded directly in `detector/backtest/simulate.py`'s exit-resolution code, not in
assumptions about what the CSV columns mean:

- `outcome` ("win"/"loss") is the sign of the net-of-cost R-multiple, not "which level resolved
  first." A cost-driven sign flip on a take-profit touch is possible in principle
  (`other_negative_exit`) -- checked empirically, not assumed away. On the real dataset: **zero**
  such cases, because `trading_cost_price` (0.00013-0.000167 for these 3 pairs) is roughly 1-2% of a
  typical 1R risk distance, far too small to flip a take-profit touch's sign.
- For a non-partial loss, `exit_price` must equal `stop_loss` (or, if `gap_filled`, the gap-open
  price) -- `_resolve_single_leg`/`_fill_candle_immediate_loss`.
- **Critical, non-obvious finding**: `detector/experimental/htf_trigger_1am_9am_backtest.py`'s
  `SYMBOL_CONFIG` sets `breakeven_after_partial=True` for EURUSD/USDCAD/AUDUSD, and
  `audit/2026-11-17-causal-lookahead-audit/run_d1_d2_d3.py:239` builds
  `DetectorConfig(backtest=SYMBOL_CONFIG[symbol])` -- i.e. this exact, unmodified, per-symbol-constant
  config generated the primary source. So for every partial-exit trade in this source, leg 2's
  adverse level is `entry_price` (moved to breakeven), **never** the original `stop_loss` column. The
  classifier checks `exit_price` against the right reference depending on `has_partial_exit`, and
  never conflates the two populations.
- `ambiguous_bar=True` (SL/breakeven and TP touched in the same M15 bar) is classified `Ambiguous`
  regardless of which way the production engine's own pessimistic tie-break resolved it -- this lab
  does not inherit that resolution as proof of the true intrabar order.

Real-dataset result (1269 = 1265 losses + 4 open): **1262 confirmed (99.4%)**, **0 stop-after-partial**
(see below), **0 other-negative-exit**, **3 ambiguous (0.2%)**, **4 open-censored (0.3%)**.

**`stop_after_partial_exit` is empirically ~0, and that is a real, non-fabricated finding, not a
classifier defect**: with `breakeven_after_partial=True`, a trade that fires its partial leg has
already locked in a profitable leg 1; leg 2's worst case is only the (tiny) trading cost at breakeven,
not a full stop distance. Blending the two legs by position fraction makes a net *loss* on a
partial-exit trade arithmetically almost impossible given this reward structure -- consistent with
`has_partial_exit=True` covering ~38% of all trades (from Phase 1) landing almost entirely in the win
population, not the loss population.

**Conclusion for Paso 1's gate**: 1262/1265 losses (99.76%) are Confirmed with high classifier
confidence (0.98). This clears the viability gate explicitly -- the investigation does NOT stop here.

## Unit B — Post-Stop-Loss behavior reconstruction

`behavior/post_stop_metrics.py` extends Phase 1's `extract/post_stop_trajectory.py` (reused, not
duplicated: both share `common/series_index.py`'s cached bisect index). Causality:

- The measurement baseline is each event's own `exit_price` (the ACTUAL executed price, already
  gap-adjusted), never a nominal/idealized level.
- The first bar considered is strictly AFTER `exit_ts` (reuses the existing `bisect_right` boundary);
  the exit bar's own M15 range is never used retrospectively. `first_actionable_ts = exit_ts + 15min`
  makes this boundary explicit for any later hypothetical re-entry rule.
- Horizons: **1h, 4h, 1d, 3d**, measured in **calendar time** (wall-clock), not market-effective time.
  This choice is declared once here and applied uniformly; weekend/holiday gaps spanned by a horizon
  are flagged (`weekend_gap_spanned`, gap > 20 minutes between consecutive available bars) rather than
  silently absorbed or interpolated.
- MFE/MAE are measured relative to the ORIGINAL trade's direction (MAE = continuation of the move that
  caused the SL; MFE = reversal back toward the original direction), in price, in R (of the ORIGINAL
  risk), and in ATR (14-bar M15 ATR computed strictly from bars at/before the event -- never leaking
  the future into the event's own volatility estimate).
- `first_move_direction` ("continuation"/"reversal"/None) uses a **pre-registered threshold of
  0.25R** -- chosen before any Phase-2 result was inspected, as large enough to exceed typical FX
  spread/noise at this risk scale, small enough to catch early moves. Never tuned afterward.
- `recovered_to_entry_price` / `time_to_entry_recovery_s`: whether/when price returns all the way to
  the original entry price (not just the 0.25R threshold).
- R-normalization is skipped (`None`, never 0.0) whenever `risk_price` is zero/invalid.

## Unit C — Matched control group

`control/sampling.py` answers: is post-SL behavior actually different from ordinary market behavior?

- A control borrows its `(instrument, session, direction, risk_price)` from exactly one real SL event
  -- all four are pre-event-decided by construction (they describe the real event's own setup, not
  the control point's future). Only the control's OWN timestamp is freely chosen.
- The control timestamp comes from the SAME stratum (instrument x session x direction x
  **period bucket**, see below) as its matched real event, drawn from a random 400-candidate pool of
  that instrument's M15 bars, **nearest-ATR-matched** (14-bar M15 ATR, causal) against the real
  event's own ATR at its stop.
- Candidates within a 4-hour buffer of ANY real SL event (same instrument) are dropped first, to limit
  the same market episode contributing to both groups.
- Controls are measured with the exact same `compute_post_stop_behavior` function used for real
  events (wrapped in a minimal synthetic `EventRecord` via `control_to_event_record`), so the two
  groups are computed identically and are directly comparable -- never a second, possibly-divergent
  implementation.
- Determinism: one `random.Random(DEFAULT_SEED=20261124)` instance threaded explicitly through every
  draw -- the seed is this design's registration date, not tuned to produce a particular result.

## Unit D — Stratification

Grouped one dimension at a time only -- instrument, session/model, direction, period bucket -- plus
the pooled-overall result. **Not** a full cross-product grid: the brief explicitly asked this phase
to avoid combinatorial subgroup search, and a 3x2x2x4 grid would fragment most cells below any useful
sample size anyway.

**Period buckets, predeclared before any comparison ran**: `2015-2017`, `2018-2020`, `2021-2023`,
`2024-2026` -- four roughly-equal calendar spans covering the dataset's known range, chosen for even
coverage, not to highlight or hide any particular difference.

`MIN_HEADLINE_N = 30`: a group below this is still reported in full (n, point estimate, CI) but
flagged `small_sample=True` -- never suppressed, never treated as solid evidence on its own.

## Statistical inference

`stats/bootstrap.py` implements a **block bootstrap**, block = `(instrument, ISO calendar week)` --
declared once, used for every metric, never re-chosen per result. This treats near-in-time events
(which are not independent draws) as dependent within a block, resampling whole blocks with
replacement. The SL-vs-control comparison uses a **paired** block bootstrap (resampling blocks of
matched pairs together, preserving the 1:1 match), reporting `statistic(SL) - statistic(control)` as
a percentile CI on the difference -- directly answering "is the gap big enough to be interesting,"
never just "is SL's own number nonzero."

No threshold or hypothesis in this document was chosen after inspecting Phase-2 results; this file
was written alongside the code, before `stats/atlas.py` was run for the first time.
