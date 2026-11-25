# Deliverable D — Reconstructed Rejection Funnel (by model, instrument, period)

Reproduce: `uv run --project detector python research/loss-pattern-discovery/extract/funnel_reconstruction.py`
(per-symbol; merge as in `docs/67` section on the OOM workaround). Source data:
`artifacts/phase8_funnel_reconstruction.json` (per-symbol `counters_by_model`, `splits`,
`stage6_removed_by_model`, `triggers_by_model_period`, `confirmed_by_model_period`).

## Funnel stages (exact, reused from the real pipeline's own counters)

`Trigger with Key Level -> Model-1 confirmed/rejected -> Confirmed signal eligible for Stage 6 ->
Candidate built/rejected (rr_floor only, Deliverable C) -> Fill eligible/skipped -> Filled/never
filled -> Executed outcome`.

## By model, aggregate (reconciles exactly to the Phase 9 baseline)

| Stage | 1AM | 9AM |
|---|---|---|
| Triggers with Key Level | 11206 | 8712 |
| Model-1 confirmed | 1805 | 3311 |
| Candidates built (Stage 6 survivors) | 718 | 1806 |
| Filled | 620 | 1427 |
| Evaluable (filled, closed) | 619 | 1424 |

All five rows match the user's stated baseline table exactly, with zero unexplained discrepancy.

## By model and instrument

| Instrument | Model | Triggers | Confirmed | Candidates | Filled | `_rr_floor_cut` removed |
|---|---|---|---|---|---|---|
| EURUSD | 1AM | 4199 | 680 | 173 | 143 | 507 |
| EURUSD | 9AM | 2716 | 1039 | 610 | 493 | 429 |
| USDCAD | 1AM | 3830 | 601 | 231 | 207 | 370 |
| USDCAD | 9AM | 3036 | 1202 | 623 | 489 | 579 |
| AUDUSD | 1AM | 3177 | 524 | 314 | 270 | 210 |
| AUDUSD | 9AM | 2960 | 1070 | 573 | 445 | 497 |
| **Sum** | 1AM | **11206** | **1805** | **718** | **620** | **1087** |
| **Sum** | 9AM | **8712** | **3311** | **1806** | **1427** | **1505** |

Every instrument individually shows the same qualitative pattern as the pooled numbers: 9AM
confirms a materially larger share of its triggers than 1AM (EURUSD 38.2% vs. 16.2%; USDCAD 39.6%
vs. 15.7%; AUDUSD 36.1% vs. 16.5%), and `_rr_floor_cut` is the sole Stage-6 attrition mechanism in
every instrument/model cell (no cell has any `_dedup` or `_kill_zone_cut` removals -- verified
`all_zero: True` for all three, per Deliverable C).

## By model and period (trigger volume and confirmation rate)

| Period | 1AM triggers | 1AM confirmed | 1AM rate | 9AM triggers | 9AM confirmed | 9AM rate |
|---|---|---|---|---|---|---|
| 2015-2017 | 2909 | 417 | 14.3% | 2103 | 818 | 38.9% |
| 2018-2020 | 2852 | 501 | 17.6% | 2188 | 820 | 37.5% |
| 2021-2023 | 2838 | 477 | 16.8% | 2304 | 859 | 37.3% |
| 2024-2026 | 2607 | 410 | 15.7% | 2117 | 814 | 38.5% |

**The confirmation-rate gap between 1AM (~14-18%) and 9AM (~37-39%) is stable across all four
periods** -- it is not driven by any single era, regime, or data-quality window. Trigger volume per
model is also roughly flat across periods for both models (no period dominates either model's
total), so the gap is not a period-weighting artifact of combining periods of very different size.

## Period-bucketing method

`period_bucket` (reused unmodified from `control/sampling.py`) is applied to each trigger's own
confirmation-window OPEN timestamp, recovered via `_window_open_ts_from_stable_id` (the inverse of
`stable_trigger_id`'s own isoformat field) -- the same timestamp already used as the trigger's
identity, not a derived or re-simulated one.
