# Deliverable E — E1 Association Analysis

Reproduce: `uv run --project detector python research/loss-pattern-discovery/stats/confirmation_path_e1_association.py`.
Primary population: executed, evaluable (not `OPEN`) -- identical to Phase 5-9's own
`build_primary_population`, restricted further to signals with a reconstructed confirmation path.
Coverage: **100.0%** (2043 of 2043 primary-population events; zero missing).

## Baseline reproduction (step 9, before the contrast)

Re-deriving E1 as `CONFIRMED_STOP AND duration_bars == 1` (Phase 6's `TimingCategory.NEXT_BAR_SL`,
unchanged) over this phase's own covered population reproduces the established numbers exactly --
verified by an internal consistency check below, not merely assumed: summing each model's two
subgroup E1 counts gives 1AM `44 + 28 = 72` and 9AM `51 + 38 = 89`, matching 72/619 and 89/1424
exactly.

## H1/H2 — Primary contrast, WITHIN each model (`internal_invalidation_count == 0` vs. `>= 1`)

| Model | Group | n | E1 rate | Diff (zero − one-or-more) | 95% CI | Excludes zero? |
|---|---|---|---|---|---|---|
| 1AM | zero invalidation | 364 | 12.09% | +1.11pp | [-4.19pp, +6.36pp] | **No** |
| 1AM | >=1 invalidation | 255 | 10.98% | -- | -- | -- |
| 9AM | zero invalidation | 626 | 8.15% | +3.39pp | [+0.83pp, +5.97pp] | **Yes** |
| 9AM | >=1 invalidation | 798 | 4.76% | -- | -- | -- |

Both models have sufficient support (both subgroups >= 20 events, the pre-registered minimum).
**9AM shows a statistically distinguishable association: signals that confirm directly (zero
invalidations) have a HIGHER E1 rate than signals that needed at least one internal restart.**
1AM shows the SAME DIRECTION point estimate, but its 95% CI includes zero -- not independently
distinguishable from no association at this sample size.

## Per-instrument consistency check (never a causal claim, descriptive only)

| Instrument | 1AM diff | 1AM CI | 9AM diff | 9AM CI |
|---|---|---|---|---|
| EURUSD | +3.03pp | [-8.90pp, +15.23pp] | +2.86pp | [-1.35pp, +7.06pp] |
| USDCAD | +0.99pp | [-8.83pp, +11.00pp] | +4.13pp | [-0.24pp, +8.85pp] |
| AUDUSD | +1.15pp | [-5.33pp, +6.98pp] | +3.17pp | [-1.33pp, +7.77pp] |

**Every one of the 6 model x instrument combinations shows the SAME direction** (zero-invalidation
rate > one-or-more-invalidation rate) -- no instrument reverses the sign, AUDUSD included (its
own heterogeneity in earlier phases is not reproduced here). None of the individual
instrument-level CIs excludes zero on its own -- expected at these smaller per-instrument sample
sizes; the pooled 9AM result (n=1424) is where the association becomes statistically
distinguishable, consistent with a real but modest effect that only separates from noise with
enough pooled data.

## H3 — Descriptive standardization of the 1AM/9AM E1 gap

Pooled weights (zero-invalidation: 48.46%, >=1 invalidation: 51.54%) applied identically to both
models' E1 rates within each stratum:

| | Unadjusted | Standardized by path complexity |
|---|---|---|
| 1AM rate | 11.63% | 11.52% |
| 9AM rate | 6.25% | 6.40% |
| **Gap (1AM - 9AM)** | **+5.38pp** | **+5.11pp** |
| 95% CI | [+2.52pp, +8.26pp] | [+2.23pp, +8.10pp] |

**Standardizing the 1AM/9AM gap by confirmation-path complexity leaves it essentially unchanged**
(+5.11pp vs. +5.38pp unadjusted, overlapping CIs) -- this structural variable does not explain the
persistent model gap, joining `risk_atr` (Phase 5/6) and confirmation-window timing (Phase 7) as
tested-and-ruled-out candidates for THAT specific gap. This is a DESCRIPTIVE comparison, never a
causal decomposition of the +5.38pp figure.

## Composition at the primary-population stage (descriptive, not causal)

| | Confirmed population (Deliverable D) | Executed + evaluable population (this deliverable) |
|---|---|---|
| 1AM zero-invalidation share | 73.0% | 58.8% |
| 9AM zero-invalidation share | 56.1% | 44.0% |

Both models show a LOWER zero-invalidation share among executed+evaluable trades than among all
confirmed signals -- Stage 6/fill filtering (Phase 9: 100% attributable to the RR floor) removes a
disproportionate share of zero-invalidation signals relative to >=1-invalidation ones. This is
reported as a composition fact for Unit F; it is not interpreted causally, and no claim is made
about WHY the RR floor interacts with path complexity this way (that mechanism is out of this
phase's scope and would require the Phase 11 RR investigation, Deliverable H, to examine properly).
