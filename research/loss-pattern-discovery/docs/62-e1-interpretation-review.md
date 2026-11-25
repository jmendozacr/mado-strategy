# Deliverable F — E1 Interpretation Review

Phases 6/7's own numbers are UNCHANGED and reproduced exactly by this phase's own reconciliation
(`docs/58`): E1 = 72/619 (11.63%) for 1AM, 89/1424 (6.25%) for 9AM, +5.38pp, 95% CI [2.52, 8.26].
This document reviews how that association should be READ in light of Phase 8's funnel findings --
it does not recompute or adjust it.

## The core interpretive point

`P(E1 | executed trade)` conditions on an ALREADY-SELECTED population -- and this phase found that
the TWO MODELS' selection processes are not equally stringent. 1AM confirms only ~16% of its
credited triggers into a Model-1 signal; 9AM confirms ~37-40% (`docs/60`) -- roughly 2.3-2.5x more
permissive, plausibly because its confirmation window is twice as long (240min vs. 120min, Phase 7).
1AM's executed population is therefore drawn from a narrower, more selective slice of its own
opportunity set than 9AM's is from its own.

**This does NOT mean the E1 comparison is invalid** -- both populations are real, executed trades,
and the +5.38pp figure accurately describes a real difference between them. It DOES mean the
comparison is between two differently-selected populations, not between "the same kind of
opportunity, just from two clocks." A hypothetical world where 9AM used as strict a confirmation
bar as 1AM might execute far fewer, differently-composed trades -- this phase cannot say whether
THAT population's E1 rate would differ from today's 6.25%, because that population does not exist
in this data (no contrafactual re-simulation was run, per Phase 7's and this phase's own
boundaries).

## What Deliverable E's covariate findings add

Filled 1AM candidates have a higher `planned_risk_atr_at_order_placement` than filled 9AM
candidates (`docs/61`) -- consistent with, and now extended before-fill, Phase 5/6's finding that
risk_atr does not explain the E1 gap (standardizing on it does not shrink the gap, Phase 5 `docs/32`,
Phase 7 `docs/50`). The composition difference is real but, so far as risk_atr and confirmation-
timing position (Phase 7) have been tested, does not explain WHY 9AM's larger, more easily
confirmed population has a lower early-stop rate than 1AM's smaller, more selective one.

## What remains an open question, not answered by any phase so far

Whether 1AM's higher confirmation bar (fewer, more selective candidates) is ITSELF a plausible
mechanism for its higher E1 rate -- a stricter filter could, in principle, still pass through
setups with a geometry more prone to an early reversal, if the filter criterion is orthogonal to
that risk. This phase raises the question; it is not tested here (would require characterizing
WHAT about 1AM's confirmation criterion differs qualitatively, beyond timing and risk_atr, an
explicitly structural question out of this phase's scope).

## No change to Phases 5-7's historical verdicts

`RESIDUAL_MODEL_ASSOCIATION` (Phase 5), `NEXT_BAR_DIFFERENCE_PERSISTS` (Phase 6),
`E1_DIFFERENCE_PERSISTS_AFTER_TIMING_ADJUSTMENT` (Phase 7) all stand unmodified. This phase adds
context about WHERE in the signal-generation funnel the two models' populations diverge most
sharply (confirmation rate, not fill rate) -- it does not revise any prior number.
