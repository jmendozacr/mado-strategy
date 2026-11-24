# Deliverable B — Post-Stop-Loss Behavior Atlas (results)

Population: 1262 `confirmed_stop_event`/`stop_after_partial_exit` losses (the eligible population from
Unit A). All figures are median (90% block-bootstrap CI, block = instrument x ISO calendar week),
from `artifacts/phase2_atlas.json` (regenerate with `uv run --project detector python
research/loss-pattern-discovery/stats/atlas.py`).

## Overall (pooled, all eligible events)

| Horizon | MAE (R) | MFE (R) | Directional return (R) | P(continuation) | P(reversal) | P(recovered to entry) |
|---|---|---|---|---|---|---|
| 1h | 0.49 [0.45, 0.52] | 0.50 [0.47, 0.55] | 0.02 [-0.02, 0.07] | 55.3% [53.1, 57.5] | 43.3% [41.1, 45.5] | 25.4% [23.5, 27.3] |
| 4h | 0.91 [0.83, 0.96] | 0.97 [0.93, 1.02] | 0.04 [-0.02, 0.10] | 55.6% [53.5, 57.9] | 43.7% [41.5, 45.9] | 48.7% [46.4, 50.8] |
| 1d | 2.34 [2.20, 2.49] | 2.44 [2.30, 2.62] | 0.12 [-0.01, 0.32] | 55.7% [53.5, 57.9] | 43.7% [41.5, 45.9] | 75.4% [73.3, 77.3] |
| 3d | 3.63 [3.40, 3.97] | 3.96 [3.74, 4.21] | 0.06 [-0.23, 0.38] | 55.9% [53.6, 58.1] | 44.1% [41.9, 46.4] | 85.4% [83.8, 87.0] |

Censoring/gaps: 0.0% censored through 1d, 0.2% by 3d (data-end effect, negligible); weekend gaps
spanned by 0.0% of 1h/4h/1d windows, 19.0% of 3d windows (expected — a 3-day window often crosses a
weekend for FX).

## By instrument (1d horizon)

| Instrument | n | P(continuation) | MAE (R) | P(recovered to entry) |
|---|---|---|---|---|
| EURUSD | 397 | 57.4% [53.4, 61.2] | 2.49 [2.24, 2.74] | 72.0% [68.2, 75.7] |
| USDCAD | 423 | 56.7% [52.5, 60.9] | 2.18 [1.99, 2.43] | 76.1% [72.6, 79.5] |
| AUDUSD | 442 | 53.2% [49.3, 56.8] | 2.32 [2.11, 2.66] | 77.6% [74.3, 80.9] |

All three pairs' confidence intervals overlap heavily — no pair stands out as behaviorally different
at this horizon, including EURUSD (deliberately not excluded despite its weak backtest edge, per S22).

## By session/model (1d horizon)

| Model | n | P(continuation) | MAE (R) | P(recovered to entry) |
|---|---|---|---|---|
| 9am | 887 | 54.9% [52.2, 57.7] | 2.05 [1.87, 2.21] | 70.0% [67.4, 72.6] |
| 1am | 375 | 57.6% [53.5, 61.6] | 3.18 [2.97, 3.67] | 88.0% [85.1, 90.8] |

**The one stratified difference with clearly non-overlapping CIs**: the 1am model's post-stop MAE
(3.18R) is materially larger than 9am's (2.05R), and its recovery-to-entry rate is also higher (88.0%
vs 70.0%). Continuation/reversal split itself is similar between the two. This is a real descriptive
difference in this dataset, not yet explained causally here (candidate hypotheses: different typical
stop-distance geometry or liquidity conditions at the 1am session) — flagged for a future research
unit, not acted on in this phase.

## By direction (1d horizon)

| Direction | n | P(continuation) | MAE (R) | P(recovered to entry) |
|---|---|---|---|---|
| Bullish | 648 | 55.1% [51.7, 58.4] | 2.39 [2.14, 2.70] | 74.5% [71.8, 77.4] |
| Bearish | 614 | 56.4% [53.2, 59.6] | 2.30 [2.11, 2.48] | 76.2% [73.3, 79.0] |

No meaningful asymmetry between original-buy and original-sell stop events.

## By period bucket (1d horizon) — predeclared, see `docs/07-...`

| Period | n | P(continuation) | MAE (R) | P(recovered to entry) |
|---|---|---|---|---|
| 2015-2017 | 300 | 52.7% [48.0, 57.3] | 2.38 [2.11, 2.73] | 70.7% [66.2, 74.9] |
| 2018-2020 | 345 | 59.4% [55.2, 63.6] | 2.39 [2.04, 2.80] | 75.4% [71.2, 79.5] |
| 2021-2023 | 330 | 56.1% [51.5, 60.6] | 2.29 [2.07, 2.58] | 77.9% [74.0, 81.4] |
| 2024-2026 | 287 | 54.0% [49.1, 58.9] | 2.39 [2.04, 2.63] | 77.4% [73.3, 81.3] |

Reasonably stable across the four predeclared periods -- the 2015-2017 vs. 2018-2020 continuation gap
(52.7% vs. 59.4%) has borderline-overlapping CIs and is not treated as a confirmed regime difference
on its own (see `docs/11-research-findings.md`).

## Ambiguous events (sensitivity only, n=3 — never pooled into the above)

MAE median 7.77R (CI [3.50, 8.39], `small_sample=True`), P(continuation) 66.7% (CI [33.3%, 100%]). 3
events is far too few to support any claim; reported only so the exclusion is auditable, not hidden.
