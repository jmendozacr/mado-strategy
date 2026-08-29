# Steward Reckoning — CRT Backtest Simulation Engine (pre-archive, backward-looking)

**Checkpoint**: reckoning | **Verdict**: `delivered` | **Ratified**: human, no override needed

## What this gate did differently

The reckoning ran the tool end-to-end on REAL data — 100k M5 EURUSD candles, ~1.3 years — the first gate in this change's pipeline to do so; every prior gate (plan-verify, verify-final, judgment-day) used synthetic fixtures or the smaller 400-candle probe.

## Scoring against the 7 north-star reckoning criteria

| # | Criterion | Result |
|---|---|---|
| 1 | Trader-legible verdict from a real run | Met — win rate + average R computed over 1,896 trades |
| 2 | Reconciliation sums exactly; `excluded_rr_floor` inspected | Met — 139,888 + 1,896 = 141,784 exact; `rr_floor` genuinely excludes 3,701 signals (not near-zero) |
| 3 | Risk is not a constant | Met — risk varies across 144 distinct values on real data, confirming the foresight-gate fix (ADR-05) actually holds in production, not just in fixtures |
| 4 | Trading-cost treatment stated in the summary itself | Met — `(frictionless)` label present; mechanism verified correct |
| 5 | Every trade joins exactly one detection row | Met, on real data |
| 6 | Zero regressions; byte-identical non-backtest output | Met — 193/193, byte-identical |
| 7 | §5 ratifications held through delivery, no drift | Met — delivery over-shot the sufficiency bar (1,896 trades vs. the originally-ratified ~85 estimate) |

No promise↔delivery drift found.

## The steward's own finding (beyond the 7 criteria)

The default `metrics_summary.txt` reads `average R: +0.235` (frictionless). A cost sweep against the real data's own `<SPREAD>` column (mean 1.04 pips, median 0.8) shows the edge crosses breakeven around ~1.25 pips round-trip cost — the headline default number is optimistic relative to realistic trading costs. The `(frictionless)` disclosure is present and honest, and `--trading-cost` works correctly; the gap is that a reader has to know to run the sweep themselves to see the realistic number.

Bonus finding, unprompted: the NY kill-zone gate nearly doubles the edge (+0.235R gated vs. +0.124R ungated) — a genuine, real-data methodology validation the change was never specifically asked to produce.

## Human ratification (2 conscience questions, answered directly, no override needed)

1. **Usability** (frictionless default vs. real-spread reading) — "Dejarlo como está" (leave it as-is). The disclosure mechanism is sufficient; not a code change. Registered as a low-priority UX followup only.
2. **Does the marginal/breakeven-at-real-cost result close the original question?** — "Cierra la pregunta, esto quedó hecho" (this closes the question, it's done). No request for the deferred pieces (drawdown/concurrency/partials) before deciding. This change stands as complete, not phase 1 of N.

## Priority note for `project/pending-changes`

The steward's real-scale run bumped the priority of one already-tracked followup: the `never confirmed` bucket mislabel (originally measured at ~9% on a 400-candle probe) turns out to affect ~5,800 signals at real scale (45% of the population is in that bucket; ~9% of those are mislabeled). Still not blocking — the admission logic itself is correct, only the disclosure label is misleading — but weighted higher for whichever change picks it up next.

## Outcome

**`delivered`.** Archive precondition satisfied.
