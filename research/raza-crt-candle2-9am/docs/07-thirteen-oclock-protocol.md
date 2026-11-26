# Protocol — 9AM Confirmations Resolving Exactly at 13:00 New York

**Dated and committed on its own, 2026-11-26, before any subgroup outcome (R, win/loss) for this
specific comparison is calculated.** `docs/05`/`docs/06` already establish WHY this population is
the right one to study and that the timing check passes (the close becomes available at the SAME
instant as the order-placement decision, never strictly before, never strictly after).

**Explicitly on the record before computing anything below**: the full-population retrospective
result from the first experiment (INSIDE 40.6% / OUTSIDE 59.1% of all 8,712 activations; +0.704R
retrospective difference, `docs/02`) is already known. THIS unit is a separate, narrower,
EXPLORATORY historical comparison over a small, specific sub-population -- it does not confirm or
extend that first result, and its own sample size may turn out too small for a useful conclusion,
which this protocol treats as an acceptable outcome, stated plainly if it occurs.

## Population (recovered upstream of the RR filter and order fills)

**Every 9AM Model-1 confirmation (EURUSD/USDCAD/AUDUSD, 2015-01-01+, same D3/C2 pipeline) whose own
`model1_available_ts` equals the current H4 candle's own close-availability instant EXACTLY**
(`current_open_ts + 4h`) -- feasibility-checked (not a subgroup outcome) at 72 (EURUSD) + 81
(USDCAD) + 79 (AUDUSD) = **232 confirmed signals pooled**. This is the population BEFORE Stage 6's
RR floor, before candidate-building, before any fill attempt -- the 119 EXECUTED trades from the
first experiment's own timeline check are a DOWNSTREAM reconciliation target for this population,
never its definition. A confirmation that resolves strictly before 13:00 belongs to a DIFFERENT
decision problem (docs/05) and is excluded from this population even if its own order eventually
fills after 13:00.

## Unit of observation

One confirmed signal (`stable_id`) in the population above. Both arms are computed for every one
of the 232, never a different denominator per arm.

## Two arms, same rules, one difference

- **Baseline**: the real, unmodified D3/C2 rules applied to this population's own confirmed
  signals -- `build_stage6_population` (RR floor, dedup, kill-zone, unchanged config) ->
  `fill_pass_c` -> `_resolve_exits`. Byte-for-byte the same function calls Phase 8-10 already
  verified, applied to a restricted INPUT set.
- **Variant**: the SAME three function calls, applied to the SAME population restricted further to
  `close_position == "INSIDE"` (the final H4 close strictly between the reference low and high,
  per `docs/01`'s own tolerance convention) -- computed BEFORE Stage 6, so a signal that fails the
  gate never reaches the RR floor, dedup, or fill search at all in the variant arm.

**Only one rule changes.** Double sweeps (`sweep_side == "BOTH"`) are KEPT in the primary
comparison on both arms -- a double-swept signal that nonetheless closes strictly inside still
passes the variant gate, exactly like a single-sided one. `sweep_side` (single-sided vs. double)
is reported as its own descriptive breakdown, never used as a filter.

## Primary metric

**Net R per original 13:00 confirmation** -- same denominator (232) for both arms:

- A signal that never becomes a candidate, never fills, or fails the variant gate contributes
  **R = 0** to that arm's sum (a skipped or unfilled order realizes nothing, never an invented
  negative or positive value).
- A signal that fills and CLOSES contributes its own real `r_multiple` (from `_resolve_exits`,
  the same unmodified function Phase 8/9 used).
- A signal that fills but is STILL OPEN at the data's end is **censored** -- excluded from the
  primary net-R sum (never assigned 0 or any invented value), its count reported separately, and
  its effect on the comparison stated explicitly (if the baseline and variant arms censor a
  different number of signals, that asymmetry itself is reported, never averaged away).

Reported alongside the primary metric, for interpretability: net R per CLOSED trade (mean R among
only the trades that actually closed) and total net R (sum), so a higher per-trade average among
fewer trades is never read as equivalent to a higher total.

## Decomposition (pre-declared, computed after the primary metric, never substituted for it)

For each signal, the per-signal difference (`variant_R - baseline_R`) is classified as:
`UNAFFECTED` (both arms reach the identical outcome -- true whenever `close_position == "INSIDE"`
and nothing else differs downstream), `LOSS_AVOIDED` (baseline closed at a loss, variant skipped
it at the gate or never filled), `GAIN_FORGONE` (baseline closed at a win, variant skipped it),
`NEWLY_CENSORED`/`NO_LONGER_CENSORED` (an open-trade censoring status differs between arms), and
`BOTH_ZERO` (neither arm ever executed this signal). This decomposition is reported as COUNTS, not
folded into the mean-R number itself.

## Uncertainty

Block bootstrap, 2,000 resamples, 95% percentile CI, on the mean paired difference
(`variant_R - baseline_R`, non-censored signals only) -- **blocks are whole NY trading dates,
pooled across all three instruments together** (never resampled per instrument separately): every
signal whose current-candle date falls on the same NY calendar date, regardless of pair, is one
block. This is a DIFFERENT blocking unit than the first experiment's own `(symbol, date)` block
(docs/01), by the brief's own explicit instruction for this specific unit.

## Reconciliation requirement

Every baseline-arm EXECUTED signal in this population must match the real ledger's own record
(outcome, r_multiple) exactly, by `stable_id` -- verified before any outcome number is trusted
(`raza_extract.thirteen_oclock_experiment.reconcile_baseline_against_ledger`). Any discrepancy is
investigated and explained before this protocol's own results are reported, never silently
accepted.

## Stop condition (pre-declared)

If the number of CLOSED trades under either arm, pooled across all three pairs, is small enough
that the bootstrap CI spans a range many times the point estimate's own magnitude (no fixed
numeric threshold declared -- judged plainly in the report, the same discipline this lab has used
for every prior "insufficient support" call), the report states the sample is too small for a
useful conclusion rather than asserting a direction.

## What this unit does not do

No change to `min_risk_reward`, Stop Loss, Take Profit, cost model, or any rule other than the
single close-position gate stated above. No wider trading-hours question. No detector/scanner
change. No adoption recommendation -- left explicitly for review, per the brief's own closing
instruction.
