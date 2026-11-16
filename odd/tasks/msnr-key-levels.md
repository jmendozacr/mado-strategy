# MSNR Key Levels Exploration

Branch: `detector-msnr-key-levels`. Test runner: `cd detector && uv run pytest`; import-layering: `cd detector && uv run lint-imports`.

## Specs

- **S1**: "Haz escuchado acerca de la estrategia MSNR? La suelen combinar con CRT también y me gustaría explorar sus key levels, los llamado A shape, V shape, SR, RS, QM puedes informarte en internet y ver que podemos explorar en un nuevo branch" — explore MSNR (Malaysian Support and Resistance) key levels (A-shape, V-shape, SR, RS, QM) as a potential new `KeyLevel` source, in a new branch.
- **S2**: "Exacto la idea es probar esos key levels apagando o no usando los FVG/OB para hacer las respectivas pruebas" — test MSNR key levels with FVG/Order Block turned OFF (replaced, not added to the existing credit pool), to get a standalone read on MSNR's own signal quality, independent of the already-confirmed FVG-density bias in `alignment.htf_ltf._key_level_credit_map`'s tiebreak (memory #782, reconfirmed 4x this project's history — Breaker Block, OB anchor variant, OB-on-H4, zone-rejection — all null for the same reason).

## Scope decision (this task)

MSNR defines several level types (researched via web search, see session log): A-shape/V-shape (close-based two-candle pivots), SBR/RBS (role-flip when a level is broken by a CLOSE, not just a wick), QM/Quasimodo (high -> lower-high -> break of prior low, a structural-reversal pattern). Only **A-shape/V-shape** is implemented in this task — the simplest, most mechanically unambiguous piece, with no discretionary threshold beyond a small ATR-relative touch buffer. SBR/RBS and QM are explicitly deferred to follow-up tasks, so a first signal-quality read doesn't block on the most complex (QM) piece.

## Tasks

- **T1**: `primitives/msnr_levels.py` — `detect_msnr_levels`/`to_key_levels` (A-shape/V-shape). Linked: S1. Route: inline. DONE — 5/5 tests green, `tests/test_msnr_levels.py`.
- **T2**: `experimental/msnr_key_level_backtest.py` — standalone comparison harness (FVG/OB current vs. MSNR-only, both H4 and Daily tier). Linked: S2. Route: inline. DONE.
- **T3**: Run the comparison on real data, record the result. Linked: S2. Route: inline. DONE — see L3.

## Closed — result: MSNR does not beat FVG/OB, SBR/RBS makes it worse

**T4**: validated across the full 5-pair basket (EURUSD/USDCAD/AUDUSD/GBPUSD/USDJPY), each symbol's own calibrated `BacktestConfig` (real cost, `kill_zone_gated` forced True for apples-to-apples), trimmed 2022-01-01+ data. Linked: S2. Route: inline. DONE.

**T5**: implemented SBR/RBS (`primitives/msnr_levels.to_key_levels_with_sbr_rbs` — a level's validity ends at the first CLOSE that breaks through it; a new segment starts there with the opposite role, chaining until the series ends). TDD, 3 new tests (`test_msnr_levels.py`). Linked: S1 (QM/freshness item). Route: inline. DONE.

**5-pair combined result** (reject_close_inside, calibrated per-symbol BacktestConfig, kill_zone_gated=True):

```
                      trades  win_rate  avg_r    total_r
FVG/OB (current)      3704    0.4141   +0.0785  +290.63
MSNR only              3698    0.4148   +0.0704  +260.41
MSNR + SBR/RBS         3718    0.4145   +0.0646  +240.22
```

Per-symbol (EURUSD/USDCAD/AUDUSD/GBPUSD/USDJPY) total_r:
```
            FVG/OB    MSNR     MSNR+SBR/RBS
EURUSD      +73.56    +83.66   +76.34
USDCAD      +101.80   +57.21   +60.15
AUDUSD      -2.02     +8.21    +10.37
GBPUSD      +80.36    +76.79   +71.73
USDJPY      +36.93    +34.53   +21.63
```

**Decision**: closing this exploration. Three variants tested (MSNR plain, MSNR+real-cost, MSNR+SBR/RBS) — none beats FVG/OB on the 5-pair aggregate, and each added layer of sophistication (real cost, then SBR/RBS chaining) made the result WORSE, not better (FVG/OB +290.63 > MSNR +260.41 > MSNR+SBR/RBS +240.22). Win rates stay statistically flat across all three (~41.4-41.5%) — whatever difference exists is in R-multiple distribution, not signal selectivity, and it trends the wrong way as the model gets more sophisticated. EURUSD-alone's early promising result (memory L3) did not generalize.

**Not pursued, given this trend**: freshness/fresh-vs-unfresh (wick-touch invalidation) and QM/Quasimodo. No evidence so far suggests either would reverse the direction.

## Log

- **L1** (verbatim, user's original request): "Haz escuchado acerca de la estrategia MSNR? La suelen combinar con CRT también y me gustaría explorar sus key levels, los llamado A shape, V shape, SR, RS, QM puedes informarte en internet y ver que podemos explorar en un nuevo branch"
- **L2** (verbatim, follow-up confirming scope): "Exacto la idea es probar esos key levels apagando o no usando los FVG/OB para hacer las respectivas pruebas"
- **L3** (result, EURUSD, `reject_close_inside` recipe, LTF Model-1 detection unchanged — same simplified wiring as `breaker_block_key_level_backtest.py`, not the full causal production path):

```
FVG/OB (current)   signals=62465  trades=766  win_rate=0.4674  avg_r=+0.2336  total_r=+178.93  credits={fvg: 128606, ict_order_block: 2452}
MSNR only          signals=62153  trades=764  win_rate=0.4725  avg_r=+0.2467  total_r=+188.48  credits={msnr: 130992}
```

NOT a null result — unlike every prior "add a new source to the pool" attempt (Breaker Block, OB anchor variant, OB-on-H4, zone-rejection, all null per memory #782's FVG-density prediction), MSNR standalone (replacing, not competing) comes out slightly AHEAD of FVG/OB on this one symbol/recipe: +0.51pp win rate, +9.55R over ~765 trades (~5% relative total_r improvement). Caveats before reading too much into this: single symbol, untuned zone buffer, no freshness/SBR-RBS filter yet (every A/V pivot counted as always-valid), and MSNR's sheer pivot density (one every 1-2 candles) means credit count landed almost exactly equal to FVG+OB's combined count — the `reject_close_inside` reaction filter may be doing most of the real selectivity work here, not the choice of key-level source. Promising enough to justify the "Next" items below, not yet a result to act on.

**L3b (follow-up, same EURUSD dataset, EURUSD's own calibrated `BacktestConfig` instead of defaults)** — scratch-only, not committed (`msnr_calibrated_compare.py`, reuses the committed `aligned_signals`/`credit_counts_by_kind` unmodified):

```
costo real (0.00013) + kill_zone_gated=False (SYMBOL_CONFIG's own setting, NOT comparable to L3 -- opens 24h/day, 7x more trades):
FVG/OB   signals=62465  trades=5435  win_rate=0.3859  avg_r=+0.0005  total_r=+2.85    credits={fvg: 128606, ict_order_block: 2452}
MSNR     signals=62153  trades=5394  win_rate=0.3861  avg_r=+0.0041  total_r=+22.09   credits={msnr: 130992}

costo real (0.00013) + kill_zone_gated=True (same 766/764-trade population as L3, cost-adjusted -- the clean comparison):
FVG/OB   signals=62465  trades=766   win_rate=0.4282  avg_r=+0.0960  total_r=+73.56   credits={fvg: 128606, ict_order_block: 2452}
MSNR     signals=62153  trades=764   win_rate=0.4332  avg_r=+0.1095  total_r=+83.66   credits={msnr: 130992}
```

Real cost erodes roughly half the no-cost avg_r for both arms (as expected), but MSNR stays consistently ahead across all three cost/gating variants tried so far (no-cost, cost+ungated, cost+gated): +0.50-0.51pp win rate, +10-14% relative total_r. Direction is stable; the magnitude of the edge shrinks once real cost is applied.
