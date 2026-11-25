# Phase 8 — Design, Observation Units, and Pre-Registration (Unit B)

Written after Deliverable A's provenance audit (`docs/56`) and the diagnostic adapter's own
correctness smoke-test, but BEFORE inspecting the full reconciled funnel numbers across all three
pairs or computing any conversion rate -- the verdict criteria (section 5 below) are fixed now.

## 1. The funnel, with true observation units (never flattened into one)

| Stage | True observation unit | Cardinality relative to the stage above |
|---|---|---|
| 1. Window considered | (model, NY-day) | 1 per model per calendar day walked |
| 2. Feeder reference available | (model, NY-day) | subset of stage 1 (`reference_incomplete_skipped` is the disjoint complement) |
| 3. Sweep outcome | (model, NY-day) | exactly 1 of {bearish-only, bullish-only, both, neither} per stage-2 window -- `record_sweep` guarantees mutual exclusivity |
| 4. Valid trigger | (model, NY-day, direction) | 0, 1, or 2 per window (one per direction that both swept AND was credited by a Key Level) |
| 5. Model-1 confirmation attempt | (model, NY-day, direction) | same unit as stage 4 -- `model1_confirmed + sum(zero_signal_reason_categories) == triggers_with_key_level` by construction |
| 6. Aligned candidate | `signal_id` | subset of stage 5's confirmed outcomes, AFTER `build_stage6_population`'s own further exclusions (duplicate/kill-zone/RR-floor -- not audited stage-by-stage this phase, out of scope) |
| 7. Fill-eligible | `signal_id` | subset of stage 6 (`skipped_no_placement` is the disjoint complement -- order-placement timestamp maps to no M15 bar) |
| 8. Filled (executed trade) | `signal_id` | subset of stage 7 (`never_filled` is the disjoint complement -- no fill within `max_fill_wait`) |
| 9. Trade managed to exit | `signal_id` (== stage 8, 1:1 via `_resolve_exits`) | every filled candidate produces exactly one `Trade` |
| 10. Outcome bucket (E0-E4) | `signal_id` (== stage 9) | Phase 6's own taxonomy, unchanged |

**Mandatory rule, never violated below**: a rate is only computed when its numerator and
denominator share the SAME unit from the table above, linked by a verified, not assumed,
containment relationship (e.g. stage 4 -> stage 5 is valid: same unit, subset. Stage 1 -> stage 4
is NOT a per-window rate: the denominator is (model,NY-day) but the numerator is
(model,NY-day,direction) -- reported as "triggers per window" with that caveat explicit, never as
"P(trigger | window)" implying a single Bernoulli event per window).

## 2. Why stages 6-8 need the diagnostic adapter (Deliverable A's finding)

`candidates_built`/`filled`/`never_filled`/`skipped_no_placement` are POOLED across both models in
the persisted funnel CSV (`docs/56`). No candidate-level file is persisted. The only way to recover
stages 6-8's per-model split is to re-derive `population.candidates` and `fill_pass_c`'s internal
partition, tagging each item with the `model_by_sig` mapping that `run_d_c2`'s own
`CausalSignalRecord` objects already carry (never inventing or reinterpreting an identity -- the
SAME `signal_id` the original pipeline assigned). `extract/funnel_reconstruction.py` does exactly
this, reusing `run_d_c2`, `build_stage6_population`, and `fill_pass_c` UNMODIFIED, and
cross-checks its own per-model sums against `fill_pass_c`'s own pooled return values as a built-in
correctness gate (`verify_against_pooled_counts`) -- if they do not match exactly, the
reconstruction is wrong and must not be trusted (tested explicitly).

## 3. What this phase does NOT attempt

Stage 6's OWN further exclusions inside `build_stage6_population` (duplicate/kill-zone/RR-floor)
are not broken out per-model this phase -- only the boundary BEFORE stage 6 (triggers/confirmations,
already model-specific in the funnel CSV) and AFTER stage 6 (candidates/fills, recovered by the
adapter). A full per-model breakdown of `build_stage6_population`'s own internal exclusion reasons
is a reasonable future unit, not attempted here (would require instrumenting that function's
internals, a heavier intervention than this phase's read-only adapter).

## 4. Pre-registered selection-characterization variables (Unit G)

Only fields knowable strictly before the question being asked, per stage:

- **Before confirmation**: `origin_model`, `instrument`, NY day-of-week/period bucket,
  `feeder_ref_available_ts`, `activation_instant_ts` (HTF sweep+Key-Level evidence only).
- **At confirmation**: `confirmation_elapsed_minutes`/`confirmation_relative_position` (Phase 7,
  reused), planned `risk_price`/`planned_rr`/`take_profit`-`entry_price` geometry.
- **At/after fill only, for FILLED candidates**: `order_to_fill_minutes` (Phase 7, reused, already
  excluded from any predictor role), `atr_m15_at_entry` (Phase 4's existing causal boundary).

**New fields, pre-declared before computing them**: `atr_at_order_placement` (ATR using bars closed
strictly before `order_placed_ts`, computable for BOTH filled and never-filled candidates, since
`order_placed_ts` exists for every stage-6 candidate) and `planned_risk_atr_at_order_placement`
(`risk_price / atr_at_order_placement`, same availability). These are DELIBERATELY NOT assumed
identical to Phase 4/5's `atr_m15_at_entry`/`risk_atr` (computed at `entry_ts`, which only exists for
FILLED candidates, strictly later) -- kept as separate fields, never substituted for each other.

## 5. Verdict criteria (Deliverable G), fixed before inspecting the reconstructed numbers

| Verdict | Criterion |
|---|---|
| `INSUFFICIENT_EVENT_LEVEL_PROVENANCE` | the diagnostic adapter's cross-check (`verify_against_pooled_counts`) fails for any pair, OR a required stage-6/7/8 split cannot be reconstructed at all |
| `PARTIAL_FUNNEL_RECONSTRUCTION` | the cross-check passes but some stage (e.g. stage 6's own internal exclusion reasons) remains genuinely unrecoverable and is documented as such |
| `FUNNEL_RECONSTRUCTED_AND_RECONCILED` | every stage 1-10 reconciles exactly against the real ledger baseline (620/619/1 for 1AM, 1427/1424/3 for 9AM, E1=72/619 and 89/1424) with zero unexplained discrepancies |
| `MATERIAL_EXECUTION_SELECTION_DIFFERENCE` | 1AM and 9AM differ by >=10 percentage points (absolute) in any stage-to-stage conversion rate that is actually identifiable per section 1's unit rule, OR the pre-confirmation/pre-fill covariate distributions (section 4) differ with a non-overlapping IQR on a variable plausibly relevant to execution |
| `NO_MAJOR_SELECTION_DIFFERENCE_DETECTED` | no identifiable conversion rate or covariate distribution differs by the above threshold |

`FUNNEL_RECONSTRUCTED_AND_RECONCILED`/`PARTIAL_FUNNEL_RECONSTRUCTION`/
`INSUFFICIENT_EVENT_LEVEL_PROVENANCE` describe INTEGRITY; `MATERIAL_EXECUTION_SELECTION_DIFFERENCE`/
`NO_MAJOR_SELECTION_DIFFERENCE_DETECTED` describe SELECTION -- both are reported together, per the
brief's own instruction, never collapsed into one label. The 10-point threshold is a pre-declared,
round, conservative bar deliberately set HIGHER than the 5pp relevance bar Phases 5-7 used for the
E1 endpoint itself -- funnel-stage conversion rates are a secondary, exploratory question this
phase is not trying to find the smallest detectable difference in.
