# Spec: crt-detector-draw-on-liquidity

**Version**: V1 | **Status**: signed | **Change**: `crt-detector-draw-on-liquidity`
**Derived from**: `triage.md` (formal split, S) + `explore.md` (design pass, READY FOR SPEC).
**Scope boundary**: this spec formalizes ONLY "what observable liquidity candidates exist?" — never "which candidate is the active DOL?". `DOLSelector` is explicitly out of scope (Section J).

## A. Signed architectural boundary

```text
LiquidityCandidateDetector
    ↓
List[LiquidityCandidate]          <- THIS SPEC (existence)

DOLSelector
    ↓
future selection / short-term scope / target semantics   <- DEFERRED, not designed
```

The detector models EXISTENCE. A future selector will model RELEVANCE/SELECTION. Not mixed here.

## Domain: liquidity-candidate-detection

### REQ-LIQ-01: Candidate emission per closed candle
Each closed candle visible to the detector contributes exactly one HIGH candidate (`price = candle.high`) and one LOW candidate (`price = candle.low`) — unconditionally, with no lookback bound, no recency filter, no ranking.
**Source: MENTORSHIP** (charter-3 `[00:11:29]`: "máximos o mínimos de velas previas" — highs/lows of previous candles are liquidity points; the plural "puntos"/"cuales" and both worked examples confirm multiple candidates can exist simultaneously) **+ DESIGN DECISION** (every visible closed candle contributes, not just "the previous one" — the linchpin choice: "corto plazo" (short-term) is left deliberately unoperationalized here; it becomes a property of a future selector's windowing, never a bound on existence. **Do not label "all historical candles are short-term" as MENTORSHIP** — that is not what this REQ asserts).
- **REQ-LIQ-01.1** (happy, LC2): GIVEN a series of `N` candles, WHEN `detect_liquidity_candidates` runs, THEN exactly `2N` candidates are returned.
- **REQ-LIQ-01.2** (edge, LC1): GIVEN `N=1`, THEN 2 candidates are returned (a single candle's own high/low are already valid observations — no "previous candle" relationship is required, unlike Bias's close-relation).
- **REQ-LIQ-01.3** (edge, LC9 — crucial): GIVEN an ancient candle hundreds of indices back, THEN it still contributes a candidate. **Historical candidate existence ≠ currently-relevant short-term DOL** — V1 makes no claim about relevance, only about existence.
- **REQ-LIQ-01.4** (edge, LC8): GIVEN a gap between candles, THEN no special rule applies — each candle's high/low is computed identically regardless of adjacency to its neighbor.

### REQ-LIQ-02: Candidate price exactness
`candidate.price` equals the source candle's `high` or `low` exactly — no rounding, quantization, tick-size snapping, or type conversion.
**Source: MENTORSHIP** (the price IS the candle's own high/low) **+ REPO CONVENTION** (reuses `Candle.high`/`Candle.low`'s existing `float` type verbatim — no `Decimal`, no tick size; this repo does not use either anywhere in `detector/core`).

### REQ-LIQ-03: Candidate identity — no price-based deduplication
Candidate identity is `(source_index, kind)`. Two candidates with the same `price` from different candles are NOT deduplicated — both are emitted as distinct observations.
**Source: DESIGN DECISION** — no source statement merges equal-price observations into one stronger "level" for DOL specifically (the one "equal lows" mention in the corpus, charter-6 `[00:07:59]`, concerns Key Level selection, not DOL identity — importing that reasoning here would be exactly the generic-ICT contamination this research was told to avoid).
- **REQ-LIQ-03.1** (edge, LC3): GIVEN two candles share the same `high` price, THEN two distinct `LiquidityCandidate(kind="high", ...)` observations are emitted, one per `source_index`.
- **REQ-LIQ-03.2** (edge, LC4): GIVEN two candles share the same `low` price, THEN the mirror of REQ-LIQ-03.1 holds for `kind="low"`.

### REQ-LIQ-04: Flat candle produces two distinct candidates
GIVEN a candle where `high == low`, THEN it still produces both a HIGH and a LOW candidate, identical in `price` but distinct in `kind`.
**Source: DESIGN DECISION** — a direct, forced consequence of REQ-LIQ-01 (both fields always emitted) and REQ-LIQ-03 (identity includes `kind`); not a separately invented rule.
- **REQ-LIQ-04.1** (edge, LC5): the two candidates are never collapsed into one, even under a hypothetical stricter dedup policy — `kind` alone already distinguishes them.

### REQ-LIQ-05: No lifecycle or selection semantics
`LiquidityCandidate` has exactly three fields: `kind`, `price`, `source_index`. No `active`, `inactive`, `consumed`, `reached`, `expired`, `selected`, `direction`, `rank`, `score`, `distance`, `confidence`, or `timeframe_priority` field exists.
**Source: DESIGN DECISION**, forced by `triage.md` Section 4/5's explicit deferral of `DOLSelector` and lifecycle/consumption semantics — the mentorship does not define those transitions sufficiently to formalize them here, and inheriting Order Flow's "unbroken" convention would be inventing a bridge the source doesn't build.
- **REQ-LIQ-05.1** (field-shape assertion, mirrors REQ-BIAS-05): `{f.name for f in dataclasses.fields(LiquidityCandidate)} == {"kind", "price", "source_index"}`.

### REQ-LIQ-06: No-lookahead / prefix consistency
`detect_liquidity_candidates(series.up_to(n))` MUST match the full-series output exactly for every candidate with `source_index < n`.
**Source: REPO CONVENTION** (mirrors REQ-OF-05, REQ-BIAS-06). Settling constant `k=0` — a candidate depends only on its own source candle, the strictest class in this family.
- **REQ-LIQ-06.1** (property, LC6/LC10): GIVEN a series is extended with arbitrary future candles, THEN every previously-emitted candidate observation remains structurally identical — appending never mutates, removes, or re-derives an existing candidate; it only ever adds new ones for the new candles.

### REQ-LIQ-07: Timeframe-agnostic
`detect_liquidity_candidates` accepts a generic `OHLCSeries` and never branches on `.timeframe`; the caller decides which series represents HTF/ITF/LTF for a given analysis.
**Source: REPO CONVENTION** (mirrors REQ-OF-06).

### REQ-LIQ-08: Deterministic output ordering
Candidates are returned ordered by `source_index` ascending; within the same index, HIGH precedes LOW. This ordering carries NO ranking or DOL-relevance meaning — it exists solely to prevent implementer divergence in serialization/API output.
**Source: DESIGN DECISION** (arbitrary but must be pinned; explicitly not a selection signal).

### REQ-LIQ-09: No duplicate candidate for cross-subsystem semantic overlap
If a candle's high/low is also used by another subsystem as a CRT High/Low (or any other structural label), the detector does NOT emit a second, differently-typed candidate (e.g. `CRT_HIGH`) for the same observation. Exactly one generic `LiquidityCandidate` is emitted per (candle, side); cross-referencing with another detector's output (e.g. `primitives/crt_range.py`) is done externally by joining on `(source_index, price)`.
**Source: DESIGN DECISION** — a dedicated CRT-aware type would require importing `primitives.crt_range`, breaking the primitives-import-only-`core`-layer contract every other module at this layer shares, for zero informational gain.
- **REQ-LIQ-09.1** (LC7): GIVEN a candidate's `(source_index, price)` matches a `CRTRange`'s high or low elsewhere in the pipeline, THEN `detect_liquidity_candidates`'s own output is unaffected — no second candidate, no tag, no import of `crt_range`.

## B. Final `LiquidityCandidate` semantics (summary)

An immutable historical observation: this candle, at this index, showed this price as its high (or low). Nothing more. Not a target, not a ranking, not a claim of relevance.

## C. Type/API proposal

```python
@dataclass(frozen=True)
class LiquidityCandidate:
    kind: Literal["high", "low"]
    price: float
    source_index: int


def detect_liquidity_candidates(series: OHLCSeries) -> list[LiquidityCandidate]: ...
```

## D. Layer decision

`detector/primitives/liquidity.py`. Imports only `core.candle` — same layer contract as `primitives/bias.py`, `primitives/swing.py`, `primitives/fvg.py`, `primitives/ict_order_block.py` (all `primitives → core` only, per `.importlinter`'s layered-pipeline contract). No new dependency, no `.importlinter` edit needed.

## E. Formal REQs

REQ-LIQ-01 through REQ-LIQ-09, above — each with Source tags and Given/When/Then.

## F. Candidate identity/deduplication contract

`(source_index, kind)` is sole identity (REQ-LIQ-03). No price-based deduplication, no pooling/grouping. A future selector MAY choose to pool nearby observations when actually selecting — that is its call, not this detector's.

## G. CRT overlap contract

No duplicate types for cross-subsystem semantic overlap (REQ-LIQ-09). Generic observation + external tagging via join, never internal duplication.

## H. No-lookahead/cutoff contract

REQ-LIQ-06/06.1 — exact equality at `k=0`, the strictest class in this repo's no-lookahead property family. No "still forming candle" concept exists at this layer — `OHLCSeries` represents known/closed data throughout this repo; the caller excludes an actively-forming bar via `series.up_to(n)`, identical convention to every other detector here.

## I. Source/design ledger

| Rule | Tag |
|---|---|
| Highs/lows of previous candles can be liquidity points; multiple can exist simultaneously | MENTORSHIP |
| Every visible closed candle contributes candidates (not just "the previous one") | DESIGN DECISION |
| Candidate identity = `(source_index, kind)`, no deduplication | DESIGN DECISION |
| Flat candle still produces two distinct candidates | DESIGN DECISION (forced consequence) |
| No lifecycle/selection fields | DESIGN DECISION (forced by triage's DOLSelector deferral) |
| No duplicate type for CRT overlap | DESIGN DECISION |
| Deterministic HIGH-then-LOW ordering | DESIGN DECISION (arbitrary, pinned, non-ranking) |
| Price type reused verbatim (`float`, no Decimal/tick-size) | REPO CONVENTION |
| Immutable frozen dataclass | REPO CONVENTION |
| No-lookahead / timeframe-agnostic | REPO CONVENTION |

Explicitly NOT labeled MENTORSHIP: "all historical candles are short-term" — this spec does not assert that; it asserts existence only, deferring "short-term" to selection.

## J. Deferred `DOLSelector` semantics (explicit list — not designed here)

- Short-term / recency windowing scope (no bound exists in the source).
- Ranking/ordering policy among simultaneous candidates ("nearest-first" stays EXAMPLE-ONLY, charter-3 `[00:10:32]`/`[00:14:47]`, never promoted to a rule).
- "Active target" / "currently relevant DOL" determination.
- "Reached" semantics (wick vs. close criterion).
- Consumption / post-reach behavior.
- Candidate replacement after a reach event.
- Any pooling/grouping of nearby candidates (D2/D3 in `explore.md`, rejected for V1).
- `DirectionContext` integration (combining with `OrderFlowEvent`/`BiasEvidence`).

`DOLSelector consumes LiquidityCandidate observations and determines relevant/active draw(s).` Everything past that sentence is UNDER-SPECIFIED and intentionally undesigned.

## K. Recommendation

```text
READY FOR IMPLEMENTATION
```

No spec ambiguity remains for candidate existence. `DOLSelector` stays `DEFERRED`. Not implemented in this pass — halted for human sign-off before any code.

## Out of scope (explicit, per triage)

`DOLSelector` and everything in Section J; `DirectionContext`; Draw-on-Liquidity "reached"/consumption semantics; any outcome/statistics work (WR, MeanR, PF, prevalence tuning, backtest, ablation) — this spec is not evaluated by predictive performance, and candidate volume is never reduced because it "looks too high" (REQ-LIQ-01.3 exists precisely to keep that pressure out).

## Revision History

- 2026-09-08 (draft V1): derived from `triage.md` (S) and `explore.md` (design pass, READY FOR SPEC). Pending human sign-off before TDD implementation.
- 2026-09-08 (sign-off): V1 signed as-is, no changes requested. Proceeding to TDD implementation.
