# Deliverable A — Model Population Audit

Full executed-trade population (2047 = 778 win + 1265 loss + 4 open), split by `origin_model`. Every
proportion names its own denominator. Reproduce: `uv run --project detector python
research/loss-pattern-discovery/stats/model_population_audit.py`.

| | 9AM | 1AM |
|---|---|---|
| n_total | 1427 | 620 |
| n_win | 535 | 243 |
| n_loss | 889 | 376 |
| n_confirmed_stop | 887 | 375 |
| n_ambiguous_stop | 2 | 1 |
| n_open_censored | 3 | 1 |
| % negative (loss / total) | 62.3% | 60.65% |
| % confirmed (confirmed / loss) | 99.78% | 99.73% |
| Duration, all evaluable (median bars) | **21** | **6** |
| risk_price (median, price units) | 0.00131 | 0.00080 |
| **risk_atr** (median) | 1.349 | **1.438** |
| cost_to_risk_ratio (median) | 0.109 | 0.178 |
| % partial exit | 37.7% | 39.4% |

**Win rates are close (37.7% vs 39.4%)** -- the selection-bias concern raised in section 4 (that a
different win/loss mix could create an artificial loss-population difference) is not a major factor
here.

**The most structurally striking difference is duration, not risk sizing**: 1AM trades resolve at a
median of 6 bars (~1.5h) regardless of outcome, vs. 9AM's 21 bars (~5.25h) -- a >3x difference that
holds across BOTH wins and losses, not just the confirmed-stop population Phase 4 looked at.

**risk_atr is NOT smaller for 1AM** -- if anything it is slightly LARGER (1.438 vs. 1.349), even
though 1AM's absolute `risk_price` is roughly half of 9AM's. This single fact already previews
Deliverable C's result: standardizing by risk_atr cannot shrink a gap that risk_atr does not actually
favor in the "tighter stop" direction. `cost_to_risk_ratio` is notably higher for 1AM (0.178 vs.
0.109) -- a candidate factor NOT tested this phase (noted for Phase 6, not chased now).
