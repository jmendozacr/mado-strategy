# Deliverable H — Recommendation for Phase 9 (not executed this phase)

One recommendation, per the brief's instruction.

## Recommended: a structural investigation of what Model-1's confirmation criterion actually filters on, comparing the two models' confirmed-vs-never-confirmed populations

Phase 8 found the single largest, most consistent 1AM/9AM difference is NOT in execution (fill
rate given a candidate: broadly similar, 78-90%) or in post-entry outcome composition (risk_atr,
timing position: both ruled out, Phases 5-7) -- it is in CONFIRMATION: 9AM confirms ~2.3-2.5x as
many credited triggers into Model-1 signals as 1AM does, consistently across all three pairs
(`docs/60`). This phase named the window-duration difference as a PLAUSIBLE, UNTESTED mechanism for
that gap (`docs/61`/`docs/62`) -- Phase 9 should test it directly, structurally, not by varying the
window and re-simulating (still out of scope -- a genuine contrafactual needs its own careful
design), but by characterizing WHICH triggers 1AM's shorter window causes to time out
(`zero_signal_reason_categories`'s `"model1_pending_or_invalidated"` and
`"no_model1_anchor_found"` buckets, already captured per-model in this phase's own reconstruction,
`docs/58`) vs. which ones 9AM's longer window allows to resolve -- a descriptive, not
predictive, comparison of the REJECTED population's own characteristics (available strictly at or
before the trigger instant), continuing this phase's own read-only-adapter approach.

## Why not the other options named in the brief

- **A pre-entry predictive test**: premature. This phase's own Deliverable F explicitly flags an
  open, untested question (does 1AM's stricter confirmation bar itself explain its higher E1 rate)
  that should be investigated structurally FIRST -- building a predictor now would conflate
  confirmation-selection effects with genuine pre-entry signal.
- **Another provenance audit**: not needed immediately -- this phase's provenance work
  (Deliverable A) and diagnostic adapter (Deliverable B) are reusable building blocks for Phase 9's
  own confirmation-stage investigation; no new audit unit is required first.
- **Closing the research line**: not justified -- Phase 8 surfaced a large, clean, newly-identified
  structural difference (confirmation rate) that no prior phase examined; it deserves one focused
  follow-up before any decision to stop.

This is a recommendation only. Per the brief, Phase 9 does not start without separate, explicit
authorization.
