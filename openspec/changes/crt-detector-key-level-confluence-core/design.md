# Design: crt-detector-key-level-confluence-core

**Triage**: L | **Design version**: V2 | **Spec**: V2 signed (2026-08-29) | **Program**: `crt-detector-key-level-confluence` sub-change #1 (walking skeleton) | **Persona lens**: architect

## 0. V2 Change Log (against design V1)

| # | Source | Change |
|---|---|---|
| 1 | spec V2 REQ-53 | `KeyLevel` gains `expiry_index: int | None`. `to_key_levels` now **MUST** read `fill_status`/`fill_index` (V1 forbade it). Credit predicate gains the expiry conjunct. §5, §6. |
| 2 | spec V2 REQ-56 | `_filter_to_confluent`'s `keep()` gains the `fvg_fill` disjunct. §6. |
| 3 | spec V2 | **ADR-013 rewritten**, not amended — V1's ADR argued for the rule V2 rejects. Now scoped to the whole validity window `[origin_index, expiry_index)`. |
| 4 | finding #2 | Numeric acceptance band for the gate's discriminating power set in §9.1. |
| 5 | finding #7 | Cross-artefact equality **dropped** (arithmetically false); replaced by two independently-correct assertions plus a true containment. §9. |
| 6 | findings #8–#16 | Nine test-mechanics decisions resolved in §8.1–§8.9. |
| 7 | spec V2 | Test Derivation 38 → 55 REQ scenarios. §8. |
| 8 | finding #11 | "`excluded_no_key_level` monotonicity" removed from Fitness Functions (tautological as stated); REQ-54.5 rehomed to the strengthened alignment property. |

## 1. Architecture Overview

Confluence is **determined once** in `alignment/`, **stored once** on `AlignedSignal.key_level`, and **read twice** — by the CSV/chart gate in `cli.py` and by the `excluded_no_key_level` bucket in `backtest/simulate.py`. Neither consumer recomputes it (REQ-59); a single field is the source of truth for both, which is what makes REQ-42.1's trades↔detections join hold by construction under gating.

`entries/model1.py` is pure-LTF by ADR-001 and cannot see HTF context, so the check sits one layer up. `alignment/htf_ltf.py` already holds the HTF purge candle (`_purge_index_map`'s key IS the purge index), making it the only layering-legal place to *determine* confluence. Enforcement is a separate concern and stays in `cli.py`'s existing filter chain, inserted immediately after the `population` snapshot so that the backtest bucket stays live and countable while CSV/chart output downstream is narrowed.

A Key Level now carries a **validity window** `[origin_index, expiry_index)` — knowable from the third candle of the FVG formation, dead from the candle that mitigates it. Both bounds are answerable at the crediting purge candle from data strictly at or before it, which is what keeps ADR-003 intact (§ADR-013).

The seam that sub-changes #2/#3 plug into is `core.KeyLevel` (SEAM-01) plus a per-source `to_key_levels` adapter (SEAM-02). `alignment` never imports a detector module: Key Level sources are **injected** by the `cli.py` assembly, so registering ICTOrderBlock or Breaker Block later touches the assembly only.

**Pattern**: existing — matches `detector/cli.py`'s `_filter_by_date_range` / `_filter_by_session` / `_exclude_invalidated_model1` chain and `alignment/htf_ltf.py`'s `ltf_signals=`/`htf_ranges=` injection parameters. No named pattern adopted.

## 2. File Changes

| Path | Action | Purpose |
|---|---|---|
| `detector/core/key_level.py` | Create | `KeyLevel` frozen dataclass (SEAM-01) — imports nothing |
| `detector/primitives/fvg.py` | Modify | `to_key_levels(fvgs)` adapter (SEAM-02); `origin_index = end_index`, `expiry_index` from fill state |
| `detector/alignment/htf_ltf.py` | Modify | `AlignedSignal.key_level`; `htf_key_levels` param; `_key_level_credit_map`, `_purge_wick_extreme` |
| `detector/cli.py` | Modify | HTF FVG→KeyLevel local in `_detect_all`; `_filter_to_confluent` after the `population` snapshot |
| `detector/backtest/simulate.py` | Modify | `_PopulationCuts` record; 4th cut branch; `ReconciliationReport.excluded_no_key_level` |
| `detector/viz/trades_table.py` | Modify | `  no key level:` line in the reconciliation block |
| `openspec/specs/detector/spec.md` | Modify | Destructive sync of REQ-30, REQ-40, REQ-45, REQ-46 at archive |
| `openspec/changes/.../evidence/real-data-h4-m15.md` | Create | REQ-60 recorded evidence (§8.5) |
| `detector/tests/fixtures/synthetic.py` | Modify | `key_level_confluence_pair_setup(confluent)` minimal-pair builder (§8.9) |
| `detector/tests/fixtures/mt5_csv.py` | Modify | `write_series_csv(series, path)` — renders any `OHLCSeries` as MT5 CSV (§8.9) |
| `detector/tests/test_fvg.py` | Modify | `to_key_levels` adapter units (REQ-53.1/.2/.3, REQ-54.1) |
| `detector/tests/test_alignment.py` | Modify | Confluence determination (REQ-54.4, REQ-55.1–.12) |
| `detector/tests/property/test_no_lookahead.py` | Modify | Two-sided boundary (REQ-54.2/.3); key-level injection (§8.3); REQ-54.5 |
| `detector/tests/test_cli.py` | Modify | `_filter_to_confluent` predicate (REQ-56.1/.4/.6/.7), REQ-58.1, REQ-59.2 |
| `detector/tests/test_cli_e2e.py` | Modify | Gate e2e (REQ-56.2/.3/.5, REQ-57.1–.3, REQ-58.2/.3) |
| `detector/tests/test_backtest_simulate.py` | Modify | `_aligned` default (§8.1); REQ-30.7, REQ-40.5; exclusive membership |
| `detector/tests/test_backtest_metrics.py` | Modify | `_aligned` default (§8.1); 8-bucket sum invariant (REQ-40.1), REQ-40.4 |
| `detector/tests/test_cli_backtest_e2e.py` | Modify | `_HTF_DAILY` redesign (§8.2); REQ-40.6, REQ-45.3, REQ-59.1, `no key level:` line |
| `detector/tests/test_fitness_imports.py` | Modify | SEAM-01 AST import allow-list (§8.4) |

`backtest/metrics.py` is **not** changed — `ReconciliationReport` lives in `simulate.py` and `compute_metrics` passes it through untouched (corrects the proposal's Affected Areas table). `viz/chart.py` is **not** changed — HTF FVGs never reach it (ADR-014), so REQ-57.2 holds by construction.

## 3. Flow Changes

| Flow | Action | REQ-IDs | E2E spec | Notes |
|---|---|---|---|---|
| Detector run without `--backtest` (`detections.csv` + `overlay.png`) | Modify | REQ-56.1–56.7, REQ-57.1–57.3, REQ-58.1–58.3 | `detector/tests/test_cli_e2e.py` (extend) | Determinably-non-confluent, non-`fvg_fill` Model-1 rows and markers withheld; 7-column header and every other row unchanged |
| Detector run with `--backtest` (`trades.csv` + `metrics_summary.txt`) | Modify | REQ-30.7, REQ-40.1/.4/.5/.6, REQ-45.1–45.3, REQ-59.1 | `detector/tests/test_cli_backtest_e2e.py` (extend) | 8th bucket disclosed; byte-compat anchor re-based differentially |

## 4. Architecture Touchpoints

| Layer/Component | Action | Why | Baseline fit |
|---|---|---|---|
| `core` | new | `key_level.py` joins the existing bottom layer; imports nothing | aligns |
| `primitives` | extend | `to_key_levels` adapter on existing `fvg.py`, reading fields `fvg.py` already owns | aligns |
| `alignment` | extend | New field + confluence determination; existing injection-param convention | aligns |
| `cli` (assembly) | modify | New HTF FVG stage in `_detect_all`; `_filter_to_confluent` inserted into the private filter chain — intra-component, no boundary or contract between components changes | aligns |
| `backtest` | extend | 8th bucket in the existing ADR-009 reconciliation contract | aligns |
| `viz.trades_table` | extend | One additional disclosure line | aligns |
| `.importlinter` layers contract (ADR-001/ADR-007) | — | No new `root_package`, no new edge; verified conformant | aligns |

Zero `deviates` rows → no deviation ADR required.

## 5. Data Model

```python
# core/key_level.py
@dataclass(frozen=True)
class KeyLevel:
    kind: Literal["fvg"]         # source tag only; widened by #2/#3. NEVER direction.
    top: float
    bottom: float
    origin_index: int            # first index at which the level is provably knowable
    expiry_index: int | None = None   # first index at which it is no longer valid; None = never expires

# alignment/htf_ltf.py
@dataclass(frozen=True)
class AlignedSignal:
    ltf_signal: Model1Signal
    htf_context: CRTRange | None
    aligned: Alignment
    key_level: KeyLevel | None = None   # default keeps every existing construction site valid

# backtest/simulate.py
@dataclass(frozen=True)
class _PopulationCuts:
    survivors: list[AlignedSignal]
    no_crt_range: int
    unaligned: int
    never_confirmed: int
    no_key_level: int

@dataclass(frozen=True)
class ReconciliationReport:
    ...                                  # 9 existing fields, order unchanged
    excluded_no_key_level: int           # declared after excluded_never_confirmed
```

Validity window semantics: a level is valid at index `p` iff `origin_index < p` and (`expiry_index is None` or `p < expiry_index`). Half-open by design — `origin_index` exclusive (REQ-54.4), `expiry_index` inclusive of its own index (REQ-55.11).

## 6. Interface Contracts

```python
# primitives/fvg.py — SEAM-02
def to_key_levels(fvgs: list[FVG]) -> list[KeyLevel]
# kind="fvg", top=fvg.top, bottom=fvg.bottom, origin_index=fvg.end_index.
# expiry_index = fvg.fill_index when fvg.fill_status == "filled", else None (REQ-53.2).
# Reading fill state is REQUIRED, not forbidden: the credit predicate consumes it only
# as `purge_index < expiry_index`, which is the past-tense question "was this level
# filled by purge_index?" — answerable at the purge candle (REQ-54.5).

# alignment/htf_ltf.py
def tag_alignment(..., htf_key_levels: list[KeyLevel] | None = None) -> list[AlignedSignal]
# None means "no Key Level sources registered" -> every key_level is None.
# Deliberately does NOT self-compute (unlike ltf_signals/htf_ranges) — ADR-012.

def _key_level_credit_map(
    candles: tuple[Candle, ...],
    purge_index_to_range: dict[int, CRTRange],
    key_levels: list[KeyLevel],
) -> dict[int, KeyLevel]
# Eager, keyed by purge index -> O(purges x levels), independent of LTF signal count.
# Credit predicate, all three conjuncts:
#   level.origin_index < purge_index                                  (REQ-54.4)
#   level.expiry_index is None or purge_index < level.expiry_index    (REQ-55.9/.10/.11)
#   level.bottom <= extreme <= level.top                              (REQ-55.4, edges inclusive)
# extreme = purge_candle.high if purge_candle.high > crt_range.high else purge_candle.low
#   -- high-first, matching first_breach_index's own check order exactly: a candle
#      breaching both sides is credited on the side that made it the purge candle
#      (REQ-55.6). NEVER derived from ltf_signal.direction (REQ-55.7).
# Multiple matches -> lowest origin_index wins (REQ-55.12), input order on ties
#   -- same precedence as _purge_index_map's setdefault and ADR-010's dedup survivor.

# cli.py
def _filter_to_confluent(detections: _Detections) -> _Detections
# keep(t) = (t.aligned != "aligned"
#            or t.ltf_signal.confirmation_type == "fvg_fill"     # REQ-56.7
#            or t.key_level is not None)
# Filters aligned_signals, and drops the parallel model1_signals rows by
# ltf_signal.signal_id (the join key REQ-42 already relies on) so the CSV writer's
# two lists cannot disagree. aligned_signals is None (single-series) -> no-op (REQ-56.6).
```

HTF Key Level source registration in `_detect_all`, using the **same** `config.fvg` as the LTF pass (§8.6):

```python
htf_key_levels = to_key_levels(detect_fvgs(htf_series, config.fvg))   # local; never a _Detections field (REQ-58.1)
```

`viz/trades_table.py` — exact literal line, inserted between `  never confirmed:` and `  duplicate:` (§8.7):

```python
f"  no key level: {r.excluded_no_key_level}",
```

No external interface change: no CLI flag, no CSV column, no header change.

## 7. Architecture Decisions

### ADR-012: `KeyLevel` is a normalising frozen dataclass in `core/`, and sources are injected, never self-computed

**Status**: Proposed

**Context**: Three sub-changes will each add a Key Level source (FVG now; ICTOrderBlock, Breaker Block later). The confluence rule must not grow a branch per source, and `alignment` must not acquire an import of each detector module — SEAM-01 exists precisely to prevent that. `tag_alignment`'s existing convention is `param=None → compute it myself`, which would hard-wire `detect_fvgs` into `alignment`.

**Decision**: `core/key_level.py` holds a frozen `KeyLevel(kind, top, bottom, origin_index, expiry_index)` importing nothing. Each source module owns a `to_key_levels` adapter. `tag_alignment` takes `htf_key_levels` and **breaks** the `None → self-compute` convention: `None` means "no sources registered". Source registration lives in `cli.py`'s `_detect_all`.

**Consequences**:
- #2/#3 add a source by touching their own module plus one `_detect_all` line — `alignment`, `viz`, `backtest` are untouched, which the SEAM-01 AST fitness test pins (§8.4).
- `kind` carries the source tag only, never direction — direction already lives on the signal, and overloading it would make #2's CSV attribution column ambiguous.
- The validity window is normalised too: a source whose levels never expire simply leaves `expiry_index` at `None`, so #2/#3 inherit the semantics without widening the shape.
- Cost: one convention broken inside a function that establishes the opposite convention twice. Mitigated by an explicit code comment and by this ADR; a caller that forgets to inject fails loudly (every aligned non-`fvg_fill` signal is withheld), not silently.

**Alternatives Considered**:
- **`Protocol`/structural typing over each detector's own type**: `alignment` would still need each concrete type at the call site, and `origin_index`/`expiry_index` semantics differ per source — the normalisation is the value, and a Protocol does not perform it.
- **`FVG | ICTOrderBlock | BreakerBlock` union**: every consumer grows a match per source; adding a source becomes an edit in `alignment`, the exact coupling SEAM-01 forbids.
- **`tag_alignment` self-computing FVG key levels when `None`**: consistent with the local convention, but imports `primitives.fvg` into the confluence path and makes #2 a change to `alignment`. Consistency lost to seam integrity, deliberately.

### ADR-013: A Key Level's validity is a half-open window `[origin_index, expiry_index)` — knowable-start, mitigation-end

**Status**: Proposed — **supersedes design V1's ADR-013, which argued the opposite end-bound**

**Context**: Two bounds, one concept. (a) `detect_fvgs` reads `candles[i]` and `candles[i+2]`; the gap does not exist as an observation until index `i+2`, so `FVG.start_index` — the natural-looking anchor — would credit a signal against something not yet knowable, violating ADR-003. (b) V1 decided a mitigated FVG stays valid forever. A blind judge ran that rule over real `pairs/` H4/M15 data: unexpiring filled zones accumulated to roughly **9×** the instrument's price range, so nearly every purge wick landed inside some zone and the gate withheld only **2.8%** of signals — a validity gate that validates everything. The counterfactual (expire on mitigation) measured **30–34%**. The user reversed the decision on that evidence.

**Decision**: `to_key_levels` sets `origin_index = fvg.end_index` (`start_index + 2`) and `expiry_index = fvg.fill_index` when `fill_status == "filled"`, `None` otherwise. Credit requires `origin_index < purge_index` **and** (`expiry_index is None or purge_index < expiry_index`). Both bounds are pinned by a two-sided property test that truncates the HTF series and re-derives the levels (§8.3).

**Consequences**:
- Reading fill state is not lookahead: `_sweep_fill_status` resolves an FVG's fill at the filling candle, so whether a level is expired at index `p` is fully determined by candles `≤ p` — the truncation property (REQ-54.5) is the proof, not a comment.
- Regression to `start_index` fails the "absent before" half; over-correction to `start_index + 3` fails the "present at" half. Both directions are caught.
- The gate becomes discriminating enough to be worth having — but that is now an empirical claim, so §9.1 attaches a numeric acceptance band it must clear on real data.
- Cost: an FVG that fills on the very next eligible candle (`start_index + 3`) has a one-candle creditable window, and one that fills at `origin_index + 1` has none. That falls out of the two bounds; no separate rule, and no separate requirement (spec V2 verified this).
- Cost: `origin_index` and the level's drawn geometric start differ by two candles; a reader inspecting a chart must not expect them to coincide.

**Alternatives Considered**:
- **`start_index` as origin**: matches where the zone is drawn, but is knowably wrong — the level cannot be observed there.
- **No expiry (design V1's rule)**: simpler, and defensible on paper — a mitigated zone is still a price the market once respected. Rejected on measurement: 2.8% withheld makes the gate a no-op, which fails the change's own problem statement. Evidence beat the argument.
- **Partial-mitigation or time-decay expiry**: more faithful to how a discretionary trader ages a level, but there is no definitional source in the charters and no way to pick the parameter. Deferred (spec V2 out-of-scope) until real-data evidence asks for it.

### ADR-014: Confluence is determined in `alignment`, enforced in `cli`, and HTF Key Levels never enter `_Detections`

**Status**: Proposed

**Context**: The program artefact asked for both a pre-CSV filter and a live 8th exclusion bucket. Applied at one point these are mutually exclusive: filtering before `population` is snapshotted makes the bucket always zero. Separately, `_Detections` fields are swept by `_filter_by_date_range` and `_filter_by_session`, which filter `htf_crt_ranges` by HTF timestamp.

**Decision**: Determine confluence once inside `tag_alignment` and store it on `AlignedSignal.key_level` (REQ-59). Insert `_filter_to_confluent(detections)` in `cli.py` between the `population` snapshot (line ~120) and `_filter_by_types` (line ~121). HTF Key Levels are a **local variable** in `_detect_all`, threaded into `tag_alignment` and discarded — never a `_Detections` field (REQ-58).

**Consequences**:
- `population` inherits pre-filter data, so `excluded_no_key_level` is live and countable while CSV/chart output is narrowed (REQ-40.6). Both requirements are satisfied without a second determination.
- REQ-42.1/REQ-59.1 hold by construction: a traded signal survived the bucket, so it carries a `key_level`, so it survived the CSV gate — because both read the *same field*, not two computations that could drift.
- Keeping levels out of `_Detections` means `--from-date`/`--session` cannot narrow the Key Level pool. Were they a field, a display filter would silently change which signals are *valid* — a filter contract inversion. It also gives REQ-57.2 (not rendered) and REQ-57.3 (`--types fvg` unchanged) for free: `render_chart` and `write_detections_csv` never see them.
- Cost: the gate's correctness depends on statement order in `main()`. A refactor moving it above the snapshot regresses silently — pinned by REQ-40.6's e2e and the REQ-59.1 join scenario, which both fail loudly.

**Alternatives Considered**:
- **Filter before the `population` snapshot**: simpler, but the bucket becomes dead (always zero) and REQ-40 loses the disclosure that is half the point.
- **Recompute confluence inside `simulate()`**: creates a second source of truth that can disagree with the CSV gate with no test noticing — the exact failure ADR-009's rejected alternatives already name, and the failure class this project shipped once in the `--types` population-snapshot defect.
- **Store `htf_key_levels` on `_Detections`**: symmetric with `htf_crt_ranges`, but subjects the level pool to the results-filter chain and forces explicit exclusions in `render_chart`/`write_detections_csv` to satisfy REQ-57.2/.3.

### ADR-015: The new bucket is identified by name, in the last position of `_population_cuts`, whose return becomes a named-field record

**Status**: Proposed

**Context**: `excluded_duplicate` is documented as "stage 4" in the shipped REQ-46; inserting a bucket mid-chain silently falsifies every ordinal downstream. The identical hazard exists in code: `_population_cuts` returns a positional tuple whose int count goes from three to four adjacent, same-typed values. A swap of `never_confirmed` and `no_key_level` at the single unpack site leaves the REQ-40.1 sum invariant **passing** — two independently-true sums hiding a compensating error, exactly ADR-009's warning.

**Decision**: Buckets are referenced by name, never by ordinal, in spec text and code. `excluded_no_key_level` is appended **last** in `_population_cuts`' `elif` chain (after `never_confirmed`), and `_population_cuts` returns a frozen `_PopulationCuts` record instead of a tuple.

**Consequences**:
- The three existing bucket counts stay byte-identical against the current regression suite — no re-baselining.
- A signal both `unaligned` and non-confluent lands in `excluded_unaligned` automatically by the earliest-wins `elif` chain (REQ-40.5); an `fvg_fill` signal lands in `excluded_no_crt_range` and never reaches the confluence cut (REQ-30.4) — both by the existing branch order, verified in code, no reordering needed.
- The swap is made impossible rather than merely detectable; the per-signal exclusive-membership test remains as the semantic check.
- Cost: ~6 lines and one new module-private type for a single producer/consumer pair — an abstraction with one user, accepted only because the failure it removes is invisible to the sum invariant.

**Alternatives Considered**:
- **Keep the tuple**: zero new code, but the one failure mode that matters passes every existing assertion.
- **Insert the bucket in "logical" order, mid-chain**: changes which bucket existing borderline signals land in, forcing a re-baseline of shipped counts for no behavioural gain.
- **Renumber the ordinals in REQ-46**: fixes today's text and leaves the failure class in place for the next insertion.

### ADR-016: REQ-45's and REQ-56.3's byte-compat guarantees are re-anchored differentially, not absolutely

**Status**: Proposed

**Context**: REQ-45 promised `detections.csv`/`overlay.png` byte-identity against "today's exact output" for non-`--backtest` runs, and spec V1's REQ-56.3 promised the same against "a run before this change". The confluence gate runs on **every** run, so both absolute pre-feature baselines become permanently unreproducible the moment this ships, and both requirements unverifiable forever.

**Decision**: Re-anchor both differentially. REQ-45 → the equivalent run differing **only** by the `--backtest` flag. REQ-56.3 → two runs of the **current** code over a minimal input pair differing only in whether the HTF Key Level zone contains the purge candle's credited extreme (§8.9's builder is what makes that pair minimal).

**Consequences**:
- Strengthens both: they stay verifiable after any future change to the detection population, whereas an absolute anchor decays on every such change.
- The "nothing else changed" promise is preserved differently, by REQ-56.3/.4 (surgical scope) and REQ-56.5 (header contract).
- Cost: a destructive sync of signed REQ-45 text at archive; the pre-change absolute output is no longer a reference for anything — which is precisely why §8.5 captures the pre-gate real-data baseline *before* any code is written. That capture is the last moment it exists.

**Alternatives Considered**:
- **Leave REQ-45 standing and add a carve-out REQ**: leaves a signed requirement contradicted by shipped behaviour — the situation `sdd-archive` §4 exists to prevent.
- **Gate only under `--backtest`**: preserves the absolute anchor, but the user's stated rule is that a non-confluent Model-1 is not a setup at all; it would keep publishing invalid setups in the primary artefact.

## 8. Test Mechanics (design-resolved — plan-verify findings #8–#16)

### 8.1 — `_aligned()` helper default (finding #8)

`test_backtest_simulate.py` and `test_backtest_metrics.py` each define `_aligned(signal, htf_context=_HTF_CONTEXT, aligned="aligned")`. With `key_level` defaulting to `None`, ~25 existing tests silently become "no key level" tests and produce zero trades — a mass semantic rewrite nobody authored.

**Decision**: give the helper a default confluent level.

```python
_KEY_LEVEL = KeyLevel(kind="fvg", top=1.1050, bottom=1.0950, origin_index=0, expiry_index=None)

def _aligned(signal, htf_context=_HTF_CONTEXT, aligned="aligned", key_level=_KEY_LEVEL):
    return AlignedSignal(ltf_signal=signal, htf_context=htf_context, aligned=aligned, key_level=key_level)
```

Those tests exercise fill/exit/bucket mechanics with confluence irrelevant and, pre-change, implicitly satisfied — the default preserves their authored intent. The confluence-specific tests (REQ-30.7, REQ-40.5, exclusive membership) pass `key_level=None` **explicitly**, which puts the negative case at the call site where a reader can see it. Updating ~25 call sites individually was rejected: it produces a large diff whose every hunk says the same thing, and a reviewer cannot tell an intentional `key_level=None` from a missed one.

### 8.2 — `_HTF_DAILY` e2e fixture redesign (finding #9)

The current 3-candle daily HTF fixture cannot produce a credited Key Level at all: no FVG can form and be knowable before the purge candle at index 1. **This is an explicit S-000 task, not implicit**, and it re-baselines CRT range / `htf_context` / `take_profit` / R:R-floor / expected-trade-count expectations across the **20 tests** in `test_cli_backtest_e2e.py`.

Constraints the redesign must satisfy (minimum **6** HTF candles):

1. FVG on candles 0/1/2 → `origin_index = 2`. Bearish (`candles[0].low > candles[2].high`), zone `[candles[2].high, candles[0].low]`, width ≥ `0.1 × ATR14(index 2)`.
2. CRT range candle at index 3: `range_high = candles[3].high`, `range_low = candles[3].low` (ranges take the start candle's own extremes).
3. Purge candle at index **4** — the LTF anchor's calendar day. `candles[4].high > candles[3].high` (high-side breach → bearish signal), and that high inside the FVG zone.
4. FVG unexpired at index 4: a bearish FVG fills on `high >= top`, so every candle 3..4 must have `high < candles[0].low`.
5. Ranges starting at 0/1/2 must each first-breach strictly before index 4, so `_purge_index_map`'s `setdefault` leaves index 4 to the index-3 range. The falling 0→2 shape needed by (1) already delivers this.
6. Index 4 is not the last HTF candle (index 5 exists) — avoids `insufficient_htf_data`.
7. `candles[3].low` (the bearish `take_profit`) must clear the R:R floor against the LTF entry ~1.1010 and SL 1.1037: `take_profit <= 1.0956`.

Indicative layout (dates shifted so the LTF day is the purge day; exact OHLC is apply's to finalise against these constraints):

| idx | date | O | H | L | C | role |
|---|---|---|---|---|---|---|
| 0 | 2026.07.02 | 1.1060 | 1.1065 | **1.1040** | 1.1045 | FVG top = 1.1040 |
| 1 | 2026.07.03 | 1.1042 | 1.1044 | 1.1034 | 1.1036 | middle |
| 2 | 2026.07.04 | 1.1032 | **1.1030** | 1.1020 | 1.1022 | FVG bottom = 1.1030 → zone [1.1030, 1.1040] |
| 3 | 2026.07.05 | 1.1020 | 1.1028 | **1.0900** | 1.0910 | CRT range H=1.1028 L=1.0900 (= take_profit) |
| 4 | 2026.07.06 | 1.0915 | **1.1035** | 1.0905 | 1.0920 | purge (high 1.1035 > 1.1028, inside zone) |
| 5 | 2026.07.07 | 1.0920 | 1.0930 | 1.0910 | 1.0925 | trailing |

`_LTF_CANDLES` stays as-is except for the date shift: its candle-4 low of 1.0790 still reaches the new `take_profit` of 1.0900, so the fixture's win outcome is preserved.

### 8.3 — Property-harness key-level injection (finding #10)

Three `tag_alignment` call sites in `test_no_lookahead.py` would otherwise go vacuous. Two different treatments, because the tests have two different subjects:

- **`test_alignment_detection_has_no_lookahead`** (lines 272/279): inject **per-truncation** levels — `to_key_levels(detect_fvgs(htf_series))` for the full call, `to_key_levels(detect_fvgs(truncated_htf))` for the truncated call. The existing `full_by_key[key] == tag` assertion then compares `key_level` too, which is exactly REQ-54.5 at property strength: an implementation deriving `expiry_index` from anything past the purge candle fails it. **This is REQ-54.5's home** — no separate property test is added.
- **`test_backtest_resolution_is_monotone_in_series_length`** and **`test_backtest_exit_is_local_to_its_own_window`** (lines 381/428): inject a single synthetic **cover-all** level spanning the HTF price range (`bottom=min(low)`, `top=max(high)`, `origin_index=0`, `expiry_index=None`). Their subject is `simulate()`'s use of the series, not confluence; holding confluence constant-and-satisfied keeps them exactly as strong as before this change, *deterministically*, rather than leaving them dependent on whether random data happens to produce an overlapping FVG. The docstrings must say so.

### 8.4 — SEAM-01 fitness mechanism (finding #14)

**Decision**: AST parse of `alignment/htf_ltf.py`'s import statements in `test_fitness_imports.py`. `ast.parse` the file, collect the module path of every `Import`/`ImportFrom`, assert the set equals a frozen expected set:

```
{bisect, dataclasses, datetime, typing,
 core.candle, core.config, core.key_level, core.pairing_table,
 entries.model1, primitives.crt_range}
```

The rule SEAM-01 actually expresses is an **allow-list** ("no new detector-source module joins this import list"), not a deny-list of today's known sources. `.importlinter` was rejected: it has no allow-list-of-modules contract, a `forbidden` contract naming `primitives.fvg` would not catch #2's `primitives.order_block`, and adding a second contract type to a file whose ADR-001 layers contract is deliberately its only one dilutes that contract's meaning. Runtime module inspection was rejected: `sys.modules` shows transitive imports, so it cannot distinguish "this module imports X" from "something it imports imports X" — false positives on every shared dependency. Cost: the frozen set must be edited deliberately when a legitimate import is added — which is the point of the assertion, and its failure message names SEAM-01.

### 8.5 — REQ-60 real-data validation (finding #12)

**Decision**: a **manual validation run whose output is recorded in change artefacts** — not a committed automated test.

`pairs/` is gitignored (18MB, not distributable), so a committed test needs a skip-if-absent guard and would then be green on every machine lacking the data: a test advertising coverage it never exercises is worse than none. REQ-60 asks for *recorded evidence*, and §9.1's band is a human judgement gate at S-000, not a regression check.

Mechanics, all part of S-000:

1. **Before writing any code**, capture the pre-gate baseline on the current `HEAD` — the last moment it is reproducible (ADR-016). Same command, output to `.../evidence/pre-gate/`.
2. Run post-implementation for each instrument, from the repo root:
   ```
   uv run --project detector python -m detector.cli \
     --csv pairs/M15/EURUSDm_M15_202207260000_202608192030.csv --symbol EURUSDm \
     --htf-csv pairs/H4/EURUSDm_H4_202001020000_202608192000.csv --htf-symbol EURUSDm \
     --output-dir .sdd/evidence/crt-detector-key-level-confluence-core/eurusdm --backtest
   ```
   `EURUSDm` is the reference instrument; `GBPUSDm` and `DXYm` (same H4/M15 file pattern) are run as corroboration.
3. Record into `openspec/changes/crt-detector-key-level-confluence-core/evidence/real-data-h4-m15.md` (committed — small text): per instrument, REQ-60.1's five counts, the withheld fraction `W` (§9.1), and the pre-gate/post-gate Model-1 row counts. `signals_considered` and `excluded_no_key_level` come from `metrics_summary.txt`; row counts from `detections.csv`.
4. **Runtime budget**: 10 minutes wall clock per run. Exceeding it is an escalation, not a silent wait — this codebase has twice had to remove O(n²) hot paths at MT5 scale.

### 8.6 — HTF `FVGConfig` (finding #13)

**Decision**: the **same** `config.fvg` as the LTF pass. `min_size_atr` is ATR-relative and the ATR is computed on the HTF series itself, so the threshold already self-scales to the HTF's own volatility. A separate `htf_fvg` config field would be a new public config surface with one speculative user and no principled way to choose its value — YAGNI. If §8.5's evidence shows the level density is wrong, that is evidence for a follow-up config change, recorded as such rather than pre-built.

### 8.7 — `metrics_summary.txt` literal line (finding #15)

Exact string, produced by `f"  no key level: {r.excluded_no_key_level}"` — two leading spaces, lowercase, single spaces between words, single space after the colon. Position: **immediately after `  never confirmed:` and immediately before `  duplicate:`**, matching REQ-40's stated bucket precedence order, which the existing seven-line block already mirrors exactly. `  no crt range:` is the precedent for a multi-word bucket rendered with spaces rather than underscores. `write_metrics_summary`'s docstring calls this wording a never-paraphrase contract; the e2e assertion checks the exact substring **and** its position relative to its two neighbours.

### 8.8 — `excluded_no_key_level` in the monotonicity assertion list (finding #11)

The proposed assertion in `test_backtest_resolution_is_monotone_in_series_length` (~line 413) truncates only the LTF series while the population and its levels are fixed on the full HTF series — so it can never fail. **But so can none of its five existing siblings** (`signals_considered`, `no_crt_range`, `unaligned`, `never_confirmed`, `duplicate`, `kill_zone`): that block asserts "these cuts do not depend on series length beyond the anchor", a weak but real invariance property. Adding the new bucket there is **consistent** with them, not newly tautological, and it is kept.

What is **dropped** is claiming it as a fitness function. The falsifiable confluence-vs-truncation property is REQ-54.5, which truncates **both** series consistently and lives in §8.3's strengthened alignment property. §9 reflects this.

### 8.9 — Minimal-pair fixture builder (finding #16)

**Decision**: one builder at the lowest common denominator (a series pair), plus one CSV renderer. Three builders that must stay in lockstep is the divergence hazard the minimal-pair discipline exists to prevent.

```python
# tests/fixtures/synthetic.py
@dataclass(frozen=True)
class KeyLevelConfluencePair:
    htf_series: OHLCSeries
    ltf_series: OHLCSeries
    expected_key_level: KeyLevel | None   # the level REQ-55 must credit; None for the non-confluent twin

def key_level_confluence_pair_setup(confluent: bool) -> KeyLevelConfluencePair: ...

# tests/fixtures/mt5_csv.py
def write_series_csv(series: OHLCSeries, path) -> None: ...
```

The two variants differ in **exactly one number** — the HTF FVG's `bottom` (one candle's `high`), shifted so the zone no longer contains the purge candle's credited extreme. Timestamps, CRT range, purge candle, LTF series and Model-1 signal are identical, which is what makes REQ-56.3's differential comparison meaningful.

Consumers derive their own altitude from the pair:
- `test_alignment.py` — calls `tag_alignment(pair.htf_series, pair.ltf_series, htf_key_levels=to_key_levels(detect_fvgs(pair.htf_series)))` and asserts against `pair.expected_key_level`.
- `test_cli.py` — same call, wraps the result in a `_Detections` and exercises `_filter_to_confluent`.
- `test_cli_e2e.py` — renders both series via `write_series_csv` and runs `main()`.

`test_backtest_simulate.py`/`test_backtest_metrics.py` are **not** consumers: they construct `AlignedSignal`s directly and are served by §8.1's helper default.

## 9. Test Derivation

| REQ-ID | Scenario | Level | Test path | Flow ref |
|---|---|---|---|---|
| REQ-53.1 | FVG zone preserved, `kind` identifies source | unit | `tests/test_fvg.py` | — |
| REQ-53.2 | filled → `expiry_index = fill_index`; open → `None`; equal otherwise | unit | `tests/test_fvg.py` | — |
| REQ-53.3 | no FVG → empty list, not error/None | unit | `tests/test_fvg.py` | — |
| REQ-54.1 | FVG at 40/41/42 → `origin_index == 42` | unit | `tests/test_fvg.py` | — |
| REQ-54.2 | present at `up_to(origin_index + 1)` | property | `tests/property/test_no_lookahead.py` | — |
| REQ-54.3 | absent at `up_to(origin_index)` | property | `tests/property/test_no_lookahead.py` | — |
| REQ-54.4 | `origin_index >= purge_index` → not credited | unit | `tests/test_alignment.py` | — |
| REQ-54.5 | credit identical under HTF truncation to `p + 1` | property | `tests/property/test_no_lookahead.py` (§8.3) | — |
| REQ-55.1 | high-side breach, high inside zone → credited | unit | `tests/test_alignment.py` | — |
| REQ-55.2 | low-side breach, low inside zone → credited | unit | `tests/test_alignment.py` | — |
| REQ-55.3 | 1 tick outside → not credited | unit | `tests/test_alignment.py` | — |
| REQ-55.4 | extreme exactly on `bottom` → credited | unit | `tests/test_alignment.py` | — |
| REQ-55.5 | unaligned/insufficient → `None`, not a negative | unit | `tests/test_alignment.py` | — |
| REQ-55.6 | both sides breached → `high` side credited | unit | `tests/test_alignment.py` | — |
| REQ-55.7 | `direction`-based selection must fail this | unit | `tests/test_alignment.py` | — |
| REQ-55.8 | unfilled level, origin earlier → credited | unit | `tests/test_alignment.py` | — |
| REQ-55.9 | `expiry_index = 60 < purge 80` → not credited | unit | `tests/test_alignment.py` | — |
| REQ-55.10 | `expiry_index = 90 > purge 80` → credited | unit | `tests/test_alignment.py` | — |
| REQ-55.11 | `expiry_index == purge_index` → not credited | unit | `tests/test_alignment.py` | — |
| REQ-55.12 | two qualifying levels → lowest `origin_index` wins | unit | `tests/test_alignment.py` | — |
| REQ-56.1 | aligned + key level → row present | unit | `tests/test_cli.py` | — |
| REQ-56.2 | aligned, no key level → no row, no marker | e2e | `tests/test_cli_e2e.py` | Run without `--backtest` (Modify) |
| REQ-56.3 | differential minimal pair: only gated rows differ | e2e | `tests/test_cli_e2e.py` | Run without `--backtest` (Modify) |
| REQ-56.4 | swing/fvg/crt_range/mss rows untouched | unit | `tests/test_cli.py` | — |
| REQ-56.5 | 7-column header byte-identical | e2e | `tests/test_cli_e2e.py` | Run without `--backtest` (Modify) |
| REQ-56.6 | single-series → nothing withheld | unit | `tests/test_cli.py` | — |
| REQ-56.7 | `fvg_fill`-confirmed, no key level → kept | unit | `tests/test_cli.py` | — |
| REQ-57.1 | pair mode → key levels available to REQ-55 | e2e | `tests/test_cli_e2e.py` | Run without `--backtest` (Modify) |
| REQ-57.2 | HTF FVGs not drawn on `overlay.png` | e2e | `tests/test_cli_e2e.py` | Run without `--backtest` (Modify) |
| REQ-57.3 | `--types fvg` still LTF-only | e2e | `tests/test_cli_e2e.py` | Run without `--backtest` (Modify) |
| REQ-58.1 | `_Detections` field-name allow-list holds | architectural | `tests/test_cli.py` | — |
| REQ-58.2 | `--from-date` does not change confluence outcomes | e2e | `tests/test_cli_e2e.py` | Run without `--backtest` (Modify) |
| REQ-58.3 | `--session` does not change confluence outcomes | e2e | `tests/test_cli_e2e.py` | Run without `--backtest` (Modify) |
| REQ-59.1 | every traded `signal_id` is a Model-1 CSV row | e2e | `tests/test_cli_backtest_e2e.py` | Run with `--backtest` (Modify) |
| REQ-59.2 | flipping one `key_level` moves CSV row and bucket together | unit | `tests/test_cli.py` | — |
| REQ-60.1 | five counts recorded for a real H4/M15 run | evidence | `.../evidence/real-data-h4-m15.md` (§8.5) | — |
| REQ-60.2 | withheld fraction inside §9.1's band | evidence | `.../evidence/real-data-h4-m15.md` (§8.5) | — |
| REQ-30.1 | aligned CONFIRMED → candidate | unit | `tests/test_backtest_simulate.py` (regression) | — |
| REQ-30.2 | aligned INVALIDATED + retest → candidate | unit | `tests/test_backtest_simulate.py` (regression) | — |
| REQ-30.3 | `retest_index is None` → `never_confirmed` | unit | `tests/test_backtest_simulate.py` (regression) | — |
| REQ-30.4 | `fvg_fill` → `no_crt_range`, never `no_key_level` | unit | `tests/test_backtest_simulate.py` | — |
| REQ-30.5 | unaligned/insufficient → `unaligned` | unit | `tests/test_backtest_simulate.py` (regression) | — |
| REQ-30.6 | aligned PENDING + retest → candidate | unit | `tests/test_backtest_simulate.py` (regression) | — |
| REQ-30.7 | aligned, retest set, no key level → `no_key_level` | unit | `tests/test_backtest_simulate.py` | — |
| REQ-40.1 | `opened + sum(8 buckets) == considered` | unit | `tests/test_backtest_metrics.py` | — |
| REQ-40.2 | `signals_considered` is post-results-filter | e2e | `tests/test_cli_backtest_e2e.py` (regression) | Run with `--backtest` (Modify) |
| REQ-40.3 | unaligned + outside kill zone → `unaligned` | unit | `tests/test_backtest_simulate.py` (regression) | — |
| REQ-40.4 | PENDING + retest resolves through 5 later cuts | unit | `tests/test_backtest_metrics.py` | — |
| REQ-40.5 | unaligned + no key level → `unaligned` | unit | `tests/test_backtest_simulate.py` | — |
| REQ-40.6 | gated signal still counted; bucket non-zero | e2e | `tests/test_cli_backtest_e2e.py` | Run with `--backtest` (Modify) |
| REQ-45.1 | `--session ... --backtest` overlay byte-identical | e2e | `tests/test_cli_backtest_e2e.py` (regression) | Run with `--backtest` (Modify) |
| REQ-45.2 | 13-column `trades.csv` header | e2e | `tests/test_cli_backtest_e2e.py` (regression) | Run with `--backtest` (Modify) |
| REQ-45.3 | differential byte-identity vs non-backtest run | e2e | `tests/test_cli_backtest_e2e.py` | Run with `--backtest` (Modify) |
| REQ-46.1 | 3 identical candidates → 1 survivor | unit | `tests/test_backtest_simulate.py` (regression) | — |
| REQ-46.2 | different `entry_type` → both survive | unit | `tests/test_backtest_simulate.py` (regression) | — |
| — | SEAM-01: `alignment/htf_ltf.py` import allow-list | architectural | `tests/test_fitness_imports.py` (§8.4) | — |
| — | `.importlinter` layers contract still passes | architectural | `tests/test_fitness_imports.py` | — |
| — | Per-signal exclusive bucket membership, mixed population | unit | `tests/test_backtest_simulate.py` | — |
| — | Gate CSV set == REQ-56 predicate over the population | e2e | `tests/test_cli_backtest_e2e.py` | Run with `--backtest` (Modify) |
| — | Every `excluded_no_key_level` signal absent from `detections.csv` | e2e | `tests/test_cli_backtest_e2e.py` | Run with `--backtest` (Modify) |
| — | `  no key level:` line present, between its two neighbours | e2e | `tests/test_cli_backtest_e2e.py` | Run with `--backtest` (Modify) |

All **55** spec scenarios covered; both Modify flows carry e2e rows. `property` and `evidence` appear alongside the standard levels: `property` is this project's established hypothesis harness (`tests/property/`), and `evidence` is REQ-60's recorded manual run (§8.5) — the only requirement whose subject is a measurement rather than a behaviour.

## 9.1 Acceptance band for the gate's discriminating power (finding #2)

Define, on the reference H4/M15 run:

```
W = excluded_no_key_level / |{ aligned, non-fvg_fill Model-1 signals in signals_considered }|
```

**Acceptance criterion (S-000): `0.10 <= W <= 0.75` on EURUSDm H4/M15, AND at least 50 trades open after the full cut chain.**

- **Lower bound 0.10** — comfortably above the 2.8% that was judged near-vacuous, and roughly 3× below the 30–34% the expiring rule measured on GBPUSDm/DXYm. Set with that margin deliberately: a bound tuned to the measurement would be a tautology that only re-asserts what was already observed.
- **Upper bound 0.75** — more than double the measured 34%, so honest instrument-to-instrument variation cannot trip it, while still catching a gate that discards nearly everything. A `W` above 0.75 also cannot coexist with the trade floor on this data.
- **Trade floor 50** — the north-star's CQ2. A statistically decision-grade sample; a gate that satisfies `W` but leaves fewer than 50 trades has traded one failure for another.

`W` outside the band, or fewer than 50 trades, **halts S-000 and escalates before S-001..S-006 are built** — the whole point of putting this in the walking skeleton. GBPUSDm and DXYm are recorded as corroboration and are expected in the same band; one corroborating instrument outside it is an escalation trigger for judgement, not an automatic fail.

## 10. Fitness Functions

- **SEAM-01 consumer coupling**: `alignment/htf_ltf.py`'s import set matches a frozen allow-list — AST-based, `tests/test_fitness_imports.py` (§8.4). Re-asserted after #2 and #3.
- **Layers contract (ADR-001/ADR-007)**: unchanged `.importlinter`; `uv run lint-imports` must pass. No new `root_package`.
- **Two-sided no-lookahead boundary (ADR-003/ADR-013)**: hypothesis property over `to_key_levels(detect_fvgs(...))`, both halves.
- **Validity-window lookahead safety**: credit under HTF truncation to `purge_index + 1` is identical to credit on the full series — both `origin_index` and `expiry_index`, both indices on the **HTF** series (stated in the test docstring; a cross-series comparison would be silently meaningless). §8.3.
- **`_Detections` field allow-list (REQ-58.1)**: the record's field names match a frozen set, so no future edit can quietly add a Key Level field and subject the pool to the results-filter chain.
- **Per-signal exclusive bucket membership (ADR-009, strengthened)**: each `signal_id` in exactly one of `trades_opened` or the 8 buckets — never zero, never two. Strictly stronger than the totals-only sum check.
- **Minimal-pair discipline**: the confluent/non-confluent fixture pair varies **only** the HTF FVG's overlap with the purge extreme (§8.9), so the two cannot be distinguished by an unrelated field — the ghost-test pattern this project's judgment-day already found once.
- **Gate/bucket agreement (replaces V1's arithmetically-false equality)**: two independently-correct assertions plus one true containment.
  1. *CSV side*: the set of Model-1 `signal_id`s in `detections.csv` equals `{s.signal_id for s in population if keep(s)}`, `keep` being REQ-56's own predicate evaluated on the in-memory population.
  2. *Bucket side*: REQ-40.1's eight-bucket sum plus per-signal exclusive membership.
  3. *Cross-artefact containment*: every `signal_id` counted in `excluded_no_key_level` is **absent** from `detections.csv`, and every traded `signal_id` is **present** (REQ-59.1).

  V1's `count(model1 rows) == signals_considered - excluded_no_key_level` is dropped as arithmetically false, exactly as the spec's own V1 push-back said. Two independent reasons: (a) a signal that is `aligned`, non-`fvg_fill` and non-confluent but has `retest_index is None` lands in `excluded_never_confirmed` (the earlier cut) yet is still withheld by the CSV gate, so withheld ≥ `excluded_no_key_level` strictly; (b) on a `--types` run that excludes model1/alignment, `signals_considered` is 0 by the existing carve-out while the CSV may still carry rows. Containment (3) survives both cases because it is one-directional.

## 11. Migration / Rollout

No database, no feature flag, no deployment ordering. The one destructive step is the archive-time sync of REQ-30/40/45/46 into `openspec/specs/detector/spec.md` (`sdd-archive` §4, full-text MODIFIED blocks already drafted in the signed spec).

Rollback is staged (proposal §Rollback Plan): remove the `_filter_to_confluent` call → artefacts return to unfiltered content; remove the bucket branch, the `ReconciliationReport` field and the summary line → the invariant re-closes at seven; restore the spec from git. `core/key_level.py`, `to_key_levels`, the HTF detection call and `AlignedSignal.key_level` are pure computation with no artefact effect and may remain in place — which is what makes partial rollback safe.

## 12. Performance Considerations

One extra `detect_fvgs` pass over the **HTF** series per paired run — by construction 16–48× smaller than the LTF series (H4 vs M15), so negligible against the existing LTF passes. Confluence credit is an eager map keyed by purge index: O(purges × key_levels), bounded by the HTF series length and **independent of LTF signal count**, avoiding the O(signals × levels) shape this project has twice had to remove from hot paths. Expiry adds one integer comparison per (purge, level) pair — no new pass, since `fill_index` is already resolved by `detect_fvgs`' existing two-heap sweep. `_filter_to_confluent` is one linear pass plus a `set` of `signal_id`s. §8.5's 10-minute per-run budget is the real-data guard.

## 13. Architecture Impact

**Architecture impact**: `additive`

**Rationale**: Derived from §4 — `core` gains a new module inside an existing baseline layer; `primitives`, `alignment`, `backtest` and `viz.trades_table` are extended within their existing contracts; the single `modify` row (`cli` assembly) is intra-component (a stage inserted into a private filter chain), touching no boundary, dependency direction, or layer contract. `.importlinter` is unchanged and conformant. Unchanged from V1 — the V2 expiry reversal alters a predicate, not a boundary. The baseline gains entries; nothing in it becomes wrong.

## 14. Open Questions

None.

## 15. Sensitive Areas

None affected — the registry lists no sensitive area for this project, and this change reads MT5 CSV exports and writes regenerable artefacts only. Matches the signed spec's own coverage.

**Size budget**: exceeded, as V1 was. This V2 additionally carries §8's nine resolved test-mechanics decisions and §9's 61-row derivation over 55 scenarios; compressing either would return them to the "unspecified" state plan-verify iteration 1 flagged. Precedent accepted at V1.
