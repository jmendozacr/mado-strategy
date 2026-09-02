# Proposal + Spec: ICT Order Block Detector

> M light pipeline — merged propose+spec artefact. **Spec V2** (this file) — REQ-61..64 rewritten per user correction after S-000's real-data gate (obs #457-ish investigation trail below); REQ-65/66 carry forward unchanged. `proposal.md` still holds V1 for history; this file is now spec-authoritative. See "## Changes from V1" at the end of the Requirements section.

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
  - Real-data comparison run on the same H4/M15 pairing and same 3 instruments (EURUSDm, GBPUSDm, DXYm) as #1's S-000.9 gate, gating on ICTOrderBlock alone, producing ICTOrderBlock's own discrimination number
out_of_scope:
  - crt-detector-breaker-block (sub-change #3)
  - Rejection Block, Swing as Key Level sources (deferred program-wide)
  - A sources-registry abstraction for >2 sources (Rule of Three; plain concat suffices at 2)
  - ICT Order Block as its own detections.csv row/type or overlay.png marker — it is HTF-only, computed-not-rendered, mirroring confluence-core's REQ-57 treatment of HTF FVGs
  - --types ict_order_block CLI flag — nothing to filter; there is no such row type to include/exclude
  - Mandatory liquidity-sweep or FVG-coincidence validity filters (product decision, obs #464: base rule only)
  - Chart rendering polish, new config surface beyond ICTOrderBlockConfig
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

`cli.py` composes: `to_structure_breaks(detect_mss_events(series, config.mss, swings=swings))` → `detect_ict_order_blocks(...)` → `to_key_levels(...)`, concatenated with FVG's HTF key levels before feeding `tag_alignment`. **`alignment/htf_ltf.py` needs zero changes** — confirmed it already imports only `core.key_level` (REQ-53.4 in confluence-core's spec).

**Config**: `ICTOrderBlockConfig` is an empty frozen dataclass, mirroring `SwingConfig`'s existing precedent. The base rule (per product decision, obs #464) has no discretionary threshold — the backward scan is bounded by `StructureBreak.broken_swing_index` itself (a structural bound, not a magic number), and invalidation is a deterministic close-through-zone check. This satisfies REQ-25.1's config-completeness scan without inventing an unused parameter.

**`detections.csv` column**: `_HEADER` in `viz/table.py` currently `[..., "aligned"]` (7 columns); this change appends `"key_level_source"` (8 columns), and `_HEADER_WITH_SIGNAL_ID = _HEADER + ["signal_id"]` becomes 9 columns automatically — a one-line diff, same pattern `signal_id` already used.

**Branch dependency (called out, not silently assumed)**: this change's seam (`core/key_level.py`, `primitives/fvg.py`'s `to_key_levels`, the HTF-key-level wiring in `cli.py`) currently exists only on `wip/crt-detector-key-level-confluence-core-s000` (uncommitted, not on `master`). Per the program's revised sequencing (obs #413), `sdd-apply` for this change builds against that branch's state, not `master` directly — a slice-level integration detail, flagged here so it isn't rediscovered mid-apply.

## Risks

1. **Branch dependency**: building on an uncommitted, paused sub-change's branch — if that branch is rebased or abandoned before #1 resumes, this change's foundation moves under it.
2. **Base-rule-only choice may reproduce weak discrimination** — addressed explicitly by the go/no-go item in Success Criteria, not silently absorbed.
3. **Backward-scan bound is a design-time detail** (explore open question #2) — `broken_swing_index` is used as the natural bound; if design deviates, it should be justified against ICT convention, since it directly affects which candle gets flagged and thus the comparison number's validity.
4. **Second CSV schema reopening** (after #1's REQ-45 in the same program) — the pattern is now proven twice; the column itself (`key_level_source`, a source `kind` string) generalizes cleanly to sub-change #3's future Breaker Block source with no further schema change expected.
5. **Cross-change spec drift**: confluence-core's own signed spec (REQ-56.5, "Explicitly Out of Scope" table) states the 7-column header "stays signed" and is "NOT touched" — that statement becomes stale once this change ships. Reconciling confluence-core's own spec text is confluence-core's job when it resumes/archives, not this change's — flagged here so it isn't lost.

## Rollback Plan

Purely additive except two 1–3 line touches (`core/key_level.py`'s `Literal` widening, `viz/table.py`'s `_HEADER`). No persisted state, no migrations — `detections.csv`/`trades.csv` are regenerated artefacts. Revert = `git revert` the change's commit(s); no backfill required.

## Success Criteria

- All REQ-61..66 scenarios pass; no-lookahead property test green; `uv run lint-imports` passes (layering respected).
- Real-data run completes on EURUSDm/GBPUSDm/DXYm (H4/M15), producing ICTOrderBlock's own discrimination percentage, disclosed alongside FVG's 1.5–3.0% (obs #449) — this number is descriptive evidence, not a pass/fail gate on this change.
- **Explicit go/no-go note (not a REQ)**: if ICTOrderBlock's discrimination is ALSO in the 1–3% range, this is signal about the confluence-gate CONCEPT itself, not just FVG — escalate to the user before automatically proceeding to `crt-detector-breaker-block` (#3), per triage's PM flag.
- REQ-24/REQ-41.3 (main spec) and REQ-56.5 (confluence-core spec) amendments applied consistently; `detections.csv` header verified 8/9 columns as specified.

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

### REQ-63: Registration as a Key Level source — V2 (origin_index updated)
`core.key_level.KeyLevel.kind` MUST widen to `Literal["fvg", "ict_order_block"]`. The system MUST expose `to_key_levels(blocks: list[ICTOrderBlock]) -> list[KeyLevel]` producing, for every `ICTOrderBlock`, a `KeyLevel` with `kind="ict_order_block"`, `top`/`bottom` = the Order Block's own zone, `origin_index` = the CONFIRMATION candle's index (`i+1`) — an Order Block is not knowable as real until the very next candle's engulfing-and-close confirms it, always exactly one candle after the anchor — and `expiry_index` = `invalidation_index` when invalidated, absent when open. `alignment/htf_ltf.py` MUST require ZERO changes.
- **REQ-63.1** (happy, origin is the confirmation candle, not the anchor): GIVEN a bullish `ICTOrderBlock` anchored at candle `i=13`, confirmed at candle `i+1=14`, WHEN presented as a `KeyLevel`, THEN `origin_index=14`, not `13`.
- **REQ-63.2** (alternate, expiry): GIVEN an `ICTOrderBlock` invalidated at index `40`, WHEN presented as a `KeyLevel`, THEN `expiry_index=40`.
- **REQ-63.3** (structural, regression): GIVEN `alignment/htf_ltf.py`'s own import statements, WHEN inspected after this change, THEN they are UNCHANGED — it still imports only `core.key_level`.

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

### REQ-66: ICTOrderBlock's own discrimination number (real-data comparison)
The system's real-data validation MUST run on the SAME H4/M15 pairing and SAME 3 instruments (EURUSDm, GBPUSDm, DXYm) as sub-change #1's S-000.9 gate, gating confluence SOLELY on ICTOrderBlock-sourced Key Levels (FVG Key Levels excluded from this run, to isolate the number), and the run's evidence MUST record, per instrument: the count of `aligned`, non-`fvg_fill` Model-1 signals; how many were credited an ICTOrderBlock Key Level; how many were not; the resulting `excluded_no_key_level` count; and `trades_opened`. This produces a comparison figure against FVG's already-measured 1.5–3.0% (obs #449). This REQ does NOT gate pass/fail on any specific threshold — the number itself is the deliverable (explicitly NOT mirroring #1's REQ-60.2 pattern).
- **REQ-66.1** (happy): GIVEN the real EURUSDm H4/M15 pair with `--backtest`, WHEN run gating on ICTOrderBlock alone, THEN the evidence records all counts above.
- **REQ-66.2** (edge, no threshold gate): GIVEN any resulting discrimination percentage, WHEN evidence is recorded, THEN the run does NOT fail or halt based on that percentage's value alone.
- **REQ-66.3** (edge, full coverage): GIVEN all 3 instruments run, WHEN evidence is compiled, THEN a complete count set exists for each of EURUSDm, GBPUSDm, and DXYm — not a subset.

## Changes from V1

1. **Detection rule replaced entirely** (user correction #1): V1's rule — "last opposing-bodied candle before an MSS-confirmed `StructureBreak`, backward scan bounded by `broken_swing_index`" — is replaced by the immediate-engulfing pattern ported from the user's own live `crt-scanner` tool (`D:\Josué\Documents\proyectos\crt-scanner\scanner\detectors\ob_detector.py`): for every consecutive pair `(i, i+1)`, `i` closes opposite-to-direction, `i+1` fully engulfs `i`'s range and closes in-direction. `crt-scanner`'s `bias` parameter is only a caller-side branch selector, not an independent validity filter — confirmed with the user — so this detector checks BOTH directions unconditionally at every pair, no external bias input.
2. **Eliminates the MSS/StructureBreak dependency from V1 entirely** — no `core/structure_break.py`, no `composite/mss.py::to_structure_breaks` adapter, no backward scan, no swing-break anchoring. `detect_ict_order_blocks` no longer needs a `breaks: list[StructureBreak]` parameter.
3. **Invalidation changed from full-body close-through to first touch** (user correction #2, "con que toque el OB para mí ya está mitigada"): V1 required a candle's CLOSE to fully pass through the zone; V2 invalidates on ANY range overlap, wick or otherwise. The scan now explicitly starts at `i+2`, not `i+1` — the confirmation candle `i+1` always overlaps the zone by definition, so scanning from `i+1` would trivially self-invalidate every Order Block the instant it forms.
4. **`origin_index` simplified**: from "the crediting `StructureBreak`'s index" (unbounded, potentially distant) to "the confirmation candle's index (`i+1`)" — always exactly one candle after the anchor.
5. **REQ-64 simplified**: from an unbounded-forward MSS monotonicity guarantee to a fixed `k=1` boundary-equality property, structurally identical in shape to `swing`/`fvg`'s own no-lookahead properties.
6. **Dropped REQ-61.3** ("last-one-wins among backward-scan candidates") — no longer applicable; there is no backward scan or candidate competition under the pair-based rule. Its slot is filled by REQ-61.6, the one real ambiguity the new mechanism DOES produce (a candle as both confirmation and next-pair anchor).
7. **REQ-65 and REQ-66 carry forward with no substantive change** — neither references the dropped `StructureBreak`/MSS mechanics; both are expressed purely at the `KeyLevel`/`kind` abstraction (REQ-63's contract).

**Not addressed by this rewrite (flagged for design V2)**: the `## Approach`/`## Risks` sections above (and `proposal.md`, kept as V1 history) still describe the eliminated `core/structure_break.py`/`composite/mss.py::to_structure_breaks` design — stale, will be replaced by `sdd-design` V2.
