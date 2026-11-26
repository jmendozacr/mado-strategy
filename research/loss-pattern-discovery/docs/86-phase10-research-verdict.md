# Deliverable G — Phase 10 Research Verdict

Criteria fixed in `docs/79-phase10-design-and-pre-registration.md` section 5, BEFORE running
Deliverable E's first real-data computation. Applied mechanically below -- no criterion was
adjusted after seeing the numbers.

## Applying the criteria

| Criterion | Holds? | Evidence |
|---|---|---|
| `INSUFFICIENT_PATH_RECONSTRUCTION` | No | equivalence tests pass; coverage is 100.0% (5116/5116 confirmed, 2043/2043 primary population); the contrast is non-degenerate in both models |
| `INSUFFICIENT_STATISTICAL_EVIDENCE` | No | both models' smaller subgroup exceeds 20 events (1AM: 255; 9AM: 626) |
| `CONFIRMATION_PATH_ASSOCIATION_FOUND` | No | fails on two independent grounds: 1AM's CI includes zero, AND neither model's point difference (1AM +1.11pp, 9AM +3.39pp) exceeds the 5pp relevance bar |
| `MODEL_SPECIFIC_ASSOCIATION` | **Yes** | sufficient support in both models; 9AM's 95% CI excludes zero ([+0.83pp, +5.97pp]), 1AM's does not ([-4.19pp, +6.36pp]), despite both pointing the same direction |
| `NO_ROBUST_CONFIRMATION_PATH_ASSOCIATION` | No | requires BOTH CIs to include zero -- 9AM's does not |
| `INCONCLUSIVE` | No | the pattern resolves cleanly into `MODEL_SPECIFIC_ASSOCIATION` |

## Verdict: `MODEL_SPECIFIC_ASSOCIATION`

**Signals that confirm Model-1 directly (zero internal invalidations) show a higher E1 rate than
signals that needed at least one internal restart -- but this association is only
statistically distinguishable from zero within 9AM, not within 1AM**, even though 1AM's point
estimate points the same direction and every per-instrument breakdown (both models, all three
pairs) shows the same sign. This is read as a genuine but model-specific signal, not as evidence
that 1AM shows "no effect" -- 1AM's own confidence interval is wide enough to be consistent with
an effect of similar magnitude to 9AM's, just not distinguishable from zero at this sample size
(255 events in the smaller subgroup).

## What this verdict does NOT claim

- It does NOT claim more internal invalidations CAUSE a lower E1 rate, or that direct confirmation
  CAUSES a higher one -- `internal_invalidation_count` is a pre-order structural fact; no causal
  mechanism linking it to post-order stop-loss timing is proposed or tested.
- It does NOT claim this is operable, tradable, or validated out-of-sample.
- It does NOT revise, or depend on revising, Phase 5-9's own +5.38pp 1AM/9AM E1 gap -- Deliverable
  E's own standardization check (H3) shows that gap is essentially unchanged (+5.11pp) when
  accounted for by this variable, so the two findings coexist rather than one explaining the
  other.
- It does NOT claim AUDUSD is now free of heterogeneity in general -- only that THIS SPECIFIC
  contrast does not reproduce AUDUSD-specific heterogeneity found in other analyses.

## Honest characterization of the effect size

9AM's point difference is +3.39pp (8.15% for zero-invalidation vs. 4.76% for >=1 invalidation) --
a RELATIVE difference of roughly 1.7x between the two subgroups, even though the ABSOLUTE
difference is modest. 1AM's point difference (+1.11pp, 12.09% vs. 10.98%) is smaller in both
absolute and relative terms, on a higher baseline. **Neither model's point estimate clears Phase
5's own 5pp relevance bar** -- 9AM's association is statistically distinguishable from zero
(the CI excludes zero) while still being, in absolute magnitude, SMALLER than what this lab has
previously treated as a minimum economically meaningful difference. This verdict is reported as a
statistically real but small-magnitude, model-specific association -- not a large or obviously
actionable effect, and this is stated plainly rather than rounded up.
