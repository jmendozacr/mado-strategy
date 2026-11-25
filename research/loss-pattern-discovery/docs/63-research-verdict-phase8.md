# Deliverable G — Research Verdict (Phase 8)

Two verdicts, per the brief's own instruction (integrity + selection describe different things).
Criteria fixed in `docs/57` section 5, before inspecting the reconstructed numbers.

## Integrity verdict: `FUNNEL_RECONSTRUCTED_AND_RECONCILED`

| Check | Result |
|---|---|
| Diagnostic adapter cross-check (`verify_against_pooled_counts`) | `matches: true`, all 3 pairs |
| Sweep/trigger invariants (`verify_sweep_and_trigger_invariants`) | hold exactly on real data (tested) |
| Baseline (620/619/1 for 1AM, 1427/1424/3 for 9AM) | **matches exactly** |
| Total executed = 2047, evaluable = 2043 | **matches exactly** |
| Every `filled` cell matches its ledger-executed count | `all_filled_match_ledger: true` |
| Duplicate `event_id`s | **0 found** |
| Unresolvable model/instrument identifiers | **0 found** |
| E1 endpoint (72/619, 89/1424, +5.38pp) | **reproduces Phases 6/7 exactly** |
| `fully_reconciled` (the report's own composite flag) | **`true`** |

Every criterion for `FUNNEL_RECONSTRUCTED_AND_RECONCILED` (docs/57) is met with zero unexplained
discrepancy. (`PARTIAL_FUNNEL_RECONSTRUCTION` would have applied if `build_stage6_population`'s own
internal exclusion-reason breakdown were required and unavailable -- it is not required by this
phase's own scope, docs/57 section 3, so its absence does not downgrade this verdict.)

## Selection verdict: `MATERIAL_EXECUTION_SELECTION_DIFFERENCE`

| Identifiable rate | Gap | Clears the 10pp bar? |
|---|---|---|
| P(confirmed \| trigger with Key Level) | 9AM ~2.3-2.5x 1AM (16% vs. 37-40%, >20pp) | **Yes, by a wide margin, all 3 pairs** |
| Filled trades per window considered | +11.38pp (EURUSD), +9.19pp (USDCAD), +5.71pp (AUDUSD) | EURUSD/USDCAD yes; AUDUSD close (65% relative uplift) |
| `planned_risk_atr_at_order_placement` (filled vs. never-filled) | consistent directional gap, all 6 cells, not tested against the 10pp bar (a distributional, not rate, comparison) | n/a -- reported as a consistent pattern |

The confirmation-rate gap alone, over 20 percentage points and consistent across all three pairs,
unambiguously satisfies `MATERIAL_EXECUTION_SELECTION_DIFFERENCE`'s criterion on its own.

## What these two verdicts, together, say -- and do not say

The funnel is trustworthy (every count reconciles) AND the two models select materially different
populations before a single trade executes (confirmation rate, not fill rate, is where they
diverge most). **This is not converted into a causal claim about E1** (docs/62): Phase 8 does not
claim the confirmation-rate difference explains the E1 gap, only that it exists, is large, and is a
plausible candidate the research line has not yet tested directly (Phase 9 recommendation,
`docs/64`).
