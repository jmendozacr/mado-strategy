# Real-data H4/M15 evidence (S-000.9, post-implementation) — HALT

**Verdict: HALT.** Two of the three binding S-000 acceptance criteria (design §9.1) FAIL on EURUSDm, the reference instrument. Per design §9.1 / slices.md S-000 / the launch instruction: this halts S-000 and escalates to the human before S-001..S-006 are built. The numbers below are reported as measured — no attempt was made to adjust the gate or the strategy to pass.

**Command** (per instrument): same as `evidence/pre-gate-h4-m15.md`, plus `--backtest`, run against this slice's code (HEAD + working tree), output under `.sdd/evidence/crt-detector-key-level-confluence-core/{instrument}/`. All three runs completed in 43-49s wall clock, well inside the 10-minute budget.

## REQ-60.1 — six counts per instrument, pre- and post-gate

| Instrument | signals_considered | trades_opened (pre → post) | win rate (pre → post) | average R (pre → post) | total R (pre → post) | detections.csv Model-1 rows (pre → post) |
|---|---|---|---|---|---|---|
| EURUSDm | 142984 (unchanged) | 2402 → 2325 | 0.273 → 0.271 | **0.244 → 0.230** | 585.672 → 535.634 | 142984 → 140192 |
| GBPUSDm | 143054 (unchanged) | 2502 → 2456 | 0.265 → 0.268 | 0.270 → 0.286 | 675.741 → 702.821 | 143054 → 141467 |
| DXYm | 142776 (unchanged) | 2838 → 2714 | 0.262 → 0.259 | 0.502 → 0.496 | 1423.185 → 1344.533 | 142776 → 139616 |

`signals_considered` is identical pre/post on all three instruments — confirms REQ-40's decoupling guarantee (the confluence gate never narrows the backtest population count, only `detections.csv`/`trades_opened` composition).

New `excluded_no_key_level` bucket: EURUSDm 1081, GBPUSDm 578, DXYm 1220 — all far smaller than the `withheld` figures below, confirming design §10's noted asymmetry (withheld > `excluded_no_key_level` strictly, since the CSV gate also withholds aligned non-`fvg_fill` signals that never reach the confluence check at all, e.g. `excluded_never_confirmed`).

## REQ-60.2 — withheld fraction `W`

```
W = (pre_gate_model1_rows − post_gate_model1_rows) / (signals_considered − excluded_no_crt_range − excluded_unaligned)
```

| Instrument | Numerator (withheld rows) | Denominator | W | In `[0.10, 0.75]`? |
|---|---|---|---|---|
| **EURUSDm (reference)** | 2792 | 105061 | **0.0266** | **NO — FAILS, ~3.8× below the 0.10 floor** |
| GBPUSDm (corroboration) | 1587 | 105566 | 0.0150 | NO |
| DXYm (corroboration) | 3160 | 104108 | 0.0304 | NO |

All three instruments land in the same 1.5%-3.0% band — consistent, not an isolated outlier. This is even below the 2.8% ADR-013 measured for the REJECTED no-expiry alternative (design V1), and roughly 4-11× below the 10-34% range the expiring-rule counterfactual was expected to produce. The gate is barely discriminating on real H4/M15 data: on this dataset, an aligned, non-`fvg_fill` HTF purge candle almost always has SOME unexpired HTF FVG zone in reach, regardless of the specific validity-window/expiry logic implemented in this slice.

## REQ-60.3 — minimum sample floor

| Instrument | trades_opened (post-gate) | `>= 50`? |
|---|---|---|
| **EURUSDm (reference)** | 2325 | **YES — PASSES** |
| GBPUSDm | 2456 | YES |
| DXYm | 2714 | YES |

## REQ-60.4 — average-R non-regression (frictionless, strict, no tolerance)

| Instrument | Pre-gate average R | Post-gate average R | Regression? |
|---|---|---|---|
| **EURUSDm (reference)** | +0.244 | **+0.230** | **YES — FAILS (post < pre)** |
| GBPUSDm (corroboration) | +0.270 | +0.286 | No (improved) |
| DXYm (corroboration) | +0.502 | +0.496 | Yes (declined, corroboration only) |

EURUSDm — the binding instrument — regresses: post-gate average R (0.230) is strictly below the pre-gate baseline (0.244). Total R also declined (535.634 vs 585.672), expected given fewer trades, but average R (the per-trade expectancy metric REQ-60.4 actually gates on) declined too, which the design's own framing (§9.1) states directly measures "the gate improves the strategy" — it did not, on this data.

## Verdict

| Criterion | Result |
|---|---|
| REQ-60.2 (`0.10 <= W <= 0.75`) | **FAIL** — EURUSDm W = 0.0266 |
| REQ-60.3 (`trades_opened >= 50`) | PASS — 2325 |
| REQ-60.4 (average R non-regression) | **FAIL** — 0.230 < 0.244 |

Two of three binding criteria fail on the reference instrument. Per design §9.1's explicit rule ("Any of the three failing halts S-000 and escalates to the user before S-001..S-006 are built"), **this slice HALTS here.** No fix was attempted — the gate as specified (right-closed expiry window, both-sides-independent crediting, same-config HTF FVG source) is correctly implemented per every unit/e2e test in this slice, but on real EURUSDm/GBPUSDm/DXYm H4/M15 data it discriminates far less than design's north-star assumed, and the one instrument REQ-60.4 gates on shows a real, if small, expectancy regression rather than an improvement.
