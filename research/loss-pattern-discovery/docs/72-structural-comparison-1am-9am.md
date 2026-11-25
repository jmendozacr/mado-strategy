# Deliverable E — Structural Comparison, 1AM vs. 9AM

Scope discipline (per the Phase 9 brief): this document enumerates STRUCTURAL differences between
the two models' confirmation mechanics and reports which rejection categories correlate with each
difference. It does **not** run a counterfactual re-simulation (e.g. "give 1AM a 240-minute
window and see what happens"), and it does **not** claim any single structural difference CAUSES
the confirmation-rate gap. Phase 7 already tested timing-position as a causal candidate for the
(different) E1 outcome gap and found the difference persisted after adjustment
(`E1_DIFFERENCE_PERSISTS_AFTER_TIMING_ADJUSTMENT`) -- this document is strictly about the
confirmation-stage selection difference newly characterized in Phase 8/9, and keeps the same
causal discipline.

## Structural differences, enumerated

| Dimension | 1AM | 9AM | Shared / identical |
|---|---|---|---|
| Confirmation window span | 02:00-04:00 NY, 120 min | 09:00-13:00 NY, 240 min | -- |
| Window architecture | Single window serves BOTH activation and confirmation | Activation sub-window (09:00-11:00 NY) closes well before the confirmation window's own close | -- |
| Anchor search rule (`find_first_valid_anchor`) | -- | -- | Identical: 20-candle age-bounded lookback, independent of window length |
| Engulf/retest state machine (`_track_anchor`) | -- | -- | Byte-for-byte identical code path for both models |
| Retry-on-invalidation loop (`confirm_in_ltf_window_v2`) | -- | -- | Identical: always retries, never returns terminal INVALIDATED, for both models |
| Stage-6 RR floor (`min_risk_reward`) | 2.0 | 2.0 | Identical config value for both models and all 3 pairs |
| Stage-6 kill-zone gate | inactive (`kill_zone_gated=False`) | inactive (`kill_zone_gated=False`) | Identical -- never applies to either model |

**The only mechanical differences between the two models are the window's own span and its
activation/confirmation architecture.** Every downstream rule (anchor search, engulf/retest,
retry loop, Stage-6 cuts) is literally the same code, the same parameters, for both models.

## Rejection-category correlation with the window-architecture difference

| Rejection category | 1AM | 9AM | Structural correlate |
|---|---|---|---|
| `window_empty_before_search` | 11.6% | **0.0%** | 1AM's single combined window makes `eligible_start >= window_end` reachable whenever activation lands late in the window; 9AM's split architecture gives a ~2-hour buffer that makes this condition essentially unreachable |
| `no_model1_anchor_found` -> `zero_anchors_ever` | 13.4% of this bucket | 1.0% of this bucket | Correlates with 1AM's shorter overall search budget (120 min vs. 240 min) |
| `no_model1_anchor_found` -> `chain_exhausted` | 86.6% of this bucket | 99.0% of this bucket | Correlates with retry-chain room; a longer window gives the SAME retry logic more chances to exhaust rather than find zero |
| `model1_pending_or_invalidated` (always PENDING) | 30.9% of all triggers | 39.8% of all triggers | 9AM's larger confirmed+pending share (vs. 1AM's larger no-anchor+window-empty share) is consistent with 9AM giving the SAME per-attempt engulf/retest mechanics more total window-time to reach either a confirmed or a still-pending state, rather than exhausting before ever engulfing |

These are documented **associations between a structural difference and a rejection-category
distribution**, not an attributed cause. Multiple structural differences co-occur (span AND
architecture change together between the two models; there is no natural pair of models in this
dataset that isolates one from the other), so no single-variable causal claim is licensed by this
data without the counterfactual re-simulation this phase is explicitly scoped to avoid.

## What is common to both models, despite the gap

Both models reconcile to `confirmed + sum(rejections) == triggers` exactly (Deliverable B). Both
models' Stage-6 attrition is 100% `_rr_floor_cut` with zero `_dedup`/`_kill_zone_cut` (Deliverable
C). Both models' confirmation-rate gap is stable across all four periods (Deliverable D) -- it is
not an artifact of any one regime. The gap is therefore a persistent, structural feature of how
the two models are configured, observed consistently across instruments and periods, not a
transient data artifact -- while remaining, by design, an association rather than an established
causal claim.
