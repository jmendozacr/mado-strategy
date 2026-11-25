# Deliverable B — Pre-Entry Comparability Report

Purely descriptive (no hypothesis test here -- H1/H2 are Deliverable C). Primary population:
2047 total trades (1427 9AM, 620 1AM), `compute_pre_entry_features` computed strictly from
pre-entry data. Reproduce: `uv run --project detector python
research/loss-pattern-discovery/stats/model_population_audit.py`.

## Distributions by model (median [p10, p90])

| Feature | 9AM | 1AM |
|---|---|---|
| `atr_m15_at_entry` (price) | 0.000966 [0.000563, 0.001649] | 0.000591 [0.000393, 0.000968] |
| `risk_price` | 0.001310 [0.000678, 0.002398] | 0.000803 [0.000600, 0.001402] |
| `risk_atr` | 1.349 [0.982, 1.918] | 1.438 [1.066, 1.877] |
| `planned_rr` | 2.935 [2.159, 5.147] | 2.822 [2.153, 4.288] |
| `cost_to_risk_ratio` | 0.109 [0.060, 0.198] | 0.178 [0.099, 0.265] |
| `ny_hour_at_entry` | 12.0 [10.5, 13.5] | 3.75 [3.0, 5.5] |
| `day_of_week_ny` | 2 [0, 4] | 2 [0, 4] |
| `time_activation_to_entry_s` | 8100s [3600, 14400] | 7200s [3600, 14400] |
| `recent_range_atr` | 3.935 [2.792, 5.455] | 3.640 [2.741, 5.085] |
| `position_in_recent_range` | 0.504 [0.221, 0.773] | 0.510 [0.248, 0.749] |

## Reading these differences

**`ny_hour_at_entry` is non-overlapping by construction, not a finding.** The two session labels
literally mean "signal confirmed near 1AM NY" vs "near 9AM NY" -- this entry does not need
adjustment or matching (the brief's section 11 explicitly warns against forcing NY-hour matching
when models operate in non-overlapping hours by design).

**`day_of_week_ny` and `time_activation_to_entry_s` are comparable.** Same median day-of-week,
same shape; activation-to-entry lag is of the same order (~2-2.25h median) for both models -- no
evidence either model waits systematically longer for its trigger to resolve into an entry.

**`recent_range_atr` and `position_in_recent_range` are comparable.** Both models enter near the
middle of their own recent range (position ~0.50-0.51), with similar recent-range-to-ATR ratios --
no evidence one model enters from a systematically more extreme location in its recent range.

**`planned_rr` is comparable** (2.82 vs 2.94 median) -- the two models are not targeting
structurally different reward multiples.

**Three features differ more materially, already surfaced in `docs/30-...` and carried forward
into Deliverable C/D:**
- `atr_m15_at_entry`: 1AM's median M15 ATR at entry is ~61% of 9AM's -- 1AM trades enter in a
  visibly lower-volatility-in-price-units regime (consistent with 1AM corresponding to a quieter
  session than 9AM in wall-clock terms).
- `risk_atr`: 1AM is *not* lower (1.438 vs 1.349) -- rules out a naive "1AM just uses a tighter
  stop" story, since risk expressed in the asset's own ATR units is, if anything, slightly larger.
- `cost_to_risk_ratio`: 1AM is notably higher (0.178 vs 0.109) -- trading cost consumes a larger
  share of planned risk for 1AM trades, a direct consequence of `risk_price` being smaller while
  the fixed-in-price-units trading cost (`SYMBOL_CONFIG`) stays the same.

None of these three is used as an adjustment variable beyond `risk_atr` itself (pre-registered in
`docs/29-...`); `cost_to_risk_ratio` and `atr_m15_at_entry` remain untested candidate explanations
for a future unit, as already flagged in `docs/33-...`.
