# Deliverable E — Secondary Behavioral Analysis (H3, limited and exploratory)

Run because `docs/32-...`'s common-support check passed (0% unsupported). Reuses
`behavior/post_stop_metrics.py` and `behavior/recovery_analysis.py` **completely unmodified** -- same
1d horizon, same thresholds as Phase 2/3 -- only re-stratified by the SAME pooled risk_atr quintiles
from Deliverable C. Reproduce: `uv run --project detector python
research/loss-pattern-discovery/stats/secondary_behavioral_adjustment.py`.

## Unadjusted (reproduces Phase 2/3 exactly -- not re-presented as new evidence)

| | 1AM (n=375) | 9AM (n=887) |
|---|---|---|
| MAE-post-SL (1d, R) | 3.16 | 2.05 |
| P(recovery, 1d) | 88.0% | 69.9% |

## Within each risk_atr quintile (stratum 0 = lowest risk_atr .. 4 = highest)

| Stratum | n (1AM/9AM) | MAE 1AM | MAE 9AM | Recovery 1AM | Recovery 9AM |
|---|---|---|---|---|---|
| 0 | 52/201 | 3.49 | 2.64 | 90.4% | 73.6% |
| 1 | 61/191 | 4.75 | 2.23 | 85.2% | 69.6% |
| 2 | 85/168 | 4.05 | 2.21 | 83.5% | 70.2% |
| 3 | 95/157 | 2.95 | 1.85 | 92.6% | 66.9% |
| 4 | 82/170 | 2.70 | 1.68 | 87.8% | 68.2% |

**Both the MAE gap and the recovery gap persist in EVERY risk_atr stratum**, with similar or even
larger magnitude than unadjusted in some strata (e.g. stratum 1's MAE gap, 4.75R vs. 2.23R, is larger
than the unadjusted 3.16R vs. 2.05R). This is fully consistent with Deliverable C's own conclusion:
`risk_atr` does not explain the 1AM/9AM behavioral difference, in either the early-stop endpoint or
these two already-established post-SL metrics.

## What this does not establish

This is secondary and limited, exactly as scoped: it does not re-open the recovery/continuation
question (Phase 3's `NO_DIFFERENTIAL_RECOVERY_EVIDENCE`/`SENSITIVE_TO_CONTROL_DESIGN` verdicts stand
unchanged -- this is a 1AM-vs-9AM comparison, not a vs.-control one), and it is not a search for a
new recovery-based strategy.
