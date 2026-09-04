# Proposal + Spec: ICT Order Block Detector

> M light pipeline — merged propose+spec artefact. **Spec V4** (this file) — REQ-63 amended (NEW REQ-63.7): a Daily-sourced Order Block's invalidation MUST be checked candle-by-candle against the H4 series, not by translating a boundary computed from the Daily series' own (coarser) invalidation scan. Caught during `sdd-apply`'s real-data run when the user's own mental model ("quien mata ese OB de 1D debe ser una vela de 4h") surfaced a gap V3 missed. REQ-63/66 (V3) rewritten and REQ-67 added for the Daily-tier Key Level pivot; REQ-61/62/64/65 carry forward unchanged from V2. `proposal.md` still holds V1 for history; this file is now spec-authoritative. See "## Changes from V3" and "## Changes from V2" at the end of the Requirements section (V1 history: "## Changes from V1", further down).

## Daily-tier pivot (V3 — supersedes V2's H4-only Key Level scope)

V1 and V2 both computed Order Block Key Levels on the H4 series — a 2-tier scope (H4 Key Level ↔ H4 purge) confirmed WRONG against the user's own separate, previously-working tool (`crt-scanner_old/core/htf_confluence.py`), which crosses H4 CRT signals against DAILY-timeframe Key Levels — the real hierarchy is 3-tier: **Daily (Key Level) → H4 (CRT signal/purge) → M15 (execution)**. Full investigation trail: `openspec/changes/crt-detector-ict-order-block/NEXT-STEPS.md`, engram topic `sdd/crt-detector-ict-order-block/pause`. See "## Changes from V2" below for the full corrected REQ-63/66/67 text.

## Corrected detection rule (V2 — supersedes the Approach section below, which still describes V1's eliminated MSS/StructureBreak mechanism; a design V2 pass will replace it)

Real-data evidence (`evidence/real-data-h4-m15.md`) showed V1's MSS-anchored rule excludes 82-84% of aligned Model-1 signals — verified NOT a bug (`sdd/crt-detector-ict-order-block/restrictiveness-investigation`, obs #471) and NOT fixable via a recency-window tweak (`sdd/crt-detector-ict-order-block/recency-window-sweep`, obs #472, W stays 68-86% across N=3..20). User review of their own separate live-scanner tool (`crt-scanner`) surfaced a materially different detection AND invalidation rule they actually trade by — see "## Changes from V1" below for the full corrected REQ-61/62/63/64 text.

## Intent

Sub-change #2 of the `crt-detector-key-level-confluence` program. Sub-change #1's real-data gate found FVG-only confluence discriminates only 1.5–3.0% of Model-1 signals (floor 10%, obs #449) — too weak, on one data point, to decide accept/tighten/reconsider on the confluence-gate concept. This change adds a second, independent Key Level source — the classical ICT Order Block — through the seam #1 already built, purely to produce a second, comparable real-data discrimination number. It is not a UX feature; it is an evidence-generation step for a stalled product decision.

## Scope (in/out)

```yaml
in_scope:
  - New primitives/ict_order_block.py: immediate-engulfing ICTOrderBlock detector (V2 — candle i opposite-bodied, candle i+1 fully engulfs i's range and closes in-direction; zone = candle i's body; invalidation = first candle from i+2 onward whose range overlaps the zone at all). No composite/mss.py or core/structure_break.py dependency — V1's MSS/StructureBreak mechanism is ELIMINATED, self-contained like primitives/fvg.py.
  - Registration as 2nd Key Level source: primitives/ict_order_block.py::to_key_levels, KeyLevel.kind widened to Literal["fvg", "ict_order_block"]
  - detections.csv trailing key_level_source column (8th column) — reopens signed main-spec REQ-24/REQ-41.3 and confluence-core's REQ-56.5
  - No-lookahead property test for the new detector (ADR-03 pattern)
  - Real-data comparison run on the same 3 instruments (EURUSDm, GBPUSDm, DXYm) as #1's S-000.9 gate, now WITH `--daily-csv` provided, gating on ICTOrderBlock alone, producing ICTOrderBlock's own Daily-tier discrimination number (REQ-66 V3)
  - V3: Daily-tier Key Level detection — `detect_ict_order_blocks` runs against a NEW Daily series input, not H4 (REQ-63 V3)
  - V3: new CLI input `--daily-csv`/`--daily-symbol`, optional pair mode mirroring the existing `--htf-csv`/`--htf-symbol` precedent (REQ-67)
  - V3: `alignment/htf_ltf.py::_key_level_credit_map` tie-break flips from oldest-wins to most-recent-wins (REQ-63 V3) — this crosses into sub-change #1's original design ownership; landing here first is a user-confirmed sequencing call (see program `crt-detector-key-level-confluence`)
out_of_scope:
  - crt-detector-breaker-block (sub-change #3)
  - Rejection Block, Swing as Key Level sources (deferred program-wide)
  - A sources-registry abstraction for >2 sources (Rule of Three; plain concat suffices at 2)
  - ICT Order Block as its own detections.csv row/type or overlay.png marker — it is HTF-only, computed-not-rendered, mirroring confluence-core's REQ-57 treatment of HTF FVGs
  - --types ict_order_block CLI flag — nothing to filter; there is no such row type to include/exclude
  - Mandatory liquidity-sweep or FVG-coincidence validity filters (product decision, obs #464: base rule only)
  - Chart rendering polish, new config surface beyond ICTOrderBlockConfig
  - V3: porting the Daily-tier pivot to FVG (sub-change #1, `crt-detector-key-level-confluence-core`) — stays paused; this change lands the 3-tier pattern as reference, #1 ports it later
```

## Approach

**Layering constraint (confirmed by reading `.importlinter` directly):** `primitives` sits below `composite`/`entries`; `primitives/ict_order_block.py` cannot import `composite.mss`. Resolution mirrors the existing `core/key_level.py` precedent — a new core-layer type carrying only raw primitives:

```python
# core/structure_break.py (NEW)
@dataclass(frozen=True)
class StructureBreak:
    index: int
    direction: Literal["bullish", "bearish"]
    broken_swing_index: int
    broken_swing_price: float

# composite/mss.py (+adapter, mirrors fvg.py::to_key_levels shape)
def to_structure_breaks(events: list[MSSEvent]) -> list[StructureBreak]: ...

# primitives/ict_order_block.py (NEW)
@dataclass(frozen=True)
class ICTOrderBlock:
    candle_index: int
    break_index: int
    direction: Literal["bullish", "bearish"]
    top: float
    bottom: float
    status: Literal["open", "invalidated"]
    invalidation_index: int | None = None

def detect_ict_order_blocks(
    series: OHLCSeries, breaks: list[StructureBreak],
    config: ICTOrderBlockConfig = ICTOrderBlockConfig(),
) -> list[ICTOrderBlock]: ...

def to_key_levels(blocks: list[ICTOrderBlock]) -> list[KeyLevel]: ...
```

`cli.py` composes: `to_structure_breaks(detect_mss_events(series, config.mss, swings=swings))` → `detect_ict_order_blocks(...)` → `to_key_levels(...)`, concatenated with FVG's HTF key levels before feeding `tag_alignment`. (V2 shape — see "## Daily-tier pivot" above and "## Changes from V2" below: V3 feeds `detect_ict_order_blocks` the Daily series instead of HTF, and `alignment/htf_ltf.py`'s `_key_level_credit_map` gets a tie-break comparator change — its IMPORTS still need zero changes, REQ-63.3, but it is no longer byte-identical to its pre-this-change state.)

**Config**: `ICTOrderBlockConfig` is an empty frozen dataclass, mirroring `SwingConfig`'s existing precedent. The base rule (per product decision, obs #464) has no discretionary threshold — the backward scan is bounded by `StructureBreak.broken_swing_index` itself (a structural bound, not a magic number), and invalidation is a deterministic close-through-zone check. This satisfies REQ-25.1's config-completeness scan without inventing an unused parameter.

**`detections.csv` column**: `_HEADER` in `viz/table.py` currently `[..., "aligned"]` (7 columns); this change appends `"key_level_source"` (8 columns), and `_HEADER_WITH_SIGNAL_ID = _HEADER + ["signal_id"]` becomes 9 columns automatically — a one-line diff, same pattern `signal_id` already used.

**Branch dependency (called out, not silently assumed)**: this change's seam (`core/key_level.py`, `primitives/fvg.py`'s `to_key_levels`, the HTF-key-level wiring in `cli.py`) currently exists only on `wip/crt-detector-key-level-confluence-core-s000` (uncommitted, not on `master`). Per the program's revised sequencing (obs #413), `sdd-apply` for this change builds against that branch's state, not `master` directly — a slice-level integration detail, flagged here so it isn't rediscovered mid-apply.

## Risks

1. **Branch dependency**: building on an uncommitted, paused sub-change's branch — if that branch is rebased or abandoned before #1 resumes, this change's foundation moves under it.
2. **Base-rule-only choice may reproduce weak discrimination** — addressed explicitly by the go/no-go item in Success Criteria, not silently absorbed.
3. **V3: `alignment/htf_ltf.py` ownership crosses into sub-change #1's original design territory** — the tie-break comparator this change modifies (REQ-63.4) was designed by #1 (FVG, confluence-core), not this change. Landing it here first is a user-confirmed sequencing call; #1 must reconcile its own design/spec text against this change's edit when it resumes, not silently re-diverge.
4. **Second CSV schema reopening** (after #1's REQ-45 in the same program) — the pattern is now proven twice; the column itself (`key_level_source`, a source `kind` string) generalizes cleanly to sub-change #3's future Breaker Block source with no further schema change expected.
5. **Cross-change spec drift**: confluence-core's own signed spec (REQ-56.5, "Explicitly Out of Scope" table) states the 7-column header "stays signed" and is "NOT touched" — that statement becomes stale once this change ships. Reconciling confluence-core's own spec text is confluence-core's job when it resumes/archives, not this change's — flagged here so it isn't lost.
6. **V3: Daily data availability — VERIFIED, not a live risk.** `pairs/D1/*.csv` confirmed present for all 3 real-data instruments: `EURUSDm_Daily_202001020000_202608190000.csv`, `GBPUSDm_Daily_202001020000_202608190000.csv`, `DXYm_Daily_202110270000_202608190000.csv` — sufficient history depth for REQ-66's run.

## Rollback Plan

Purely additive except: `core/key_level.py`'s `Literal` widening, `viz/table.py`'s `_HEADER`, and (V3) `cli.py`'s new `--daily-csv`/`--daily-symbol` flags + `alignment/htf_ltf.py`'s tie-break comparator. No persisted state, no migrations — `detections.csv`/`trades.csv` are regenerated artefacts. Revert = `git revert` the change's commit(s); no backfill required.

## Success Criteria

- All REQ-61..67 scenarios pass; no-lookahead property test green; `uv run lint-imports` passes (layering respected).
- Real-data run completes on EURUSDm/GBPUSDm/DXYm (H4/M15/Daily, `--daily-csv` provided), producing ICTOrderBlock's own Daily-tier discrimination percentage, disclosed alongside FVG's 1.5–3.0% (obs #449) and V2's now-superseded H4-tier number (98.0–98.4%) — this number is descriptive evidence, not a pass/fail gate on this change.
- **Explicit go/no-go note (not a REQ)**: if ICTOrderBlock's Daily-tier discrimination is ALSO in the 1–3% range, this is signal about the confluence-gate CONCEPT itself, not just FVG — escalate to the user before automatically proceeding to `crt-detector-breaker-block` (#3), per triage's PM flag.
- REQ-24/REQ-41.3 (main spec) and REQ-56.5 (confluence-core spec) amendments applied consistently; `detections.csv` header verified 8/9 columns as specified.
- `--daily-csv`/`--daily-symbol` pairing validated (REQ-67), mirroring `--htf-csv`/`--htf-symbol`'s existing behaviour exactly.

## Requirements

### REQ-61: Detect ICT Order Block (immediate-engulfing rule) — V2
The system MUST detect an `ICTOrderBlock` for every pair of consecutive candles `(i, i+1)` in the HTF series, checked unconditionally in BOTH directions — no external bias input, no `StructureBreak`, no backward scan:
- **Bullish Order Block**: candle `i` closes bearish (`i.close < i.open`) AND candle `i+1` fully engulfs `i`'s range (`i+1.high >= i.high` AND `i+1.low <= i.low`) AND candle `i+1` closes bullish (`i+1.close > i+1.open`).
- **Bearish Order Block**: mirror — `i` closes bullish, `i+1` fully engulfs `i`, `i+1` closes bearish.
- The zone is candle `i`'s own BODY — `top = max(i.open, i.close)`, `bottom = min(i.open, i.close)`.
- A pair that does not satisfy all three conditions for either direction yields no Order Block for that pair — never an error.
- **REQ-61.1** (happy, bullish): GIVEN candle `i` closes bearish and candle `i+1` fully engulfs `i`'s range and closes bullish, WHEN detected, THEN a bullish `ICTOrderBlock` is emitted anchored at `i`, zone = candle `i`'s body, confirmed at `i+1`.
- **REQ-61.2** (happy, bearish): mirror of REQ-61.1 — candle `i` closes bullish, candle `i+1` fully engulfs `i` and closes bearish.
- **REQ-61.3** (edge, partial engulf — no OB): GIVEN candle `i` closes bearish and candle `i+1` closes bullish but `i+1` does NOT fully engulf `i`'s range (e.g. `i+1.high < i.high`), WHEN evaluated, THEN no `ICTOrderBlock` is emitted for that pair.
- **REQ-61.4** (edge, wrong confirmation close — no OB): GIVEN candle `i` closes bearish and candle `i+1` fully engulfs `i`'s range but `i+1` itself closes bearish (not bullish), WHEN evaluated, THEN no `ICTOrderBlock` is emitted for that pair.
- **REQ-61.5** (edge, doji excluded): GIVEN candle `i` has `open == close` (doji), WHEN evaluated as a potential anchor, THEN it never qualifies for either direction — the strict `close < open` / `close > open` inequalities a doji can satisfy neither.
- **REQ-61.6** (edge, adjacent pairs are independent): GIVEN candle `B` is simultaneously the confirmation of a bullish Order Block anchored at `A` (pair `A,B`) AND itself closes bullish so that `B` also satisfies the bearish-OB anchor condition for the adjacent pair `(B, C)`, and `C` fully engulfs `B` and closes bearish, WHEN detected, THEN BOTH Order Blocks are emitted independently — no exclusivity constraint between overlapping matches.

### REQ-62: Invalidation by first touch — V2
The system MUST mark an `ICTOrderBlock` `invalidated` at the FIRST candle strictly after its confirmation candle (`i+1`) — i.e. starting the scan at `i+2` — whose range overlaps the zone AT ALL: `candle.high >= bottom AND candle.low <= top`, for either direction. This is a touch test (wick or body, any overlap), not a close-through test. An Order Block never invalidated by series end remains `status="open"`, `invalidation_index=None`.
- **REQ-62.1** (happy): GIVEN a bullish Order Block with `bottom=1.0950, top=1.0980`, confirmed at `i+1`, and the candle at index `i+2` has `low=1.0955` (inside the zone), WHEN evaluated, THEN `status="invalidated"` at index `i+2`.
- **REQ-62.2** (edge, wick-only touch invalidates): GIVEN a later candle's wick merely dips to the zone boundary while its CLOSE remains entirely outside the zone, WHEN evaluated, THEN the Order Block IS invalidated at that candle — a mere touch mitigates it.
- **REQ-62.3** (edge, boundary-inclusive): GIVEN a later candle's `high` exactly equals `bottom` (or `low` exactly equals `top`), WHEN evaluated, THEN it counts as an overlap and invalidates.
- **REQ-62.4** (edge, confirmation candle excluded from the scan): GIVEN the confirmation candle `i+1` — which by definition already overlaps the zone, since full engulfment implies `i+1.high >= i.high` and `i+1.low <= i.low` — WHEN evaluated, THEN it is NEVER treated as the invalidating candle; the invalidation scan begins strictly at `i+2`, never at `i+1`.
- **REQ-62.5** (edge, never invalidated): GIVEN no candle from `i+2` onward ever overlaps the zone, WHEN evaluated at series end, THEN `status="open"`, `invalidation_index=None`.

### REQ-63: Registration as a Key Level source — V4 (Daily-tier source, H4-native invalidation, most-recent tie-break)
`core.key_level.KeyLevel.kind` MUST widen to `Literal["fvg", "ict_order_block"]`. The system MUST expose `to_key_levels(blocks: list[ICTOrderBlock]) -> list[KeyLevel]` producing, for every `ICTOrderBlock`, a `KeyLevel` with `kind="ict_order_block"`, `top`/`bottom` = the Order Block's own zone, `origin_index` = the CONFIRMATION candle's index (`i+1`) — an Order Block is not knowable as real until the very next candle's engulfing-and-close confirms it, always exactly one candle after the anchor — and `expiry_index` = `invalidation_index` when invalidated, absent when open. This raw output stays Daily-indexed and is NOT the final word on expiry for the Daily-tier flow — see REQ-63.7 (V4).

**Timeframe (V3)**: `detect_ict_order_blocks` MUST run against the Daily series (REQ-67's input), not the HTF (H4) series — Order Block Key Levels are Daily-tier, matching the 3-tier hierarchy (Daily Key Level → H4 CRT signal/purge → M15 execution). `origin_index` is an index into the Daily series, reindexed to H4-index-space per the existing rule (confirming day's CLOSE, unchanged by V4). (Previously: computed from the HTF/H4 series.)

**Invalidation granularity (V4, NEW — corrects V3)**: for a Daily-sourced Order Block, whether and when it becomes invalidated MUST be determined by scanning the H4 series candle-by-candle — starting at the reindexed `origin_index` (inclusive) — for the first H4 candle whose range overlaps the zone `[bottom, top]`, NOT by asking whether some Daily candle's full-day range touched it. The Order Block's own Daily-native `invalidation_index`/`status` (from `detect_ict_order_blocks`'s generic same-series scan) are NOT used for this — they are computed but discarded for the Daily-tier flow, replaced entirely by the H4-native scan's result. Rationale: a Daily candle's high/low aggregates 24h of movement into one blunt yes/no touch test, collapsing a Key Level's real survival time to at most ~1 day regardless of which of that day's ~6 H4 candles (if any) actually touched it first; checking H4 candle-by-candle gives the Key Level's true, finer-grained lifetime — matching how the level is actually consumed (against H4 purges) in the first place.

**Confluence matching (V3, MODIFIED)**: `alignment/htf_ltf.py`'s `_key_level_credit_map` MUST select the MOST RECENT qualifying Key Level (by `origin_index`) among candidates for a given purge, not the oldest. (Previously: oldest, `min(qualifying, key=lambda level: level.origin_index)`.) All other matching semantics are unchanged and hereby reconfirmed: a Daily Key Level qualifies for an H4 purge when the purge candle's own wick extreme (`_purge_wick_extremes`, unchanged) falls inside the Key Level's zone `[bottom, top]` inclusive of both edges, with NO tolerance — exact overlap only. A comparable external tool's 10% tolerance was explicitly considered and rejected for this change.

- **REQ-63.1** (happy, origin is the confirmation candle, not the anchor): GIVEN a bullish `ICTOrderBlock` anchored at Daily candle `i=13`, confirmed at candle `i+1=14`, WHEN presented as a `KeyLevel`, THEN `origin_index=14`, not `13`.
- **REQ-63.2** (alternate, expiry, V4 — supersedes V3's Daily-native reading): GIVEN a Daily-sourced Order Block whose zone is first touched by the H4 candle at H4 index `102` (not by asking which Daily candle touched it), WHEN the Key Level is credited, THEN `expiry_index=102`, an H4 index, derived from the H4-native scan (REQ-63.7).
- **REQ-63.3** (structural, regression): GIVEN `alignment/htf_ltf.py`'s own import statements, WHEN inspected after this change, THEN they are UNCHANGED — it still imports only `core.key_level`.
- **REQ-63.4** (NEW, most-recent tie-break): GIVEN two Daily Key Levels both qualify for the same H4 purge (both overlap the purge candle's wick extreme), WHEN credited, THEN the one with the GREATER `origin_index` (more recent) is selected, not the lesser.
- **REQ-63.5** (NEW, Daily-tier source): GIVEN a Daily series is provided (REQ-67), WHEN Order Blocks are detected for Key Level registration, THEN they are computed from the Daily series' own candles — never from the H4 series.
- **REQ-63.6** (NEW, exact overlap reconfirmed): GIVEN a purge candle's wick extreme lies outside a Daily Key Level's zone by any margin, however small, WHEN credited, THEN NO confluence is recorded for that Key Level — no tolerance is applied, regardless of how close the miss.
- **REQ-63.7** (NEW, V4, H4-native invalidation scan): GIVEN a Daily-sourced Order Block confirmed on Daily candle `D`, reindexed to H4 origin index `X`, WHEN checking for invalidation, THEN the system scans H4 candles starting at index `X` (inclusive) and marks the Order Block invalidated at the FIRST H4 candle whose range overlaps `[bottom, top]` — never at a Daily candle, and never by translating the Daily-native `invalidation_index`. If no H4 candle ever overlaps, the Order Block has no `expiry_index` (open indefinitely, same as an un-invalidated H4-native Order Block).

### REQ-64: No-lookahead (ICT Order Block) — V2 (simplified to fixed k=1)
`detect_ict_order_blocks(series.up_to(n))` MUST match the full-series output for every `ICTOrderBlock` whose confirmation candle (`i+1`) has index `< n` — a fixed `k=1` boundary-equality property (an Order Block anchored at `i` is knowable only once candle `i+1` exists in the prefix), the same standard fixed-K test already used by `swing`/`fvg`'s own no-lookahead properties. Invalidation status for an already-knowable Order Block MUST be re-derivable from any prefix that includes the invalidating candle, and MUST remain `open` in any shorter prefix.
- **REQ-64.1** (property test): prefix-consistency at fixed `k=1`, per ADR-03, mirroring the existing per-detector property tests in `tests/property/test_no_lookahead.py` — structurally simpler than V1's break-anchored property.

### REQ-65 (MODIFIED — reopens signed REQ-24/REQ-41.3, and confluence-core's REQ-56.5): `detections.csv` gains `key_level_source`
Destructive-sync reopening, same style as confluence-core's own REQ-45 reopening (V2→V3).

**Original REQ-24** (main spec V5): "Columns `timestamp,type,direction,price_high,price_low,status` (+`aligned` for Model-1 rows). Zero detections → header-only CSV, exit 0."

**MODIFIED REQ-24**: Columns `timestamp,type,direction,price_high,price_low,status,aligned,key_level_source` (8 columns). The new trailing `key_level_source` column is populated ONLY for Model-1 rows tagged `aligned` with a Key Level recorded (REQ-63), carrying that Key Level's `kind` (`fvg` or `ict_order_block`); empty for every other row (non-Model-1 rows, `unaligned`/`insufficient_htf_data` rows, and `aligned` rows with no Key Level recorded). Zero-detections behavior unchanged.
- **REQ-24.1** (unchanged): scannable for e.g. "any PENDING Model-1" without re-parsing the image.
- **REQ-24.2** (NEW, happy): GIVEN an `aligned` Model-1 signal credited to an ICTOrderBlock-sourced Key Level, WHEN `detections.csv` is written, THEN its `key_level_source` cell is exactly `"ict_order_block"`.
- **REQ-24.3** (NEW, edge): GIVEN a non-Model-1 row (swing/fvg/crt_range/mss), WHEN `detections.csv` is written, THEN its `key_level_source` cell is empty.

**Original REQ-41.3**: "GIVEN a detector run WITHOUT `--backtest`, WHEN `detections.csv` is written, THEN it has no `signal_id` column and matches the 7-column header exactly."

**MODIFIED REQ-41.3**: "...matches the 8-column header exactly (the 7 prior columns plus `key_level_source`)."

**Confluence-core's REQ-56.5** ("GIVEN a run WITHOUT `--backtest`, THEN `detections.csv`'s header is byte-identical to the 7-column header of REQ-24/REQ-41.3") likewise needs its "7-column" wording bumped to 8 once confluence-core resumes — that edit belongs to confluence-core's own spec file, not this one; flagged here (Risk #5) so it is not lost. Confluence-core's "Explicitly Out of Scope" table row ("Key Level source-attribution column ... Deferred to sub-change #2") is fulfilled by this REQ.
- **REQ-65.1** (edge, contract): GIVEN a run WITH `--backtest`, WHEN `detections.csv` is inspected, THEN its header is exactly 9 columns: the 8 above plus trailing `signal_id`.

### REQ-66: ICTOrderBlock's own discrimination number (real-data comparison) — V4 (Daily-tier, H4-native invalidation)
The system's real-data validation MUST run on the SAME 3 instruments (EURUSDm, GBPUSDm, DXYm) as sub-change #1's S-000.9 gate, WITH `--daily-csv`/`--daily-symbol` provided (REQ-67), gating confluence SOLELY on ICTOrderBlock-sourced Key Levels now detected on the Daily series with H4-native invalidation (REQ-63.7) (FVG Key Levels excluded from this run, to isolate the number), and the run's evidence MUST record, per instrument: the count of `aligned`, non-`fvg_fill` Model-1 signals; how many were credited an ICTOrderBlock Key Level; how many were not; the resulting `excluded_no_key_level` count; and `trades_opened`. (Previously, V3: Daily-native invalidation, measured 99.85–99.95% exclusion — INVALIDATED by the REQ-63.7 correction, not a comparison baseline; V2: ICTOrderBlock on the H4 series, no `--daily-csv`.) This produces a comparison figure against FVG's already-measured 1.5–3.0% (obs #449) AND against V2's own H4-tier ICTOrderBlock number (98.0–98.4%, `evidence/real-data-h4-m15.md`) — kept for the record, the corrected Daily-tier (V4) one is the one that matters going forward. This REQ does NOT gate pass/fail on any specific threshold — the number itself is the deliverable.
- **REQ-66.1** (happy): GIVEN the real EURUSDm H4/M15/Daily triple with `--backtest`, WHEN run gating on ICTOrderBlock alone, THEN the evidence records all counts above.
- **REQ-66.2** (edge, no threshold gate): GIVEN any resulting discrimination percentage, WHEN evidence is recorded, THEN the run does NOT fail or halt based on that percentage's value alone.
- **REQ-66.3** (edge, full coverage): GIVEN all 3 instruments run, WHEN evidence is compiled, THEN a complete count set exists for each of EURUSDm, GBPUSDm, and DXYm — not a subset.

### REQ-67 (NEW): Daily series CLI input
The system MUST accept an optional Daily-timeframe series input via `--daily-csv`/`--daily-symbol`, mirroring the existing optional `--htf-csv`/`--htf-symbol` pair-mode precedent (`cli.py` lines 56-57, 87-89): both flags MUST be provided together (error if only one is given), and omitting both is valid — the run proceeds without Daily-tier ICTOrderBlock Key Levels rather than failing.
- **REQ-67.1** (happy): GIVEN `--daily-csv` and `--daily-symbol` are both provided, WHEN the detector runs, THEN Order Block Key Levels are computed from the Daily series per REQ-63.
- **REQ-67.2** (edge, omitted): GIVEN both `--daily-csv` and `--daily-symbol` are omitted, WHEN the detector runs, THEN no ICTOrderBlock Key Levels are registered (FVG-only confluence, as before V3) and the run does NOT fail.
- **REQ-67.3** (edge, partial pair rejected): GIVEN only ONE of `--daily-csv`/`--daily-symbol` is provided, WHEN the CLI parses arguments, THEN it exits with an error before any detection runs — mirroring `--htf-csv`/`--htf-symbol`'s existing validation.

## Changes from V3

1. **REQ-63.7 added (H4-native invalidation scan)**: the single biggest correction of this pass. V3 computed a Daily-sourced Order Block's expiry by running `detect_ict_order_blocks`'s OWN generic invalidation scan on the Daily series (asking "did SOME Daily candle's full-day range touch the zone"), then translating that Daily-space boundary into an H4 index via `_ceiling_htf_index`. That collapses the Key Level's real survival time to at most ~1 day, regardless of which specific H4 candle within that day actually touched it — a full day's range is a blunt, coarse touch test. V4 instead scans H4 candles one-by-one starting at the reindexed origin index, and marks invalidation at the first H4 candle that actually overlaps the zone — the granularity the user's own mental model expected from the start ("quien mata ese OB de 1D debe ser una vela de 4h").
2. **REQ-63.2 rewritten**: `expiry_index` is now explicitly an H4 index derived from the H4-native scan, not a translated Daily-native one.
3. **`detect_ict_order_blocks`'s own Daily-native `invalidation_index`/`status` output is computed but discarded** for the Daily-tier confluence flow — it's still correct and used as-is for the (unrelated) H4-tier fallback path (REQ-67.2, `--daily-csv` omitted), where the function's own same-series scan IS the right one.
4. **REQ-66 rescoped again**: V3's real-data run (99.85–99.95% exclusion) is INVALIDATED by this correction, not a comparison baseline — the run must be repeated under REQ-63.7's corrected mechanism before any number is treated as evidence.
5. **Caught how**: not by design review — by the user restating their own mental model of the mechanism mid-conversation, after seeing V3's real-data result and a diagram of it. A reminder that "the code does X and X matches the written REQ" does not by itself prove X was the right thing to build.

## Changes from V2

1. **Timeframe pivot (user correction #3)**: Order Block Key Level detection moves from H4 to Daily — confirmed against `crt-scanner_old/core/htf_confluence.py`'s working 3-tier hierarchy (Daily Key Level → H4 CRT signal/purge → M15 execution). V1 and V2 both scoped this 2-tier (H4↔H4), confirmed wrong SCOPE, not just a wrong detection rule.
2. **REQ-63 substantially rewritten**: adds the Daily-series-source requirement and the `_key_level_credit_map` tie-break flip (oldest→most-recent). `to_key_levels`'s own mapping logic (`origin_index`=confirmation candle, `expiry_index`=invalidation_index) is UNCHANGED — only which series' indices those numbers refer to changes.
3. **REQ-63.3's "zero changes to alignment/htf_ltf.py" claim narrowed**: imports genuinely stay unchanged (still true, kept as REQ-63.3 verbatim), but the file is no longer byte-identical to its pre-this-change state — the tie-break comparator changes (new REQ-63.4).
4. **`_purge_wick_extremes`-based matching reconfirmed, NOT changed**: 3 rounds of user clarification confirmed the EXISTING wick-of-purge-candle mechanism is correct and needs no redesign — only its Key Level INPUT source changes from H4 to Daily. This was the change initially suspected to be needed and turned out not to be (new REQ-63.6 locks in "no tolerance" against future drift toward a tempting-but-rejected 10%-tolerance alternative seen in a comparable external tool, `htf_confluence.py`).
5. **REQ-66 rescoped to Daily-tier**: the real-data comparison run now requires `--daily-csv` and measures ICTOrderBlock's Daily-tier discrimination number, distinct from V2's now-superseded H4-tier number (98.0–98.4%, kept in the record for comparison, not as the design figure going forward).
6. **REQ-67 added**: new optional `--daily-csv`/`--daily-symbol` CLI input pair, following the existing `--htf-csv`/`--htf-symbol` precedent exactly (paired validation, optional, graceful degradation when omitted).
7. **Sequencing decision recorded**: this change (program sub-change #2) lands the 3-tier pattern FIRST as reference implementation; sub-change #1 (FVG, `crt-detector-key-level-confluence-core`) stays paused and ports the pattern later — not addressed by this spec.
8. **REQ-61/62/64/65 carry forward from V2 with NO changes** — none of them reference timeframe or Key Level source; the detection rule, invalidation, no-lookahead property, and CSV column plumbing are timeframe-agnostic.

**Not addressed by this rewrite (flagged for design V3)**: `design.md` still describes V2's H4-only wiring — stale, will be replaced by `sdd-design` V3. In particular, its File Changes Table needs `cli.py` (Daily series wiring + new flags), `alignment/htf_ltf.py` (tie-break, previously listed as "ZERO CHANGE"), and a Daily CSV loading path added.

## Changes from V1

1. **Detection rule replaced entirely** (user correction #1): V1's rule — "last opposing-bodied candle before an MSS-confirmed `StructureBreak`, backward scan bounded by `broken_swing_index`" — is replaced by the immediate-engulfing pattern ported from the user's own live `crt-scanner` tool (`D:\Josué\Documents\proyectos\crt-scanner\scanner\detectors\ob_detector.py`): for every consecutive pair `(i, i+1)`, `i` closes opposite-to-direction, `i+1` fully engulfs `i`'s range and closes in-direction. `crt-scanner`'s `bias` parameter is only a caller-side branch selector, not an independent validity filter — confirmed with the user — so this detector checks BOTH directions unconditionally at every pair, no external bias input.
2. **Eliminates the MSS/StructureBreak dependency from V1 entirely** — no `core/structure_break.py`, no `composite/mss.py::to_structure_breaks` adapter, no backward scan, no swing-break anchoring. `detect_ict_order_blocks` no longer needs a `breaks: list[StructureBreak]` parameter.
3. **Invalidation changed from full-body close-through to first touch** (user correction #2, "con que toque el OB para mí ya está mitigada"): V1 required a candle's CLOSE to fully pass through the zone; V2 invalidates on ANY range overlap, wick or otherwise. The scan now explicitly starts at `i+2`, not `i+1` — the confirmation candle `i+1` always overlaps the zone by definition, so scanning from `i+1` would trivially self-invalidate every Order Block the instant it forms.
4. **`origin_index` simplified**: from "the crediting `StructureBreak`'s index" (unbounded, potentially distant) to "the confirmation candle's index (`i+1`)" — always exactly one candle after the anchor.
5. **REQ-64 simplified**: from an unbounded-forward MSS monotonicity guarantee to a fixed `k=1` boundary-equality property, structurally identical in shape to `swing`/`fvg`'s own no-lookahead properties.
6. **Dropped REQ-61.3** ("last-one-wins among backward-scan candidates") — no longer applicable; there is no backward scan or candidate competition under the pair-based rule. Its slot is filled by REQ-61.6, the one real ambiguity the new mechanism DOES produce (a candle as both confirmation and next-pair anchor).
7. **REQ-65 and REQ-66 carry forward with no substantive change** — neither references the dropped `StructureBreak`/MSS mechanics; both are expressed purely at the `KeyLevel`/`kind` abstraction (REQ-63's contract).

**Not addressed by this rewrite (flagged for design V2)**: the `## Approach`/`## Risks` sections above (and `proposal.md`, kept as V1 history) still describe the eliminated `core/structure_break.py`/`composite/mss.py::to_structure_breaks` design — stale, will be replaced by `sdd-design` V2.
