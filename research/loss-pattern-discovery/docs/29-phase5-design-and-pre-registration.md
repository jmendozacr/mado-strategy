# Phase 5 — Design and Pre-Registration: 1AM vs. 9AM Failure Mechanism

Written and frozen before any Phase-5 script was run against real data.

## 1. Endpoint definition, verified against the pipeline (not assumed)

`entry_timestamp_broker`/`exit_timestamp_broker` are M15 bar OPEN timestamps on the same grid as the
M15 series (re-confirmed, not re-derived: Phase 1-4 established this repeatedly, most directly via
`detector/backtest/simulate.py::_fill_candle_immediate_loss`, the exact engine path that produces
`duration_bars == 0` same-bar fill-and-stop trades -- 92 of Phase 4's 1262 confirmed stops are this
case). There is no finer intrabar timestamp available anywhere in this pipeline to "preserve" beyond
the M15 bar grid.

**Primary endpoint, precisely**: `same_or_next_bar = duration_bars <= 1`, where
`duration_bars = exit_index - entry_index` (bar INDEX difference on the instrument's own M15 series,
via `bisect_left` -- exact match, never approximate wall-clock time, so a weekend gap between entry
and exit never inflates or deflates this count). This distinguishes same-bar (`duration_bars == 0`),
next-bar (`== 1`), and later (`>= 2`) exactly, per the brief's own requirement (section 13, test 4) --
implemented once in `common/trade_timing.py`, reused everywhere in this phase instead of a second,
possibly-inconsistent timestamp-diff implementation.

## 2. Two separate populations (never mixed)

- **Primary population**: every EVALUABLE executed trade -- all 2047 minus the 4 `OPEN_CENSORED`
  (2043 trades: 778 win, 1265 loss). `AMBIGUOUS_STOP` losses (3) are KEPT in this population (they
  did execute and resolve, with a known duration) but counted as NOT a confirmed stop for H1's
  numerator -- conservative, never inflates the stop rate, and documented as a choice, not hidden.
- **Secondary population**: the 1262 `CONFIRMED_STOP`/`STOP_AFTER_PARTIAL` losses only, used for H3
  (the already-computed Phase 2/3 MAE/recovery figures) and for Deliverable D (the duration-vs-
  integrity artifact check), exactly as Phase 4 scoped it.

## 3. Hypotheses, registered

- **H1 (primary)**: `P(confirmed_stop AND same_or_next_bar | primary population)` differs between
  1AM and 9AM. Evaluated unadjusted, then risk_atr-standardized, then checked for common-support
  validity. 95% CI, block bootstrap (block = instrument x ISO week, reusing `stats.bootstrap`'s
  existing convention).
- **H2**: the 1AM/9AM gap in H1 (and in time-to-SL) shrinks substantially once standardized by
  `risk_atr`. `risk_atr`, instrument, and period are candidate explanatory variables, NOT
  pre-validated predictors -- none were chosen by checking which produces the best-looking result;
  all four were named in the user's own brief before this phase's first computation.
- **H3 (secondary, limited)**: the Phase 2/3 MAE-post-SL/recovery-to-entry gaps are partially
  explained by risk_atr. Evaluated only if H1/H2's common-support check passes; reuses
  `behavior/post_stop_metrics.py` and `behavior/recovery_analysis.py` completely unmodified (same
  horizons, same 0.25R/5pp thresholds) -- this phase only re-stratifies their EXISTING per-event
  outputs by a risk_atr quintile, never recomputes them with new parameters.

## 4. risk_atr standardization, pre-declared

- **Strata**: quintiles (5 bins) of `risk_atr`, cut points computed on the POOLED (1AM+9AM combined)
  primary-population distribution -- fixed once, before any by-model breakdown is inspected.
- **Common support**: a stratum has sufficient common support if it contains **>=20 trades from
  EACH model**. Strata failing this are reported (count, which model is underrepresented) and
  EXCLUDED from the standardized adjustment, with the excluded population share stated explicitly --
  never silently dropped.
- **Standardization method**: direct standardization (Mantel-Haenszel-style weighting, not
  propensity-score matching or any ML model) -- for each model, the within-stratum confirmed-
  same/next-bar proportion is reweighted by the POOLED stratum size, giving each model's
  "counterfactual rate if it had the pooled risk_atr distribution." Chosen for transparency and
  because the brief explicitly permits "estandarización o emparejamiento" and forbids complex ML for
  this step.
- **Bootstrap**: blocks (instrument x ISO week) resampled independently within each model (standard
  block bootstrap preserving each model's own sample size), stratum weights held FIXED at their
  observed pooled values per resample (not themselves re-estimated) -- a documented simplification,
  not a hidden one.

## 5. Sensitivity (one-way only, per this lab's existing convention)

The adjusted H1 gap is additionally checked WITHIN each instrument and WITHIN each of the 4
predeclared period buckets, separately (never a joint risk_atr x instrument x period grid, which
would fragment the ~2043-trade population into cells far below any useful size).

## 6. Verdict criteria, pre-declared (section 14.F)

| Verdict | Criterion |
|---|---|
| `NO_ROBUST_DIFFERENCE` | The UNADJUSTED H1 gap's 95% CI includes 0, or `\|gap\| < 5pp` (reusing this lab's existing relevance bar) -- there is nothing to explain in the first place. |
| `INSUFFICIENT_COMMON_SUPPORT` | More than 30% of EITHER model's primary-population mass falls in a risk_atr stratum lacking common support -- the adjustment is not reliable regardless of its numeric result. |
| `MOSTLY_EXPLAINED_BY_RISK_GEOMETRY` | The unadjusted gap is relevant (CI excludes 0, `\|gap\| >= 5pp`), common support holds, AND the standardized gap's CI includes 0 or `\|gap\| < 5pp`. |
| `RESIDUAL_MODEL_ASSOCIATION` | The unadjusted gap is relevant, common support holds, AND the standardized gap ALSO has CI excluding 0 with `\|gap\| >= 5pp`. |
| `INCONCLUSIVE` | None of the above cleanly applies (e.g. conflicting instrument-level sensitivity, estimation failure, or a stratum/population too small to compute a stable CI). |

No criterion above was adjusted after seeing a Phase-5 result. Per section 11 of the brief: even
`RESIDUAL_MODEL_ASSOCIATION` is reported as an unexplained ASSOCIATION, never as proof that the
model label causes the difference -- `origin_model` is not randomly assigned, and candidate
explanatory variables (especially `risk_atr`) may be mediators of the model's own mechanism rather
than pure confounders; this document does not assume which.
