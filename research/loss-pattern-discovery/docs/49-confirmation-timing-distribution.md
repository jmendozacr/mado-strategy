# Deliverable D — Confirmation Timing Distribution

Purely descriptive (Unit C), before any adjustment is attempted. Reproduce: `uv run --project
detector python research/loss-pattern-discovery/stats/confirmation_timing_distribution.py`.
Bins are a fixed, pre-declared 30-minute width (two M15 bars) -- never tuned on E1 outcomes.

## By model

| | 9AM (n=1424, window=240min) | 1AM (n=619, window=120min) |
|---|---|---|
| `confirmation_elapsed_minutes` median [p10,p90] | 150.0 [60, 210] | 75.0 [45, 105] |
| `confirmation_remaining_minutes` median [p10,p90] | 90.0 [30, 180] | 45.0 [15, 75] |
| `confirmation_relative_position` median [p10,p90] | **0.625** [0.25, 0.875] | **0.625** [0.375, 0.875] |
| `order_to_fill_minutes` median [p10,p90] | 0.0 [0, 90] | 0.0 [0, 135] |

**The median RELATIVE position is identical between models (0.625) despite a 2x difference in
absolute window duration.** Both models' confirmations skew toward the LATTER part of their own
window (0.625 > 0.5, consistent with needing time for the anchor+engulf+retest sequence to
develop), and this skew is proportionally the same in both models. In ABSOLUTE terms, 9AM's
confirmations spread across a much wider range (up to 210min at p90) that has no 1AM counterpart at
all (1AM's window caps at 120min) -- the common-support problem the brief anticipated (section 9) is
real and visible here already, before any adjustment is attempted.

30-minute-bin histogram (count of confirmations per bin, fixed bin edges):

| Bin (minutes) | 9AM | 1AM |
|---|---|---|
| [0,30) | 0 | 0 |
| [30,60) | 44 | 150 |
| [60,90) | 193 | 243 |
| [90,120) | 237 | 226 |
| [120,150) | 234 | n/a (window ends at 120) |
| [150,180) | 270 | n/a |
| [180,210) | 215 | n/a |
| [210,240) | 231 | n/a |

9AM's distribution is fairly broad across its full window (no dominant early or late spike -- the
largest bin, [150,180), holds 19% of 9AM's mass, not a majority). **Order-to-fill is immediate
(median 0 minutes -- filled on the very first eligible bar) for more than half of both models**,
but the tail is longer for 1AM (p90 = 135min vs. 90min for 9AM) -- 1AM trades wait longer, in the
slow cases, between order placement and actual fill.

## By instrument (one-way)

Elapsed-minutes medians are consistent across EURUSD/USDCAD/AUDUSD within each model (9AM: 135-150
min; 1AM: 75 min for all three) -- no instrument shows a starkly different confirmation-timing
profile. Relative position medians are likewise consistent (9AM: 0.5625-0.625; 1AM: 0.625 for all
three).

## By period (one-way)

No material drift across the four period buckets for either model -- 9AM's elapsed median is
135min in 2015-2020 and rises slightly to 150min in 2021-2026; 1AM's stays at exactly 75min across
all four buckets. Order-to-fill's upper tail (p90) does vary somewhat by period for 1AM (75-180min)
without a clear trend.

## What this does not yet establish

This is purely descriptive. Whether this timing position (or the composition difference it implies)
explains any part of the E1 gap is Deliverable E, not this one.
