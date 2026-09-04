# Slices: crt-detector-ict-order-block

**Triage**: M | **Spec version**: V3 signed (REQ-61..67) | **Design version**: V3 (`architecture_impact: additive`) | **Total slices**: 4 (S-000/S-001 DONE — V2 baseline, listed for reference only; S-002/S-003 remain to build)

## Branch Handling — RESOLVED, no action needed

The change already branched off `wip/crt-detector-key-level-confluence-core-s000` per the original S-000 plan; current branch `crt-detector-ict-order-block` (commit `085da8c`, "S-000 V1+V2 built and measured, paused for Daily-tier pivot") already carries that history. S-002/S-003 below continue on this SAME branch — do not re-branch.

---

## S-000: Walking Skeleton — ICTOrderBlock detection (base rule + invalidation) live end-to-end on real H4/M15 — **DONE (V2 shape)**

Reference only. Confirmed present in code: `primitives/ict_order_block.py` (immediate-engulfing detection + first-touch invalidation, REQ-61/62), `to_key_levels` (REQ-63.1/63.2), `cli.py`'s H4-scoped composition (REQ-63.3's V2-era "zero change" claim), real-data evidence at `openspec/changes/crt-detector-ict-order-block/evidence/real-data-h4-m15.md` (REQ-66, V2's H4-tier number: 98.0–98.4%). No V3 work reopens this slice — design confirmed `primitives/ict_order_block.py` needs zero code changes for V3.

## S-001: No-lookahead safety — **DONE**

Reference only. Confirmed present: `tests/property/test_no_lookahead.py::test_ict_order_block_detection_has_no_lookahead` (REQ-64/64.1). Unaffected by V3 — the property is about `detect_ict_order_blocks`'s own prefix-consistency, independent of which series it's called with.

---

## S-002: `detections.csv` gains `key_level_source` (REQ-24/41.3 reopened, confluence-core's REQ-56.5 flagged) — **PENDING, unaffected by V3**

**Scope**: happy-path | **Requires**: S-000 (done) | **Independent of S-003**
**Covers**: REQ-24.2, REQ-24.3, REQ-65, REQ-65.1, REQ-41.3 (MOD)
**Test layers**: unit

Confirmed still pending: `viz/table.py::_HEADER` is still 7 columns (`[..., "aligned"]`), no `key_level_source`. This slice is untouched by the Daily-tier pivot — `key_level_source` just threads `KeyLevel.kind` through regardless of which series the Key Level came from. Can build before, after, or in parallel with S-003.

**Acceptance**: `key_level_source` = crediting `KeyLevel.kind` for credited `aligned` rows, empty otherwise (REQ-24.2/24.3). Header 8 columns without `--backtest`, 9 with it, byte-exact (REQ-41.3 MOD, REQ-65.1).

### Tasks
- [x] S-002.1 `tests/test_table.py` — update `_HEADER` fixture to 8 columns; `test_zero_detections_emits_header_only_csv` asserts the new header (failed first, confirmed load-bearing).
- [x] S-002.2 `test_ict_order_block_credited_signal_writes_kind_in_key_level_source` (REQ-24.2).
- [x] S-002.3 `test_non_model1_rows_leave_key_level_source_empty` (REQ-24.3) + `test_aligned_signal_with_no_key_level_leaves_key_level_source_empty` (edge case within REQ-24.3).
- [x] S-002.4 Extend `--backtest` header test — 9-column header with trailing `signal_id` (REQ-65.1).
- [x] S-002.5 Implemented in `viz/table.py`: `key_level_source: str = ""` param threaded through `_row`/`_model1_row`; appended to `_HEADER`; `write_detections_csv`'s `aligned_signals` branch passes `tagged.key_level.kind if tagged.key_level is not None else ""`; single-series-mode branch keeps `""`.
- [x] S-002.6 Full suite green (223/224 — 1 pre-existing, already-registered, unrelated flaky failure: `test_no_lookahead.py::test_alignment_detection_has_no_lookahead`, engram topic `sdd/crt-detector-ict-order-block` pending-bug note; confirmed NOT touched by this slice's diff). Fixed 5 other hardcoded 7-column header assertions found via grep: `tests/test_cli_e2e.py` (4 occurrences) and `tests/test_cli_backtest_e2e.py` (2 occurrences, including a hardcoded column-count assert).

---

## S-003: Daily-tier Key Level pivot — CLI input, cross-timeframe reindexing, most-recent tie-break (REQ-63.4/63.5/63.6, REQ-67, ADR-E, ADR-F)

**Scope**: walking-skeleton (for V3's new capability) | **Requires**: S-000 (done) | **Independent of S-002**
**Covers**: REQ-63.4, REQ-63.5, REQ-63.6, REQ-67.1, REQ-67.2, REQ-67.3, REQ-66 (V3 re-run)
**Test layers**: unit + e2e (real EURUSDm/GBPUSDm/DXYm H4/M15/Daily, `--backtest`)

**Deviation from a naive cut, justified**: the reindexing (ADR-E) and the tie-break flip (REQ-63.4) are NOT separable into different slices — the tie-break flip is only meaningful/testable once Daily-sourced Key Levels can reach `_key_level_credit_map` at all, which requires reindexing to already exist (a Daily-index-space KeyLevel entering the credit map unreindexed would just be wrong, not absent). They fold into one slice, same reasoning V2's S-000 used for invalidation.

**Acceptance**: GIVEN the real EURUSDm/GBPUSDm/DXYm H4/M15/Daily triple with `--backtest` and `--daily-csv`/`--daily-symbol` provided, gating confluence SOLELY on ICTOrderBlock-sourced Key Levels (FVG excluded from this run, per REQ-66), THEN evidence records per instrument: count of `aligned` non-`fvg_fill` Model-1 signals, how many credited an ICTOrderBlock Key Level, how many weren't, `excluded_no_key_level`, `trades_opened` — disclosed alongside FVG's 1.5–3.0% (obs #449) AND V2's now-superseded H4-tier 98.0–98.4%, no threshold gate on the resulting percentage (REQ-66.2). `uv run lint-imports` passes (no new import crosses a layer boundary — design §Architecture Touchpoints).

### Tasks (Strict TDD — test first at every step)

- [x] S-003.1 Baseline confirmed green (223/224, 1 pre-existing unrelated failure) before starting.
- [x] S-003.2 `cli.py` — `--daily-csv`/`--daily-symbol` args (design §4a) + REQ-67.3 pairing validation + `--daily-csv` without `--htf-csv` rejection (S-003.10, folded in here — both are the same validation block).
- [x] S-003.3 `cli.py` — instrument-match check (ADR-F) + direct `load_mt5_csv` call (NOT `load_pair`).
- [x] S-003.4 `alignment/htf_ltf.py::_ceiling_htf_index` — implemented, tested through `tag_alignment` per convention.
- [x] S-003.5 `alignment/htf_ltf.py::_reindex_daily_key_levels`/`_daily_close` (ADR-E) — 3 tests added (`tests/test_alignment.py`): confirmed-before-boundary (credited), not-yet-knowable (not credited), expiry-translated-excludes (not credited despite zone match). All pass.
- [x] S-003.6 `tag_alignment` threads `daily_series`/`daily_key_levels` through. **Design correction found and applied during this task** (not a re-open, a pseudocode bug caught reading `test_htf_key_levels_concatenate_fvg_and_ict_order_block_sources` before coding — see engram `sdd/crt-detector-ict-order-block/design`): `order_block_key_levels` must be computed UNCONDITIONALLY (design's original gate on `daily_series is not None` silently dropped V2's existing ICTOrderBlock contribution whenever `--daily-csv` is omitted). Fixed in both `design.md` and `cli.py`; existing FVG-only tests (no `daily_series` passed) stay green unchanged.
- [x] S-003.7 Tie-break `min`→`max` by `origin_index` (REQ-63.4). `test_both_sides_breached_each_evaluated_independently_lower_origin_wins` inverted → `..._higher_origin_wins`; `_key_level_credit_map`'s docstring updated (REQ-55.6 reference removed, now cites REQ-63.4/ADR-E).
- [x] S-003.8 REQ-63.6 — no equivalent existed; added `test_wick_extreme_just_outside_zone_yields_no_confluence` as a regression guard (confirmed pre-existing behavior, not a new RED-GREEN cycle).
- [x] S-003.9 `cli.py` composition wired per the CORRECTED design (S-003.6 note). 5 new `test_cli.py` tests (REQ-67.1/67.2/67.3 + mismatch + htf-required).
- [x] S-003.10 Folded into S-003.2 (`--daily-csv` requires `--htf-csv`, same validation block, one test: `test_main_rejects_daily_csv_without_htf_csv`).
- [x] S-003.11 Full suite green: 232/233 (same 1 pre-existing unrelated failure). `lint-imports` clean (30 files, 64 deps, contract kept).
- [x] S-003.12 **MANUAL real-data run — DONE. Ran TWICE.** First run (V3 mechanism): 0 credited signals/0 trades, W=99.85–99.95% — HALTED per Success Criteria go/no-go rule, escalated to user. **The escalation surfaced a genuine mechanism bug**, not a product finding to accept: the user's own mental model of invalidation ("quien mata ese OB de 1D debe ser una vela de 4h") didn't match what was built (Daily-candle-granularity invalidation, collapsing origin/expiry to the same H4 index for 60% of detected Order Blocks — see `evidence/real-data-h4-m15.md` § "V3 run" for the root-cause writeup). Fixed as spec V4 / REQ-63.7 (H4-native invalidation scan, `_htf_expiry_index` in `alignment/htf_ltf.py`) — see `design.md` ADR-E. Second run (V4, corrected): **285/401/385 credited, 17/31/48 trades opened**, W=98.88–99.23% — now in the SAME range as V2's H4-tier number (98.0–98.4%), does NOT re-trigger the go/no-go escalation. Full writeup: `evidence/real-data-h4-m15.md` § "V4 run" (current/authoritative). **A build-preflight gap was also found and fixed along the way**: MT5's Daily export has no `<TIME>` column — `ingestion/loader.py::load_mt5_csv` now handles it (defaults to midnight), TDD'd. **Not halted — V4 result does not trigger escalation. No follow-on work (sub-change #3) started without explicit user go-ahead.**

---

## Build Order

| Order | Slice(s) | Note |
|---|---|---|
| — | S-000, S-001 | DONE — V2 baseline, not rebuilt |
| 1 | S-002, S-003 | independent of each other, both require only S-000 (done); either can go first |

## Anti-Pattern Check

Pass — no horizontal/layer-named slices; each slice single-dimension-dominant, explicit REQ-ID coverage, ≤1 dependency (both S-002/S-003 depend only on the already-satisfied S-000). 4 total slices (2 done, 2 remaining), under the M cap of 4. All spec V3 scenarios covered: REQ-61/62/63.1-63.3/64/65 via S-000/S-001/S-002; REQ-63.4/63.5/63.6/66/67 via S-003. No REQ-ID orphaned. `lint-imports` fitness function needs no new test file — covered by S-003.11's full-suite run.
