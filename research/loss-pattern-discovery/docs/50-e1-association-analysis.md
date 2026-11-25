# Deliverable E — E1 Association Analysis (H1/H2/H3)

Reproduce: `uv run --project detector python
research/loss-pattern-discovery/stats/e1_timing_association.py`. All models reuse the SAME
`is_confirmed_stop`/`compute_trade_timing`-derived E1 flag, the SAME primary population (2043
evaluable executed trades), and the SAME direct-standardization/common-support/block-bootstrap
machinery Phase 5 already established and pre-registered (`N_QUINTILES=5`,
`MIN_COMMON_SUPPORT_PER_MODEL=20`, `MAX_UNSUPPORTED_SHARE=0.30`, `RELEVANT_DIFFERENCE_PP=0.05`,
`PRIMARY_CI_LEVEL=0.95`) -- unmodified, imported directly, never re-tuned for this phase.

## Model 0 — Baseline (unadjusted E1)

| | 1AM | 9AM | Diff | 95% CI |
|---|---|---|---|---|
| Rate | 11.63% | 6.25% | **+5.38pp** | [2.52, 8.26] |

Reproduces Phase 6's own E1-alone result exactly (`docs/38`).

## Model 1 — Risk-standardized (risk_atr, reusing Phase 5's method)

Common support: **0% unsupported, both models** (all 5 quintiles have 89-320 trades per model).

| | 1AM (standardized) | 9AM (standardized) | Diff | 95% CI |
|---|---|---|---|---|
| Rate | 11.75% | 6.12% | +5.63pp | [2.78, 8.59] |

Essentially unchanged from Model 0 (if anything very slightly larger) -- `risk_atr` does not
explain the E1 gap, consistent with Phase 5/6's own prior findings on the combined E0+E1 endpoint.

## Model 2 — Timing-standardized: TWO separate runs, NOT equivalent (brief section 9)

### 2a. Absolute minutes (`confirmation_elapsed_minutes`)

**Common support fails**: `unsupported_share_9am = 50.3%` -- two of the five pooled quintiles
(roughly the top half of the elapsed-minutes range, 135-240 minutes) contain **zero 1AM
observations** (1AM's window caps at 120 minutes and structurally cannot populate them). This is
exactly the common-support problem the brief's section 9 anticipated, now empirically confirmed, not
assumed: more than half of 9AM's population has no comparable 1AM counterpart in absolute-minute
terms.

| | 1AM (standardized, SUPPORTED strata only) | 9AM (standardized, SUPPORTED strata only) | Diff | 95% CI |
|---|---|---|---|---|
| Rate | 9.92% | 9.55% | +0.38pp | [-3.03, 3.62] |

**This number must NOT be read as "timing explains the gap."** It is computed over less than half
of 9AM's population (the unsupported strata are dropped entirely from standardization, per the
pre-registered method) -- a restricted, non-representative comparison, exactly the situation
`docs/37`'s own common-support discipline exists to flag rather than silently extrapolate past.

### 2b. Relative position (`confirmation_relative_position`) -- the valid comparison

**Common support holds fully**: 0% unsupported, both models, every quintile populated by both
(e.g. stratum 0: 9AM=344/1AM=150; stratum 4: 9AM=231/1AM=116).

| | 1AM (standardized) | 9AM (standardized) | Diff | 95% CI |
|---|---|---|---|---|
| Rate | 11.72% | 6.30% | **+5.42pp** | [2.66, 8.32] |

**Virtually identical to Model 0's unadjusted +5.38pp.** Standardizing on WHERE within its own
window each model's confirmation fell -- the one timing variable that is actually comparable
between a 120-minute and a 240-minute window -- leaves the gap completely intact.

## Model 3 — Timing-standardized gap, one-way by instrument and by period (absolute minutes)

Every subgroup (3 instruments + 4 periods) shows the SAME ~47-54% `unsupported_share_9am` --
confirming the common-support failure is a structural property of the absolute-minutes variable
itself, not an artifact of a particular subgroup or period. Point estimates on the (already
untrustworthy) supported subset swing from +5.6pp (EURUSD) to -3.3pp (AUDUSD) and from +3.4pp to
-3.7pp across periods, every single one with a 95% CI crossing zero. **None of this is
interpretable as evidence of anything**, for the same reason as 2a -- it is reported to show the
insufficiency is pervasive, not cherry-picked, never as a finding about instrument/period
heterogeneity in timing's explanatory power.

## Synthesis: H1, H2, H3

- **H1** (position within window associates with E1): not directly tested as a within-model
  regression coefficient here (would require a model-specific analysis this phase did not run);
  the standardization above tests the RELATED question of whether the POPULATION gap changes when
  timing composition is equalized -- it does not.
- **H2** (composition difference explains the E1 gap): NOT supported. The one adjustment with full
  common support (relative position) leaves the gap at +5.42pp, essentially identical to +5.38pp
  unadjusted. The absolute-minutes adjustment cannot even be evaluated for H2 -- it fails common
  support outright (section 9's concern, confirmed).
- **H3** (a residual association persists even among temporally comparable confirmations): **this
  is what the data show.** Among confirmations at a comparable RELATIVE position within their own
  window, 1AM's E1 rate remains ~5.4pp higher than 9AM's, CI excluding zero.
