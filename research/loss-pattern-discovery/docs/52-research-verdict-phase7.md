# Deliverable G — Research Verdict (Phase 7)

## Process note on pre-registration (honesty over tidiness)

Phase 5 and Phase 6 each had a dedicated pre-registration document written and committed BEFORE
their main analysis ran. This phase's Unit A work (`docs/47`) pre-registered the window
reconstruction and discovered/corrected the 9AM window-duration error, but this phase did **not**
write a SEPARATE document fixing the exact Phase-7-specific verdict-category numeric mapping before
running Deliverable E's Model 2/3. The underlying numeric thresholds themselves were NOT invented
after the fact -- every one (`RELEVANT_DIFFERENCE_PP=0.05`, `PRIMARY_CI_LEVEL=0.95`,
`MAX_UNSUPPORTED_SHARE=0.30`) is imported unmodified from `stats.early_stop_hypothesis`, fixed since
Phase 5, never touched this phase. What follows maps those pre-existing, carried-over thresholds
onto this phase's five named verdict categories -- mechanically, not tuned to the result -- but the
mapping itself was written after seeing the numbers, which is a real, disclosed process gap, not a
tidied-up retrospective pre-registration.

## Verdict: `E1_DIFFERENCE_PERSISTS_AFTER_TIMING_ADJUSTMENT`

| Candidate verdict | Criterion (pre-existing thresholds) | Observed | Applies? |
|---|---|---|---|
| `INSUFFICIENT_TEMPORAL_OVERLAP` | the chosen stratifying variable's `unsupported_share` for either model > 30% | **Absolute minutes: 50.3% for 9AM -- YES.** Relative position: 0% for both -- NO. | Applies to the absolute-minutes variable specifically, not to the analysis as a whole (see below) |
| `TIMING_ASSOCIATION_EXPLAINS_MUCH_OF_GAP` | on a variable with adequate support, standardized CI includes 0 or \|gap\| < 5pp | Relative position: +5.42pp, CI [2.66, 8.32] -- excludes 0, >= 5pp | No |
| `TIMING_ASSOCIATION_PARTIALLY_REDUCES_GAP` | standardized \|gap\| shrinks materially (here: by >=2pp) but stays >=5pp or CI still excludes 0 | +5.42pp vs. +5.38pp unadjusted -- no shrinkage at all | No |
| **`E1_DIFFERENCE_PERSISTS_AFTER_TIMING_ADJUSTMENT`** | on the variable with adequate support, standardized gap stays relevant (>=5pp) AND CI excludes 0, materially unchanged from unadjusted | **Exactly this: +5.42pp, CI [2.66, 8.32], vs. +5.38pp unadjusted** | **Yes** |
| `INCONCLUSIVE` | none of the above cleanly applies | -- | No |

**Why the verdict is not simply `INSUFFICIENT_TEMPORAL_OVERLAP`**: that category correctly
describes the ABSOLUTE-minutes stratification (and is reported prominently as its own finding --
section 9's concern, empirically confirmed, not a limitation to bury). But this phase ran a SECOND,
equally principled stratifying variable -- relative position -- precisely because the brief itself
(section 9) anticipated that absolute minutes would not be comparable across differently-sized
windows. That second variable has full common support and gives a clear, unambiguous answer. Using
`INSUFFICIENT_TEMPORAL_OVERLAP` as the OVERALL verdict would discard the one valid comparison this
phase actually has, in favor of reporting only the one that was expected to fail.

## Justification, with numbers

1. Model 0 (baseline E1): +5.38pp, CI [2.52, 8.26] -- relevant and robust, reproducing Phase 6
   exactly.
2. Model 1 (risk_atr-standardized): +5.63pp, CI [2.78, 8.59] -- unchanged, full common support.
   H2 (risk explains it) not supported, consistent with Phase 5/6.
3. Model 2a (absolute-minutes-standardized): common support fails (50.3% of 9AM unsupported) --
   not usable for H2. Reported as its own finding (`docs/50`), not as evidence either way.
4. Model 2b (relative-position-standardized, the valid test): +5.42pp, CI [2.66, 8.32] -- full
   common support, virtually identical to unadjusted. H2 (timing composition explains it) not
   supported.
5. Model 3 confirms the Model 2a common-support failure is structural (pervasive across every
   instrument and period subgroup), not an artifact of one subgroup.

## What this verdict does and does not claim

**Does claim**: among trades confirmed at a comparable RELATIVE position within their own model's
confirmation window, 1AM still shows a materially and statistically higher E1 (next-bar stop) rate
than 9AM. This is H3 (a residual association, observational) -- consistent with every prior phase's
finding that this 1AM/9AM gap survives every adjustment attempted so far (risk_atr in Phases 5/6,
now confirmation timing in Phase 7).

**Does NOT claim**:
- That the 9AM window-widening decision CAUSES the gap, or that reverting it would change anything
  -- no contrafactual re-simulation was run (brief section 10's explicit boundary).
- That absolute window duration is irrelevant -- it clearly shapes WHICH confirmations exist at all
  (Deliverable F's selection-bias caveat: a wider window can admit candidates a narrower one would
  never even confirm), a question this phase's executed-trades-only population cannot answer.
- Any tradable edge. 2015-2026 remains previously-examined, not genuine out-of-sample data.
- That `origin_model` causes anything -- unchanged from every prior phase's own caution.
