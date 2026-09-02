# Slices: crt-detector-ict-order-block

**Triage**: M | **Spec version**: V1 signed (REQ-61..66) | **Design version**: v1 (`architecture_impact: additive`) | **Total slices**: 3

## Branch Handling (read before S-000)

This change's seam (`core/key_level.py`, `primitives/fvg.py::to_key_levels`, the HTF-key-level wiring in `cli.py`) exists only on `wip/crt-detector-key-level-confluence-core-s000` — confirmed via `git merge-base master wip/crt-detector-key-level-confluence-core-s000` == current `master` HEAD (`3864a9d`), i.e. that WIP branch is a **single commit directly ahead of master**, not a diverged line. `sdd-apply` MUST:

```
git checkout -b crt-detector-ict-order-block wip/crt-detector-key-level-confluence-core-s000
```

Branch directly off the WIP branch — **not** cherry-pick, **not** rebase. Justification: the WIP work is one commit (`50daee0`, "S-000 walking skeleton, 8/9 tasks (HALTED)"), paused (not under active parallel development), and its ancestor IS master's current tip — there is nothing to reconcile. If `wip/crt-detector-key-level-confluence-core-s000` moves before this change merges, that break surfaces as a normal merge conflict when integrating back to `master` — flagged in the design's own Risk #1, not this slice's problem to pre-solve.

---

## S-000: Walking Skeleton — ICTOrderBlock detection (full base rule incl. invalidation) live end-to-end on real H4/M15

**Scope**: walking-skeleton | **Requires**: nothing (branches per above)
**Covers**: REQ-61.1, REQ-61.2, REQ-61.3, REQ-61.4, REQ-61.5, REQ-62.1, REQ-62.2, REQ-62.3, REQ-63.1, REQ-63.2, REQ-63.3, REQ-66, REQ-66.1, REQ-66.2, REQ-66.3
**Test layers**: unit + e2e (real EURUSDm/GBPUSDm/DXYm H4/M15, `--backtest`)

**Deviation from the design's suggested cut, justified**: invalidation (REQ-62) folds into S-000 rather than a later slice — without it, `ICTOrderBlock`s never expire, and REQ-66's real-data number would over-credit purges against zones that should already be dead, making it non-comparable to FVG's 1.5–3.0% (obs #449). Confluence-core's own S-000 hit the identical situation with FVG's `fill_status`/expiry. REQ-61.3 (last-one-wins) and REQ-61.5 (doji exclusion) also fold in — they aren't separable behavior, they're what a correct backward scan does by construction. What separates cleanly is REQ-64's no-lookahead property (a different KIND of guarantee, testable independently once detection exists) — that's S-001.

**Acceptance**: GIVEN the real EURUSDm/GBPUSDm/DXYm H4/M15 pairs with `--backtest`, gating confluence SOLELY on ICTOrderBlock-sourced Key Levels (FVG excluded from this run, per REQ-66), THEN evidence records per instrument: count of `aligned` non-`fvg_fill` Model-1 signals, how many credited an ICTOrderBlock Key Level, how many weren't, `excluded_no_key_level`, and `trades_opened` — for all 3 instruments, no threshold gate on the resulting percentage (REQ-66.2). `uv run lint-imports` passes (existing `test_fitness_imports.py::test_import_linter_layers_contract_holds` covers the new module automatically).

### Tasks (Strict TDD — test first at every step)

- [ ] S-000.1 Branch setup per "Branch Handling" above. Confirm `uv run pytest` and `uv run lint-imports` both pass on the fresh branch before writing new code.
- [ ] S-000.2 `core/structure_break.py` (NEW) — `StructureBreak` frozen dataclass per Data Model.
- [ ] S-000.3 `composite/mss.py::to_structure_breaks` — test first (empty→empty; one `MSSEvent`→one `StructureBreak` field-mapped); implement the adapter.
- [ ] S-000.4 `core/config.py::ICTOrderBlockConfig` — empty frozen dataclass mirroring `SwingConfig`; wire into `DetectorConfig`.
- [ ] S-000.5 `primitives/ict_order_block.py::detect_ict_order_blocks` — backward-scan anchor selection, TDD order: REQ-61.1 (happy bullish) → REQ-61.2 (happy bearish) → REQ-61.3 (last-one-wins) + REQ-61.5 (doji excluded) against the same scan → REQ-61.4 (no qualifying candle → no block, never an error).
- [ ] S-000.6 `primitives/ict_order_block.py` — forward invalidation scan, TDD order: REQ-62.1 (happy) → REQ-62.2 (wick-only, stays open) → REQ-62.3 (never invalidated to series end).
- [ ] S-000.7 `primitives/ict_order_block.py::to_key_levels` — test-first REQ-63.1 (`origin_index` = crediting break's index, not `candle_index`) and REQ-63.2 (`expiry_index` = `invalidation_index`); implement.
- [ ] S-000.8 `core/key_level.py` — widen `kind` Literal to include `"ict_order_block"`.
- [ ] S-000.9 REQ-63.3 regression test — `tests/test_alignment.py::test_htf_ltf_imports_unchanged`: AST-parse `alignment/htf_ltf.py`'s imports, assert only `core.key_level`. Write BEFORE touching `cli.py` (S-000.10) so it's a true regression guard.
- [ ] S-000.10 `cli.py` wiring — compose `to_structure_breaks(detect_mss_events(...))` → `detect_ict_order_blocks(...)` → aliased `to_key_levels` (`ict_order_block_to_key_levels`, avoiding the naming collision with `fvg.py`'s own `to_key_levels`), concatenate into `htf_key_levels`. Cover with a `test_cli.py`/`test_cli_e2e.py` test confirming both sources reach `tag_alignment`.
- [ ] S-000.11 Full suite: `uv run pytest` + `uv run lint-imports` green.
- [ ] S-000.12 **MANUAL, not pytest** — REQ-66 real-data run. Same shape as #1's S-000.9, same H4/M15 pairs, same 3 instruments, gating SOLELY on ICTOrderBlock Key Levels (temporarily exclude FVG's term for this run only — never leave that exclusion in shipped `cli.py`). Output to `.sdd/evidence/crt-detector-ict-order-block/{instrument}/`; narrative + counts table to `openspec/changes/crt-detector-ict-order-block/evidence/real-data-h4-m15.md`, disclosing the percentage alongside FVG's 1.5–3.0% (obs #449). **Per Success Criteria: if the ICTOrderBlock-only figure is ALSO in the 1–3% range, HALT and escalate to the user before any follow-on work — do not auto-proceed to S-001/S-002 or to sub-change #3.**

---

## S-001: No-lookahead safety — ICTOrderBlock detection is prefix-consistent under truncation

**Scope**: edge-case | **Requires**: S-000
**Covers**: REQ-64, REQ-64.1
**Test layers**: property (Hypothesis)

**Acceptance**: GIVEN `detect_ict_order_blocks(series.up_to(n), breaks_up_to(n))`, THEN for every Order Block anchored/resolved at index `< n`, its fields match the full-series output, for all `n`, across 100 Hypothesis examples — mirrors `test_mss_detection_has_no_lookahead`'s monotonic-key shape.

### Tasks
- [ ] S-001.1 `tests/property/test_no_lookahead.py::test_ict_order_block_detection_has_no_lookahead` per design §7's code block.
- [ ] S-001.2 Sanity-check the test isn't vacuously passing (confirm it catches a deliberately introduced lookahead bug), then run the full suite.

---

## S-002: `detections.csv` gains `key_level_source` (REQ-24/41.3 reopened, confluence-core's REQ-56.5 flagged)

**Scope**: happy-path | **Requires**: S-000
**Covers**: REQ-24.2, REQ-24.3, REQ-65, REQ-65.1, REQ-41.3 (MOD)
**Test layers**: unit

**Acceptance**: `key_level_source` = crediting `KeyLevel.kind` for credited `aligned` rows, empty otherwise (REQ-24.2/24.3). Header 8 columns without `--backtest`, 9 with it, byte-exact (REQ-41.3 MOD, REQ-65.1).

### Tasks
- [ ] S-002.1 `tests/test_table.py` — update `_HEADER` fixture to 8 columns; `test_zero_detections_emits_header_only_csv` asserts the new header (fails first, confirms load-bearing).
- [ ] S-002.2 `test_ict_order_block_credited_signal_writes_kind_in_key_level_source` (REQ-24.2).
- [ ] S-002.3 `test_non_model1_rows_leave_key_level_source_empty` (REQ-24.3).
- [ ] S-002.4 Extend `--backtest` header test — 9-column header with trailing `signal_id` (REQ-65.1).
- [ ] S-002.5 Implement in `viz/table.py`: `key_level_source: str = ""` param threaded through `_row`/`_model1_row`; append to `_HEADER`; `write_detections_csv`'s `aligned_signals` branch passes `tagged.key_level.kind if tagged.key_level else ""`; single-series-mode branch keeps `""`.
- [ ] S-002.6 Full suite green — grep `_HEADER`/`"aligned"]` across `tests/` first to catch any other hardcoded 7-column assumption.

---

## Build Order

| Order | Slice(s) | Note |
|---|---|---|
| 1 | S-000 | skeleton — S-000.12's real-data run gates escalation to the user before any follow-on work (incl. sub-change #3) is even considered |
| 2 | S-001, S-002 | independent of each other, both require only S-000 |

## Anti-Pattern Check

Pass — no horizontal/layer-named slices; each slice single-dimension-dominant, explicit REQ-ID coverage, ≤1 dependency. 3 total slices, under the M cap of 4. All spec V1 scenarios covered, no REQ-ID orphaned. `lint-imports` fitness function needs no new test file — covered by S-000.11's full-suite run.
