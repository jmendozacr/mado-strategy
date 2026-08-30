# Slices: crt-detector-key-level-confluence-core

**Triage**: L | **Spec version**: V2 signed | **Design version**: V2 | **Total slices**: 7 (1 skeleton + 6 SPIDR)

---

## S-000: Walking Skeleton — confluence gate (with expiry) live end-to-end on real H4/M15

**Scope**: walking-skeleton | **Dimension**: — | **Requires**: nothing
**Covers**: REQ-53.1, REQ-55.1, REQ-55.2, REQ-55.6, REQ-55.7, REQ-56.1, REQ-56.7, REQ-30.7, REQ-40.1, REQ-60.1, REQ-60.2
**Test layers**: unit + e2e (real EURUSDm H4/M15 pair, `--backtest`)

**Acceptance**: GIVEN a real H4/M15 pair with `--backtest` (post-implementation), THEN `metrics_summary.txt` shows a non-zero `no key level:` line, `trades_opened + sum(8 buckets) == signals_considered` exactly, AND the withheld fraction `W = excluded_no_key_level / |aligned non-fvg_fill signals|` falls in `[0.10, 0.75]` with ≥50 trades opened — outside that band HALTS before S-001..S-006 (REQ-60.2, design §9.1).

### Tasks
- [ ] S-000.1 Confirm the pre-gate baseline (`sdd/crt-detector-key-level-confluence-core/pre-gate-baseline`, obs #419) is still valid against current HEAD — reference it, do not re-run. This is the last reproducible moment; no code changes yet.
- [ ] S-000.2 **`_HTF_DAILY` e2e fixture redesign** (design §8.2) — 6-candle layout (FVG on 0/1/2, CRT range at 3, purge at 4, trailing at 5); re-baselines ~20 dependent assertions in `test_cli_backtest_e2e.py`. Single largest risk in this slice — do it early, in isolation.
- [ ] S-000.3 `core/key_level.py` — `KeyLevel` frozen dataclass (`kind, top, bottom, origin_index, expiry_index`)
- [ ] S-000.4 `primitives/fvg.py::to_key_levels` — `origin_index=end_index`; `expiry_index` from `fill_status`/`fill_index` (REQ-53.1)
- [ ] S-000.5 `alignment/htf_ltf.py` — `AlignedSignal.key_level`, `htf_key_levels` param, `_key_level_credit_map` (three conjuncts incl. expiry), `_purge_wick_extreme` (breach-side selection, REQ-55.6/.7 — NEVER `ltf_signal.direction`)
- [ ] S-000.6 `cli.py::_detect_all` (local HTF Key Levels via same `config.fvg`, §8.6) + `_filter_to_confluent` (adds the `fvg_fill` disjunct, REQ-56.7) inserted after the `population` snapshot
- [ ] S-000.7 `backtest/simulate.py::_PopulationCuts`/`ReconciliationReport.excluded_no_key_level` + `viz/trades_table.py`'s `no key level:` line + `tests/fixtures/synthetic.py::key_level_confluence_pair_setup(confluent)` / `tests/fixtures/mt5_csv.py::write_series_csv` builders (§8.9) + unit test for REQ-55.1/.2
- [ ] S-000.8 e2e: real EURUSDm H4/M15 `--backtest` run — record REQ-60 evidence to `evidence/real-data-h4-m15.md`; verify `W` and trade-count band; GBPUSDm/DXYm as corroboration

---

## S-001: FVG source normalisation — mitigation sets an expiry window, absence/non-pairing withhold nothing

**Scope**: happy-path | **Dimension**: D (Data) | **Requires**: nothing
**Covers**: REQ-53.2, REQ-53.3, REQ-56.6
**Test layers**: unit

**Acceptance**: GIVEN two FVGs identical except fill state (one filled at index 120, one open), THEN the filled one's `KeyLevel.expiry_index == 120` and the open one's is `None`, otherwise equal in every field. GIVEN no HTF FVG detected, THEN an empty list, not error/`None`. GIVEN no HTF pair supplied, THEN nothing is withheld.

### Tasks
- [ ] S-001.1 `test_fvg.py`: filled (fill_index=120) vs open FVG → `expiry_index` set vs `None`, otherwise equal (REQ-53.2)
- [ ] S-001.2 `test_fvg.py`: no FVG detected → empty list, not error/`None` (REQ-53.3)
- [ ] S-001.3 `test_cli.py`: single-series mode → nothing withheld (REQ-56.6)

---

## S-002: Validity window — knowable-start, mitigation-end, lookahead-safe under truncation

**Scope**: edge-case | **Dimension**: R (Rule) | **Requires**: nothing
**Covers**: REQ-54.1, REQ-54.2, REQ-54.3, REQ-54.4, REQ-54.5, REQ-55.9, REQ-55.10, REQ-55.11
**Test layers**: unit + property

**Acceptance**: GIVEN `origin_index=n`, THEN present when re-derived from the first `n+1` candles, absent from the first `n`. GIVEN a purge at `p` and its credited Key Level, THEN re-deriving levels from the first `p+1` HTF candles yields the identical credit outcome (REQ-54.5). GIVEN `expiry_index=60` and purge `80`, THEN not credited; `expiry_index=90`, THEN credited; `expiry_index==80`, THEN not credited (inclusive of its own index).

### Tasks
- [ ] S-002.1 `test_fvg.py`: FVG at 40/41/42 → `origin_index==42` (REQ-54.1)
- [ ] S-002.2 `test_no_lookahead.py`: two-sided `origin_index` boundary property (REQ-54.2/.3)
- [ ] S-002.3 `test_no_lookahead.py`: per-truncation Key Level injection strengthens the existing alignment property to REQ-54.5 (design §8.3) — this IS REQ-54.5's home, no separate test
- [ ] S-002.4 `test_alignment.py`: `origin_index >= purge_index` → no credit (REQ-54.4)
- [ ] S-002.5 `test_alignment.py`: `expiry_index` 60<80 not credited / 90>80 credited / ==80 not credited (REQ-55.9/.10/.11)

---

## S-003: Confluence geometry & precedence — no tolerance, inclusive edges, earliest-origin wins, gate stays surgical

**Scope**: edge-case | **Dimension**: R (Rule) | **Requires**: nothing
**Covers**: REQ-55.3, REQ-55.4, REQ-55.5, REQ-55.8, REQ-55.12, REQ-40.5, REQ-30.4
**Test layers**: unit

**Acceptance**: GIVEN a credited extreme 1 tick outside a Key Level zone, THEN no credit; exactly on `bottom`, THEN credited. GIVEN `unaligned`/`insufficient_htf_data`, THEN `None` recorded — not a negative determination. GIVEN two qualifying unexpired levels, THEN the lowest `origin_index` wins. GIVEN a signal both unaligned and non-confluent, THEN `excluded_unaligned` wins over `excluded_no_key_level`; GIVEN an `fvg_fill`-confirmed signal, THEN `excluded_no_crt_range` wins, never `excluded_no_key_level`.

### Tasks
- [ ] S-003.1 `test_alignment.py`: proximity miss (1 tick outside) → no credit (REQ-55.3)
- [ ] S-003.2 `test_alignment.py`: boundary touch on `bottom` → credited (REQ-55.4)
- [ ] S-003.3 `test_alignment.py`: unaligned/insufficient → `None`, not negative (REQ-55.5)
- [ ] S-003.4 `test_alignment.py`: unfilled level, earlier origin → credited (REQ-55.8)
- [ ] S-003.5 `test_alignment.py`: two qualifying levels → lowest `origin_index` wins (REQ-55.12)
- [ ] S-003.6 `test_backtest_simulate.py`: unaligned+non-confluent precedence (REQ-40.5); `fvg_fill` precedence over confluence (REQ-30.4)

---

## S-004: Non-backtest gate — CSV/chart withhold only non-confluent Model-1, structurally never narrowed by results filters

**Scope**: happy-path | **Dimension**: P (Path) | **Requires**: nothing
**Covers**: REQ-56.2, REQ-56.3, REQ-56.4, REQ-56.5, REQ-57.1, REQ-57.2, REQ-57.3, REQ-58.1, REQ-58.2, REQ-58.3
**Test layers**: unit + e2e

**Acceptance**: GIVEN a run without `--backtest` over a mixed population, THEN only non-confluent, non-`fvg_fill` `aligned` Model-1 rows/markers are withheld; every other row, the 7-column header, and `overlay.png` are unaffected; HTF FVGs never render; `--from-date`/`--session` never change a surviving detection's confluence outcome; the detections record itself carries no Key Level field.

### Tasks
- [ ] S-004.1 `test_cli.py`: unaligned/insufficient and non-Model-1 rows unchanged (REQ-56.4)
- [ ] S-004.2 `test_cli.py`: `_Detections` field-name allow-list holds — no Key Level field (REQ-58.1, architectural)
- [ ] S-004.3 `test_cli_e2e.py`: gate bites (no row/marker); 7-column header byte-identical (REQ-56.2/.5)
- [ ] S-004.4 `test_cli_e2e.py`: differential minimal pair (S-000's builder) — only gated rows differ (REQ-56.3)
- [ ] S-004.5 `test_cli_e2e.py`: HTF Key Levels available, not drawn; `--types fvg` stays LTF-only (REQ-57.1–.3)
- [ ] S-004.6 `test_cli_e2e.py`: `--from-date`/`--session` don't change confluence outcomes (REQ-58.2/.3)

---

## S-005: Population invariants & single source of truth — reconciliation holds, confluence read never recomputed

**Scope**: edge-case | **Dimension**: R (Rule) | **Requires**: S-004
**Covers**: REQ-40.4, REQ-40.6, REQ-59.1, REQ-59.2, SEAM-01
**Test layers**: unit + e2e + architectural

**Acceptance**: GIVEN a mixed population, THEN every signal lands in exactly one of `trades_opened` or the 8 buckets; every traded `signal_id` joins one `detections.csv` Model-1 row; flipping one signal's recorded `key_level` moves its CSV presence and bucket membership together, never independently; `alignment/htf_ltf.py` imports only the frozen SEAM-01 allow-list.

### Tasks
- [ ] S-005.1 `test_backtest_metrics.py`: PENDING+retest resolves through the 5 later cuts (REQ-40.4)
- [ ] S-005.2 `test_backtest_simulate.py`: per-signal exclusive bucket membership, mixed population
- [ ] S-005.3 `test_cli_backtest_e2e.py`: gated signal still counted, bucket non-zero (REQ-40.6)
- [ ] S-005.4 `test_cli_backtest_e2e.py`: every traded `signal_id` is a Model-1 CSV row (REQ-59.1)
- [ ] S-005.5 `test_cli.py`: flipping one `key_level` moves CSV row and bucket together (REQ-59.2)
- [ ] S-005.6 `test_fitness_imports.py`: SEAM-01 AST import allow-list (design §8.4)

---

## S-006: Byte-compat — `--backtest` is the only difference between two runs

**Scope**: edge-case | **Dimension**: D (Data) | **Requires**: S-004
**Covers**: REQ-45.1, REQ-45.2, REQ-45.3
**Test layers**: e2e (regression + new differential)

**Acceptance**: GIVEN two otherwise-identical runs differing only by `--backtest`, THEN `overlay.png` is byte-identical and `detections.csv` differs only by the trailing `signal_id` column.

### Tasks
- [ ] S-006.1 `test_cli_backtest_e2e.py`: `--session ny-killzone --backtest` overlay byte-identical
- [ ] S-006.2 `test_cli_backtest_e2e.py`: 13-column `trades.csv` header
- [ ] S-006.3 `test_cli_backtest_e2e.py`: differential byte-identity vs non-backtest run (REQ-45.3)

---

## Build Order

| Order | Slice(s) | Note |
|---|---|---|
| 1 | S-000 | skeleton — blocks all others; task S-000.8's band check gates S-001..S-006 |
| 2 | S-001, S-002, S-003, S-004 | independent, parallelizable |
| 3 | S-005, S-006 | both require S-004 only, parallelizable with each other |

## Anti-Pattern Check

Pass — no horizontal/layer-named slices, every slice single-dimension with ≥1 REQ-ID and ≤1 dependency; 7 total (skeleton + 6), matching the L target. All 44 non-regression REQ scenarios (37 new `key-level-confluence` domain + 7 non-regression delta scenarios: REQ-30.4/.7, REQ-40.1/.4/.5/.6, REQ-45.3) map to exactly one slice; the 11 regression-tagged delta scenarios (REQ-30.1/.2/.3/.5/.6, REQ-40.2/.3, REQ-45.1/.2, REQ-46.1/.2) are preserved by not breaking the existing test files each slice touches, per design's Test Derivation table.

---

## V2 Change Log (vs slices V1)

Revision against re-signed spec V2 and design V2 (7 slices retained, count unchanged — new REQs folded into existing slices rather than adding new ones):

1. **S-000 materially expanded**: gained REQ-55.6/.7 (wick-extreme breach-side selection — corrects V1's inverted `direction`-based rule), REQ-56.7 (`fvg_fill` untouched by the gate), REQ-60.1/.2 (quantitative real-data gate, not just non-zero). Task list rewritten: task 1 is now baseline confirmation (already captured, obs #419, referenced not re-run); task 2 gives the `_HTF_DAILY` 6-candle redesign explicit top billing as the single largest risk (design §8.2), re-baselining ~20 tests in `test_cli_backtest_e2e.py`; task 8's e2e acceptance is now the numeric band `0.10 ≤ W ≤ 0.75` with ≥50 trades (design §9.1), replacing V1's "non-zero" bar — falling outside it HALTS before S-001..S-006.
2. **S-001** acceptance re-worded: REQ-53.2 now asserts expiry-index derivation from fill state (V1 asserted the opposite — that mitigation must NOT move levels).
3. **S-002** (was "no-lookahead", now "validity window") absorbs REQ-54.5 (expiry is lookahead-safe under HTF truncation — homed in the existing alignment property per design §8.3, no separate test) and REQ-55.9/.10/.11 (expiry boundary: before/after/inclusive-of purge index).
4. **S-003** (confluence geometry) gains REQ-55.8 (unfilled level counts), REQ-55.12 (earliest-origin-wins on multiple matches), and REQ-30.4 (`fvg_fill` precedence over the confluence cut, alongside REQ-40.5's unaligned precedence — both are existing branch-order behavior, verified not reordered).
5. **S-004** (non-backtest gate) gains REQ-58.1–.3 (Key Levels structurally absent from `_Detections`; `--from-date`/`--session` don't change confluence outcomes) — new in V2, was V1's finding #5.
6. **S-005** (population invariants) drops REQ-42.1 (superseded — the spec's delta domain leaves it unmodified) in favour of REQ-59.1/.2 (confluence determined once, read never recomputed — the stronger, explicit V2 requirement); gains REQ-40.6 (gate never shrinks `signals_considered`).
7. **S-006** unchanged in substance; REQ-45.3's differential byte-compat anchor is now explicit (was implicit "regression" framing in V1; ADR-016 formalises the re-anchoring).
8. Dropped from every slice's fitness framing: V1's cross-artefact `count(model1 rows) == considered - excluded_no_key_level` equality (design finding #7 — arithmetically false). Slices now rely on design §10's two independently-correct assertions plus one-directional containment, exercised inside S-004/S-005's e2e tasks rather than as a standalone check.
