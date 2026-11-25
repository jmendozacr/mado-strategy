# Deliverable C — Stage-6 Candidate Attrition Audit

Reproduce: same command as Deliverable B. Full rule citations (available vs. active vs. applied vs.
responsible) are in `extract/stage6_attrition_diagnostics.py`'s module docstring and
`docs/67-phase9-design-and-pre-registration.md` section 1.

## The four-way distinction, applied to every `build_stage6_population` rule

| Rule | Available? | Active for D3/C2? | Applied? | Responsible for any D3/C2 rejection? |
|---|---|---|---|---|
| `excluded_no_crt_range` (fvg_fill signals) | Yes | No -- D3/C2 never produces `fvg_fill` | N/A | **Never** |
| `excluded_unaligned` | Yes | No -- `aligned` is always literally `"aligned"` | N/A | **Never** |
| `excluded_never_confirmed` (INVALIDATED) | Yes | No -- `aligned_signals` only ever contains CONFIRMED signals | N/A | **Never** |
| `excluded_no_key_level` | Yes | No -- `CausalTrigger.credited_level` is never `None` by construction | N/A | **Never** |
| `excluded_confirmed_no_retest` (PENDING, no retest) | Yes | No -- CONFIRMED always has `retest_index` set | N/A | **Never** |
| `_dedup` (`excluded_duplicate`) | Yes | Yes (always runs) | Yes | **Never, empirically** (0 across all 3 pairs, both models) |
| `_kill_zone_cut` (`excluded_kill_zone`) | Yes | **No** -- `SYMBOL_CONFIG[...].kill_zone_gated == False` for all 3 pairs | N/A | **Never** |
| `_rr_floor_cut` (`excluded_rr_floor`, `min_risk_reward=2.0`) | Yes | **Yes** | Yes | **The ONLY mechanism, 100% of the attrition** |

Verified empirically, not just predicted: `population_cuts_check["all_zero"] == True` for all three
pairs (EURUSD, USDCAD, AUDUSD), and `stage6_removed_by_model` shows `duplicate: 0` and
`kill_zone: 0` for both models, every pair.

## The Stage-6 gap, fully attributed

| | 1AM | 9AM |
|---|---|---|
| Model-1 confirmed | 1805 | 3311 |
| Candidates built | 718 | 1806 |
| **Gap (confirmed − candidates)** | **1087** | **1505** |
| ...of which `_dedup` | 0 | 0 |
| ...of which `_kill_zone_cut` | 0 | 0 |
| ...of which `_rr_floor_cut` | **1087 (100%)** | **1505 (100%)** |

**Every single confirmed Model-1 signal that fails to become a Stage-6 candidate, for both models,
across all three pairs, fails SPECIFICALLY because its planned reward-to-risk ratio is below 2.0.**
No deduplication, no kill-zone gating, plays any role at all in this pipeline's actual data.

## Terminal-reason discipline

Because `_dedup` and `_kill_zone_cut` never remove anything here, every removed candidate's
terminal reason is unambiguous: `_rr_floor_cut`, evaluated last in the fixed sequence
(`_population_cuts` -> `_build_candidate` -> `_dedup` -> `_kill_zone_cut` -> `_rr_floor_cut`). No
candidate is ever double-counted against an earlier, non-firing rule, and no candidate removed at
an earlier stage (none exist here) ever reaches the RR-floor check at all.

## Equivalence (requirement 20/7)

`build_stage6_population_instrumented`'s own final `candidates` list is identical, signal-id for
signal-id, to calling the real `build_stage6_population` directly -- verified by
`tests/test_stage6_attrition_diagnostics.py::test_instrumented_population_matches_the_real_function_exactly`.
