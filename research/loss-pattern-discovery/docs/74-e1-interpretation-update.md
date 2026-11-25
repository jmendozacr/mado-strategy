# Deliverable G — E1 Interpretation Update

**This document changes no historical number from Phases 5-8.** The E1 endpoint difference
reported there (1AM rate 11.63% vs. 9AM rate 6.25% among evaluable executed trades, 95% CI
[2.52pp, 8.26pp] -- recomputed identically by this phase's own reconciliation, see Deliverable A's
`e1_endpoint` block) stands exactly as before. What changes is how that number should be read in
light of this phase's findings.

## What Phases 5-7 already established

- Phase 5: the E1 gap survives a risk_atr adjustment (`RESIDUAL_MODEL_ASSOCIATION`).
- Phase 6: the gap survives a same-bar-engine-convention audit (`NEXT_BAR_DIFFERENCE_PERSISTS`).
- Phase 7: the gap survives a confirmation-window-timing-position adjustment, using the
  CORRECTED 240-minute 9AM window (`E1_DIFFERENCE_PERSISTS_AFTER_TIMING_ADJUSTMENT`).

All three of these audits operated entirely within Layer 4 (After Fill, Deliverable F) -- they
asked whether trade-level mechanics (stop execution convention, intrabar ambiguity, timing
position within the confirmation window) explain the gap AMONG ALREADY-EXECUTED trades. None of
them touched the question this phase answers: how different are the two models' EXECUTED
populations before any trade-level dynamics even begin?

## What this phase adds

The 1AM and 9AM executed populations (619 and 1424 evaluable trades respectively) are drawn from
dramatically different selection processes upstream of execution:

- 1AM confirms 16.1% of its triggers; 9AM confirms 38.0% (Deliverable B) -- a ~2.4x difference in
  the confirmation-stage selection rate, stable across all four periods and all three instruments
  (Deliverables D, E).
- Both models then apply an IDENTICAL Stage-6 RR floor (2.0) to their respective confirmed
  populations, with 100% of each model's Stage-6 attrition attributed to that single rule
  (Deliverable C) -- so Stage 6 does not differentially reshape the two populations beyond what
  the RR floor does to each independently.

**Interpretive consequence**: the E1 gap measured in Phases 5-7 is a property of two populations
that were ALREADY selected at a ~2.4x differential rate before reaching the trade-outcome stage
those phases examined. This phase does not show that the selection difference CAUSES the E1 gap
(Deliverable F's layer discipline forbids using Layer 2/3 selection facts to explain a Layer-4
outcome difference without an explicit mechanism linking them, and no such mechanism is
established here). What it does show is that **the E1 gap can no longer be interpreted as if the
two models' executed trades were drawn from comparably-selected populations that merely differ in
stop-timing mechanics** -- the populations differ substantially in how they were assembled, and
any future causal hypothesis about E1 must account for that selection difference rather than
treating 1AM and 9AM as two samples from an otherwise-equivalent process.

## What this phase does NOT claim

- It does not claim the confirmation-rate gap explains any specific fraction of the E1 rate gap
  (that would require a mediation analysis this phase was not scoped to run).
- It does not claim the RR-floor attrition (Deliverable C) contributes to the E1 gap -- it is
  identical in rule and rate-of-application logic for both models.
- It does not revise Phase 5-7's own verdicts, which remain correct statements about what survives
  WITHIN the executed population.

## Recommendation carried into Deliverable I

A future phase, if authorized, should test whether selection on confirmation-stage mechanics
(e.g., which anchor-probe/rejection category a trigger falls into) correlates with the eventual
E1 outcome AMONG CONFIRMED-BUT-NOT-YET-EXECUTED signals, using the same non-causal,
pre-registered, selection-vs-prediction discipline this entire lab has maintained since Phase 1.
