# Phase 10 — Design and Pre-Registration

Written after reading `causal_anchor_v2.py` (`find_first_valid_anchor`, `confirm_in_ltf_window_v2`)
and `entries/model1.py::_track_anchor`, both in full, and after reviewing Phase 9's own
`extract/model1_rejection_diagnostics.py` (the existing diagnostic adapter for the REJECTED side).
Hypotheses, the primary contrast, and verdict criteria below are fixed BEFORE running any E1
association (Unit E) -- per the brief's own instruction and this lab's standing discipline since
Phase 7.

## 1. Deliverable A — Confirmation State Machine Audit (the 10 questions, answered from source)

1. **An attempt begins** when `confirm_in_ltf_window_v2` calls `_track_anchor(truncated,
   current_anchor, direction, purge_target, "purge_engulf", config, origin_index)`. The FIRST
   attempt's `current_anchor` comes from `find_first_valid_anchor`'s single call at the top of the
   function; every SUBSEQUENT attempt's `current_anchor` is set to the PREVIOUS attempt's own
   `result.confirmation_index` (the index at which it invalidated) -- never a fresh anchor search.
2. **A "new anchor" on retry is not a new search.** `find_first_valid_anchor` is called EXACTLY
   ONCE per `confirm_in_ltf_window_v2` invocation. What the brief colloquially calls a "new anchor"
   on retry is literally the INVALIDATING candle's own index, reused directly as the next attempt's
   `anchor_index` -- the retry loop never re-scans for a fresh level break. `origin_index` and
   `purge_target` (both derived from the very first anchor search) are carried forward unchanged
   across every retry.
3. **An internal invalidation** is `_track_anchor` returning `DetectionStatus.INVALIDATED`: a
   candle's close breaches the CURRENT anchor's own protected extreme (opposite side from the
   engulf direction) before the retest sequence completes -- whether or not the engulf itself had
   already happened (both pre-engulf and post-engulf invalidation return `INVALIDATED`, carrying
   `retest_index=None` or the already-set `retest_index` respectively).
4. **A retry is allowed exactly when** `_track_anchor`'s own return has `status ==
   DetectionStatus.INVALIDATED` -- `confirm_in_ltf_window_v2`'s own loop condition
   (`if result is None or result.status != DetectionStatus.INVALIDATED: return result`). No other
   status ever retries.
5. **The search limit per attempt** is `window_end = min(anchor_index + config.max_retest_lookback,
   len(candles) - 1)`, with `max_retest_lookback = 20` (D3's `Model1Config` default) -- `len(candles)`
   here is `len(truncated)`, which `confirm_in_ltf_window_v2` itself caps at the confirmation
   window's own `end_idx + 1`. A later attempt's search ceiling can therefore never exceed the
   window's own end, regardless of how many retries have already happened.
6. **The anchor actually used in a given attempt** is simply `current_anchor` for that attempt --
   for a terminal `CONFIRMED` signal, this equals `signal.anchor_index` on the real
   `Model1Signal` the pipeline persists.
7. **Engulf confirms** when a candle's close breaks beyond the current anchor's own body range
   (`_closes_beyond`, direction-specific) -- `confirmed = True`, entry type/price selected via
   `_select_entry`, and the loop `continue`s to the next candle (engulf and retest can never
   complete on the same candle).
8. **Retest confirms** when, after engulfing, the FIRST candle whose wick overlaps the anchor's
   body range sets `retest_index`, and a LATER candle's close breaks beyond THAT retest candle's
   own open (`_closes_beyond_open`) -- returning `CONFIRMED` at that later candle's index.
9. **Information available at each M15 close**: `causal_intrabar.available_at(candle,
   M15_DURATION)` -- a candle's own OHLC (hence whether it engulfs, retests, or invalidates) is
   knowable only once that candle's own 15-minute bar has fully closed, never earlier. Every
   decision `_track_anchor` makes about candle `j` depends only on candles `<= j`.
10. **The order is placed** at `model1_available_ts = causal_intrabar.available_at(candles[
    signal.confirmation_index], M15_DURATION)` -- the close of the exact candle that completed the
    retest. `CausalSignalRecord.order_placed_ts` is set to this same value.

**An internal invalidation is a confirmation-process event, not a Stop Loss exit.** It happens
strictly BEFORE order placement (`order_placed_ts`), so it can never itself be, or cause, a trade
outcome -- there is no position yet when it occurs. This document never treats an invalidation as
a loss.

**Algebraic identity, not three independent counters**: for any signal that reaches a terminal
attempt (`CONFIRMED`, `PENDING`, or a never-engulfed `None`), `confirmation_attempt_count =
internal_invalidation_count + 1` EXACTLY, because every non-terminal attempt result is, by
construction, `INVALIDATED` (the only status that loops), and every terminal attempt is counted
once. `anchor_restart_count` is the same quantity as `internal_invalidation_count` (one restart
per invalidation, no other restart path exists). This phase therefore uses `internal_
invalidation_count` as the ONE primary structural variable, not three correlated ones.

## 2. Candidate features and their causal validity

| Feature | Definition | Available at | Used as |
|---|---|---|---|
| `internal_invalidation_count` | number of `INVALIDATED` attempts before the terminal one | `confirmation_available_at` (the LAST attempt is the terminal, confirming one) | **Primary** (H1/H2/H3) |
| `confirmation_attempt_count` | `internal_invalidation_count + 1` | same | descriptive only (redundant with the above) |
| `first_anchor_found_at` | `available_at` of the very first attempt's own anchor candle | at or before `confirmation_available_at` | descriptive only |
| `final_anchor_found_at` | `available_at` of the TERMINAL attempt's own anchor candle | at or before `confirmation_available_at` | descriptive only |
| `confirmation_elapsed_minutes` / `confirmation_relative_position` | already audited in Phase 7 (`features/confirmation_window_features.py`) | `confirmation_available_at` | descriptive only, reused unmodified |
| `time_from_first_anchor_to_confirmation` | `confirmation_available_at - first_anchor_found_at` | by construction, non-negative | descriptive only |

Every feature is a function of candles `<= signal.confirmation_index` only -- none of them can
ever use `atr_m15_at_entry`, fill timing, MFE/MAE, or any post-order-placement information. This
phase does not promote every correlated counter into an independent hypothesis test (per the
brief's explicit instruction); `confirmation_attempt_count` and `internal_invalidation_count`
differ only by a constant offset, so testing both would not be two independent tests.

## 3. Hypotheses (restated precisely)

- **H1 (confirmation path complexity)**: `P(E1 | executed, evaluable, internal_invalidation_count
  == 0)` differs from `P(E1 | executed, evaluable, internal_invalidation_count >= 1)`, WITHIN each
  model separately (the two models' confirmation processes are not pooled for this test -- Phase
  8/9 already established they select very differently).
- **H2 (model-specific association)**: the H1 relationship's sign and/or magnitude differs between
  1AM and 9AM.
- **H3 (residual model difference)**: the unadjusted 1AM-9AM E1 gap (+5.38pp) changes materially
  when descriptively standardized against the `internal_invalidation_count` contrast's own
  composition in each model -- reported as a descriptive comparison to +5.38pp, never as a causal
  decomposition.

No directional prediction is registered for any hypothesis.

## 4. Primary pre-registered contrast (Unit D/F)

`internal_invalidation_count == 0` vs. `>= 1`, computed WITHIN the primary population (executed,
evaluable, i.e. `Outcome != OPEN` -- identical population as Phase 5-9's own `build_primary_
population`), restricted further to signals whose confirmation path was successfully reconstructed
(Deliverable B/C). This binary split is chosen BEFORE inspecting any E1 rate, per the brief's
explicit requirement; no alternative threshold (e.g. `>= 2`) is substituted after seeing results.
If Unit B's own equivalence proof fails, or reconstruction coverage over the primary population
falls short of 95%, this contrast is declared `INSUFFICIENT_PATH_RECONSTRUCTION` and Unit E is not
run on the affected subset.

## 5. Pre-registered verdict criteria (Deliverable G), fixed before Unit E's first real-data run

| Verdict | Criterion |
|---|---|
| `INSUFFICIENT_PATH_RECONSTRUCTION` | the equivalence test fails, OR path-reconstruction coverage over the primary population is below 95%, OR the primary contrast is structurally degenerate (e.g. one side has zero events in a model) |
| `INSUFFICIENT_STATISTICAL_EVIDENCE` | reconstruction succeeds, but either side of the primary contrast has fewer than 20 evaluable events in a model (mirrors Phase 5's own `MIN_COMMON_SUPPORT_PER_MODEL`) -- reported per model, never pooled across models to manufacture support |
| `CONFIRMATION_PATH_ASSOCIATION_FOUND` | both models have sufficient support, the within-model 95% CI on the primary contrast's E1-rate difference excludes zero in the SAME direction for both models, and the point difference exceeds 5pp (Phase 5's own relevance bar) in at least one model |
| `MODEL_SPECIFIC_ASSOCIATION` | sufficient support in both models, but the within-model CIs disagree in direction, or one excludes zero while the other does not |
| `NO_ROBUST_CONFIRMATION_PATH_ASSOCIATION` | sufficient support in both models, and the within-model 95% CI includes zero for BOTH models |
| `INCONCLUSIVE` | none of the above cleanly applies (e.g. mixed instrument/period signals that do not resolve into one of the patterns above) |

These criteria are applied mechanically to whatever Unit E computes; no criterion is adjusted
after seeing the E1 numbers.

## 6. What this phase does not attempt

No causal claim that invalidations cause E1. No claim that direct confirmation is "better." No
profitability claim. No out-of-sample validation (2015-2026 remains previously examined). No
change to `min_risk_reward`, no RR backtest of any kind (reserved for the registered-but-not-run
Phase 11 proposal, Deliverable H). No new predictive model or strategy.
