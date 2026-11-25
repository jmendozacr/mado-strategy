# Deliverable B — Model-Specific Funnel Reconstruction

Reproduce: `uv run --project detector python
research/loss-pattern-discovery/extract/funnel_reconstruction.py` (writes
`artifacts/phase8_funnel_reconstruction.json`), then `uv run --project detector python
research/loss-pattern-discovery/stats/funnel_reconciliation_report.py`.

Pinned exactly to D3/C2 (`anchor_source="new"`, `windows_9am="new"`, `arm_name="d3_c2"`,
`start_date=2015-01-01`) -- verified by cross-checking every genuinely model-specific
`FunnelCounters` value this reconstruction independently recomputes against the real
`funnel_2015plus_run2.csv` row values: every single one (`windows_considered`, `swept_*`,
`triggers_with_key_level`, `model1_confirmed`, `zero_signal_reason_categories`) matches exactly,
for all three pairs, both models.

## Full per-model, per-instrument funnel (stages 1-8)

| | EURUSD 1AM | EURUSD 9AM | USDCAD 1AM | USDCAD 9AM | AUDUSD 1AM | AUDUSD 9AM |
|---|---|---|---|---|---|---|
| Windows considered | 3085 | 3078 | 3083 | 3076 | 3083 | 3076 |
| Reference incomplete (skipped) | 1249 | 1256 | 1251 | 1258 | 1251 | 1258 |
| Triggers with Key Level | 4199 | 2716 | 3830 | 3036 | 3177 | 2960 |
| Model-1 confirmed | 680 | 1039 | 601 | 1202 | 524 | 1070 |
| Candidates built (reconstructed) | 173 | 610 | 231 | 623 | 314 | 573 |
| Fill-eligible, never filled | 30 | 117 | 24 | 134 | 44 | 128 |
| Filled (= executed, incl. open) | 143 | 493 | 207 | 489 | 270 | 445 |

**Cross-check (requirement 9/10, `verify_against_pooled_counts`)**: every per-model split, summed,
reproduces `fill_pass_c`'s own unmodified pooled return value EXACTLY, for all three pairs
(`matches: true` in all three `artifacts/phase8_funnel_reconstruction.json` entries). The
reconstruction never drops or double-counts a single candidate relative to the original function.

## Reconciliation against the real executed-trade ledger

| | Reconstructed `filled` | Ledger executed (incl. open) | Match? |
|---|---|---|---|
| EURUSD 1AM | 143 | 143 | Yes |
| EURUSD 9AM | 493 | 493 (492 evaluable + 1 open) | Yes |
| USDCAD 1AM | 207 | 207 | Yes |
| USDCAD 9AM | 489 | 489 (488 evaluable + 1 open) | Yes |
| AUDUSD 1AM | 270 | 270 (269 evaluable + 1 open) | Yes |
| AUDUSD 9AM | 445 | 444 evaluable + 0 open = 444... | see note below |

**Note on AUDUSD 9AM**: the 4th open-censored trade (`AUDUSD|d3_c2|9am|2026-11-10T14:00:00|bullish`)
belongs to AUDUSD/9AM, so 444 evaluable + 1 open = **445** -- matches exactly. (Re-verified directly
against the extracted ledger's own open-trade list, not assumed.)

**Totals**: 143+493+207+489+270+445 = **2047**, matching the baseline (`620` 1AM + `1427` 9AM)
exactly: 1AM = 143+207+270 = 620; 9AM = 493+489+445 = 1427. **Every single executed trade
reconciles to a specific (symbol, model) cell with zero unexplained discrepancy.**

## Why `candidates_built`'s 1AM/9AM split differs sharply from `model1_confirmed`'s

9AM's `model1_confirmed` is consistently ~2x 1AM's (per Deliverable D's conversion rates) --
unsurprising given its much longer search window. But the `candidates_built` STAGE (after
`build_stage6_population`'s own further exclusions) does not preserve that same ratio uniformly
across pairs (EURUSD: 173 vs. 610, ~3.5x; USDCAD: 231 vs. 623, ~2.7x; AUDUSD: 314 vs. 573, ~1.8x) --
this phase does not audit `build_stage6_population`'s own internal exclusion categories per model
(docs/57 section 3, an explicit scope boundary), so this heterogeneity is reported, not explained.
