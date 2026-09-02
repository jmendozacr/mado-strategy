# Real-data H4/M15 evidence (S-000.12, REQ-66) — ICTOrderBlock-only discrimination number

> **Note (2026-09-01): this file was overwritten to record the V2 (immediate-engulfing) detection/invalidation rule run.** The V1 (MSS/StructureBreak-anchored) run originally captured here is superseded by the spec/design V2 rewrite — V1's rule no longer exists in the codebase. The V1 numbers are NOT deleted; they are kept below, under "## SUPERSEDED — V1 run (MSS-anchored rule, invalidated by the V2 redesign)", for the investigation trail. The section immediately below this note is the current, authoritative V2 run.

## V2 run — immediate-engulfing rule (current)

**Isolation**: confluence gated SOLELY on ICTOrderBlock-sourced Key Levels for this run — the FVG term was temporarily commented out of `cli.py`'s `htf_key_levels` concatenation (`# TEMP: S-000.12 isolation run, revert before commit`), all 3 instruments run, evidence captured, then reverted. `git diff cli.py` (post-revert) shows exactly the shipped V2 composition (`to_key_levels(detect_fvgs(...)) + ict_order_block_to_key_levels(...)`) with no trace of the temporary edit — confirmed clean.

**Command** (per instrument, run from repo root), same H4/M15 pairing and 3 instruments as #1's S-000.9 gate:
```
./detector/.venv/Scripts/python.exe -m detector.cli \
  --csv pairs/M15/{instrument}_M15_*.csv --symbol {instrument} \
  --htf-csv pairs/H4/{instrument}_H4_*.csv --htf-symbol {instrument} \
  --output-dir .sdd/evidence/crt-detector-ict-order-block/{instrument} --backtest
```
All three runs completed in 55-66s wall clock. Output under `.sdd/evidence/crt-detector-ict-order-block/{instrument}/` (repo root, gitignored).

### REQ-66.1/66.3 — raw counts per instrument

`signals_considered`, `excluded_no_crt_range` (fvg_fill-confirmed bucket), and `excluded_unaligned` all matched #1's already-captured pre-gate baseline (`crt-detector-key-level-confluence-core/evidence/pre-gate-h4-m15.md`) exactly — Model-1/CRT-range/alignment detection is untouched by this change; only `AlignedSignal.key_level` sourcing differs.

| Instrument | signals_considered | aligned, non-fvg_fill total (denominator) | never confirmed | **credited an ICTOrderBlock Key Level** | **excluded_no_key_level** | not credited (never_confirmed + excluded_no_key_level) | trades_opened |
|---|---|---|---|---|---|---|---|
| EURUSDm | 142984 | 105061 | 63901 | **674** | **40486** | 104387 | 70 |
| GBPUSDm | 143054 | 105566 | 64332 | **620** | **40614** | 104946 | 74 |
| DXYm | 142776 | 104108 | 64299 | **756** | **39053** | 103352 | 71 |

Full coverage — a complete count set exists for all 3 instruments (REQ-66.3). No threshold gate applied to any of these numbers (REQ-66.2) — reported as measured, no pass/fail interpretation attached.

### Discrimination number, computed identically to FVG's (comparable to obs #449's 1.5–3.0%)

Same formula as FVG's disclosed figure (`crt-detector-key-level-confluence-core/evidence/real-data-h4-m15.md`, REQ-60.2):

```
W = (pre_gate_model1_rows − post_gate_model1_rows) / (signals_considered − excluded_no_crt_range − excluded_unaligned)
```

using `detections.csv` Model-1 row counts before/after the REQ-56 confluence gate (pre-gate row counts reused unchanged from #1's own pre-gate baseline):

| Instrument | pre-gate Model-1 rows | post-gate Model-1 rows (ICTOrderBlock-only, V2) | withheld rows | denominator | **W (ICTOrderBlock, V2)** | FVG's W (obs #449) |
|---|---|---|---|---|---|---|
| EURUSDm | 142984 | 39662 | 103322 | 105061 | **0.9834** | 0.0266 |
| GBPUSDm | 143054 | 39161 | 103893 | 105566 | **0.9842** | 0.0150 |
| DXYm | 142776 | 40711 | 102065 | 104108 | **0.9804** | 0.0304 |

Second, narrower percentage — `excluded_no_key_level` alone as a fraction of the aligned-non-fvg_fill denominator (excludes never-confirmed signals, which never got a chance to check a Key Level at all):

| Instrument | excluded_no_key_level / denominator |
|---|---|
| EURUSDm | 0.3854 |
| GBPUSDm | 0.3847 |
| DXYm | 0.3751 |

### Supplementary: trade population size and expectancy (not a REQ-66 requirement, context only)

| Instrument | Pre-gate trades_opened | ICTOrderBlock-only trades_opened (V2) | Pre-gate average R | ICTOrderBlock-only average R (V2) |
|---|---|---|---|---|
| EURUSDm | 2402 | 70 | +0.244 | +0.568 |
| GBPUSDm | 2502 | 74 | +0.270 | +0.402 |
| DXYm | 2838 | 71 | +0.502 | -0.510 |

Reported as measured, no interpretation attached.

---

## SUPERSEDED — V1 run (MSS-anchored rule, invalidated by the V2 redesign)

Everything below this line was captured against V1's detection rule ("last opposing-bodied candle before an MSS-confirmed `StructureBreak`"), which no longer exists in the codebase — `composite/mss.py::to_structure_breaks` and `core/structure_break.py` were reverted/deleted when spec/design V2 replaced the detection and invalidation rules entirely. Kept for the investigation trail only; not comparable to the V2 numbers above without noting the rule changed underneath them.

**Isolation**: confluence gated SOLELY on ICTOrderBlock-sourced Key Levels for this run — the FVG term was temporarily commented out of `cli.py`'s `htf_key_levels` concatenation (`# TEMP: S-000.12 isolation run, revert before commit`), all 3 instruments run, evidence captured, then reverted. `git diff cli.py` (post-revert) shows exactly S-000.10's shipped composition (`to_key_levels(detect_fvgs(...)) + ict_order_block_to_key_levels(...)`) with no trace of the temporary edit — confirmed clean.

**Command** (per instrument, run from repo root):
```
./detector/.venv/Scripts/python.exe -m detector.cli \
  --csv pairs/M15/{instrument}_M15_*.csv --symbol {instrument} \
  --htf-csv pairs/H4/{instrument}_H4_*.csv --htf-symbol {instrument} \
  --output-dir .sdd/evidence/crt-detector-ict-order-block/{instrument} --backtest
```
Same H4/M15 pairing and 3 instruments as #1's S-000.9 gate (`crt-detector-key-level-confluence-core`). All three runs completed in 60-83s wall clock. Output under `.sdd/evidence/crt-detector-ict-order-block/{instrument}/` (repo root, gitignored).

### REQ-66.1/66.3 — raw counts per instrument (V1)

`signals_considered`, `excluded_no_crt_range` (fvg_fill-confirmed bucket), and `excluded_unaligned` all matched #1's already-captured pre-gate baseline (`crt-detector-key-level-confluence-core/evidence/pre-gate-h4-m15.md`) exactly — confirms Model-1/CRT-range/alignment detection is untouched by this change, as designed (Key Level sourcing only affects `AlignedSignal.key_level`, never `.aligned`).

| Instrument | signals_considered | aligned, non-fvg_fill total (denominator) | never confirmed | **credited an ICTOrderBlock Key Level** | **excluded_no_key_level** | not credited (never_confirmed + excluded_no_key_level) | trades_opened |
|---|---|---|---|---|---|---|---|
| EURUSDm | 142984 | 105061 | 63901 | **6755** | **34405** | 98306 | 430 |
| GBPUSDm | 143054 | 105566 | 64332 | **6640** | **34594** | 98926 | 497 |
| DXYm | 142776 | 104108 | 64299 | **6899** | **32910** | 97209 | 532 |

Full coverage confirmed — a complete count set exists for all 3 instruments (REQ-66.3). No threshold gate applied to any of these numbers (REQ-66.2) — they are reported as measured.

### ICTOrderBlock's own discrimination number (V1), computed identically to FVG's (comparable to obs #449's 1.5–3.0%)

FVG's disclosed figure (`crt-detector-key-level-confluence-core/evidence/real-data-h4-m15.md`, REQ-60.2) is:

```
W = (pre_gate_model1_rows − post_gate_model1_rows) / (signals_considered − excluded_no_crt_range − excluded_unaligned)
```

using `detections.csv` Model-1 row counts before/after the REQ-56 confluence gate. Applying the identical formula to this run (pre-gate row counts reused unchanged from #1's own pre-gate baseline, since Model-1 detection is unaffected by which Key Level source feeds the gate):

| Instrument | pre-gate Model-1 rows | post-gate Model-1 rows (ICTOrderBlock-only, V1) | withheld rows | denominator | **W (ICTOrderBlock, V1)** | FVG's W (obs #449) |
|---|---|---|---|---|---|---|
| EURUSDm | 142984 | 55810 | 87174 | 105061 | **0.8297 (82.97%)** | 0.0266 (2.66%) |
| GBPUSDm | 143054 | 54895 | 88159 | 105566 | **0.8351 (83.51%)** | 0.0150 (1.50%) |
| DXYm | 142776 | 57416 | 85360 | 104108 | **0.8199 (81.99%)** | 0.0304 (3.04%) |

A second, narrower percentage — `excluded_no_key_level` alone as a fraction of the aligned-non-fvg_fill denominator (excludes the never-confirmed signals that never got a chance to check a Key Level at all) — for reference:

| Instrument | excluded_no_key_level / denominator |
|---|---|
| EURUSDm | 0.3275 (32.75%) |
| GBPUSDm | 0.3277 (32.77%) |
| DXYm | 0.3161 (31.61%) |

### Supplementary (V1): trade population size and expectancy (not a REQ-66 requirement, context only)

| Instrument | Pre-gate trades_opened | ICTOrderBlock-only trades_opened (V1) | Pre-gate average R | ICTOrderBlock-only average R (V1) |
|---|---|---|---|---|
| EURUSDm | 2402 | 430 | +0.244 | +0.133 |
| GBPUSDm | 2502 | 497 | +0.270 | +0.299 |
| DXYm | 2838 | 532 | +0.502 | +0.394 |
