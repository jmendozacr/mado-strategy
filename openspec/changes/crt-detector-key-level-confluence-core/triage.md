# Triage: CRT Key Level Confluence — Core (Walking Skeleton)

**Classification**: L
**Decided at**: 2026-08-29T00:00:00Z
**Change name**: `crt-detector-key-level-confluence-core`

## Problem & Scope

> **[CORRECTED 2026-08-29 — supersedes the original block below, retained struck through for history]** The detector evaluates every detected Model-1 setup equally; charter-1 [00:12:02] names confluence with an HTF Key Level as a PRECONDITION of a valid setup — not a comparison dimension, a validity gate — and nothing in the pipeline checks for it. This sub-change makes that check a hard gate using the one Key Level source that already exists in code (FVG). A Model-1 that does not react at an HTF FVG is not a real setup: it stops appearing in `detections.csv` (even without `--backtest`) and is excluded from the `--backtest` population as an 8th reconciliation bucket. Swing is explicitly deferred to a later sub-change.

```yaml
scope:
  in_scope:
    - core/key_level.py: KeyLevel frozen dataclass (kind, top, bottom, origin_index) — a normalising type, not a Protocol/union
    - to_key_levels adapter function for the EXISTING FVG detector ONLY (Swing deferred — user's explicit call, "omitamos los swings, dejémoslo para una fase futura")
    - origin_index = the provably-knowable index (FVG: end_index = start_index + 2), never the geometric anchor — no-lookahead correctness, not a style choice
    - Confluence by DIRECT GEOMETRIC OVERLAP between the HTF purge candle's actual wick extreme and the FVG's [top, bottom] zone — NO tolerance parameter (rejected on the merits after reviewing charter-1's own example frames, which render Key Levels as zones the wick visibly enters)
    - Confluence tag wired into alignment/htf_ltf.py::tag_alignment, stored once on AlignedSignal.key_level
    - Confluence is a VALIDITY GATE (8th exclusion bucket, excluded_no_key_level) — NOT a reporting partition; no confluent/non-confluent metrics split
    - The gate withholds non-confluent Model-1 rows from detections.csv/overlay.png on EVERY run, with or without --backtest (REQ-45 reopened, re-anchored differentially not absolutely)
    - The gate is surgical — only signals where confluence was DETERMINABLE (aligned=="aligned") and came back negative are withheld; unaligned/insufficient_htf_data rows are unaffected
    - HTF Key Level sources computed in _detect_all, never stored on _Detections, never rendered, --types fvg semantics unchanged (LTF-only)
    - Default validation pairing: H4 HTF / M15 LTF
    - Consumer-coupling fitness test (alignment imports core.key_level, not any detector module directly)
    - No-lookahead property test over the confluence tag itself (two-sided origin_index boundary + gate-level index comparison)
  out_of_scope:
    - Swing as a Key Level source — deferred to a later sub-change of the same program (was in-scope in the original draft below; removed by explicit user decision)
    - Swing-significance criterion — moot for this sub-change now that Swing itself is deferred (was flagged REQUIRED in the original draft below)
    - detections.csv source-attribution column — deferred to sub-change #2 (ICTOrderBlock), where a 2nd source makes it actually discriminating rather than a constant "fvg" value
    - Any confluence tolerance/proximity parameter — rejected on the merits, not deferred (geometric overlap needs no tunable)
    - ICT Order Block detector — separate sub-change #2 (crt-detector-ict-order-block)
    - Breaker Block detector — separate sub-change #3 (crt-detector-breaker-block)
    - Rejection Block — deferred out of the whole program, no definitional source
    - Partial exits / equity curve — separate already-registered change (crt-detector-backtest-partial-exits)
```

<details>
<summary>Original (superseded) problem & scope block, retained for history</summary>

> The detector evaluates every detected Model-1 setup equally; charter-1 [00:12:02] names confluence with an HTF Key Level as the reliability filter that separates a real CRT setup from noise, and nothing in the pipeline checks for it. This sub-change delivers the smallest real slice of that filter — using ONLY Key Level sources that already exist (FVG, Swing) — so the confluence question becomes answerable end-to-end before any new detector gets built.

```yaml
scope:
  in_scope:
    - core/key_level.py: KeyLevel frozen dataclass (kind, top, bottom, origin_index) — a normalising type, not a Protocol/union
    - to_key_levels adapter functions for the EXISTING FVG and Swing detectors (adapter lives with each source module)
    - Swing-significance fix: SwingConfig gains a strength/lookback field; detect_swings (or a filter layered over it) applies it — REQUIRED, not optional
    - Confluence proximity tolerance as a new DetectorConfig field (never a module constant)
    - Confluence tag wired into alignment/htf_ltf.py::tag_alignment — a KeyLevel with origin_index < purge_index within tolerance credits the purge candle
    - New detections.csv column disclosing confluence
    - --backtest population split: confluent vs non-confluent win rate / average R, preserving confluent + non_confluent == opened alongside opened + sum(exclusion_buckets) == considered
    - CLI exposure for the new flags/columns
    - Default validation pairing: H4 HTF / M15 LTF
    - Consumer-coupling fitness test (alignment imports core.key_level, not any detector module directly)
    - No-lookahead property test over the confluence tag itself
  out_of_scope:
    - ICT Order Block detector — separate sub-change #2 (crt-detector-ict-order-block)
    - Breaker Block detector — separate sub-change #3 (crt-detector-breaker-block)
    - Rejection Block — deferred out of the whole program, no definitional source
    - Partial exits / equity curve — separate already-registered change (crt-detector-backtest-partial-exits)
```
</details>

## Description Received

> Program sub-change #1 of 3 (`crt-detector-key-level-confluence`, engram #413) — the walking skeleton, `depends_on: []`. Introduces `core/key_level.py` as SEAM-01 (normalising type, consumer-coupling fitness test), `to_key_levels` adapters as SEAM-02, and the confluence field on `AlignedSignal` as SEAM-03 — the contracts sub-changes #2 and #3 will register new Key Level sources against.

## Criteria Evaluation

| Criterion | Evidence | Score |
|---|---|---|
| Files affected (estimated) | ~15: new `core/key_level.py`; edits to `core/config.py`, `primitives/fvg.py`, `primitives/swing.py`, `alignment/htf_ltf.py`, `viz/table.py`, `backtest/metrics.py`, `cli.py`; ~7-8 test files (new `test_key_level.py`, swing-significance tests, `test_alignment.py`, `test_cli.py`/`test_cli_e2e.py`, `tests/property/test_no_lookahead.py` extension, `test_backtest_metrics.py`, import-linter/fitness test) | L |
| Lines affected (estimated) | ~600-1200 (new dataclass + 2 adapters + 2 config fields + tag-wiring logic + CSV column + backtest partition split + CLI flags + property/unit test suite) | L |
| Bounded contexts | 1 (single `detector` subsystem) but spans all 5 pipeline layers (`core → primitives → alignment → backtest/viz/cli`) | M-L |
| New patterns | New — `KeyLevel` normalising dataclass + `to_key_levels` adapter contract is the first of its kind in the codebase (no existing Protocol/union unification pattern to mirror) | L |
| Test types | Existing types — hypothesis property tests already exist (`tests/property/test_no_lookahead.py` is already tracked, being extended not invented) | S/M |
| Precedent | Partial — `viz/table.py`'s `include_signal_id` trailing-column pattern covers the CSV work; `backtest/metrics.py`'s pure-function-over-partitions shape covers the confluent/non-confluent split; but the defining artefact (`KeyLevel` type + adapter contract + swing-significance semantics + no-lookahead confluence tagging) is greenfield — no reduction applied | no change |

### Overrides Triggered

None. No migration, no new external dependency, no cross-cutting logging/observability change, no auth/payment/PII/security-boundary/deploy alteration (confirmed: read-only CLI analysis tool over MT5 CSV exports).

**Final classification**: L — files-affected and new-pattern criteria both independently land at L; the program's own architect estimate (L) is confirmed mechanically, not rubber-stamped. The precedent modifier does not apply: while two peripheral pieces (CSV column, backtest split) mirror real precedent, the change's defining contribution — the `KeyLevel` type and its adapter contract, which sub-changes #2 and #3 depend on — has no precedent to mirror.

## Recommended Path

- Phase: full Planner with Council
- Skills to invoke (in order): `sdd-explore` → `sdd-propose` → `sdd-spec` → `sdd-design` → `sdd-slice` (target 4-7 slices) → `sdd-verify --mode=plan` → `/build` (apply ⇄ verify in-loop) → `/evaluate` (simplify → verify final → archive)
- Slice target: 4-7

## Recommended Personas (L)

| Role | Reason |
|---|---|
| Business Analyst | Always for L |
| PM | Always for L |
| QA Engineer | Always for L |
| Architect | Always for L |
| Tech Writer | SEAM-01/SEAM-02 are explicit verbatim-shape interface contracts that sub-changes #2 and #3 will implement against — clarity of the contract documentation matters beyond this sub-change |
| UX Designer | Touches a user-facing surface: new CLI flags, a new `detections.csv` column, and `--backtest` confluent/non-confluent output disclosure |

Security Engineer and DBA/Data Engineer not triggered — no sensitivity override, no schema/migration.

## Spec Reference

spec_source: internal — no reference captured (Step 7b skipped per instruction).

## Risks Flagged at Triage

- Swing-significance parameter is a REQUIRED new criterion (not optional) per the program artefact — without it, confluence would pass on ~100% of the population and discriminate nothing. Design phase must formalize the strength/lookback field and its disclosure in run output.
- Two invariants must hold simultaneously post-change: `confluent + non_confluent == opened` (new) AND `opened + sum(exclusion_buckets) == considered` (existing, ADR-009) — verify phase must assert both together, not just the new one.
- SEAM-01/SEAM-02 contracts set the shape sub-changes #2 and #3 will build against — getting the adapter signature wrong here compounds downstream. Architect persona should treat this as a first-class review concern, not incidental.
- No-lookahead property test over the confluence tag itself is called out as "highest-value test in the program" — QA persona should prioritize accordingly.

## Halt?

No

## Notes for Next Phase

- Read the full program artefact (`sdd/crt-detector-key-level-confluence/program`, engram #413) for the SEAMS table, proposed ADRs, and Program-wide Fitness Functions before exploring — this sub-change is pre-scoped, not open-ended.
- Proposed ADRs already drafted by the program (KeyLevel as frozen dataclass not Protocol/union; confluence tolerance as `DetectorConfig` field) are inputs to `sdd-design`, not decisions to re-litigate from scratch — confirm or challenge with evidence, don't re-derive.
- Default validation pairing is H4 HTF / M15 LTF per `project/strategy-preferences` (engram #411).
- Architecture baseline conformance already checked by the program: no `.importlinter` changes expected — `sdd-design` should verify this holds, not assume it.
