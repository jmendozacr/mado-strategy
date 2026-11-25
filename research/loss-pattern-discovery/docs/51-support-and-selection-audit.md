# Deliverable F — Support and Selection Audit

## Candidate/non-executed signal counts: they DO exist, read-only audited here

`audit/2026-11-17-causal-lookahead-audit/funnel_2015plus_run2.csv` -- produced by the SAME
`run_d1_d2_d3.py` run that wrote this lab's own trades CSV (same `output_label`,
"2015plus_run2") -- retains, per arm/pair/model, a funnel of counts from the raw HTF trigger all
the way to the executed trade:

```
arm,candidates_built,filled,model,model1_confirmed,never_filled,pair,reference_incomplete_skipped,
skipped_no_placement,swept_bearish_only,swept_both,swept_bullish_only,swept_neither,
triggers_with_key_level,windows_considered,zero_signal_reason_categories
```

Example row (d3_c2, EURUSD, 1am): `windows_considered=3085, triggers_with_key_level=4199,
model1_confirmed=680, never_filled=147, zero_signal_reason_categories={'no_model1_anchor_found':
1759, 'model1_pending_or_invalidated': 1282, 'window_empty_before_search': 478}`.

**Model-specific and trustworthy**: `windows_considered`, `triggers_with_key_level`,
`model1_confirmed`, `never_filled`, the `swept_*` breakdown, and `zero_signal_reason_categories` --
each row's own model column genuinely differs between 1am/9am for the same pair (e.g. EURUSD
`model1_confirmed`: 680 for 1am vs. 1039 for 9am).

**A caveat, flagged not resolved**: `candidates_built` and `filled` are IDENTICAL across the 1am and
9am rows for the same pair (e.g. both EURUSD rows show `candidates_built=783, filled=636`). This
looks like a pair-level (not model-level) aggregate duplicated across both model rows, rather than a
genuine per-model count -- this phase does not re-derive or correct that column; it is reported
honestly as ambiguous, not relied upon for any model-vs-model comparison.

## What this means for this phase's own population

This phase (like every prior one) works from `model1_confirmed`-and-later trades only (the
`filled`/executed subset) -- `windows_considered` (3085-4199 per pair/model) is roughly 3-6x the
number of trades this lab ever analyzes. The window-widening question (Unit A/B/E) concerns ONLY
the `model1_confirmed`-stage boundary for 9AM -- a wider window could, in principle, change WHICH
candidates reach `model1_confirmed` at all (more time to find an anchor+engulf+retest sequence), not
just when an already-confirmed one occurred. **This phase does not and cannot determine the total
effect of the window-widening decision on the full candidate population** -- only on the
already-executed trades it analyzes. This is the same L1 selection-bias limitation this lab has
carried since Phase 4, now specifically re-flagged for window-duration questions.

## No contrafactual re-simulation performed

Per the brief's explicit instruction (section 10), this phase does NOT re-run the pipeline with an
alternative (e.g. narrower) 9AM window to see which candidates would or would not have confirmed --
that would be a different, explicitly causal/contrafactual design this phase does not attempt.
Excluding late-window confirmations from today's DESCRIPTIVE/ASSOCIATIVE analysis (Deliverable
E's Model 2/3) is not equivalent to, and is never presented as, "what would have happened with a
shorter window."
