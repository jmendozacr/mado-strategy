# Slices: crt-detector-key-level-confluence-core

**Triage**: L | **Spec version**: V3 signed | **Design version**: V3 | **Total slices**: 7 (1 skeleton + 6 SPIDR)

## V3 Change Log (vs slices V2)

1. **S-000.1 rewritten** (design §8.5): supplements obs #419 in place across EURUSDm/GBPUSDm/DXYm; EURUSDm's match against obs #419 IS the still-valid gate (mismatch halts) — no re-capture, no re-run of the cost sweep.
2. **S-000's acceptance band corrected** (design §9.1): `W`'s numerator is the CSV-gate withheld count (pre/post `detections.csv` Model-1 row delta), not `excluded_no_key_level` (which caps at 0.392 — the unreachable-bound defect verify-plan-2 #7 raised). Adds binding REQ-60.3 (≥50 trades) and REQ-60.4 (halt on average-R regression vs. pre-gate baseline, strict, no tolerance).
3. **New S-000.3** — `_HTF_DAILY_MIXED` fixture (design §8.10), extending S-000.2's redesign; feeds S-005.3/REQ-40.6's non-zero-bucket assertion. S-000 grows to 9 tasks — a justified single-context addition tightly coupled to S-000.2's fixture, not scope creep.
4. **S-005 gains REQ-46.1/.2 + a NEW dedup-after-confluence assertion** (design §8.11): the confluence cut now precedes dedup, so a duplicate group straddling it collapses differently — genuinely new coverage, not re-labelling. Also promotes REQ-40.2's rewritten assertion (folded into S-005.3) and REQ-53.4 (already S-005.6's test, now named explicitly) out of implicit-regression status.
5. **REQ-55.13 → S-003** (new task S-003.7), not S-000: spec-tagged "alternate" (edge, not happy); its production logic already ships via S-000.6's both-sides pooling; S-003 already owns the sibling precedence scenario REQ-55.12. Keeps S-000 minimal per walking-skeleton discipline — the real-data e2e run (14.1% both-sides incidence) exercises the underlying logic regardless.
6. **S-002.5 / REQ-55.11 inverted**: `expiry_index == purge_index` is now CREDITED (right-closed window) — was excluded in V2. Given/When/Then and task wording flipped.

---

## S-000: Walking Skeleton — confluence gate (with expiry) live end-to-end on real H4/M15

**Scope**: walking-skeleton | **Dimension**: — | **Requires**: nothing
**Covers**: REQ-53.1, REQ-55.1, REQ-55.2, REQ-55.6, REQ-55.7, REQ-56.1, REQ-56.7, REQ-30.7, REQ-40.1, REQ-60.1, REQ-60.2, REQ-60.3, REQ-60.4
**Test layers**: unit + e2e (real EURUSDm H4/M15 pair, `--backtest`)

**Acceptance**: GIVEN a real H4/M15 pair with `--backtest` (post-implementation), THEN `trades_opened + sum(8 buckets) == signals_considered` exactly; the withheld fraction `W = (pre-gate − post-gate detections.csv Model-1 row count) / (signals_considered − excluded_no_crt_range − excluded_unaligned)` falls in `[0.10, 0.75]` (REQ-60.2); `trades_opened >= 50` (REQ-60.3); AND post-gate average R is not below the pre-gate baseline's average R, strict comparison, no tolerance (REQ-60.4) — any failure HALTS before S-001..S-006 (design §9.1).

### Tasks
- [ ] S-000.1 Supplement the pre-gate baseline (obs #419) in place — run the pre-gate command on EURUSDm/GBPUSDm/DXYm into `.sdd/evidence/.../pre-gate/{instrument}/`; EURUSDm's `metrics_summary.txt` MUST match obs #419's recorded block exactly (mismatch HALTS — baseline no longer describes HEAD); record all three into `evidence/pre-gate-h4-m15.md` incl. `detections.csv` Model-1 row counts; `mem_update` obs #419 (no re-run of its cost sweep). (design §8.5)
- [ ] S-000.2 **`_HTF_DAILY` e2e fixture redesign** (design §8.2) — 6-candle layout (FVG on 0/1/2, CRT range at 3, purge at 4, trailing at 5); re-baselines ~20 dependent assertions in `test_cli_backtest_e2e.py`. Single largest risk in this slice — do it early, in isolation.
- [ ] S-000.3 **`_HTF_DAILY_MIXED` mixed-population fixture** (design §8.10, NEW) — extends S-000.2's fixture with a second HTF purge (indices 6-8) + second-day LTF block, one confluent signal and one not, in the SAME run; feeds S-005.3's REQ-40.6 non-zero-bucket assertion. Apply MUST verify via `detect_fvgs` that no stray FVG forms on 3..8.
- [ ] S-000.4 `core/key_level.py` — `KeyLevel` frozen dataclass (`kind, top, bottom, origin_index, expiry_index`)
- [ ] S-000.5 `primitives/fvg.py::to_key_levels` — `origin_index=end_index`; `expiry_index` from `fill_status`/`fill_index` (REQ-53.1)
- [ ] S-000.6 `alignment/htf_ltf.py` — `AlignedSignal.key_level`, `htf_key_levels` param, `_key_level_credit_map` (three conjuncts incl. right-closed expiry), `_purge_wick_extremes` (plural — both breached sides pooled independently, REQ-55.6/.7 — NEVER `ltf_signal.direction`)
- [ ] S-000.7 `cli.py::_detect_all` (local HTF Key Levels via same `config.fvg`, §8.6) + `_filter_to_confluent` (adds the `fvg_fill` disjunct, REQ-56.7) inserted after the `population` snapshot
- [ ] S-000.8 `backtest/simulate.py::_PopulationCuts`/`ReconciliationReport.excluded_no_key_level` + `viz/trades_table.py`'s `no key level:` line + `tests/fixtures/synthetic.py::key_level_confluence_pair_setup(confluent)` / `tests/fixtures/mt5_csv.py::write_series_csv` builders (§8.9) + unit test for REQ-55.1/.2
- [ ] S-000.9 e2e: real EURUSDm H4/M15 `--backtest` run — record REQ-60 evidence to `evidence/real-data-h4-m15.md`; verify `W`, the ≥50-trade floor (REQ-60.3), and average-R non-regression (REQ-60.4); GBPUSDm/DXYm as corroboration

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

## S-002: Validity window — knowable-start, mitigation-end-inclusive, lookahead-safe under truncation

**Scope**: edge-case | **Dimension**: R (Rule) | **Requires**: nothing
**Covers**: REQ-54.1, REQ-54.2, REQ-54.3, REQ-54.4, REQ-54.5, REQ-55.9, REQ-55.10, REQ-55.11
**Test layers**: unit + property

**Acceptance**: GIVEN `origin_index=n`, THEN present when re-derived from the first `n+1` candles, absent from the first `n`. GIVEN a purge at `p` and its credited Key Level, THEN re-deriving levels from the first `p+1` HTF candles yields the identical credit outcome (REQ-54.5). GIVEN `expiry_index=60` and purge `80`, THEN not credited; `expiry_index=90`, THEN credited; `expiry_index==80` (the purge candle IS the fill candle), THEN CREDITED — right-closed, V3-corrected (REQ-55.11).

### Tasks
- [ ] S-002.1 `test_fvg.py`: FVG at 40/41/42 → `origin_index==42` (REQ-54.1)
- [ ] S-002.2 `test_no_lookahead.py`: two-sided `origin_index` boundary property (REQ-54.2/.3)
- [ ] S-002.3 `test_no_lookahead.py`: per-truncation Key Level injection strengthens the existing alignment property to REQ-54.5 (design §8.3) — this IS REQ-54.5's home, no separate test
- [ ] S-002.4 `test_alignment.py`: `origin_index >= purge_index` → no credit (REQ-54.4)
- [ ] S-002.5 `test_alignment.py`: `expiry_index` 60<80 not credited / 90>80 credited / ==80 **CREDITED** — right-closed boundary, V3-corrected from V2's exclusion (REQ-55.9/.10/.11)

---

## S-003: Confluence geometry & precedence — no tolerance, inclusive edges, earliest-origin wins, gate stays surgical

**Scope**: edge-case | **Dimension**: R (Rule) | **Requires**: nothing
**Covers**: REQ-55.3, REQ-55.4, REQ-55.5, REQ-55.8, REQ-55.12, REQ-55.13, REQ-40.5, REQ-30.4
**Test layers**: unit

**Acceptance**: GIVEN a credited extreme 1 tick outside a Key Level zone, THEN no credit; exactly on `bottom`, THEN credited. GIVEN `unaligned`/`insufficient_htf_data`, THEN `None` recorded — not a negative determination. GIVEN two qualifying unexpired levels, THEN the lowest `origin_index` wins. GIVEN a both-sides breach where only the low-side extreme's zone matches, THEN confluence holds via the low-side level (REQ-55.13 — the case V2's high-always rule wrongly failed). GIVEN a signal both unaligned and non-confluent, THEN `excluded_unaligned` wins over `excluded_no_key_level`; GIVEN an `fvg_fill`-confirmed signal, THEN `excluded_no_crt_range` wins, never `excluded_no_key_level`.

### Tasks
- [ ] S-003.1 `test_alignment.py`: proximity miss (1 tick outside) → no credit (REQ-55.3)
- [ ] S-003.2 `test_alignment.py`: boundary touch on `bottom` → credited (REQ-55.4)
- [ ] S-003.3 `test_alignment.py`: unaligned/insufficient → `None`, not negative (REQ-55.5)
- [ ] S-003.4 `test_alignment.py`: unfilled level, earlier origin → credited (REQ-55.8)
- [ ] S-003.5 `test_alignment.py`: two qualifying levels → lowest `origin_index` wins (REQ-55.12)
- [ ] S-003.6 `test_backtest_simulate.py`: unaligned+non-confluent precedence (REQ-40.5); `fvg_fill` precedence over confluence (REQ-30.4)
- [ ] S-003.7 `test_alignment.py`: both-sides breach, only low-side extreme qualifies → confluence holds, low-side level recorded (REQ-55.13, NEW V3 — placed here not S-000: spec-tagged "alternate"/edge, production logic already ships via S-000.6's pooling, sibling to S-003's REQ-55.12 precedence scenario)

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

## S-005: Population invariants & single source of truth — reconciliation holds, dedup runs post-confluence, confluence read never recomputed

**Scope**: edge-case | **Dimension**: R (Rule) | **Requires**: S-004
**Covers**: REQ-40.2, REQ-40.4, REQ-40.6, REQ-46.1, REQ-46.2, REQ-53.4, REQ-59.1, REQ-59.2, SEAM-01
**Test layers**: unit + e2e + architectural

**Acceptance**: GIVEN a mixed population, THEN every signal lands in exactly one of `trades_opened` or the 8 buckets; every traded `signal_id` joins one `detections.csv` Model-1 row; flipping one signal's recorded `key_level` moves its CSV presence and bucket membership together, never independently; 3 identical-tuple candidates collapse to 1 survivor and a `key_level=None` duplicate-group member lands in `excluded_no_key_level`, never `excluded_duplicate` (dedup runs on the post-confluence survivor set); `alignment/htf_ltf.py` imports only the frozen SEAM-01 allow-list.

### Tasks
- [ ] S-005.1 `test_backtest_metrics.py`: PENDING+retest resolves through the 5 later cuts (REQ-40.4)
- [ ] S-005.2 `test_backtest_simulate.py`: per-signal exclusive bucket membership, mixed population
- [ ] S-005.3 `test_cli_backtest_e2e.py`: gated signal still counted, bucket non-zero, using §8.10's mixed fixture (REQ-40.6); `signals_considered` assertion REWRITTEN to derive independently of `detections.csv` Model-1 row count, V3-corrected (REQ-40.2)
- [ ] S-005.4 `test_cli_backtest_e2e.py`: every traded `signal_id` is a Model-1 CSV row (REQ-59.1)
- [ ] S-005.5 `test_cli.py`: flipping one `key_level` moves CSV row and bucket together, scoped to signals reaching the confluence check (REQ-59.2, V3-scoped)
- [ ] S-005.6 `test_fitness_imports.py`: SEAM-01 AST import allow-list — consumer-coupling (REQ-53.4, design §8.4)
- [ ] S-005.7 `test_backtest_simulate.py`: REQ-46.1 (3 identical-tuple candidates → 1 survivor, 2 `excluded_duplicate`) + REQ-46.2 (different `entry_type` → both survive), re-verified against the `_PopulationCuts` record (design §8.11)
- [ ] S-005.8 `test_backtest_simulate.py`: NEW — duplicate group member with `key_level=None` is counted in `excluded_no_key_level`, never `excluded_duplicate`; dedup operates on the post-confluence survivor set (design §8.11)

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
| 1 | S-000 | skeleton — blocks all others; task S-000.9's band/floor/regression check gates S-001..S-006 |
| 2 | S-001, S-002, S-003, S-004 | independent, parallelizable |
| 3 | S-005, S-006 | both require S-004 only, parallelizable with each other |

## Anti-Pattern Check

Pass — no horizontal/layer-named slices, every slice single-dimension with ≥1 REQ-ID and ≤2 dependencies; 7 total (skeleton + 6), matching the L target. All 59 spec V3 scenarios (41 new-domain + 18 delta) covered: 51 map to an explicit slice `Covers` entry; the remaining 8 regression-tagged delta scenarios (REQ-30.1/.2/.3/.5/.6, REQ-40.3, REQ-45.1/.2) are preserved by not breaking the existing test files each slice touches, per design's Test Derivation table. REQ-40.2 and REQ-46.1/.2, implicit-regression in V2, are now explicit S-005 coverage (design V3 §8.11, verify-plan-2 #6/#9).
