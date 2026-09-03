# Design: ICT Order Block Detector (`crt-detector-ict-order-block`)

**Spec**: V4 signed (REQ-61..67, REQ-63.7 new) | **Triage**: M | **architecture_impact**: additive

## 0a. V4 correction (read this first)

V3's real-data run (99.85–99.95% exclusion) exposed a mechanism gap: ADR-E's `expiry_index` reindexing translated a boundary that `detect_ict_order_blocks` computed by scanning the DAILY series for invalidation (any Daily candle's full-day range touching the zone), then converted that Daily-space boundary into an H4 index. That's a coarse, blunt touch test — it can't distinguish "touched at the very start of the day" from "touched at the very end," and for the ~60% of Order Blocks with a 1-day Daily-native window, it collapsed `origin_index`/`expiry_index` to the same H4 index, making them structurally uncreditable regardless of price action (see `evidence/real-data-h4-m15.md` § "V3 run"). The user's own mental model, surfaced only after seeing that result, was different from the start: the KILLER of a Daily-sourced Order Block should be an H4 candle, checked one at a time — a day is ~6 independent chances, not one blunt one. REQ-63.7 (spec V4) now requires this. §5 (ADR-E) and §4b are rewritten below; V3's original text is not preserved inline — see spec.md's "## Changes from V3" for the full delta record.

## 0. V3 change summary (read this first)

V2's design assumed Order Block Key Levels lived on the SAME series (H4) as the CRT purge they credit — so `alignment/htf_ltf.py` needed "ZERO CHANGE" and index comparisons were safe by construction. V3 breaks that assumption: Order Block Key Levels now come from the **Daily** series (REQ-63), a DIFFERENT series with a different index space than the H4 series `_key_level_credit_map` compares against. This surfaced a real defect risk during design (not caught by spec review): `KeyLevel.origin_index`/`expiry_index` are pure integers with no series identity attached, and `_key_level_credit_map` compares them directly against H4 `purge_index` values. Concatenating Daily-indexed and H4-indexed `KeyLevel`s into one list and comparing their raw indices would silently produce wrong results — see ADR-E. §2/§4/§5 below are new or substantially rewritten; §3 (`ICTOrderBlock`/`detect_ict_order_blocks`/`to_key_levels`) is confirmed UNCHANGED from V2.

## 1. Architecture Overview

New/modified pieces against the layered pipeline (`core → ingestion → primitives → composite/entries → alignment → backtest → viz/cli`):

```
core/key_level.py         [NO CHANGE]              KeyLevel unchanged — kind already includes "ict_order_block" (V2)
core/config.py            [NO CHANGE]              ICTOrderBlockConfig (empty) already wired into DetectorConfig
        │
primitives/ict_order_block.py [NO CHANGE]  ICTOrderBlock, detect_ict_order_blocks(), to_key_levels() — same
        │   pure functions as V2; V3 changes WHICH series the caller passes in, not their bodies
        │
ingestion/loader.py       [NO CHANGE]              load_mt5_csv() is granularity-agnostic — reused as-is for Daily
alignment/htf_ltf.py      [MOD, V3]  tag_alignment() gains daily_series/daily_key_levels params (reindexing +
        │                            merge, ADR-E); _key_level_credit_map's tie-break flips to most-recent (REQ-63.4)
backtest/simulate.py      [NO CHANGE]  already checks only `key_level is None`, never `.kind`/`.origin_index`
        │
viz/table.py               [NO CHANGE, V3]  V2's key_level_source column plumbing (REQ-65) is source-agnostic already
cli.py                      [MOD, V3]  new --daily-csv/--daily-symbol args (REQ-67) + composition passes both
                                        htf_series and daily_series through to tag_alignment
```

`primitives/ict_order_block.py` needs literally zero code changes for V3 — it was already series-agnostic (V2's own §1 conclusion: "same import shape as `fvg.py`"). What changes is entirely at the composition boundary: `cli.py` now loads a THIRD series, and `alignment/htf_ltf.py` gains the one piece of new logic V3 actually requires — reconciling two different series' index spaces before comparing them (ADR-E).

## 2. File Changes Table

| Path | Action | Purpose |
|---|---|---|
| `detector/cli.py` | MOD | New `--daily-csv`/`--daily-symbol` args (REQ-67, mirrors `--htf-csv`/`--htf-symbol` exactly); load `daily_series` via plain `load_mt5_csv` (NOT `load_pair` — see ADR-F); pass `daily_series` + Daily-sourced key levels into `tag_alignment` |
| `detector/alignment/htf_ltf.py` | MOD | `tag_alignment()` gains `daily_series`/`daily_key_levels` optional params; new `_reindex_daily_key_levels()` (ADR-E); `_key_level_credit_map`'s tie-break `min`→most-recent (REQ-63.4) |
| `detector/tests/test_alignment.py` | MOD | New tests for reindexing (ADR-E) and the most-recent tie-break (REQ-63.4); existing FVG-only tests unchanged (no `daily_series` passed → old behavior exactly) |
| `detector/tests/test_cli.py` | MOD | REQ-67.1/67.2/67.3 — `--daily-csv`/`--daily-symbol` pairing validation, composition wiring |
| `detector/tests/test_ict_order_block.py` | NO CHANGE | REQ-61/62/63.1/63.2 unit tests already exercise the series-agnostic detector directly — nothing about them assumes H4 |

No changes needed: `detector/primitives/ict_order_block.py`, `detector/ingestion/loader.py`, `detector/ingestion/pairing.py`, `detector/core/key_level.py`, `detector/core/config.py`, `detector/backtest/simulate.py`, `detector/viz/table.py`, `.importlinter`.

## 3. Data Model — confirmed UNCHANGED from V2

```python
# detector/primitives/ict_order_block.py — verbatim, no edits
@dataclass(frozen=True)
class ICTOrderBlock:
    candle_index: int          # anchor (i), in whatever series was passed to detect_ict_order_blocks
    confirmation_index: int    # i+1 — becomes KeyLevel.origin_index (REQ-63.1), same series
    direction: Literal["bullish", "bearish"]
    top: float
    bottom: float
    status: Literal["open", "invalidated"]
    invalidation_index: int | None = None

@dataclass(frozen=True)
class ICTOrderBlockConfig:
    pass  # still fully structural, no tunable margin (V2 §3 reasoning holds)
```

`core/key_level.py`'s `KeyLevel` is also unchanged — `origin_index`/`expiry_index` stay plain `int`/`int | None`, deliberately NOT retyped to carry series identity (see ADR-E "Alternatives Considered" for why a `KeyLevel`-level fix was rejected in favor of a narrower one).

## 4. Interface Contracts

### 4a. `cli.py` — new args + composition (REQ-67)

```python
parser.add_argument("--daily-csv", help="Path to the Daily CSV — enables Daily-tier ICTOrderBlock Key Levels with --daily-symbol")
parser.add_argument("--daily-symbol", help="Daily instrument identity — enables Daily-tier Key Levels with --daily-csv")
```

Validation (mirrors the existing `--htf-csv`/`--htf-symbol` block exactly, REQ-67.3):

```python
if bool(args.daily_csv) != bool(args.daily_symbol):
    print("error: --daily-csv and --daily-symbol must be provided together", file=sys.stderr)
    return 1
```

Loading (NOT `load_pair` — see ADR-F): reuses `load_mt5_csv` directly, plus one instrument-match check mirroring `load_pair`'s own:

```python
daily_series = None
if args.daily_csv:
    if args.daily_symbol != args.symbol:
        print(f"error: mismatched instrument pairing: daily_symbol={args.daily_symbol} symbol={args.symbol}", file=sys.stderr)
        return 1
    daily_series = load_mt5_csv(args.daily_csv, symbol=args.daily_symbol)
```

Composition (`_detect_all`, inside the existing `if htf_series is not None:` branch — Daily Key Levels only matter where HTF purges exist to credit them against, see Executor Notes §11):

```python
htf_order_blocks = detect_ict_order_blocks(
    daily_series if daily_series is not None else htf_series, config.ict_order_block
)
# ^ falls back to htf_series (V2 behavior) when no --daily-csv given.
order_block_key_levels = ict_order_block_to_key_levels(htf_order_blocks)  # ALWAYS computed —
# see the correction note below; gating this on daily_series is not None (an earlier
# draft of this pseudocode did) silently DROPS order_block_key_levels whenever
# --daily-csv is omitted, breaking the existing test
# test_cli.py::test_htf_key_levels_concatenate_fvg_and_ict_order_block_sources and
# REQ-67.2's "byte-identical to V2" promise — caught during sdd-apply by reading that
# test before writing code, not by review. `order_block_key_levels` is H4-indexed in
# the fallback branch (same series `detect_ict_order_blocks` ran against) and
# Daily-indexed only when `daily_series is not None` — `tag_alignment` (below) must
# route it accordingly, never reindex an already-H4-indexed list.
fvg_key_levels = to_key_levels(detect_fvgs(htf_series, config.fvg))  # FVG stays H4-native, unchanged

if daily_series is not None:
    aligned_signals = tag_alignment(
        htf_series, ltf_series, config.crt_range, config.fvg, config.model1,
        ltf_signals=model1_signals, htf_ranges=htf_crt_ranges, htf_key_levels=fvg_key_levels,
        daily_series=daily_series, daily_key_levels=order_block_key_levels,
    )
else:
    aligned_signals = tag_alignment(
        htf_series, ltf_series, config.crt_range, config.fvg, config.model1,
        ltf_signals=model1_signals, htf_ranges=htf_crt_ranges,
        htf_key_levels=fvg_key_levels + order_block_key_levels,  # V2's exact concatenation, unchanged
    )
```

### 4b. `alignment/htf_ltf.py` — reindexing + tie-break (REQ-63.4/63.5/63.6)

```python
def tag_alignment(
    htf_series: OHLCSeries,
    ltf_series: OHLCSeries,
    crt_config: CRTRangeConfig = CRTRangeConfig(),
    fvg_config: FVGConfig = FVGConfig(),
    model1_config: Model1Config = Model1Config(),
    ltf_signals: list[Model1Signal] | None = None,
    htf_ranges: list[CRTRange] | None = None,
    htf_key_levels: list[KeyLevel] | None = None,
    daily_series: OHLCSeries | None = None,          # NEW
    daily_key_levels: list[KeyLevel] | None = None,   # NEW
) -> list[AlignedSignal]:
    ...
    htf_candles = htf_series.candles
    htf_timestamps = [c.timestamp for c in htf_candles]
    ...
    all_key_levels = list(htf_key_levels or [])
    if daily_series is not None and daily_key_levels:
        all_key_levels += _reindex_daily_key_levels(daily_key_levels, daily_series.candles, htf_candles)
    key_level_credit_map = _key_level_credit_map(
        htf_candles, purge_index_to_range, all_key_levels
    )
    ...
```

New private functions (same `bisect` idiom as the existing `_enclosing_htf_index` for the origin boundary; the expiry side is a genuine H4-native scan, V4/REQ-63.7 — NOT a translated Daily-space boundary, which is what V3 got wrong):

```python
def _reindex_daily_key_levels(
    levels: list[KeyLevel], daily_candles: tuple[Candle, ...], htf_candles: tuple[Candle, ...],
) -> list[KeyLevel]:
    """V4/REQ-63.7: translates Daily-sourced KeyLevels into H4-index-space.
    origin_index reindexes from the CONFIRMATION daily candle's CLOSE
    (conservative: never knowable earlier) — unchanged from V3. expiry_index
    is NOT translated from detect_ict_order_blocks's own Daily-native
    invalidation_index at all (that was V3's mistake, corrected here) — it
    is freshly computed by scanning H4 candles one by one, starting at the
    reindexed origin_index, for the first H4 candle whose range actually
    overlaps the zone. A Daily candle's high/low blends 24h of movement into
    one blunt touch test; the H4 scan gives the Key Level its true,
    finer-grained survival time instead of collapsing it to ~1 Daily candle."""
    htf_timestamps = [c.timestamp for c in htf_candles]
    reindexed = []
    for level in levels:
        origin = _ceiling_htf_index(htf_timestamps, _daily_close(daily_candles, level.origin_index))
        expiry = _htf_expiry_index(htf_candles, origin, level.top, level.bottom)
        reindexed.append(replace(level, origin_index=origin, expiry_index=expiry))
    return reindexed


def _daily_close(daily_candles: tuple[Candle, ...], index: int) -> datetime:
    """A Daily candle's own close = the next Daily candle's open when one
    exists; falls back to +1 day for the series' own last candle (D1 bars
    are UTC-daily per the confirmed-UTC+0 broker finding, obs #450-disproof)."""
    if index + 1 < len(daily_candles):
        return daily_candles[index + 1].timestamp
    return daily_candles[index].timestamp + timedelta(days=1)


def _ceiling_htf_index(htf_timestamps: list[datetime], timestamp: datetime) -> int:
    """First H4 index whose own timestamp >= `timestamp` — the mirror image
    of _enclosing_htf_index's floor lookup. Falls back to len(htf_timestamps)
    (an out-of-range sentinel index, never a real H4 index) when the boundary
    is beyond the last available H4 candle — _htf_expiry_index's range()
    below then naturally scans zero candles and returns None, and
    _key_level_credit_map's `level.origin_index < purge_index` correctly
    never matches — both the intended 'not yet knowable' outcome."""
    return bisect.bisect_left(htf_timestamps, timestamp)


def _htf_expiry_index(
    htf_candles: tuple[Candle, ...], start_index: int, top: float, bottom: float,
) -> int | None:
    """REQ-63.7: the H4-native invalidation scan a Daily-sourced Order Block
    needs. Scans H4 candles from start_index (inclusive) onward for the
    first whose range overlaps [bottom, top]. Starts AT start_index, not
    start_index + 1 — unlike detect_ict_order_blocks's own i+2 exclusion
    (REQ-62.4), start_index here is a reindexed ORIGIN boundary, not a
    same-series confirmation candle guaranteed to overlap the zone by
    construction (full engulfment) — there is no structural reason to
    exclude it from the scan."""
    for i in range(start_index, len(htf_candles)):
        candle = htf_candles[i]
        if candle.high >= bottom and candle.low <= top:
            return i
    return None
```

`_key_level_credit_map`'s tie-break (REQ-63.4):

```python
# was: credit_map[purge_index] = min(qualifying, key=lambda level: level.origin_index)
credit_map[purge_index] = max(qualifying, key=lambda level: level.origin_index)
```

No tolerance change needed (REQ-63.6) — `level.bottom <= extreme <= level.top` was already exact-overlap; V3 just reconfirms it, no code differs.

## 5. ADRs

### ADR-E: Reindex Daily-sourced Key Levels into H4-index-space at the alignment boundary, rather than retyping `KeyLevel`

**Status**: Proposed

**Context**: `_key_level_credit_map` compares `KeyLevel.origin_index`/`expiry_index` (plain `int`) directly against H4 `purge_index` values. This was safe under V2 because every `KeyLevel` in play (FVG- and ICTOrderBlock-sourced alike) carried H4 indices. V3 makes ICTOrderBlock Key Levels Daily-sourced (REQ-63) — their `origin_index`/`expiry_index` are now Daily-series indices, numerically much smaller than H4 indices covering the same calendar span (roughly 1 Daily candle per 6 H4 candles). Comparing them directly against `purge_index` without translation would compile and run without error but silently produce wrong crediting decisions — a defect no test written against a single-timeframe fixture would catch.

**Decision (V4, corrected)**: Add a reindexing step in `alignment/htf_ltf.py` (`_reindex_daily_key_levels`, `_ceiling_htf_index`, `_htf_expiry_index`) BEFORE Key Levels enter `_key_level_credit_map`. `origin_index` reindexes from the confirming Daily candle's close via the same `bisect` idiom `_enclosing_htf_index` already uses (unchanged from V3 — the earliest point the level is genuinely knowable). `expiry_index` is NOT a translation at all (V3's mistake) — it is a fresh H4-native scan (`_htf_expiry_index`), starting at the reindexed origin, checking H4 candles one by one for the first real overlap. `core.key_level.KeyLevel` itself, and `_key_level_credit_map`'s comparison logic, stay untyped/unchanged — the fix lives entirely at the one boundary that newly needs it.

**V3's error, for the record**: the first version of this ADR translated `detect_ict_order_blocks`'s own Daily-native `invalidation_index` (computed by asking whether some FULL Daily candle's range touched the zone) into H4-space, reasoning that being "conservative on both edges" was the safe choice. It wasn't safe, it was wrong: a Daily candle's high/low blends 24 hours of price action into one blunt yes/no test, so for any Order Block with a 1-day Daily-native validity window (60% of them, measured), `origin_index` and the translated `expiry_index` collapsed to the same H4 index — permanently uncreditable regardless of what price actually did within that day. Real-data evidence (`evidence/real-data-h4-m15.md` § "V3 run") measured the consequence (99.85–99.95% exclusion) before the mechanism itself was questioned — the number was real, but it measured the WRONG mechanism. The fix isn't "less conservative," it's "ask the right series."

**Consequences**:
- `tag_alignment` gains two new optional parameters (`daily_series`, `daily_key_levels`) — backward compatible, `None` preserves V2 behavior exactly (REQ-63.3's "imports unchanged" stays literally true; this is a body change, not a new import).
- `_reindex_daily_key_levels` now needs `htf_candles` (OHLC, not just timestamps) to run the H4-native expiry scan — a slightly larger parameter than V3's `htf_timestamps`-only version, since `_htf_expiry_index` needs `high`/`low`, not just `timestamp`.
- `detect_ict_order_blocks`'s own Daily-native `invalidation_index`/`status` fields are computed (the function's contract is unchanged, §3) but DISCARDED for the Daily-tier confluence flow — mildly wasteful (the Daily-native scan runs for nothing on that path) but not worth restructuring the primitive for; it's still the RIGHT computation for the H4-tier fallback path (REQ-67.2).
- Any FUTURE Key Level source living on yet another timeframe (Breaker Block, sub-change #3) reuses this pattern directly — the second real instance of "a source lives on a different series than the purge it credits," which is what justifies writing it as a named, reusable shape now rather than inlining it.
- Cost: three new private functions + two new `tag_alignment` params — a real expansion of `alignment/htf_ltf.py`'s surface, which REQ-63.3's own text ("alignment/htf_ltf.py MUST require ZERO changes") explicitly did NOT anticipate when it was written for V2.

**Alternatives Considered**:
- **Retype `KeyLevel.origin_index`/`expiry_index` from `int` to `datetime`**: more "correct" in the abstract (timestamps are series-agnostic by construction, no translation step needed anywhere) but touches `core/key_level.py`'s public contract, `fvg.py`'s and `ict_order_block.py`'s `to_key_levels` signatures (both would need their source series to compute a timestamp), and ~15 test fixtures across `test_alignment.py`/`test_cli.py`/`test_backtest_simulate.py`/`test_table.py`/`test_ict_order_block.py` that construct `KeyLevel(..., origin_index=N)` with a bare int today. Rejected: correct destination, wrong-sized change for what V3 actually needs — the reindexing-at-the-boundary fix solves the real problem (Daily vs H4 comparison) without touching a type every existing test already depends on.
- **Do the reindexing in `cli.py` instead of `alignment/htf_ltf.py`**: keeps `alignment`'s signature/body untouched, moves the new logic to composition. Rejected: the bisect-on-timestamps idiom this needs already lives in `alignment/htf_ltf.py` (`_enclosing_htf_index`) — duplicating it in `cli.py` (which doesn't otherwise do timestamp arithmetic) fights the existing pattern rather than matching it (Core Rule #3), and "new HTF↔HTF timeframe-reconciliation logic" is squarely what the `alignment/` layer convention is for.
- **Do the reindexing inside `primitives/ict_order_block.py::to_key_levels`**: rejected — would force that leaf primitive to accept a second (H4) series purely to translate indices, coupling a single-series pure detector to a cross-series concern that only exists because of HOW `alignment` consumes its output, not because of anything about the detector itself. Keeps `to_key_levels` at zero changes (§3), which is the whole point of V3 not touching the primitive.
- **Translate the Daily-native `invalidation_index` into H4-space, "conservative on both edges" (V3's original decision)**: superseded, not merely rejected — this shipped, was measured against real data, and produced a wrong-mechanism result (see "V3's error" above). Kept here as the record of what didn't work and why, not as a live alternative.

### ADR-F: Daily series loads via `load_mt5_csv` directly, not `load_pair`

**Status**: Proposed

**Context**: `ingestion/pairing.py::load_pair` enforces `validate_pairing(htf_timeframe, ltf_timeframe)` against `core/pairing_table.py`'s 5-row table (Charter-2's HTF→LTF pairing rule) — which maps `"D"→"1H"`, NOT `"D"→"4H"` or `"D"→"15M"`. Routing the new `--daily-csv` load through `load_pair(daily_csv, daily_symbol, ltf_csv, ltf_symbol)` would validate Daily against the LTF (M15) series and ALWAYS raise `PairingError` (Daily's only valid CRT-model pairing partner is 1H, which this repo's M15/H4 pairing never touches) — the Daily input is a Key-Level-source series, not a CRT execution-timeframe pair, and was never meant to go through that validator.

**Decision**: Load `daily_series` via a direct `load_mt5_csv(args.daily_csv, symbol=args.daily_symbol)` call, with a standalone instrument-match check (`daily_symbol == symbol`) mirroring `load_pair`'s own check but WITHOUT `validate_pairing`.

**Consequences**:
- Correct: the run doesn't spuriously fail every time `--daily-csv` is used.
- `--daily-csv`'s instrument-match check is duplicated logic (2 lines) rather than reused from `load_pair` — acceptable, `load_pair`'s version is entangled with `validate_pairing`, not separable without changing `load_pair`'s own contract for a use case (non-CRT-paired auxiliary series) it was never designed for.

**Alternatives Considered**:
- **Widen `PAIRING_TABLE`/`validate_pairing` to also accept `D`↔`4H`**: rejected — `PAIRING_TABLE` encodes Charter-2's CRT execution-timeframe pairing rule (a distinct methodology concept: HTF CRT range ↔ LTF Model-1 execution), not "any two timeframes that may coexist in one run." Daily-as-Key-Level-source is a different relationship; conflating them would make `validate_pairing` mean two different things depending on caller.

## 6. Flow Changes Table

| Aspect | Before (V2) | After (V3) |
|---|---|---|
| CLI flags | `--csv/--symbol` (+ optional `--htf-csv/--htf-symbol` pair mode) | + optional `--daily-csv/--daily-symbol` (REQ-67), independent third input |
| ICTOrderBlock detection input | H4 series (`htf_series`) | Daily series (`daily_series`) when provided; falls back to `htf_series` when `--daily-csv` omitted (byte-identical to V2 — REQ-67.2) |
| Confluence tie-break (multiple qualifying Key Levels) | Oldest wins (`min` by `origin_index`) | Most recent wins (`max` by `origin_index`, REQ-63.4) |
| `alignment.htf_ltf.tag_alignment` signature | 8 params | + `daily_series`, `daily_key_levels` (both optional, default `None` — no behavior change for existing callers) |
| `detections.csv` `key_level_source` cell | `"fvg"` or `"ict_order_block"` (H4-sourced) | Same values, `"ict_order_block"` now credits a Daily-sourced level |

## 7. Test Derivation Table

| REQ-ID | Test file | Test name/shape |
|---|---|---|
| REQ-61.*/62.*/63.1/63.2/63.3/64.*/65.* | `tests/test_ict_order_block.py`, `tests/property/test_no_lookahead.py`, `tests/test_table.py` | UNCHANGED from V2 (series-agnostic, still pass verbatim) |
| REQ-63.4 (most-recent tie-break) | `tests/test_alignment.py` | `test_most_recent_key_level_wins_among_qualifying_candidates` — 2 KeyLevels both qualifying, assert the higher-`origin_index` one is credited (was: `test_lower_origin_index_wins...`, now inverted) |
| REQ-63.5 (Daily-tier source) | `tests/test_alignment.py` | `test_daily_key_levels_are_reindexed_to_htf_index_space` — builds a Daily series + H4 series with known timestamps, asserts a Daily-index-space KeyLevel's translated `origin_index` lands on the expected H4 candle |
| REQ-63.6 (exact overlap reconfirmed) | `tests/test_alignment.py` | `test_wick_extreme_just_outside_zone_yields_no_confluence` — extreme at `zone.top + epsilon`, assert `credit_map` has no entry |
| REQ-63.7 (V4, H4-native expiry scan) | `tests/test_alignment.py` | `test_daily_key_level_expiry_is_the_first_htf_candle_that_overlaps_the_zone` — H4 series with a KNOWN candle that first touches the zone, asserts `expiry_index` lands exactly there, not on a Daily-translated boundary; a second case with an H4 series where NO candle touches asserts `expiry_index is None` |
| REQ-66.* | manual (not pytest) | Real-data CLI run, EURUSDm/GBPUSDm/DXYm, WITH `--daily-csv`/`--daily-symbol`, gated on ICTOrderBlock alone |
| REQ-67.1 | `tests/test_cli.py` | `test_daily_csv_and_symbol_enable_daily_key_levels` |
| REQ-67.2 | `tests/test_cli.py` | `test_daily_csv_omitted_runs_without_daily_key_levels` |
| REQ-67.3 | `tests/test_cli.py` | `test_daily_csv_without_daily_symbol_is_rejected` (and the mirror case) |
| ADR-E reindexing edge cases | `tests/test_alignment.py` | `test_reindex_falls_back_to_next_available_htf_candle_across_weekend_gap` (bisect ceiling behavior when the exact boundary timestamp has no H4 candle) |
| `uv run lint-imports` | CI-style check | ADR-01 layers contract holds — no new import crosses a layer boundary; `alignment` still only imports `core.*`/`entries.model1`/`primitives.crt_range` |

## 8. Migration Plan

None. Purely additive: `tag_alignment`'s two new params default to `None`, `cli.py`'s two new flags default to unset — every existing invocation (V2's own signed behavior, and any run without `--daily-csv`) is byte-identical. No persisted state, no migrations. Rollback = `git revert`.

## 9. Performance Considerations

`_reindex_daily_key_levels` is O(daily_key_levels × log(H4_candles)) via `bisect` — negligible at HTF scale (thousands of candles, ADR-C's reasoning from V2 applies identically here). No new sweep-line or optimization needed.

## 10. `architecture_impact`: additive

Every touched component EXTENDS an existing boundary without breaking or redirecting it: `cli.py` gains an optional flag pair (extend), `alignment.htf_ltf.tag_alignment` gains optional parameters with `None`-preserves-old-behavior semantics (extend), `ingestion.loader.load_mt5_csv` is reused completely unchanged (aligns). No layer added, no dependency direction changed, no existing contract's REQUIRED shape altered — every row in §Architecture Touchpoints below is `aligns` (extend actions) except one, covered by ADR-E. This one is a smaller-scoped `additive` than V2's own (which added a whole new primitive module) — V3 adds two functions and two optional parameters to an EXISTING module.

### Architecture Touchpoints

| Layer/Component | Action | Why | Baseline fit |
|---|---|---|---|
| `cli` (composition) | extend | new `--daily-csv`/`--daily-symbol` flags + Daily series threaded into `tag_alignment` | aligns |
| `ingestion.loader` | extend (reused, no code change) | `load_mt5_csv` already granularity-agnostic — no new code, just a new call site | aligns |
| `alignment.htf_ltf` | modify | `tag_alignment` gains cross-timeframe reindexing (ADR-E) + tie-break flip | deviates → ADR-E (new capability: reconciling two series' index spaces, not previously a concern of this layer) |
| `primitives.ict_order_block` | none (confirmed) | zero code changes — same pure functions, different caller-supplied series | aligns |
| `core.key_level` | none (confirmed) | `KeyLevel` type unchanged (ADR-E rejected retyping it) | aligns |

## 11. Open Questions and Executor Notes

**Blocking questions**: None.

**Executor-local notes**:
- `--daily-csv` provided without `--htf-csv`: per §4a's composition, `detect_ict_order_blocks` falls back to `htf_series`, but `htf_series` is `None` in single-series mode — this combination is a genuine gap the spec doesn't address. Recommended executor default: reject it explicitly, mirroring `--backtest`'s existing "requires --htf-csv/--htf-symbol" pattern (`if args.daily_csv and not args.htf_csv: error`) — Order Block confluence has no H4 purge to credit against without HTF present, so silently no-op-ing would be more confusing than an explicit error. This is a reversible CLI-validation choice, not a product decision — apply it during `sdd-apply`, flag it in the PR/commit if a different default is chosen instead.
- Exact test fixture shapes for the reindexing tests (specific timestamps/candle counts) are `sdd-apply`'s call, not fixed here.

**Build preflights**: None — the Daily CSV files were already verified present for all 3 real-data instruments during spec V3 (`pairs/D1/*.csv`, see spec.md Risk #6).
