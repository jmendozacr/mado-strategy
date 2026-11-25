# Deliverable I — Phase 10 Recommendation (not executed)

One priority investigation, proposed but NOT run in this phase, per the boundary that this lab
closes selection questions before entertaining any predictive hypothesis.

## Recommended investigation

**Does the confirmation-stage rejection taxonomy (Deliverable B's categories: `confirmed`,
`no_model1_anchor_found` [with its `zero_anchors_ever`/`chain_exhausted` sub-split],
`model1_pending_or_invalidated`, `window_empty_before_search`) correlate with the eventual E1
outcome among signals that DO reach execution?**

Concretely: for the 2047 executed, evaluable trades, attach each trade's OWN confirmation-stage
history (e.g. did its Model-1 signal pass through a chain that had previously invalidated at
least once before confirming? how close did it come to the window's own close before confirming?)
and test whether that history associates with E1 at standard significance, using the SAME
non-causal, pre-registered, direct-standardization/bootstrap discipline this lab has used since
Phase 3.

## Why this is the priority, not something else

Deliverable G's interpretive update establishes that the two models' executed populations are
drawn from a ~2.4x differential confirmation-selection process (Deliverable B) BEFORE Stage 6 and
execution. The natural next question -- left explicitly open by Deliverable G's own scope limits
-- is whether variation WITHIN that selection process (not just between 1AM and 9AM) relates to
the trade-level outcome Phases 5-7 already characterized. This is a strictly more disciplined
version of "does the confirmation mechanism matter" than re-opening the window-duration question
(already tested and found insufficient alone, Phase 7) or re-litigating Stage-6 (fully attributed
to the RR floor, Deliverable C, with nothing left to investigate there).

## Required safeguards (restated, not new)

- Every input variable must be classified under Deliverable F's layer dictionary BEFORE use; only
  Layer 1/Layer 2 variables (available at or before confirmation) may serve as candidate
  predictors of a Layer 4 (After Fill) outcome -- this is exactly what the layer dictionary exists
  to enforce.
- Pre-register the association criteria BEFORE computing the association, as in every phase since
  Phase 7.
- Any positive association must be reported as exactly that -- an association within the executed,
  already-selected population -- never promoted to a causal or tradable claim without a
  dedicated, separately-authorized phase, per this lab's standing charter.
- No RR/SL/TP/entry-parameter optimization, no AI training, no new strategy construction -- same
  repository protection boundaries as every prior phase.

This recommendation is advisory only; it does not authorize Phase 10 and this phase stops before
any such work.
