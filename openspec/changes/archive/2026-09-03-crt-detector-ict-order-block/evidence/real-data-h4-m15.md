# Real-data H4/M15 evidence (S-000.12/S-003.12, REQ-66) — ICTOrderBlock-only discrimination number

> **Note (2026-09-02): V4 run added — current/authoritative.** V3's run (below, kept for the record) measured a mechanism the user's own mental model said was wrong (Daily-candle-granularity invalidation) — its 99.85–99.95% number is INVALIDATED, not a comparison baseline; it never represented the intended design. V4 (H4-native invalidation, REQ-63.7/spec V4) is the real Daily-tier number. V2's H4-tier run stays valid for its own scope, kept for comparison. V1 stays further below for the full trail.

## V4 run — Daily-tier Order Block Key Levels, H4-native invalidation (current, authoritative)

**What changed from V3**: invalidation of a Daily-sourced Order Block is now checked candle-by-candle against the H4 series (REQ-63.7), not by translating a boundary computed from the Daily series' own full-day touch test. See `design.md` ADR-E ("V3's error, for the record") for the full mechanism writeup — this was a genuine correction, caught only after the user restated their own mental model of how invalidation should work, mid-conversation, after seeing V3's result.

**Isolation**: same technique as V3/V2/V1 — `fvg_key_levels` temporarily hardcoded to `[]` in `cli.py::_detect_all` (`# TEMP: S-003.12 re-run (V4), revert before commit`), all 3 instruments run WITH `--daily-csv`/`--daily-symbol`, evidence captured, then reverted. `git diff cli.py` (post-revert) confirmed clean; full suite (232/233, same 1 pre-existing unrelated failure) and `lint-imports` both green afterward.

**Command**: identical to V3's (see below), output under `.sdd/evidence/crt-detector-ict-order-block-v4/{instrument}/`.

### REQ-66.1/66.3 — raw counts per instrument

| Instrument | signals_considered | denominator | never confirmed | **credited a Daily-tier Key Level** | **excluded_no_key_level** | trades_opened |
|---|---|---|---|---|---|---|
| EURUSDm | 142984 | 105061 | 63901 | **285** | **40875** | 17 |
| GBPUSDm | 143054 | 105566 | 64332 | **401** | **40833** | 31 |
| DXYm | 142776 | 104108 | 64299 | **385** | **39424** | 48 |

Full coverage — a complete count set exists for all 3 instruments (REQ-66.3). No threshold gate applied (REQ-66.2).

### Discrimination number

```
W = (pre_gate_model1_rows − post_gate_model1_rows) / denominator
```

| Instrument | pre-gate Model-1 rows | post-gate Model-1 rows (V4) | denominator | **W (V4, Daily-tier, corrected)** | W (V3, Daily-tier, INVALIDATED) | W (V2, H4-tier) | FVG's W (obs #449) |
|---|---|---|---|---|---|---|---|
| EURUSDm | 142984 | 38733 | 105061 | **0.9923 (99.23%)** | ~~0.9995~~ | 0.9834 | 0.0266 |
| GBPUSDm | 143054 | 38668 | 105566 | **0.9888 (98.88%)** | ~~0.9985~~ | 0.9842 | 0.0150 |
| DXYm | 142776 | 39815 | 104108 | **0.9890 (98.90%)** | ~~0.9989~~ | 0.9804 | 0.0304 |

**The corrected Daily-tier number (98.88–99.23%) lands in the SAME range as V2's H4-tier number (98.0–98.4%)** — a materially different, more sensible outcome than V3's mechanism-bug-driven 99.85–99.95%. 96 real trades open across the 3 instruments (17+31+48), vs. 0 under the (wrong) V3 mechanism.

### Supplementary: trade population size and expectancy (context only, not a REQ-66 requirement)

| Instrument | trades_opened | win rate | average R | total R |
|---|---|---|---|---|
| EURUSDm | 17 | 0.235 (4W/13L) | +0.207 | +3.516 |
| GBPUSDm | 31 | 0.258 (8W/23L) | +0.302 | +9.354 |
| DXYm | 48 | 0.229 (11W/37L) | +0.788 | +37.830 |

Reported as measured, no interpretation attached.

### Go/no-go: does NOT trigger the escalation this time

Spec's Success Criteria go/no-go rule fires when the figure is "ALSO in the 1–3% range." 98.88–99.23% is nowhere near that band, and now sits alongside V2's own H4-tier number rather than in an unexplained new extreme. This run does NOT halt — the mechanism correction resolved the anomaly that triggered V3's halt.

---

## V3 run — Daily-tier Order Block Key Levels, Daily-native invalidation (SUPERSEDED — mechanism was wrong, kept for the record only)

**Isolation**: same technique as V2/V1 — `fvg_key_levels` temporarily hardcoded to `[]` in `cli.py::_detect_all` (`# TEMP: S-003.12 isolation run, revert before commit`), all 3 instruments run WITH `--daily-csv`/`--daily-symbol`, evidence captured, then reverted. `git diff cli.py` (post-revert) confirmed clean — no trace of the temporary edit, full test suite (232/233, same 1 pre-existing unrelated failure as before) and `lint-imports` both green afterward.

**Command** (per instrument, run from repo root):
```
./detector/.venv/Scripts/python.exe -m detector.cli \
  --csv pairs/M15/{instrument}_M15_*.csv --symbol {instrument} \
  --htf-csv pairs/H4/{instrument}_H4_*.csv --htf-symbol {instrument} \
  --daily-csv pairs/D1/{instrument}_Daily_*.csv --daily-symbol {instrument} \
  --output-dir .sdd/evidence/crt-detector-ict-order-block-v3/{instrument} --backtest
```
All three runs completed in ~49s wall clock each. Output under `.sdd/evidence/crt-detector-ict-order-block-v3/{instrument}/` (repo root, gitignored).

**Build-preflight discovered while running this (not caught by the design's "Daily data availability" check, which only verified file EXISTENCE)**: MT5's Daily (D1) export omits the `<TIME>` column entirely (no intraday time on a daily bar) — `ingestion/loader.py::load_mt5_csv` required it unconditionally and rejected every Daily CSV with "missing required column(s): <TIME>". Fixed (TDD, `tests/test_loader.py::test_loads_daily_csv_with_no_time_column_defaulting_to_midnight`): `<TIME>` is now optional, defaulting the time-of-day to midnight when absent.

### REQ-66.1/66.3 — raw counts per instrument

`signals_considered`, `excluded_no_crt_range`, `excluded_unaligned`, and `never_confirmed` all matched V2's H4-tier run exactly — confirms Model-1/CRT-range/alignment detection is unaffected by the pivot, as designed.

| Instrument | signals_considered | aligned, non-fvg_fill total (denominator) | never confirmed | **credited a Daily-tier ICTOrderBlock Key Level** | **excluded_no_key_level** | trades_opened |
|---|---|---|---|---|---|---|
| EURUSDm | 142984 | 105061 | 63901 | **0** | **41135** | 0 |
| GBPUSDm | 143054 | 105566 | 64332 | **0** | **41176** | 0 |
| DXYm | 142776 | 104108 | 64299 | **0** | **39764** | 0 |

Full coverage — a complete count set exists for all 3 instruments (REQ-66.3). No threshold gate applied to any of these numbers (REQ-66.2) — reported as measured.

### Discrimination number, same formula as V2/FVG

```
W = (pre_gate_model1_rows − post_gate_model1_rows) / denominator
```

| Instrument | pre-gate Model-1 rows | post-gate Model-1 rows (Daily-tier ICTOrderBlock) | denominator | **W (Daily-tier)** | W (V2, H4-tier) | FVG's W (obs #449) |
|---|---|---|---|---|---|---|
| EURUSDm | 142984 | 37980 | 105061 | **0.9995 (99.95%)** | 0.9834 | 0.0266 |
| GBPUSDm | 143054 | 37643 | 105566 | **0.9985 (99.85%)** | 0.9842 | 0.0150 |
| DXYm | 142776 | 38785 | 104108 | **0.9989 (99.89%)** | 0.9804 | 0.0304 |

**Daily-tier is MORE restrictive than V2's H4-tier run** (99.85–99.95% exclusion vs. 98.0–98.4%), not less — the opposite of what the Daily-tier pivot was expected to plausibly improve.

### Root cause investigated before reporting this as a finding, not a bug

0 credited signals across all 3 instruments was suspicious enough to verify before disclosure (diagnostic script against real EURUSDm data, not just trusting the CLI output):

- Daily-series detection itself works: 222 Order Blocks detected on EURUSDm's Daily series (not zero) — the detector, `_reindex_daily_key_levels`, and `_key_level_credit_map` all execute correctly; 4 of 8834 H4 purges DO get credited to a reindexed Daily Key Level (proves the mechanism functions), just too few to land on a surviving LTF Model-1 signal.
- **Mechanism identified**: 134 of 222 detected Order Blocks (60%) have a Daily-space validity window of exactly 1 day (confirmed on day D, invalidated on day D+1 — first-touch invalidation is far more punishing at Daily granularity than H4, since a full day's range very often revisits the prior day's zone). ADR-E's reindexing is deliberately conservative on BOTH edges — `origin_index` reindexes from the confirming day's CLOSE (= day D+1's open), `expiry_index` reindexes from the invalidating day's own OPEN (= day D+1's open, the SAME instant for a 1-day window) — so these 134 Order Blocks reindex to `origin_index == expiry_index`, a window that can never satisfy `origin_index < purge_index <= expiry_index` for ANY purge. This is a real, correctly-derived CONSEQUENCE of ADR-E's stated conservative-both-ways policy, not an implementation bug — confirmed by re-deriving the boundary arithmetic by hand against 5 real detected Order Blocks.
- The remaining 88 Order Blocks (40%, window ≥ 2 days) DO have a real usable H4-index window, and are what produced the 4 credited purges — but even those rarely land on a surviving LTF Model-1 signal, on top of the exact-overlap-no-tolerance zone requirement (REQ-63.6).

**This is disclosed as a genuine measured finding per REQ-66.2 (no threshold gate on the value), not withheld or reinterpreted** — but the ADR-E conservativeness question it surfaces (should a 1-day Daily window really be maximally conservative on both edges, discarding it entirely, vs. giving it e.g. a partial day's credit?) is a real, unresolved design/product question this run was not scoped to answer unilaterally.

### HALT — per design's Success Criteria go/no-go rule (RESOLVED by the V4 mechanism fix, not by accepting this number)

99.85–99.95% exclusion is not merely "also in the 1-3% range" (spec.md's literal trigger wording) — it is MORE extreme than that band, and more extreme than V2's own H4-tier number. Per spec.md's Success Criteria ("if ICTOrderBlock's Daily-tier discrimination is ALSO in the 1–3% range... escalate to the user before automatically proceeding to `crt-detector-breaker-block` (#3)"), this run HALTED here and was escalated to the user in-conversation. **Resolution**: the escalation surfaced a real mechanism bug (Daily-granularity invalidation instead of H4-granularity), not a product finding to accept or reject — fixed under REQ-63.7, re-measured as "## V4 run" above (98.88–99.23%, does NOT re-trigger the go/no-go band). This number (99.85–99.95%) is kept here as the record of what was wrong, not as evidence about the confluence-gate concept.

---

## V2 run — immediate-engulfing rule, H4-tier (superseded in SCOPE by V3's Daily-tier pivot; numbers below remain valid for V2's own rule/data)

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
