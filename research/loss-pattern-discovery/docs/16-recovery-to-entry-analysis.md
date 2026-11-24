# Deliverable D — Recovery-to-Entry Analysis

H1: post-SL recovery to the original entry differs in frequency from comparable controlled market
moments. H0: no relevant difference. Design pre-registered in
`behavior/recovery_analysis.py`'s module docstring (written and frozen before this real-data run).

## Primary endpoint: P(recovery within 24 calendar hours), 95% CI

| | Confirmed SL | Matched control | Difference (SL - control) | 95% CI | Relevant? (CI excludes 0 AND \|diff\| >= 5pp) |
|---|---|---|---|---|---|
| P(recovery_1d) | 75.3% | ~73.6%* | **+1.66pp** | **[-1.67pp, +5.06pp]** | **No** |

\* implied by the difference; the control's own raw proportion is not separately tabulated because
the comparison is paired (block-bootstrapped on the 1262 matched pairs, block = instrument x ISO week).

**The 95% CI crosses zero, and the point estimate (1.66pp) is below the pre-declared 5-point-relevance
bar regardless.** `relevant_difference = False`. **H0 is not rejected** for the primary, pre-registered
endpoint. This is reported as a negative result, not reframed: recovery-to-entry at the 24h mark does
not show a difference from a comparable ordinary market moment large or certain enough to call
"different," in this dataset, at this precision.

## Secondary, descriptive-only metrics (NOT a search for the best horizon)

| Horizon | SL - control (90% CI, this lab's usual level) | Excludes 0? |
|---|---|---|
| 1h | +5.47pp [+2.90, +8.00] | Yes |
| 4h | +5.39pp [+2.25, +8.45] | Yes |
| 1d (primary, shown above at 95%) | +1.66pp [-1.17, +4.58] (90% CI) | No |
| 3d | +1.11pp [-1.04, +3.47] | No |

Short-horizon (1h/4h) recovery is modestly elevated versus the matched control (CI excludes zero at
90%), but that gap narrows and loses significance by the pre-registered 1d/3d endpoints. This is
reported as a descriptive observation, not as grounds to move the primary endpoint to 1h/4h after
seeing this -- the 1d endpoint was fixed before this run, and stays the basis for the verdict.

**Cumulative incidence of recovery** (same population, not independent across horizons -- each later
horizon includes the earlier ones' recoveries): 1h 22.3% -> 4h 47.2% -> 1d 75.3% -> 3d 85.5%.

**Time to first recovery** (once it happens; n=1079 recovered by 3d): median **3.25h**, IQR
[1.0h, 10.25h], 90th percentile 32h.

**Target distance in ATR units** (how far the real entry was from the executed exit, relative to
volatility at the event): median **1.58 ATR**, IQR [1.25, 2.29] -- the level being "recovered to" is
consistently a bit more than one ATR away, not a trivially close level.

**Non-recovering cases**: 183 of 1262 eligible events (14.5%) genuinely never recovered within the 3d
window (fully observed, not censored). 2 events (0.16%) were censored by 3d (dataset ran out) -- too
few to need anything beyond excluding them from the proportion (`_recovery_flag` returns `None` for a
censored non-recovery, per the Phase-3 fix); **a Kaplan-Meier or other censoring-adjusted estimator
was not used because <0.2% censoring cannot materially bias a simple complete-case proportion** at
this sample size -- a simple estimator is adequate and that judgment is recorded here explicitly, per
the brief's own allowance.

**Weekend/gap effect**: recovery by 3d is lower when a weekend gap was spanned (77.5%) than when it
wasn't (87.2%) -- plausible (events near a weekend close have less post-event time before the window
closes relative to calendar hours elapsed) but not decomposed further this phase. Unexpected-gap
exposure shows no meaningful effect (85.7% vs. 85.4%), consistent with such gaps being rare.

**By instrument** (1d, point estimates only, no CI computed for this one-way cut): EURUSD 72.0%
(n=397), USDCAD 75.9% (n=423), AUDUSD 77.6% (n=442) -- a few points apart, not tested for significance
here (would require its own bootstrap, deliberately not run to avoid "búsqueda de subgrupos").

**By origin model** (1d): 9am 69.9% (n=887) vs. **1am 88.0%** (n=375) -- an 18-point gap, the same
direction as Phase 2's own finding that 1am shows larger MAE and higher recovery than 9am
(`docs/09-atlas-results.md`). Flagged again here as a candidate hypothesis for a dedicated future
test, not explained or acted on this phase.

## Classification of this evidence

**Replication / exploratory evidence within a previously-examined dataset -- NOT out-of-sample
validation.** The 75.4%/85.4% (Phase 2) and 75.3%/85.5% (corrected) recovery figures were already
observed before H1 was written down in this phase's module docstring; 2015-2026 has already shaped
this repo's prior research (stop-floor calibration, the original D3/C2 backtest itself). No claim of
genuine OOS validation is made anywhere in this document.
