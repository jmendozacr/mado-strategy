# Explore: crt-detector-key-level-confluence-core — SYNTHESIZED

**Triage**: L. Council: architect + qa-engineer + business-analyst ran in parallel (anti-anchoring, blind to each other) for the initial pass; a second architect-only validation pass ran after the user corrected the core mechanic (confluence = validity gate, not reporting partition). Synthesized here, FINAL — supersedes both raw persona outputs. Mirrors engram `sdd/crt-detector-key-level-confluence-core/explore` (obs #415).

## Final Resolved Design (all product questions closed)

1. **Key Level source, this sub-change**: FVG only. Swing explicitly deferred by user to a later sub-change. Order Block/Breaker Block are sub-changes #2/#3 of the same program (sequential, not merged — user considered merging, explicitly declined after cost was shown).
2. **Confluence test**: direct geometric overlap between the HTF purge candle's actual wick extreme (high for bullish purge, low for bearish) and the FVG's `[top, bottom]` zone. No tolerance parameter — grounded in charter-1's example frames (Key Level renders as a price zone, purge wick visibly enters it, not merely approaches).
3. **Mitigation**: a filled/mitigated FVG still counts as a valid Key Level (does not expire). Confirmed coincidentally lookahead-safe too — `fill_status`/`fill_index` resolve later than `origin_index` and must never be read by `to_key_levels`.
4. **Confluence is a VALIDITY GATE, not a report dimension.** A Model-1 that fails confluence is not a real setup. No confluent/non-confluent partition, no parallel metrics split.
5. **Filter scope (user-resolved)**: SURGICAL — only signals where confluence was DETERMINABLE (i.e., `aligned == "aligned"`, a purge candle exists) and came back negative are dropped. Signals already excluded for other reasons (`unaligned`, `insufficient_htf_data`) are UNCHANGED. Predicate: `keep(t) = t.aligned != "aligned" or t.key_level is not None`.
6. **Source-attribution column (user-resolved)**: DEFERRED to sub-change #2. `detections.csv` stays at its signed 7-column header for this sub-change.
7. **Placement — resolved contradiction**: insert the CSV/chart filter (`_filter_to_confluent`) between `cli.py`'s `population` snapshot (line ~120) and `_filter_by_types` (line ~121) — `population` inherits pre-filter data so `simulate()`'s new bucket stays live and countable.
8. **8th exclusion bucket ordering**: `excluded_no_key_level` is stage 4, LAST of `_population_cuts`' existing 3-stage chain. Appending last keeps all 3 existing bucket counts byte-identical against the current regression suite.
9. **`origin_index` for FVG-sourced KeyLevels = `end_index` (`start_index + 2`)**, NEVER `start_index` — verified against `primitives/fvg.py`'s real loop bounds.
10. **`_detect_all` needs a new HTF FVG detection stage** — compute for the confluence check, do NOT render, do NOT change `--types fvg`'s existing LTF-only meaning.

## REQ Impact (signed spec, `openspec/specs/detector/spec.md`) — narrowed once the CSV column was deferred

**MODIFIED** (3): REQ-45/REQ-45.3 (differential byte-compat, not absolute), REQ-30 (new REQ-30.7 confluence exclusion), REQ-40/REQ-40.1 (8 buckets not 7, new REQ-40.5 precedence scenario).

**NOT touched**: REQ-24, REQ-41.3 stay exactly as signed.

## Fitness Functions / Test Derivation (QA + architect, merged)

1. Cross-artefact reconciliation: `count(model1 rows in detections.csv) == signals_considered - excluded_no_key_level` for an unfiltered `--backtest` run.
2. No-lookahead, `origin_index` boundary (two-sided): re-detect on `up_to(origin_index+1)` → present; `up_to(origin_index)` → absent.
3. No-lookahead, gate level: `key_level.origin_index < purge_index`, both HTF-series indices.
4. Fill-status independence: identical FVGs differing only in fill_status/fill_index → identical KeyLevels.
5. Precedence, mutation-resistant: per-signal exclusive bucket membership, not just sum totals.
6. Ghost-test avoidance: confluent/non-confluent minimal pair holds every other field constant.
7. REQ-42.1 confluence-dimension scenario: a traded signal is by construction confluent.
8. `ReconciliationReport` field addition must extend BOTH `test_backtest_metrics.py`'s sum-invariant AND `test_no_lookahead.py`'s monotonicity assertion list.
9. SEAM-01 consumer-coupling test (program-level).

## Risks Carried Forward (resolved or explicitly deferred, none blocking)

- `_population_cuts` 5-tuple positional return — optional named-fields refactor, deferred to design.
- HTF FVG detection is new surface — compute-only, no rendering, no `--types` semantic change (recommendation, confirm at design).

## Ready for Proposal: YES

Both product questions resolved directly by the user. No open_questions remain for `sdd-propose`.

## Sizing confirmation

L confirmed — code diff is M-sized, spec surface (3 MODIFIED signed requirements) plus walking-skeleton seam obligations hold it at L.
