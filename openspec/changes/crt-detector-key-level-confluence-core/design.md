# Design: crt-detector-key-level-confluence-core

**Triage**: L | **Design version**: V3 | **Spec**: V3 signed (2026-08-30) | **Program**: `crt-detector-key-level-confluence` sub-change #1 (walking skeleton) | **Persona lens**: architect

## 0. V3 Change Log (against design V2)

| # | Source | Change |
|---|---|---|
| 1 | spec V3 REQ-55.6/.13 | **Both-sides breach: both extremes evaluated.** `_purge_wick_extreme` (singular) becomes `_purge_wick_extremes` (returns the 1–2 breached extremes); earliest-`origin_index` tiebreak now ranges over the union of matches from both extremes. §6, §9. |
| 2 | spec V3 REQ-53/REQ-55.11 | **Expiry boundary corrected**: validity window is `(origin_index, expiry_index]` — right-CLOSED. Predicate conjunct is `purge_index <= expiry_index`, not `<`. §5, §6, ADR-013. |
| 3 | spec V3 REQ-60.2 + verify-plan-2 #7 | **`W`'s numerator corrected, not just its denominator.** The bucket count cannot reach the band's top (it is capped at the post-`never_confirmed` subset). `W`'s numerator is the CSV-gate WITHHELD count, measured as the pre/post-gate `detections.csv` Model-1 row delta. §9.1 — the single most consequential V3 change. |
| 4 | verify-plan-2 #11 | **§8.5 rewritten**: one baseline instruction, not two conflicting ones. The pre-gate capture SUPPLEMENTS obs #419 in place and doubles as its still-valid-against-HEAD confirmation. §8.5. |
| 5 | verify-plan-2 #8 | **New mixed-population e2e fixture** (2 HTF purge candles, one confluent, one not) specified in §8.10 — what REQ-40.6/S-005.3's non-zero-bucket assertions need and no existing fixture produces. §2, §8.10, §9. |
| 6 | verify-plan-2 #6 | **REQ-46 given real coverage**: its two shipped scenarios plus one NEW assertion for the interaction the inserted bucket creates (dedup now runs on the post-confluence survivor set). §8.11, §9. |
| 7 | spec V3 REQ-53.4, REQ-60.3, REQ-60.4, REQ-40.2, REQ-59.2 | Test Derivation 55 → **59** scenarios; REQ-40.2's shipped assertion must be rewritten (it asserts `signals_considered == detections.csv` Model-1 rows, false once the gate bites). §2, §9. |

## 1. Architecture Overview

Confluence is **determined once** in `alignment/`, **stored once** on `AlignedSignal.key_level`, and **read twice** — by the CSV/chart gate in `cli.py` and by the `excluded_no_key_level` bucket in `backtest/simulate.py`. Neither consumer recomputes it (REQ-59); a single field is the source of truth for both, which is what makes REQ-42.1's trades↔detections join hold by construction under gating.

The determination is **per HTF purge candle**, not per signal (spec V3's granularity note): `_key_level_credit_map` is keyed by purge index, and every LTF signal aligned to that candle inherits its verdict. That is why the map is eager and cheap — it is sized by HTF purges, not by LTF signals.

`entries/model1.py` is pure-LTF by ADR-001 and cannot see HTF context, so the check sits one layer up. `alignment/htf_ltf.py` already holds the HTF purge candle (`_purge_index_map`'s key IS the purge index), making it the only layering-legal place to *determine* confluence. Enforcement is a separate concern and stays in `cli.py`'s existing filter chain, inserted immediately after the `population` snapshot so that the backtest bucket stays live and countable while CSV/chart output downstream is narrowed.

A Key Level carries a **validity window** `(origin_index, expiry_index]` — knowable from the third candle of the FVG formation, valid up to and including the candle that mitigates it. Both bounds are answerable at the crediting purge candle from data at or before it, which is what keeps ADR-003 intact (ADR-013).

The seam that sub-changes #2/#3 plug into is `core.KeyLevel` (SEAM-01) plus a per-source `to_key_levels` adapter (SEAM-02). `alignment` never imports a detector module: Key Level sources are **injected** by the `cli.py` assembly, so registering ICTOrderBlock or Breaker Block later touches the assembly only.

**Pattern**: existing — matches `detector/cli.py`'s `_filter_by_date_range` / `_filter_by_session` / `_exclude_invalidated_model1` chain and `alignment/htf_ltf.py`'s `ltf_signals=`/`htf_ranges=` injection parameters. No named pattern adopted.

## 2. File Changes

| Path | Action | Purpose |
|---|---|---|
| `detector/core/key_level.py` | Create | `KeyLevel` frozen dataclass (SEAM-01) — imports nothing |
| `detector/primitives/fvg.py` | Modify | `to_key_levels(fvgs)` adapter (SEAM-02); `origin_index = end_index`, `expiry_index` from fill state |
| `detector/alignment/htf_ltf.py` | Modify | `AlignedSignal.key_level`; `htf_key_levels` param; `_key_level_credit_map`, `_purge_wick_extremes` |
| `detector/cli.py` | Modify | HTF FVG→KeyLevel local in `_detect_all`; `_filter_to_confluent` after the `population` snapshot |
| `detector/backtest/simulate.py` | Modify | `_PopulationCuts` record; 4th cut branch; `ReconciliationReport.excluded_no_key_level` |
| `detector/viz/trades_table.py` | Modify | `  no key level:` line in the reconciliation block |
| `openspec/specs/detector/spec.md` | Modify | Destructive sync of REQ-30, REQ-40, REQ-45, REQ-46 at archive |
| `openspec/changes/.../evidence/pre-gate-h4-m15.md` | Create | Pre-gate baseline supplement, 3 instruments (§8.5) — captured before any gate code |
| `openspec/changes/.../evidence/real-data-h4-m15.md` | Create | REQ-60.1–.4 recorded evidence (§8.5) |
| `detector/tests/fixtures/synthetic.py` | Modify | `key_level_confluence_pair_setup(confluent)` minimal-pair builder (§8.9) |
| `detector/tests/fixtures/mt5_csv.py` | Modify | `write_series_csv(series, path)` — renders any `OHLCSeries` as MT5 CSV (§8.9) |
| `detector/tests/test_fvg.py` | Modify | `to_key_levels` adapter units (REQ-53.1/.2/.3, REQ-54.1) |
| `detector/tests/test_alignment.py` | Modify | Confluence determination (REQ-54.4, REQ-55.1–.13 incl. both-sides independence) |
| `detector/tests/property/test_no_lookahead.py` | Modify | Two-sided boundary (REQ-54.2/.3); key-level injection (§8.3); REQ-54.5 |
| `detector/tests/test_cli.py` | Modify | `_filter_to_confluent` predicate (REQ-56.1/.4/.6/.7), REQ-58.1, REQ-59.2 |
| `detector/tests/test_cli_e2e.py` | Modify | Gate e2e (REQ-56.2/.3/.5, REQ-57.1–.3, REQ-58.2/.3) |
| `detector/tests/test_backtest_simulate.py` | Modify | `_aligned` default (§8.1); REQ-30.7, REQ-40.5, REQ-46.1/.2 + dedup-after-confluence (§8.11); exclusive membership |
| `detector/tests/test_backtest_metrics.py` | Modify | `_aligned` default (§8.1); 8-bucket sum invariant (REQ-40.1), REQ-40.4 |
| `detector/tests/test_cli_backtest_e2e.py` | Modify | `_HTF_DAILY` redesign (§8.2); mixed 2-purge fixture (§8.10); REQ-40.2 assertion rewrite; REQ-40.6, REQ-45.3, REQ-59.1, `no key level:` line |
| `detector/tests/test_fitness_imports.py` | Modify | SEAM-01 AST import allow-list (§8.4) — REQ-53.4's home |

`backtest/metrics.py` is **not** changed — `ReconciliationReport` lives in `simulate.py` and `compute_metrics` passes it through untouched. `viz/chart.py` is **not** changed — HTF FVGs never reach it (ADR-014), so REQ-57.2 holds by construction.

## 3. Flow Changes

| Flow | Action | REQ-IDs | E2E spec | Notes |
|---|---|---|---|---|
| Detector run without `--backtest` (`detections.csv` + `overlay.png`) | Modify | REQ-56.1–56.7, REQ-57.1–57.3, REQ-58.1–58.3 | `detector/tests/test_cli_e2e.py` (extend) | Determinably-non-confluent, non-`fvg_fill` Model-1 rows and markers withheld; 7-column header and every other row unchanged |
| Detector run with `--backtest` (`trades.csv` + `metrics_summary.txt`) | Modify | REQ-30.7, REQ-40.1/.2/.4/.5/.6, REQ-45.1–45.3, REQ-46.1/.2, REQ-59.1 | `detector/tests/test_cli_backtest_e2e.py` (extend) | 8th bucket disclosed; dedup now runs on the post-confluence survivor set; byte-compat anchor re-based differentially |

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

Zero `deviates` rows → no deviation ADR required. Unchanged from V2: V3 alters two predicates and the test surface, no component.

## 5. Data Model

```python
# core/key_level.py
@dataclass(frozen=True)
class KeyLevel:
    kind: Literal["fvg"]         # source tag only; widened by #2/#3. NEVER direction.
    top: float
    bottom: float
    origin_index: int            # first index at which the level is provably knowable
    expiry_index: int | None = None   # last index at which it is still valid; None = never expires

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

**Validity window (CORRECTED V3)**: a level is valid at purge index `p` iff `origin_index < p` and (`expiry_index is None` or `p <= expiry_index`). The window is `(origin_index, expiry_index]` — left-open, **right-closed**. The asymmetry is deliberate and spec-mandated (REQ-53's V3 boundary note): the two bounds answer different questions — *was this level knowable yet?* (strictly before `p` — a level completing at `p` was not observable when `p` opened) versus *was this level still open?* (a level filled AT `p` was open when `p` began, and the candle that fills a zone is the same candle that reacted at it). The `expiry_index` field name reads as "last valid index" for exactly this reason.

## 6. Interface Contracts

```python
# primitives/fvg.py — SEAM-02
def to_key_levels(fvgs: list[FVG]) -> list[KeyLevel]
# kind="fvg", top=fvg.top, bottom=fvg.bottom, origin_index=fvg.end_index.
# expiry_index = fvg.fill_index when fvg.fill_status == "filled", else None (REQ-53.2).
# Reading fill state is REQUIRED, not forbidden: the credit predicate consumes it only
# as `purge_index <= expiry_index`, the past-tense question "had this level already been
# filled BEFORE this purge candle?" — answerable at the purge candle (REQ-54.5).

# alignment/htf_ltf.py
def tag_alignment(..., htf_key_levels: list[KeyLevel] | None = None) -> list[AlignedSignal]
# None means "no Key Level sources registered" -> every key_level is None.
# Deliberately does NOT self-compute (unlike ltf_signals/htf_ranges) — ADR-012.

def _purge_wick_extremes(purge_candle: Candle, crt_range: CRTRange) -> tuple[float, ...]
# The extreme(s) on the side(s) actually breached — the breach(es) that made this the
# purge candle (REQ-55's "which wick extreme(s) are credited"):
#   high if purge_candle.high > crt_range.high
#   low  if purge_candle.low  < crt_range.low
# Both -> a 2-tuple (14.1% of real H4 purges); never empty (a non-breaching candle is
# not a purge index key). NEVER derived from ltf_signal.direction (REQ-55.7).

def _key_level_credit_map(
    candles: tuple[Candle, ...],
    purge_index_to_range: dict[int, CRTRange],
    key_levels: list[KeyLevel],
) -> dict[int, KeyLevel]
# Eager, keyed by purge index -> O(purges x levels x extremes<=2), independent of LTF
# signal count. A level qualifies for a purge if SOME credited extreme satisfies all three:
#   level.origin_index < purge_index                                   (REQ-54.4)
#   level.expiry_index is None or purge_index <= level.expiry_index    (REQ-55.9/.10/.11)
#   level.bottom <= extreme <= level.top                               (REQ-55.4, edges inclusive)
# Both extremes are evaluated INDEPENDENTLY and their qualifying levels pooled; confluence
# holds if EITHER yields a match (REQ-55.6, REQ-55.13). Across that pooled set the lowest
# origin_index wins (REQ-55.12), input order on ties — same precedence as _purge_index_map's
# setdefault and ADR-010's dedup survivor. There is NO high-side preference: a low-side
# match with an earlier origin beats a high-side match with a later one.

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

**Status**: Proposed (unchanged from V2)

**Context**: Three sub-changes will each add a Key Level source (FVG now; ICTOrderBlock, Breaker Block later). The confluence rule must not grow a branch per source, and `alignment` must not acquire an import of each detector module — SEAM-01 exists precisely to prevent that. `tag_alignment`'s existing convention is `param=None → compute it myself`, which would hard-wire `detect_fvgs` into `alignment`.

**Decision**: `core/key_level.py` holds a frozen `KeyLevel(kind, top, bottom, origin_index, expiry_index)` importing nothing. Each source module owns a `to_key_levels` adapter. `tag_alignment` takes `htf_key_levels` and **breaks** the `None → self-compute` convention: `None` means "no sources registered". Source registration lives in `cli.py`'s `_detect_all`.

**Consequences**:
- #2/#3 add a source by touching their own module plus one `_detect_all` line — `alignment`, `viz`, `backtest` are untouched, which the SEAM-01 AST fitness test pins (§8.4) and REQ-53.4 now asserts as a spec scenario.
- `kind` carries the source tag only, never direction — direction already lives on the signal, and overloading it would make #2's CSV attribution column ambiguous.
- The validity window is normalised too: a source whose levels never expire leaves `expiry_index` at `None`, so #2/#3 inherit the semantics without widening the shape.
- Cost: one convention broken inside a function that establishes the opposite convention twice. Mitigated by an explicit code comment and this ADR; a caller that forgets to inject fails loudly (every aligned non-`fvg_fill` signal is withheld), not silently.

**Alternatives Considered**:
- **`Protocol`/structural typing over each detector's own type**: `alignment` would still need each concrete type at the call site, and `origin_index`/`expiry_index` semantics differ per source — the normalisation is the value, and a Protocol does not perform it.
- **`FVG | ICTOrderBlock | BreakerBlock` union**: every consumer grows a match per source; adding a source becomes an edit in `alignment`, the exact coupling SEAM-01 forbids.
- **`tag_alignment` self-computing FVG key levels when `None`**: consistent with the local convention, but imports `primitives.fvg` into the confluence path and makes #2 a change to `alignment`. Consistency lost to seam integrity, deliberately.

### ADR-013: A Key Level's validity is the window `(origin_index, expiry_index]` — knowable-start, mitigation-end-inclusive

**Status**: Proposed — **supersedes design V1's ADR-013** (which argued no expiry at all) and **amends V2's** (which closed the window one candle early)

**Context**: Two bounds, one concept. (a) `detect_fvgs` reads `candles[i]` and `candles[i+2]`; the gap is not an observation until `i+2`, so `FVG.start_index` would credit a signal against something not yet knowable, violating ADR-003. (b) V1 decided a mitigated FVG stays valid forever; a blind judge measured that rule over real H4/M15 data — unexpiring filled zones accumulated to ~**9×** the instrument's price range and the gate withheld only **2.8%** of signals. The counterfactual (expire on mitigation) measured **30–34%**. (c) V2 then excluded a purge *at or after* expiry, which denied credit to the single strongest case: a candle that both reacts at and fills the same zone in one motion (~0.2% of signals) — the candle doing the filling excluded from crediting the reaction that caused it.

**Decision**: `to_key_levels` sets `origin_index = fvg.end_index` and `expiry_index = fvg.fill_index` when filled, `None` otherwise. Credit requires `origin_index < purge_index` **and** (`expiry_index is None or purge_index <= expiry_index`). Left-open, right-closed — deliberately asymmetric, because the bounds answer different questions (§5). Both bounds are pinned by a two-sided property test that truncates the HTF series and re-derives the levels (§8.3).

**Consequences**:
- Reading fill state is not lookahead: `_sweep_fill_status` resolves fill at the filling candle, so validity at `p` is determined by candles `≤ p`. REQ-54.5's truncation property is the proof, not a comment.
- Regression to `start_index` fails the "absent before" half; over-correction to `start_index + 3` fails the "present at" half. Both directions caught.
- Cost of the asymmetry: a reader cannot state the rule as "half-open on both ends"; the two conjuncts must be read separately, and a future source with different semantics must decide its own end-treatment consciously. REQ-55.11 is the executable statement of the rule.
- Cost: an FVG filled at `origin_index + 1` has a one-candle creditable window rather than none. That falls out of the bounds; no separate rule.
- Cost: `origin_index` and the level's drawn geometric start differ by two candles; a chart reader must not expect them to coincide.

**Alternatives Considered**:
- **Right-open (`p < expiry_index`, design V2)**: symmetric with the origin bound and easier to state, but excludes the purge-and-fill-in-one-candle case, which is the *most* confluent event the methodology recognises. Symmetry lost to correctness, on a measured 0.2% of signals whose direction of error is one-sided.
- **`start_index` as origin**: matches where the zone is drawn, but is knowably wrong — the level cannot be observed there.
- **No expiry (design V1)**: rejected on measurement — 2.8% withheld makes the gate a no-op.
- **Partial-mitigation or time-decay expiry**: no definitional source in the charters and no principled parameter. Deferred (spec out-of-scope).

### ADR-014: Confluence is determined in `alignment`, enforced in `cli`, and HTF Key Levels never enter `_Detections`

**Status**: Proposed (unchanged from V2)

**Context**: The program artefact asked for both a pre-CSV filter and a live 8th exclusion bucket. Applied at one point these are mutually exclusive: filtering before `population` is snapshotted makes the bucket always zero. Separately, `_Detections` fields are swept by `_filter_by_date_range` and `_filter_by_session`, which filter `htf_crt_ranges` by HTF timestamp.

**Decision**: Determine confluence once inside `tag_alignment` and store it on `AlignedSignal.key_level` (REQ-59). Insert `_filter_to_confluent(detections)` in `cli.py` between the `population` snapshot (line ~120) and `_filter_by_types` (line ~121). HTF Key Levels are a **local variable** in `_detect_all`, threaded into `tag_alignment` and discarded — never a `_Detections` field (REQ-58).

**Consequences**:
- `population` inherits pre-filter data, so `excluded_no_key_level` is live and countable while CSV/chart output is narrowed (REQ-40.6). Both requirements satisfied without a second determination.
- REQ-42.1/REQ-59.1 hold by construction: a traded signal survived the bucket, so it carries a `key_level`, so it survived the CSV gate — because both read the *same field*.
- Keeping levels out of `_Detections` means `--from-date`/`--session` cannot narrow the Key Level pool; a display filter can never silently become a validity filter. It also gives REQ-57.2 and REQ-57.3 for free.
- Cost: correctness depends on statement order in `main()`. A refactor moving the gate above the snapshot regresses silently — pinned by REQ-40.6's e2e (now non-vacuous thanks to §8.10's fixture) and the REQ-59.1 join scenario.

**Alternatives Considered**:
- **Filter before the `population` snapshot**: simpler, but the bucket becomes dead (always zero) and REQ-40 loses the disclosure that is half the point.
- **Recompute confluence inside `simulate()`**: a second source of truth that can disagree with the CSV gate with no test noticing — the failure class this project shipped once in the `--types` population-snapshot defect.
- **Store `htf_key_levels` on `_Detections`**: symmetric with `htf_crt_ranges`, but subjects the level pool to the results-filter chain and forces explicit exclusions in `render_chart`/`write_detections_csv`.

### ADR-015: The new bucket is identified by name, in the last position of `_population_cuts`, whose return becomes a named-field record

**Status**: Proposed (unchanged from V2)

**Context**: `excluded_duplicate` is documented as "stage 4" in the shipped REQ-46; inserting a bucket mid-chain silently falsifies every ordinal downstream. The identical hazard exists in code: `_population_cuts` returns a positional tuple whose int count goes from three to four adjacent, same-typed values. A swap of `never_confirmed` and `no_key_level` at the single unpack site leaves the REQ-40.1 sum invariant **passing** — two independently-true sums hiding a compensating error.

**Decision**: Buckets are referenced by name, never by ordinal, in spec text and code. `excluded_no_key_level` is appended **last** in `_population_cuts`' `elif` chain (after `never_confirmed`), and `_population_cuts` returns a frozen `_PopulationCuts` record instead of a tuple.

**Consequences**:
- The three existing bucket counts stay byte-identical against the current regression suite — no re-baselining.
- A signal both `unaligned` and non-confluent lands in `excluded_unaligned` by the earliest-wins chain (REQ-40.5); an `fvg_fill` signal lands in `excluded_no_crt_range` and never reaches the confluence cut (REQ-30.4) — both by the existing branch order, verified in code.
- The swap is made impossible rather than merely detectable; per-signal exclusive-membership remains the semantic check.
- Cost: ~6 lines and one module-private type for a single producer/consumer pair — accepted only because the failure it removes is invisible to the sum invariant.

**Alternatives Considered**:
- **Keep the tuple**: zero new code, but the one failure mode that matters passes every existing assertion.
- **Insert the bucket mid-chain in "logical" order**: changes which bucket existing borderline signals land in, forcing a re-baseline of shipped counts for no behavioural gain.
- **Renumber the ordinals in REQ-46**: fixes today's text and leaves the failure class in place for the next insertion.

### ADR-016: REQ-45's and REQ-56.3's byte-compat guarantees are re-anchored differentially, not absolutely

**Status**: Proposed (unchanged from V2)

**Context**: REQ-45 promised `detections.csv`/`overlay.png` byte-identity against "today's exact output" for non-`--backtest` runs, and spec V1's REQ-56.3 the same against "a run before this change". The gate runs on **every** run, so both absolute pre-feature baselines become permanently unreproducible the moment this ships.

**Decision**: Re-anchor both differentially. REQ-45 → the equivalent run differing **only** by the `--backtest` flag. REQ-56.3 → two runs of the **current** code over a minimal input pair differing only in whether the HTF Key Level zone contains the purge candle's credited extreme (§8.9's builder is what makes that pair minimal).

**Consequences**:
- Strengthens both: they stay verifiable after any future change to the detection population, whereas an absolute anchor decays on every such change.
- The "nothing else changed" promise is preserved by REQ-56.3/.4 (surgical scope) and REQ-56.5 (header contract).
- Cost: a destructive sync of signed REQ-45 text at archive; the pre-change absolute output stops being a reference — which is exactly why §8.5 completes the pre-gate real-data baseline *before* any code is written. That capture is the last moment it exists.

**Alternatives Considered**:
- **Leave REQ-45 standing and add a carve-out REQ**: leaves a signed requirement contradicted by shipped behaviour — what `sdd-archive` §4 exists to prevent.
- **Gate only under `--backtest`**: preserves the absolute anchor, but the user's rule is that a non-confluent Model-1 is not a setup at all; it would keep publishing invalid setups in the primary artefact.

## 8. Test Mechanics

### 8.1 — `_aligned()` helper default

`test_backtest_simulate.py` and `test_backtest_metrics.py` each define `_aligned(signal, htf_context=_HTF_CONTEXT, aligned="aligned")`. With `key_level` defaulting to `None`, ~25 existing tests silently become "no key level" tests and produce zero trades — a mass semantic rewrite nobody authored.

**Decision**: give the helper a default confluent level.

```python
_KEY_LEVEL = KeyLevel(kind="fvg", top=1.1050, bottom=1.0950, origin_index=0, expiry_index=None)

def _aligned(signal, htf_context=_HTF_CONTEXT, aligned="aligned", key_level=_KEY_LEVEL):
    return AlignedSignal(ltf_signal=signal, htf_context=htf_context, aligned=aligned, key_level=key_level)
```

Those tests exercise fill/exit/bucket mechanics with confluence irrelevant and, pre-change, implicitly satisfied — the default preserves their authored intent. Confluence-specific tests (REQ-30.7, REQ-40.5, exclusive membership) pass `key_level=None` **explicitly**, putting the negative case at the call site. Updating ~25 call sites individually was rejected: a large diff whose every hunk says the same thing, in which a reviewer cannot tell an intentional `key_level=None` from a missed one.

### 8.2 — `_HTF_DAILY` e2e fixture redesign

The current 3-candle daily HTF fixture cannot produce a credited Key Level at all: no FVG can form and be knowable before the purge candle at index 1. **This is an explicit S-000 task**, and it re-baselines CRT range / `htf_context` / `take_profit` / R:R-floor / expected-trade-count expectations across the **20 tests** in `test_cli_backtest_e2e.py`.

Constraints the redesign must satisfy (minimum **6** HTF candles):

1. FVG on candles 0/1/2 → `origin_index = 2`. Bearish (`candles[0].low > candles[2].high`), zone `[candles[2].high, candles[0].low]`, width ≥ `0.1 × ATR14(index 2)`.
2. CRT range candle at index 3: `range_high = candles[3].high`, `range_low = candles[3].low`.
3. Purge candle at index **4** — the LTF anchor's calendar day. `candles[4].high > candles[3].high` (high-side breach → bearish signal), and that high inside the FVG zone.
4. FVG unexpired at index 4: a bearish FVG fills on `high >= top`, so every candle 3..4 must have `high < candles[0].low`.
5. Ranges starting at 0/1/2 must each first-breach strictly before index 4, so `_purge_index_map`'s `setdefault` leaves index 4 to the index-3 range. The falling 0→2 shape needed by (1) already delivers this.
6. Index 4 is not the last HTF candle (index 5 exists) — avoids `insufficient_htf_data`.
7. `candles[3].low` (the bearish `take_profit`) must clear the R:R floor against the LTF entry ~1.1010 and SL 1.1037: `take_profit <= 1.0956`.

Indicative layout (exact OHLC is apply's to finalise against these constraints):

| idx | date | O | H | L | C | role |
|---|---|---|---|---|---|---|
| 0 | 2026.07.02 | 1.1060 | 1.1065 | **1.1040** | 1.1045 | FVG top = 1.1040 |
| 1 | 2026.07.03 | 1.1042 | 1.1044 | 1.1034 | 1.1036 | middle |
| 2 | 2026.07.04 | 1.1032 | **1.1030** | 1.1020 | 1.1022 | FVG bottom = 1.1030 → zone [1.1030, 1.1040] |
| 3 | 2026.07.05 | 1.1020 | 1.1028 | **1.0900** | 1.0910 | CRT range H=1.1028 L=1.0900 (= take_profit) |
| 4 | 2026.07.06 | 1.0915 | **1.1035** | 1.0905 | 1.0920 | purge (high 1.1035 > 1.1028, inside zone) |
| 5 | 2026.07.07 | 1.0920 | 1.0930 | 1.0910 | 1.0925 | trailing |

`_LTF_CANDLES` stays as-is except for the date shift: its candle-4 low of 1.0790 still reaches the new `take_profit` of 1.0900, so the fixture's win outcome is preserved.

### 8.3 — Property-harness key-level injection

Three `tag_alignment` call sites in `test_no_lookahead.py` would otherwise go vacuous. Two treatments, because the tests have two subjects:

- **`test_alignment_detection_has_no_lookahead`** (lines 272/279): inject **per-truncation** levels — `to_key_levels(detect_fvgs(htf_series))` for the full call, `to_key_levels(detect_fvgs(truncated_htf))` for the truncated call. The existing `full_by_key[key] == tag` assertion then compares `key_level` too, which is REQ-54.5 at property strength: an implementation deriving `expiry_index` from anything past the purge candle fails it. **This is REQ-54.5's home** — no separate property test is added.
- **`test_backtest_resolution_is_monotone_in_series_length`** and **`test_backtest_exit_is_local_to_its_own_window`** (lines 381/428): inject a single synthetic **cover-all** level spanning the HTF price range (`bottom=min(low)`, `top=max(high)`, `origin_index=0`, `expiry_index=None`). Their subject is `simulate()`'s use of the series, not confluence; holding confluence constant-and-satisfied keeps them exactly as strong as before, *deterministically*. The docstrings must say so.

### 8.4 — SEAM-01 fitness mechanism (REQ-53.4's home)

**Decision**: AST parse of `alignment/htf_ltf.py`'s import statements in `test_fitness_imports.py`. `ast.parse` the file, collect the module path of every `Import`/`ImportFrom`, assert the set equals a frozen expected set:

```
{bisect, dataclasses, datetime, typing,
 core.candle, core.config, core.key_level, core.pairing_table,
 entries.model1, primitives.crt_range}
```

SEAM-01 is an **allow-list** ("no new detector-source module joins this import list"), not a deny-list of today's sources — which is exactly what spec V3's REQ-53.4 now states as a scenario. `.importlinter` was rejected: no allow-list-of-modules contract exists, a `forbidden` contract naming `primitives.fvg` would not catch #2's `primitives.order_block`, and a second contract type dilutes ADR-001's deliberately-sole layers contract. Runtime module inspection was rejected: `sys.modules` shows transitive imports, so it cannot distinguish "this module imports X" from "something it imports imports X". Cost: the frozen set must be edited deliberately when a legitimate import is added — the point of the assertion; its failure message names SEAM-01 and REQ-53.4.

### 8.5 — Pre-gate baseline and REQ-60 real-data validation (reconciles verify-plan-2 finding #11)

**One instruction, replacing V2's two conflicting ones.** V2 §8.5 said "capture before any code"; slices V2 S-000.1 said "reference obs #419, do not re-run". Both were partly right: obs #419 is real and still valid, but it lacks GBPUSDm/DXYm and every `detections.csv` Model-1 row count REQ-60.1 requires.

**Decision: SUPPLEMENT obs #419 in place; do not re-capture from scratch.** Verified: `git diff f44b2c4..HEAD -- detector/` is **empty** — the detector tree at current HEAD is byte-identical to the commit obs #419 was captured at, so quantities captured now are exactly comparable with the ones already recorded. Re-capturing from scratch would additionally re-run EURUSDm's cost sweep, which nothing needs and which is the expensive part.

**S-000.1 — pre-gate capture, before any gate code is written** (`pairs/H4/` and `pairs/M15/` verified present for all three instruments):

1. Run the existing command (step 3's, minus any gate) on **EURUSDm, GBPUSDm, DXYm**, output under `.sdd/evidence/.../pre-gate/{instrument}/`.
2. **EURUSDm is the validity check**: its produced `metrics_summary.txt` MUST match obs #419's recorded block exactly. A match confirms obs #419 against HEAD (S-000.1's original intent); a mismatch HALTS — the baseline is not what it claims and nothing downstream can be trusted.
3. Record per instrument into `evidence/pre-gate-h4-m15.md` (committed, small text): `signals_considered`, `trades_opened`, win rate, average R, total R, the seven-bucket reconciliation block, and the **`detections.csv` Model-1 row count** (the "before" half of REQ-60.1's before/after pair — the quantity obs #419 lacks entirely).
4. `mem_update` obs #419 (same topic `sdd/crt-detector-key-level-confluence-core/pre-gate-baseline`) with the supplement. Its EURUSDm cost sweep carries forward unchanged; no re-run.

**Post-implementation evidence (S-000.8)** — a **manual validation run recorded in change artefacts**, not a committed automated test. `pairs/` is gitignored (18MB, not distributable), so a committed test needs a skip-if-absent guard and would be green on every machine lacking the data: a test advertising coverage it never exercises is worse than none. REQ-60 asks for *recorded evidence*, and §9.1's bands are human judgement gates at S-000.

```
uv run --project detector python -m detector.cli \
  --csv pairs/M15/EURUSDm_M15_202207260000_202608192030.csv --symbol EURUSDm \
  --htf-csv pairs/H4/EURUSDm_H4_202001020000_202608192000.csv --htf-symbol EURUSDm \
  --output-dir .sdd/evidence/crt-detector-key-level-confluence-core/eurusdm --backtest
```

Record into `evidence/real-data-h4-m15.md`: REQ-60.1's six counts per instrument, `W` and its two operands (§9.1), `trades_opened` against REQ-60.3's floor, and the REQ-60.4 comparison against the pre-gate figures. **Runtime budget**: 10 minutes wall clock per run; exceeding it is an escalation, not a silent wait — this codebase has twice had to remove O(n²) hot paths at MT5 scale.

### 8.6 — HTF `FVGConfig`

**Decision**: the **same** `config.fvg` as the LTF pass. `min_size_atr` is ATR-relative and the ATR is computed on the HTF series itself, so the threshold self-scales to the HTF's own volatility. A separate `htf_fvg` config field would be a new public config surface with one speculative user and no principled way to choose its value — YAGNI. If §8.5's evidence shows level density is wrong, that is evidence for a follow-up config change, recorded as such rather than pre-built.

### 8.7 — `metrics_summary.txt` literal line

Exact string from `f"  no key level: {r.excluded_no_key_level}"` — two leading spaces, lowercase, single spaces between words, single space after the colon. Position: **immediately after `  never confirmed:` and immediately before `  duplicate:`**, matching REQ-40's bucket precedence order, which the existing seven-line block already mirrors. `  no crt range:` is the precedent for a multi-word bucket rendered with spaces. `write_metrics_summary`'s docstring calls this wording a never-paraphrase contract; the e2e assertion checks the exact substring **and** its position relative to its two neighbours.

### 8.8 — `excluded_no_key_level` in the monotonicity assertion list

The proposed assertion in `test_backtest_resolution_is_monotone_in_series_length` (~line 413) truncates only the LTF series while the population and its levels are fixed on the full HTF series — so it can never fail. **But neither can any of its six existing siblings**: that block asserts "these cuts do not depend on series length beyond the anchor", a weak but real invariance property. Adding the new bucket there is **consistent** with them, not newly tautological, and it is kept. What is **dropped** is claiming it as a fitness function. The falsifiable confluence-vs-truncation property is REQ-54.5, in §8.3's strengthened alignment property.

### 8.9 — Minimal-pair fixture builder

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

Consumers derive their own altitude from the pair: `test_alignment.py` calls `tag_alignment(..., htf_key_levels=to_key_levels(detect_fvgs(pair.htf_series)))` and asserts against `pair.expected_key_level`; `test_cli.py` wraps the result in a `_Detections` and exercises `_filter_to_confluent`; `test_cli_e2e.py` renders both series via `write_series_csv` and runs `main()`. `test_backtest_simulate.py`/`test_backtest_metrics.py` are **not** consumers — they construct `AlignedSignal`s directly and are served by §8.1's default.

### 8.10 — Mixed-population e2e fixture: two HTF purge candles, one confluent, one not (NEW — verify-plan-2 finding #8)

REQ-40.6 and the containment assertions require a run in which `excluded_no_key_level` is **non-zero while other buckets are also populated**. No existing or previously-designed fixture can produce this: §8.2's redesign has exactly one HTF purge candle, and §8.9's minimal pair varies confluence across two *runs*, not within one. `_SECOND_ZONE_LTF_CANDLES` adds a second LTF signal but on the **same calendar day**, so both inherit one HTF candle's verdict (§1's granularity) — same verdict, no mix.

**Decision**: extend, do not duplicate. Add `_HTF_DAILY_MIXED = _HTF_DAILY + [3 rows]` and `_MIXED_LTF_CANDLES = _LTF_CANDLES + [second-day block]` in `test_cli_backtest_e2e.py`, following `_SECOND_ZONE_LTF_CANDLES`' existing extension idiom. The confluent half stays a single source of truth; only the non-confluent half is new. A separate writer `_write_mixed_ltf_csv` is needed because the shipped one hard-codes one date.

HTF extension constraints (indices 6–8, all prices strictly below the 0/1/2 zone's `bottom` so purge B is non-confluent by geometry regardless of expiry):

1. Index 6 is CRT range B; index 7 is purge B with `candles[7].high > candles[6].high` (high-side breach → bearish, mirroring purge A); index 8 exists so 7 is not the last candle.
2. `candles[7].high` must lie **outside** every unexpired zone at index 7 — with the whole 6–8 block below `1.1030` this holds against the only zone present.
3. **No additional FVG may form on candles 3..8 whose zone contains `candles[7].high`.** Apply MUST verify by running `detect_fvgs` on the finished fixture and asserting the level set is exactly the 0/1/2 zone — this is the constraint most easily broken by an OHLC tweak.
4. Ranges starting at 3, 4 and 5 must each first-breach strictly before index 7, so `setdefault` leaves index 7 to range B.

Indicative extension (apply finalises against the constraints; verified consistent with §8.2's rows):

| idx | date | O | H | L | C | role |
|---|---|---|---|---|---|---|
| 6 | 2026.07.08 | 1.0920 | 1.0940 | 1.0850 | 1.0860 | CRT range B: H=1.0940 L=1.0850 (= take_profit B) |
| 7 | 2026.07.09 | 1.0860 | **1.0955** | 1.0855 | 1.0870 | purge B — breaches 1.0940; 1.0955 ∉ [1.1030, 1.1040] → **non-confluent** |
| 8 | 2026.07.10 | 1.0870 | 1.0880 | 1.0860 | 1.0875 | trailing |

LTF extension: a second five-candle block dated **2026.07.09** (purge B's day), same shape as `_LTF_CANDLES` shifted into range B's price region so it forms its own CRT range, purges its high, confirms, and **has `retest_index` set** — otherwise it lands in `excluded_never_confirmed`, an earlier cut, and never reaches the confluence bucket at all.

Resulting population: day A's signal → `trades_opened`; day B's → `excluded_no_key_level ≥ 1`; `detections.csv` carries A's Model-1 row and not B's. That makes REQ-40.6, REQ-59.1 and both §10 containment assertions non-vacuous in a single run. Consumers: S-005.3 (REQ-40.6), S-005.4 (REQ-59.1), and the two §10 containment e2e rows.

### 8.11 — REQ-46 dedup coverage (NEW — verify-plan-2 finding #6)

REQ-46's MODIFIED block is a cross-reference correction with no behavioural change, so V2 left its two scenarios as implicit regression. That understates the actual risk: `excluded_no_key_level` is inserted **before** `excluded_duplicate`, so `_dedup` now receives a strictly smaller candidate list, and duplicate groups whose members straddle the confluence cut collapse differently than before.

**Decision**: three explicit tasks in `test_backtest_simulate.py`, mapped to S-005 (population invariants), not left as ambient regression:

1. REQ-46.1 — 3 identical-tuple candidates → 1 survivor (lowest `origin_index`), 2 in `excluded_duplicate`. Re-run against the `_PopulationCuts` record.
2. REQ-46.2 — same `anchor_index`/`entry_price`, different `entry_type` → both survive.
3. **NEW**: given a duplicate group in which one member has `key_level=None` and the others do not, the `key_level=None` member is counted in `excluded_no_key_level` and **never** in `excluded_duplicate` — dedup operates on the post-confluence survivor set. This is the assertion that fails if a future edit moves the confluence cut after dedup.

## 9. Test Derivation

| REQ-ID | Scenario | Level | Test path | Flow ref |
|---|---|---|---|---|
| REQ-53.1 | FVG zone preserved, `kind` identifies source | unit | `tests/test_fvg.py` | — |
| REQ-53.2 | filled → `expiry_index = fill_index`; open → `None`; equal otherwise | unit | `tests/test_fvg.py` | — |
| REQ-53.3 | no FVG → empty list, not error/None | unit | `tests/test_fvg.py` | — |
| REQ-53.4 | `alignment/htf_ltf.py` imports only the SEAM-01 allow-list | architectural | `tests/test_fitness_imports.py` (§8.4) | — |
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
| REQ-55.6 | both sides breached, each matching its own level → both eligible, lower `origin_index` wins | unit | `tests/test_alignment.py` | — |
| REQ-55.7 | `direction`-based selection must fail this | unit | `tests/test_alignment.py` | — |
| REQ-55.8 | unfilled level, origin earlier → credited | unit | `tests/test_alignment.py` | — |
| REQ-55.9 | `expiry_index = 60 < purge 80` → not credited | unit | `tests/test_alignment.py` | — |
| REQ-55.10 | `expiry_index = 90 > purge 80` → credited | unit | `tests/test_alignment.py` | — |
| REQ-55.11 | `expiry_index == purge_index == 80` → **credited** (right-closed) | unit | `tests/test_alignment.py` | — |
| REQ-55.12 | two qualifying levels → lowest `origin_index` wins | unit | `tests/test_alignment.py` | — |
| REQ-55.13 | both sides breached, only the LOW side matches → credited | unit | `tests/test_alignment.py` | — |
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
| REQ-59.1 | every traded `signal_id` is a Model-1 CSV row | e2e | `tests/test_cli_backtest_e2e.py` (§8.10 fixture) | Run with `--backtest` (Modify) |
| REQ-59.2 | flipping one eligible signal's `key_level` moves CSV row and bucket together | unit | `tests/test_cli.py` | — |
| REQ-60.1 | six counts recorded per instrument, pre- and post-gate | evidence | `.../evidence/real-data-h4-m15.md` (§8.5) | — |
| REQ-60.2 | withheld fraction `W` inside §9.1's band | evidence | `.../evidence/real-data-h4-m15.md` (§8.5) | — |
| REQ-60.3 | `trades_opened >= 50` post-gate | evidence | `.../evidence/real-data-h4-m15.md` (§8.5) | — |
| REQ-60.4 | post-gate average R not worse than the pre-gate baseline, else HALT | evidence | `.../evidence/real-data-h4-m15.md` (§8.5, §9.1) | — |
| REQ-30.1 | aligned CONFIRMED → candidate | unit | `tests/test_backtest_simulate.py` (regression) | — |
| REQ-30.2 | aligned INVALIDATED + retest → candidate | unit | `tests/test_backtest_simulate.py` (regression) | — |
| REQ-30.3 | `retest_index is None` → `never_confirmed` | unit | `tests/test_backtest_simulate.py` (regression) | — |
| REQ-30.4 | `fvg_fill` → `no_crt_range`, never `no_key_level` | unit | `tests/test_backtest_simulate.py` | — |
| REQ-30.5 | unaligned/insufficient → `unaligned` | unit | `tests/test_backtest_simulate.py` (regression) | — |
| REQ-30.6 | aligned PENDING + retest → candidate | unit | `tests/test_backtest_simulate.py` (regression) | — |
| REQ-30.7 | aligned, retest set, no key level → `no_key_level` | unit | `tests/test_backtest_simulate.py` | — |
| REQ-40.1 | `opened + sum(8 buckets) == considered` | unit | `tests/test_backtest_metrics.py` | — |
| REQ-40.2 | `signals_considered` post-results-filter, derived independently of `detections.csv` rows | e2e | `tests/test_cli_backtest_e2e.py` (assertion rewritten) | Run with `--backtest` (Modify) |
| REQ-40.3 | unaligned + outside kill zone → `unaligned` | unit | `tests/test_backtest_simulate.py` (regression) | — |
| REQ-40.4 | PENDING + retest resolves through 5 later cuts | unit | `tests/test_backtest_metrics.py` | — |
| REQ-40.5 | unaligned + no key level → `unaligned` | unit | `tests/test_backtest_simulate.py` | — |
| REQ-40.6 | gated signal still counted; bucket non-zero, others populated | e2e | `tests/test_cli_backtest_e2e.py` (§8.10 fixture) | Run with `--backtest` (Modify) |
| REQ-45.1 | `--session ... --backtest` overlay byte-identical | e2e | `tests/test_cli_backtest_e2e.py` (regression) | Run with `--backtest` (Modify) |
| REQ-45.2 | 13-column `trades.csv` header | e2e | `tests/test_cli_backtest_e2e.py` (regression) | Run with `--backtest` (Modify) |
| REQ-45.3 | differential byte-identity vs non-backtest run | e2e | `tests/test_cli_backtest_e2e.py` | Run with `--backtest` (Modify) |
| REQ-46.1 | 3 identical candidates → 1 survivor | unit | `tests/test_backtest_simulate.py` (§8.11) | — |
| REQ-46.2 | different `entry_type` → both survive | unit | `tests/test_backtest_simulate.py` (§8.11) | — |
| — | dedup runs on the post-confluence survivor set | unit | `tests/test_backtest_simulate.py` (§8.11) | — |
| — | `.importlinter` layers contract still passes | architectural | `tests/test_fitness_imports.py` | — |
| — | Per-signal exclusive bucket membership, mixed population | unit | `tests/test_backtest_simulate.py` | — |
| — | Gate CSV set == REQ-56 predicate over the population | e2e | `tests/test_cli_backtest_e2e.py` (§8.10) | Run with `--backtest` (Modify) |
| — | Every `excluded_no_key_level` signal absent from `detections.csv` | e2e | `tests/test_cli_backtest_e2e.py` (§8.10) | Run with `--backtest` (Modify) |
| — | `  no key level:` line present, between its two neighbours | e2e | `tests/test_cli_backtest_e2e.py` | Run with `--backtest` (Modify) |

All **59** spec V3 scenarios covered (41 new-domain + 18 delta). `property` and `evidence` appear alongside the standard levels: `property` is this project's established hypothesis harness, and `evidence` is REQ-60's recorded manual run (§8.5) — the only requirement whose subject is a measurement rather than a behaviour.

## 9.1 Acceptance criteria for S-000 (REQ-60.2/.3/.4)

**`W` — the gate's discriminating power.** Spec V3 fixed the DENOMINATOR (full `aligned`, non-`fvg_fill` population). The numerator must be fixed with it, and it is **not** `excluded_no_key_level`:

```
W = (pre_gate_model1_rows − post_gate_model1_rows) / (signals_considered − excluded_no_crt_range − excluded_unaligned)
```

- **Numerator** = the count of signals the REQ-56 CSV gate WITHHELD, measured as the `detections.csv` Model-1 row delta between the §8.5 pre-gate run and the post-gate run of the same command. This is what "the proportion of ALL aligned, non-`fvg_fill` signals withheld for lack of a Key Level" means, and it is why REQ-60.1 demands the before/after row counts.
- **Denominator** = the same population, from `metrics_summary.txt` alone. `excluded_no_crt_range` is exactly the `fvg_fill` count (verified: it is `_population_cuts`' first `elif`). On the pre-gate baseline: `142984 − 17143 − 20780 = 105061`, matching verify-plan-2's figure.

**Why the bucket count is the wrong numerator.** `excluded_no_key_level` only counts signals that survived the earlier `never_confirmed` cut — at most `105061 − 63901 = 41160` on this data, capping bucket/population at **0.392**. Using it would leave REQ-60.2's 0.75 upper bound unreachable, which is precisely the defect verify-plan-2 finding #7 raised; fixing the denominator alone would not have fixed it. Both quantities are recorded (REQ-60.1 requires both) and `bucket < withheld` strictly, for the reasons in §10.

**Acceptance criteria (S-000), all three binding:**

1. **REQ-60.2** — `0.10 <= W <= 0.75` on EURUSDm H4/M15. Lower bound comfortably above the 2.8% judged near-vacuous, and ~3× below the 30–34% the expiring rule measured; upper bound more than double 34%, so honest instrument variation cannot trip it while a gate discarding nearly everything is still caught. Set with margin deliberately — a bound tuned to the measurement would only re-assert what was already observed.
2. **REQ-60.3** — `trades_opened >= 50` post-gate. The north-star's CQ2 sample floor; a gate that satisfies `W` but leaves fewer than 50 trades has traded one failure for another.
3. **REQ-60.4** — post-gate **average R (frictionless)** must not be below the pre-gate baseline's **+0.244**. Average R, not total R: the gate is expected to REDUCE trade count, so total R almost necessarily falls and comparing it would guarantee a halt that says nothing. Per-trade expectancy is what "the gate improves the strategy" means. Comparison is strict, with no tolerance band — a false halt costs one human confirmation, a false pass costs the whole program. Win rate, total R and the 1.0-pip cost figure are recorded as context for that human decision, not as gate inputs.

Any of the three failing **halts S-000 and escalates to the user before S-001..S-006 are built** — the point of putting this in the walking skeleton. GBPUSDm and DXYm are corroboration, expected in the same band; one corroborating instrument outside it triggers judgement, not an automatic fail.

## 10. Fitness Functions

- **SEAM-01 consumer coupling (REQ-53.4)**: `alignment/htf_ltf.py`'s import set matches a frozen allow-list — AST-based, `tests/test_fitness_imports.py` (§8.4). Re-asserted after #2 and #3.
- **Layers contract (ADR-001/ADR-007)**: unchanged `.importlinter`; `uv run lint-imports` must pass. No new `root_package`.
- **Two-sided no-lookahead boundary (ADR-003/ADR-013)**: hypothesis property over `to_key_levels(detect_fvgs(...))`, both halves.
- **Validity-window lookahead safety**: credit under HTF truncation to `purge_index + 1` is identical to credit on the full series — both bounds, both indices on the **HTF** series (stated in the docstring; a cross-series comparison would be silently meaningless). §8.3.
- **`_Detections` field allow-list (REQ-58.1)**: the record's field names match a frozen set, so no future edit can quietly add a Key Level field and subject the pool to the results-filter chain.
- **Per-signal exclusive bucket membership (ADR-009, strengthened)**: each `signal_id` in exactly one of `trades_opened` or the 8 buckets — never zero, never two. Strictly stronger than the totals-only sum check.
- **Cut-order integrity (§8.11)**: a duplicate-group member with no `key_level` is counted in `excluded_no_key_level`, never `excluded_duplicate` — fails if the confluence cut is ever moved after dedup.
- **Minimal-pair discipline**: the confluent/non-confluent fixture pair varies **only** the HTF FVG's overlap with the purge extreme (§8.9), so the two cannot be distinguished by an unrelated field — the ghost-test pattern this project's judgment-day already found once.
- **Gate/bucket agreement**: two independently-correct assertions plus one true containment, all exercised on §8.10's mixed fixture so none is vacuous.
  1. *CSV side*: the set of Model-1 `signal_id`s in `detections.csv` equals `{s.signal_id for s in population if keep(s)}`, `keep` being REQ-56's own predicate over the in-memory population.
  2. *Bucket side*: REQ-40.1's eight-bucket sum plus per-signal exclusive membership.
  3. *Cross-artefact containment*: every `signal_id` counted in `excluded_no_key_level` is **absent** from `detections.csv`, and every traded `signal_id` is **present** (REQ-59.1).

  V1's `count(model1 rows) == signals_considered - excluded_no_key_level` stays dropped as arithmetically false. Two independent reasons: (a) a signal that is `aligned`, non-`fvg_fill` and non-confluent but has `retest_index is None` lands in `excluded_never_confirmed` yet is still withheld by the CSV gate, so withheld > `excluded_no_key_level` strictly — the same asymmetry §9.1 turns to account; (b) on a `--types` run excluding model1/alignment, `signals_considered` is 0 by the existing carve-out while the CSV may still carry rows. Containment (3) survives both because it is one-directional.

## 11. Migration / Rollout

No database, no feature flag, no deployment ordering. The one destructive step is the archive-time sync of REQ-30/40/45/46 into `openspec/specs/detector/spec.md` (`sdd-archive` §4, full-text MODIFIED blocks already drafted in the signed spec).

Rollback is staged: remove the `_filter_to_confluent` call → artefacts return to unfiltered content; remove the bucket branch, the `ReconciliationReport` field and the summary line → the invariant re-closes at seven; restore the spec from git. `core/key_level.py`, `to_key_levels`, the HTF detection call and `AlignedSignal.key_level` are pure computation with no artefact effect and may remain — which is what makes partial rollback safe.

## 12. Performance Considerations

One extra `detect_fvgs` pass over the **HTF** series per paired run — by construction 16–48× smaller than the LTF series (H4 vs M15), negligible against the existing LTF passes. Confluence credit is an eager map keyed by purge index: O(purges × levels × extremes), extremes ≤ 2, bounded by HTF series length and **independent of LTF signal count** — avoiding the O(signals × levels) shape this project has twice had to remove from hot paths. V3's both-sides evaluation at most doubles the innermost comparison on the 14.1% of purges that breach both sides. Expiry adds one integer comparison per (purge, level) pair — no new pass, since `fill_index` is already resolved by `detect_fvgs`' existing sweep. `_filter_to_confluent` is one linear pass plus a `set` of `signal_id`s. §8.5's 10-minute per-run budget is the real-data guard.

## 13. Architecture Impact

**Architecture impact**: `additive`

**Rationale**: Derived from §4 — `core` gains a new module inside an existing baseline layer; `primitives`, `alignment`, `backtest` and `viz.trades_table` are extended within their existing contracts; the single `modify` row (`cli` assembly) is intra-component (a stage inserted into a private filter chain), touching no boundary, dependency direction, or layer contract. `.importlinter` is unchanged and conformant. Re-derived, not copied: V3 changes two predicates (`_purge_wick_extremes`, the expiry conjunct) and the test surface, neither of which touches a component or an edge. The baseline gains entries; nothing in it becomes wrong.

## 14. Open Questions and Executor Notes

**Blocking questions**: None.

**Executor-local notes**:
- Exact OHLC values for §8.2 and §8.10 are apply's to finalise against the stated constraints; §8.10 constraint 3 (no extra FVG) must be verified by running `detect_fvgs` on the finished fixture, not by inspection.
- Whether `_purge_wick_extremes` returns a tuple or yields is a local choice; the credit pooling must not depend on extreme ORDER, only on `origin_index`.
- Placement of §8.11's third assertion within `test_backtest_simulate.py` is the executor's.

**Build preflights**:
- `pairs/H4/` and `pairs/M15/` must hold EURUSDm, GBPUSDm and DXYm before S-000.1 runs (verified present at design time; gitignored, so machine-local).
- S-000.1's EURUSDm `metrics_summary.txt` must match obs #419 exactly; a mismatch means the baseline no longer describes HEAD and S-000 halts (§8.5).
- 10-minute per-run wall-clock budget on each real-data run (§8.5).

## 15. Sensitive Areas

None affected — no `project/sensitive-areas` registry entry exists for this project, and this change reads MT5 CSV exports and writes regenerable artefacts only. No auth, payment, personal-data, secret, deploy or data-migration behaviour is altered. Matches the signed spec's own coverage.

**Size budget**: exceeded, as V1 and V2 were. V3 carries §8's eleven resolved test-mechanics decisions and §9's 63-row derivation over 59 scenarios; compressing either would return them to the "unspecified" state plan-verify iterations 1 and 2 flagged. Precedent accepted at V1 sign-off.
