# Deliverable C — Matched Control Comparison (results)

Design: `control/sampling.py` (see `docs/07-...`'s Unit C section). 1262 controls, 1:1 matched to
every eligible SL event (instrument/session/direction/risk inherited from the match; timestamp drawn
from the same stratum, ATR-nearest, excluding a 4h buffer around any real SL event). Comparison uses
a **paired** block bootstrap (`stats/bootstrap.py::block_bootstrap_paired_diff_ci`), reporting
`median(SL) - median(control)` (or `P(SL) - P(control)`), 90% CI.

## Continuation probability: SL vs. matched control

| Horizon | P(continuation \| SL) | Difference (SL - control) | 90% CI |
|---|---|---|---|
| 1h | 55.3% | +1.1 pp | [-2.0, +4.3] pp |
| 4h | 55.6% | -0.4 pp | [-3.6, +2.8] pp |
| 1d | 55.7% | -0.4 pp | [-3.6, +2.8] pp |
| 3d | 55.9% | -0.3 pp | [-3.5, +2.9] pp |

**The continuation-vs-reversal split after a real stop-loss is statistically indistinguishable from
the matched control baseline at every horizon** — every CI straddles zero, and the point differences
are tiny (within ±1.1 percentage points). The ~55%/44% continuation/reversal split described in
Deliverable B is not special to post-SL moments in this dataset; it appears to characterize the
matched-control "ordinary moment" baseline about as well. This directly matches the user's own
worked example of an uninteresting result ("65% vs 63% puede ser demasiado pequeña"): here it is
closer to 55% vs. 55%.

## Adverse excursion magnitude (MAE, R units): SL vs. matched control

| Horizon | MAE median \| SL | Difference (SL - control) | 90% CI |
|---|---|---|---|
| 1h | 0.49R | +0.029R | [-0.017, +0.075] |
| 4h | 0.91R | -0.074R | [-0.169, +0.018] |
| 1d | 2.34R | **-0.234R** | **[-0.407, -0.035]** |
| 3d | 3.63R | -0.335R | [-0.704, +0.062] |

Three of the four horizons are not statistically distinguishable from zero. The 1-day horizon's CI
excludes zero, with real SL events showing a SMALLER median adverse excursion than matched controls
-- the opposite sign from a naive "a stop predicts more pain" hypothesis. **This is treated as
inconclusive, not as a finding**, for a stated reason: this phase ran 4 horizons x 2 metrics = 8
comparisons at a 90% CI (a ~10% false-positive rate each); getting roughly one borderline-significant
result out of 8 is within what pure noise would produce, and no correction for multiple comparisons
was applied here (none was pre-registered). See `docs/11-research-findings.md` for how this is
classified.

## What this comparison does and does not show

- It shows whether the DIRECTIONAL BEHAVIOR after a real SL differs from an ordinary, matched moment
  — for continuation/reversal, it does not, within this dataset's precision.
- It does NOT evaluate any specific tradeable rule, cost structure, or entry timing — see Phase 1 and
  this phase's own scope limits (no strategy design this round).
- The control's own limitations (L8/L9 in `docs/06-...`) mean this is a comparison against "a
  matched ordinary moment with the same risk/direction," not against every possible alternative
  baseline definition.
