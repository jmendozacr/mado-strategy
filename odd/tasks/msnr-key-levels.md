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

## Next (not started)

- SBR/RBS role-flip (level broken by a CLOSE, not a wick, flips Support<->Resistance) and the "fresh vs unfresh" distinction (unfresh after first wick touch) — the MVP treats every A/V pivot as always-valid, no freshness filter at all.
- QM/Quasimodo (high -> lower-high -> break of prior low) — the most structurally complex MSNR level type, deferred entirely.
- Validate across the full 5-pair basket (EURUSD+USDCAD+AUDUSD+GBPUSD+USDJPY), not just EURUSD.
- Tune `MSNRConfig.zone_atr_multiple` (currently an untuned first-pass 0.1) -- MSNR's own credit count (130,992) landed almost exactly equal to FVG+OB's combined count (131,058) on EURUSD, suggesting the buffer size may be making MSNR about as "available" as FVG by construction, not necessarily reflecting a real quality signal yet.

## Log

- **L1** (verbatim, user's original request): "Haz escuchado acerca de la estrategia MSNR? La suelen combinar con CRT también y me gustaría explorar sus key levels, los llamado A shape, V shape, SR, RS, QM puedes informarte en internet y ver que podemos explorar en un nuevo branch"
- **L2** (verbatim, follow-up confirming scope): "Exacto la idea es probar esos key levels apagando o no usando los FVG/OB para hacer las respectivas pruebas"
- **L3** (result, EURUSD, `reject_close_inside` recipe, LTF Model-1 detection unchanged — same simplified wiring as `breaker_block_key_level_backtest.py`, not the full causal production path):

```
FVG/OB (current)   signals=62465  trades=766  win_rate=0.4674  avg_r=+0.2336  total_r=+178.93  credits={fvg: 128606, ict_order_block: 2452}
MSNR only          signals=62153  trades=764  win_rate=0.4725  avg_r=+0.2467  total_r=+188.48  credits={msnr: 130992}
```

NOT a null result — unlike every prior "add a new source to the pool" attempt (Breaker Block, OB anchor variant, OB-on-H4, zone-rejection, all null per memory #782's FVG-density prediction), MSNR standalone (replacing, not competing) comes out slightly AHEAD of FVG/OB on this one symbol/recipe: +0.51pp win rate, +9.55R over ~765 trades (~5% relative total_r improvement). Caveats before reading too much into this: single symbol, untuned zone buffer, no freshness/SBR-RBS filter yet (every A/V pivot counted as always-valid), and MSNR's sheer pivot density (one every 1-2 candles) means credit count landed almost exactly equal to FVG+OB's combined count — the `reject_close_inside` reaction filter may be doing most of the real selectivity work here, not the choice of key-level source. Promising enough to justify the "Next" items below, not yet a result to act on.
