# Design: ICT Order Block Detector (`crt-detector-ict-order-block`)

**Spec**: V2 signed (REQ-61..66) | **Triage**: M | **architecture_impact**: additive

## 1. Architecture Overview

New/modified pieces against the layered pipeline (`core → primitives → composite/entries → alignment → backtest → viz/cli`):

```
core/key_level.py         [MOD, unchanged from V1]  KeyLevel.kind widened: Literal["fvg", "ict_order_block"]
core/config.py            [MOD, unchanged from V1]  ICTOrderBlockConfig (empty) already wired into DetectorConfig
        │
primitives/ict_order_block.py [REWRITE]  detect_ict_order_blocks(), to_key_levels(), ICTOrderBlock
        │   (leaf primitive — imports only core.candle/core.config/core.key_level, same shape as fvg.py/swing.py)
        │
alignment/htf_ltf.py      [ZERO CHANGE — confirmed, REQ-63.3]  already source-agnostic (imports only core.key_level)
backtest/simulate.py      [ZERO CHANGE]  already checks only `key_level is None`, never `.kind`
        │
viz/table.py               [MOD]  _HEADER + "key_level_source"; thread AlignedSignal.key_level.kind into rows
cli.py                      [MOD]  single direct call: detect_ict_order_blocks(htf_series, config.ict_order_block)
                                    → to_key_levels(), concatenated with FVG's HTF key levels before tag_alignment

REMOVED from V1:
core/structure_break.py   [DELETE]  StructureBreak — no cross-layer type needed any more
composite/mss.py          [REVERT]  to_structure_breaks(events) adapter removed entirely — nothing else used it
```

V2's rule needs no `StructureBreak`, no `MSSEvent`, no swings, no backward scan — `primitives/ict_order_block.py` now imports only `core.candle`, `core.config`, `core.key_level`, exactly the same import shape as `primitives/fvg.py`. It is no longer a "second instance of the `core/key_level.py` cross-layer-type pattern" (V1's framing) — there is no cross-layer boundary to cross at all. `composite/mss.py` is untouched by this change end-to-end: the `to_structure_breaks` adapter V1 added there is deleted, returning the file to its pre-this-change state.

## 2. File Changes Table

| Path | Action | Purpose |
|---|---|---|
| `detector/core/structure_break.py` | **DELETE** | `StructureBreak` — no longer needed anywhere |
| `detector/composite/mss.py` | **REVERT** (remove `to_structure_breaks` + the `core.structure_break` import) | Confirmed nothing else in the codebase uses the adapter |
| `detector/core/key_level.py` | MOD, unchanged from V1 | Widen `kind: Literal["fvg"]` → `Literal["fvg", "ict_order_block"]` |
| `detector/core/config.py` | MOD, comment fix only | `ICTOrderBlockConfig` (empty) stays byte-identical; docstring comment updated (no field/behavior change) |
| `detector/primitives/ict_order_block.py` | **REWRITE** | `ICTOrderBlock` (field renamed `break_index` → `confirmation_index`), `detect_ict_order_blocks()` (no `breaks` param), `to_key_levels()` |
| `detector/cli.py` | MOD | Drop `to_structure_breaks` import + `htf_swings`/`htf_breaks` composition; call `detect_ict_order_blocks(htf_series, config.ict_order_block)` directly |
| `detector/viz/table.py` | MOD | `_HEADER` gains `"key_level_source"`; `_row`/`_model1_row` thread `AlignedSignal.key_level.kind` (REQ-65) |
| `detector/tests/test_ict_order_block.py` | **REWRITE** | REQ-61/62/63 unit tests against the pair-based rule |
| `detector/tests/property/test_no_lookahead.py` | MOD | `test_ict_order_block_detection_has_no_lookahead` (REQ-64), fixed `k=1` |
| `detector/tests/test_mss.py` | **REVERT** (remove `to_structure_breaks` import + its 2 tests, drop unused `SwingPoint` import) | `to_structure_breaks` no longer exists |
| `detector/tests/test_alignment.py` | NO CHANGE | `test_htf_ltf_imports_unchanged` (REQ-63.3) still correct |
| `detector/tests/test_cli.py` | NO CHANGE | concatenation test mocks the adapter directly, independent of internal rule |
| `detector/tests/test_table.py` | MOD | REQ-24.2/24.3/65.1 column tests |

No changes needed: `alignment/htf_ltf.py`, `backtest/simulate.py`, `.importlinter`, `tests/test_fitness_config.py`.

## 3. Data Model

```python
# detector/primitives/ict_order_block.py
@dataclass(frozen=True)
class ICTOrderBlock:
    candle_index: int          # anchor (i)
    confirmation_index: int    # i+1 — becomes KeyLevel.origin_index (REQ-63.1)
    direction: Literal["bullish", "bearish"]
    top: float
    bottom: float
    status: Literal["open", "invalidated"]
    invalidation_index: int | None = None
```

**Field rename: `break_index` → `confirmation_index`.** V1's name described "the crediting `StructureBreak`'s index" — an unbounded, potentially-distant reference to a different detector's output. V2's field is always exactly `candle_index + 1`, the pair's own confirmation candle — a different concept (a fixed structural offset, not a foreign detector's result), not merely a renamed continuation of the same thing.

```python
@dataclass(frozen=True)
class ICTOrderBlockConfig:
    pass  # base rule is fully structural — engulfment and touch-invalidation are hard geometric tests, no discretionary threshold
```

Confirmed against REQ-61/62's exact wording: engulfment and confirmation-close direction are hard inequalities with no tunable margin; invalidation is a hard range-overlap test, also with no tunable margin. `ICTOrderBlockConfig` staying empty is correct, not a placeholder.

`core/key_level.py`: `kind: Literal["fvg", "ict_order_block"]` (unchanged from V1).

## 4. Interface Contracts

```python
# detector/primitives/ict_order_block.py
from dataclasses import dataclass
from typing import Literal

from core.candle import Candle, OHLCSeries
from core.config import ICTOrderBlockConfig
from core.key_level import KeyLevel


@dataclass(frozen=True)
class ICTOrderBlock:
    candle_index: int
    confirmation_index: int
    direction: Literal["bullish", "bearish"]
    top: float
    bottom: float
    status: Literal["open", "invalidated"]
    invalidation_index: int | None = None


def detect_ict_order_blocks(
    series: OHLCSeries, config: ICTOrderBlockConfig = ICTOrderBlockConfig(),
) -> list[ICTOrderBlock]:
    """Single forward pass over consecutive candle pairs (i, i+1) (REQ-61):
    checks BOTH the bullish and bearish engulfing conditions unconditionally
    at every pair — no bias input, no external StructureBreak. A qualifying
    pair yields one ICTOrderBlock zoned to candle i's own body; the forward
    invalidation scan (REQ-62) then resolves status/invalidation_index
    independently per block, starting at i+2 (REQ-62.4)."""
    candles = series.candles
    blocks = []
    for i in range(len(candles) - 1):
        anchor, confirmation = candles[i], candles[i + 1]
        direction = _match(anchor, confirmation)
        if direction is None:
            continue
        top = max(anchor.open, anchor.close)
        bottom = min(anchor.open, anchor.close)
        status, invalidation_index = _invalidation(candles, i, top, bottom)
        blocks.append(
            ICTOrderBlock(
                candle_index=i, confirmation_index=i + 1, direction=direction,
                top=top, bottom=bottom, status=status, invalidation_index=invalidation_index,
            )
        )
    return blocks


def _match(anchor: Candle, confirmation: Candle) -> Literal["bullish", "bearish"] | None:
    engulfs = confirmation.high >= anchor.high and confirmation.low <= anchor.low
    if not engulfs:
        return None
    if anchor.close < anchor.open and confirmation.close > confirmation.open:
        return "bullish"
    if anchor.close > anchor.open and confirmation.close < confirmation.open:
        return "bearish"
    return None


def _invalidation(
    candles: tuple[Candle, ...], anchor_index: int, top: float, bottom: float,
) -> tuple[Literal["open", "invalidated"], int | None]:
    """REQ-62: the first candle from i+2 onward whose range overlaps the
    zone at all (wick or body, boundary-inclusive) invalidates. The scan
    starts at i+2, not i+1 — the confirmation candle always overlaps the
    zone by definition of full engulfment, so starting at i+1 would
    trivially self-invalidate every Order Block the instant it forms
    (REQ-62.4)."""
    for i in range(anchor_index + 2, len(candles)):
        candle = candles[i]
        if candle.high >= bottom and candle.low <= top:
            return "invalidated", i
    return "open", None


def to_key_levels(blocks: list[ICTOrderBlock]) -> list[KeyLevel]:
    return [
        KeyLevel(
            kind="ict_order_block", top=b.top, bottom=b.bottom,
            origin_index=b.confirmation_index, expiry_index=b.invalidation_index,
        )
        for b in blocks
    ]
```

`direction` is not passed as a parameter anywhere — both directions are checked unconditionally at every pair (REQ-61's "no external bias input"). A doji anchor (`open == close`) satisfies neither `close < open` nor `close > open`, so `_match` returns `None` for it without a dedicated check (REQ-61.5 falls out of the existing inequalities). REQ-61.6 (adjacent pairs independent) needs no dedicated handling — the loop evaluates every pair `i` independently.

`cli.py` composition (HTF-only), replacing V1's `htf_swings`/`htf_breaks` chain:
```python
htf_order_blocks = detect_ict_order_blocks(htf_series, config.ict_order_block)
htf_key_levels = (
    to_key_levels(detect_fvgs(htf_series, config.fvg))
    + ict_order_block_to_key_levels(htf_order_blocks)
)
```
The `htf_swings = detect_swings(htf_series, config.swing)` line V1 added is deleted along with it. The `from composite.mss import MSSEvent, detect_mss_events, to_structure_breaks` import line drops `to_structure_breaks`; `MSSEvent`/`detect_mss_events` stay (still needed for the unrelated LTF `mss_events` row in `_Detections`). The naming-collision aliasing (`ict_order_block_to_key_levels`) is unchanged.

## 5. ADRs

V1's ADR-A (`StructureBreak` layering resolution) and ADR-B (backward-scan bound) are **dropped** — neither question exists in V2.

- **ADR-C — no sweep-line optimization for `detect_ict_order_blocks`.** The pair-scan is a single unconditional O(n) forward pass. The per-block invalidation scan is structurally the same shape as `fvg.py`'s original per-FVG fill-status scan before its own two-heap sweep fix — an independent forward scan per candidate, worst case O(blocks × remaining-length). `fvg.py`/`mss.py`'s sweep fixes were driven by *measured* real-data cost at **LTF** scale (~100,000 M5 candles, tens of thousands of open candidates, 189s/212s measured); this detector runs **HTF-only** (thousands of candles). Even the pathological worst case here is negligible in wall-clock terms. Building the sweep pattern now, without evidence it's needed, would be premature optimization — revisit only if a real-data run shows otherwise.
- **ADR-D — `key_level_source` CSV plumbing is column population, not new architecture.** Unchanged from V1: `AlignedSignal.key_level: KeyLevel | None` already exists (sub-change #1's own design). The only genuine new plumbing is `viz/table.py` threading it into rows.

## 6. Flow Changes Table

| Aspect | Before | After |
|---|---|---|
| `detections.csv` header (no `--backtest`) | 7 columns, ends `...,status,aligned` | 8 columns, ends `...,aligned,key_level_source` |
| `detections.csv` header (`--backtest`) | 8 columns, ends `...,aligned,signal_id` | 9 columns, ends `...,aligned,key_level_source,signal_id` |
| `key_level_source` cell, credited `aligned` Model-1 row | *(didn't exist)* | `"fvg"` or `"ict_order_block"` |
| `key_level_source` cell, all other rows | *(didn't exist)* | empty string |
| Confluence gate credit sources | FVG-sourced Key Levels only | FVG- **or** ICTOrderBlock-sourced (concatenated) |
| Backtest population | Excluded if no FVG Key Level covered the purge | May now include signals an ICTOrderBlock Key Level covers instead |
| Real-data validation | Only FVG discrimination number exists (1.5–3.0%, obs #449) | A 2nd, independent ICTOrderBlock-only number exists (REQ-66) |

This table is unchanged in shape from V1. What is NOT the same: V1's real-data investigation (obs #471/#472) measured the MSS-anchored rule's restrictiveness, now entirely replaced. There is no carried-forward number for V2's pair-based rule — REQ-66's real-data run (S-000.12) must execute fresh against this design.

## 7. Test Derivation Table

| REQ-ID | Test file | Test name/shape |
|---|---|---|
| REQ-61.1 | `tests/test_ict_order_block.py` | `test_bullish_order_block_detected_on_engulfing_pair` |
| REQ-61.2 | same | `test_bearish_order_block_detected_on_engulfing_pair` |
| REQ-61.3 | same | `test_partial_engulf_yields_no_order_block` |
| REQ-61.4 | same | `test_wrong_confirmation_close_yields_no_order_block` |
| REQ-61.5 | same | `test_doji_anchor_never_qualifies` |
| REQ-61.6 | same | `test_adjacent_overlapping_pairs_both_emit_independently` |
| REQ-62.1 | same | `test_invalidated_on_first_range_overlap_after_confirmation` |
| REQ-62.2 | same | `test_wick_only_touch_invalidates` |
| REQ-62.3 | same | `test_boundary_touch_invalidates` |
| REQ-62.4 | same | `test_confirmation_candle_itself_never_treated_as_invalidating` |
| REQ-62.5 | same | `test_remains_open_when_never_touched_to_series_end` |
| REQ-63.1 | same | `test_key_level_origin_index_is_the_confirmation_candle_not_the_anchor` |
| REQ-63.2 | same | `test_key_level_expiry_index_matches_invalidation_index` |
| REQ-63.3 | `tests/test_alignment.py` | `test_htf_ltf_imports_unchanged` — existing, no change |
| REQ-64/64.1 | `tests/property/test_no_lookahead.py` | `test_ict_order_block_detection_has_no_lookahead` (below) |
| REQ-24.2 | `tests/test_table.py` | `test_ict_order_block_credited_signal_writes_kind_in_key_level_source` |
| REQ-24.3 | same | `test_non_model1_rows_leave_key_level_source_empty` |
| REQ-41.3 (MOD) | same | extends header test — 9-column header |
| REQ-65.1 | same | covered by the same header assertion |
| REQ-66/66.1–66.3 | manual (not pytest) | Real-data CLI run, EURUSDm/GBPUSDm/DXYm H4/M15, gated on ICTOrderBlock alone |
| `uv run lint-imports` | CI-style check | ADR-01 layers contract holds (trivially — `primitives/ict_order_block.py` imports only `core`) |

**No-lookahead property test (REQ-64) — fixed `k=1`**, structurally identical in shape to `swing`'s own no-lookahead property:

```python
_ICT_ORDER_BLOCK_K = 1

@given(series=ohlc_series())
@settings(max_examples=100)
def test_ict_order_block_detection_has_no_lookahead(series: OHLCSeries):
    full_blocks = detect_ict_order_blocks(series)
    full_by_key = {(b.candle_index, b.direction): b for b in full_blocks}

    for n in range(3, len(series.candles) + 1):
        truncated_blocks = detect_ict_order_blocks(series.up_to(n))
        settled_boundary = n - _ICT_ORDER_BLOCK_K - 1

        settled_truncated = [b for b in truncated_blocks if b.candle_index <= settled_boundary]
        settled_full_keys = {
            key for key, block in full_by_key.items() if block.candle_index <= settled_boundary
        }
        assert {(b.candle_index, b.direction) for b in settled_truncated} == settled_full_keys

        for block in settled_truncated:
            full_block = full_by_key[(block.candle_index, block.direction)]
            assert block.confirmation_index == full_block.confirmation_index
            assert (block.top, block.bottom) == (full_block.top, full_block.bottom)

            invalidated_within_prefix = (
                full_block.invalidation_index is not None
                and full_block.invalidation_index < n
            )
            if invalidated_within_prefix:
                assert block.status == "invalidated"
                assert block.invalidation_index == full_block.invalidation_index
            else:
                assert block.status == "open"
                assert block.invalidation_index is None
```

Much simpler than V1's design (which inherited MSS's unbounded-forward monotonicity property) — V2's test calls only `detect_ict_order_blocks(series)`.

## 8. Migration Plan

None. Purely additive plus mechanical touches (and the removal of V1's now-dead `StructureBreak` mechanism, itself a pure subtraction). No persisted state. Rollback = `git revert`.

## 9. `architecture_impact`: additive

Even more clearly additive than V1: one new leaf primitive module mirroring an existing precedent (`fvg.py`) exactly — same layer, same import shape (`core` only), zero cross-layer type introduced, zero changes to `composite`, zero changes to `alignment`/`backtest`. No layer added, no dependency direction changes, no existing contract broken — every row in §1 `aligns`. The only genuinely new plumbing anywhere in this design is the `viz/table.py` column-threading (ADR-D).

## 10. `open_questions`: none

All of V1's design-time questions are resolved or dissolved outright under V2's simpler rule: field shapes and the zone definition are fixed verbatim in the signed spec; the field rename is a design-time naming call, reasoning stated in §3; there is no backward-scan bound to close; the sweep-line question is settled in ADR-C with an explicit, evidence-based "not yet"; `ICTOrderBlockConfig`'s emptiness is reconfirmed against REQ-61/62's exact hard-inequality wording.
