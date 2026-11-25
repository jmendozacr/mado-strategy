# Deliverable C — Early Stop-Loss Analysis (H1, H2)

Primary endpoint: `P(confirmed_stop AND same_or_next_bar | primary population)` -- 2043 evaluable
executed trades (778 win, 1265 loss; the 4 `OPEN_CENSORED` excluded). `same_or_next_bar` =
`duration_bars <= 1` (exact M15 bar-index difference, never a wall-clock approximation -- see
`docs/29-...` section 1). Reproduce: `uv run --project detector python
research/loss-pattern-discovery/stats/early_stop_hypothesis.py`.

## H1 — Unadjusted gap

| | 1AM | 9AM |
|---|---|---|
| n | 619 | 1424 |
| Rate | **18.90%** | **9.55%** |

**Difference (1AM - 9AM): +9.35 percentage points, 95% CI [5.85pp, 12.77pp].** The CI excludes zero
and the magnitude is well above the 5pp relevance bar -- a clearly relevant, unadjusted association.

## H2 — risk_atr-standardized gap

Common support: **0% of either model's mass falls in an unsupported stratum** -- all 5 pooled
risk_atr quintiles have >=89 trades from EACH model (full table in
`artifacts/phase5_early_stop_hypothesis.json`). The standardized adjustment is on solid ground, no
extrapolation beyond observed support.

| | 1AM (standardized) | 9AM (standardized) |
|---|---|---|
| Rate | 19.20% | 9.27% |

**Standardized difference: +9.93pp, 95% CI [6.30pp, 13.44pp].** The gap does **not** shrink after
adjusting for risk_atr -- if anything it is very slightly larger than unadjusted. This is consistent
with `docs/30-...`'s own finding that 1AM's `risk_atr` is not smaller than 9AM's (1.438 vs. 1.349) --
there is no "tighter relative stop" story for standardization to explain away.

## Sensitivity (one-way, not combined into a grid)

| By instrument | n(1AM/9AM) | Diff | 95% CI | Excludes 0? |
|---|---|---|---|---|
| EURUSD | 143/492 | +18.0pp | [10.8, 25.5] | Yes |
| USDCAD | 207/488 | +12.8pp | [6.4, 19.4] | Yes |
| AUDUSD | 269/444 | +1.5pp | [-3.3, 6.5] | **No** |

| By period | n(1AM/9AM) | Diff | 95% CI | Excludes 0? |
|---|---|---|---|---|
| 2015-2017 | 124/364 | +13.5pp | [5.8, 21.3] | Yes |
| 2018-2020 | 157/372 | +6.4pp | [-0.3, 13.0] | No (borderline) |
| 2021-2023 | 191/353 | +12.8pp | [6.5, 18.8] | Yes |
| 2024-2026 | 147/335 | +5.0pp | [-1.7, 12.5] | No |

**The association is not uniform.** It is clear and large in EURUSD and USDCAD but absent in AUDUSD;
clear in 2015-2017 and 2021-2023 but not reaching significance in 2018-2020 or 2024-2026 (though all
four period point-estimates share the same positive sign). This heterogeneity is reported as-is --
not resolved, not explained, and not a reason to search for a "cleaner" subgroup.

## Conclusion for H1/H2

The 1AM/9AM gap in early-stop probability is real, large, and **does not shrink when adjusted for
`risk_atr`** -- H2 is not supported. It is also not a uniform effect across every pair/period --
reported honestly rather than smoothed over.
