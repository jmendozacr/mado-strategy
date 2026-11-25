# Deliverable D — Funnel Conversion Report

Only rates whose numerator and denominator share the same observation unit (docs/57 section 1),
computed directly from Deliverable B's reconciled counts.

## P(Model-1 confirmed | trigger with Key Level) -- same unit: (window, direction)

| | EURUSD | USDCAD | AUDUSD |
|---|---|---|---|
| 1AM | 680/4199 = **16.2%** | 601/3830 = **15.7%** | 524/3177 = **16.5%** |
| 9AM | 1039/2716 = **38.2%** | 1202/3036 = **39.6%** | 1070/2960 = **36.1%** |

**9AM confirms roughly 2.3-2.5x as often as 1AM, per credited trigger, consistently across all
three pairs.** This is the single largest, most consistent conversion-rate difference found in
this phase, and it has an obvious structural candidate explanation: 9AM's confirmation window is
240 minutes vs. 1AM's 120 (Phase 7, `docs/47`) -- twice the time for Model-1's anchor/engulf/retest
sequence to complete. This phase does not test that candidate explanation causally (would require
a contrafactual window-width re-simulation, out of scope per Phase 7's own boundary, reaffirmed
here) -- reported as a structural fact and a plausible, untested mechanism.

## P(filled | candidate built) -- same unit: `signal_id`

| | EURUSD | USDCAD | AUDUSD |
|---|---|---|---|
| 1AM | 143/173 = **82.7%** | 207/231 = **89.6%** | 270/314 = **86.0%** |
| 9AM | 493/610 = **80.8%** | 489/623 = **78.5%** | 445/573 = **77.7%** |

1AM's fill rate is consistently HIGHER than 9AM's across all three pairs, by 1.9pp (EURUSD) to
11.1pp (USDCAD) and 8.3pp (AUDUSD) -- smaller and more pair-heterogeneous than the confirmation-rate
gap above, but directionally consistent.

## Filled trades per window considered -- NOT a single-event probability; an average yield

| | EURUSD | USDCAD | AUDUSD |
|---|---|---|---|
| 1AM | 143/3085 = **4.64%** | 207/3083 = **6.71%** | 270/3083 = **8.76%** |
| 9AM | 493/3078 = **16.02%** | 489/3076 = **15.90%** | 445/3076 = **14.47%** |

**9AM produces 2.1x (AUDUSD) to 3.5x (EURUSD) as many executed trades per window-day as 1AM.**
Absolute-point gaps: +11.38pp (EURUSD), +9.19pp (USDCAD), +5.71pp (AUDUSD) -- all but AUDUSD clear
the pre-declared 10pp material-difference bar on their own; AUDUSD's relative ~65% uplift is large
even though its absolute gap sits just under the bar. This is the compounded product of the two
rates above (confirmation rate x fill-given-candidate rate x the unaudited candidates_built/
model1_confirmed survival step) -- `windows_considered` is nearly identical between models
(~3076-3085 for both), so this gap is NOT explained by 9AM simply having more opportunities to
begin with; it comes from converting a much larger share of its opportunities into trades.

## What this does NOT establish

None of the above is a per-window Bernoulli probability in the sense of "if I open a 1AM window, I
have a 4.64% chance of a trade" -- `windows_considered` pools across 11 years and three symbols,
with substantial day-to-day and symbol-to-symbol dependence (never treated as i.i.d. in this
report). These are DESCRIPTIVE yields over the full reconstructed population, reported with exact
counts and denominators, not as calibrated probabilities with a confidence interval -- the brief's
own section 13 allows CIs "cuando tengan sentido"; a block-bootstrap CI on a window-level funnel
rate would need to account for dependence this phase has not modeled, so none is reported here
rather than invented. `P(E1 | executed trade)` (Phases 6/7) remains a DIFFERENT estimand from any
rate on this page, computed on a different, much smaller, already-conditioned population
(Deliverable F discusses the implication).
