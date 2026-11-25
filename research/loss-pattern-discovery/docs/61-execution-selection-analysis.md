# Deliverable E — Execution Selection Analysis

Reproduce: `uv run --project detector python
research/loss-pattern-discovery/extract/funnel_reconstruction.py` (writes the covariates alongside
the reconstruction). `atr_at_order_placement`/`planned_risk_atr_at_order_placement` are computed
using ONLY M15 bars closed strictly before `order_placed_ts` (`compute_atr_at_event`, Phase 3's own
causal boundary, reused unmodified) -- available for BOTH filled and never-filled candidates alike,
unlike Phase 4/5's `atr_m15_at_entry`/`risk_atr` (computed at `entry_ts`, which never-filled
candidates never have). No predictor is built; this is a descriptive comparison only.

## Filled vs. never-filled candidates: `planned_risk_atr_at_order_placement` (median)

| | 1AM filled | 1AM never-filled | 9AM filled | 9AM never-filled |
|---|---|---|---|---|
| EURUSD | 1.466 | 1.282 | 1.304 | 1.235 |
| USDCAD | 1.448 | 1.390 | 1.295 | 1.140 |
| AUDUSD | 1.505 | 1.472 | 1.305 | 1.234 |

**Filled candidates consistently show a HIGHER planned risk-to-ATR ratio than never-filled ones, in
all six (model, instrument) cells.** A candidate whose planned stop sits further from entry in ATR
terms is somewhat more likely to eventually receive a fill than one with a tighter relative stop --
reported as a consistent descriptive pattern, not explained causally (several plausible mechanisms
exist, e.g. retest-distance correlation, none tested here).

**1AM's `planned_risk_atr_at_order_placement` is higher than 9AM's in every cell, filled or not**
(1AM: 1.28-1.51; 9AM: 1.14-1.31) -- consistent with Phase 5/6/7's own finding that 1AM's risk_atr is
not smaller than 9AM's, now shown to hold even BEFORE fill, among never-filled candidates too. This
is not a consequence of which candidates get selected into execution -- it is already present at
order placement.

## `atr_at_order_placement` (median, price units)

| | 1AM filled | 1AM never-filled | 9AM filled | 9AM never-filled |
|---|---|---|---|---|
| EURUSD | 0.000554 | 0.000578 | 0.001025 | 0.001051 |
| USDCAD | 0.000544 | 0.000509 | 0.001239 | 0.001185 |
| AUDUSD | 0.000576 | 0.000621 | 0.000776 | 0.000847 |

1AM's order-placement-time ATR is consistently well below 9AM's (roughly half, for EURUSD/USDCAD)
-- extending Phase 5's `atr_m15_at_entry` finding (1AM operates in a lower-M15-volatility regime)
to the PRE-FILL population as a whole, filled and never-filled alike: this is a property of WHEN
1AM's orders get placed (a quieter session), not of which ones happen to fill.

## Confirmed vs. placed vs. filled: the composition difference, summarized

Combining Deliverable D's conversion rates with this phase's own funnel reconstruction (`docs/58`):
9AM confirms roughly 2.3-2.5x as many signals per credited trigger as 1AM (`docs/60`), and both
models' FILL rate given a built candidate is broadly similar (1AM slightly higher, 78-90% vs.
9AM's 78-81%). The dominant selection difference is NOT "which candidates fill once built" -- it is
"how many candidates get built and confirmed in the first place," which the window-duration
difference (Phase 7, `docs/47`) plausibly drives, though this phase does not test that link
causally.

## What this analysis does not do

No classifier, score, or filter is built from these covariates. No threshold is chosen to separate
filled from never-filled candidates. This is a description of two already-existing populations'
observable differences, for interpretive context only (Deliverable F).
