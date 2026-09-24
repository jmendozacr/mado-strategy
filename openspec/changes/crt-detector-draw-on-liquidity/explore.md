# Design Pass: LiquidityCandidateDetector V1

**Change**: `crt-detector-draw-on-liquidity` | **Status**: design pass, NOT signed — feeds a future `sdd-spec`
**Scope**: candidate existence only. Answers "what liquidity candidates exist?", never "which one is THE DOL?". `DOLSelector` stays out of scope per `triage.md` Section 4.

## A. Formal DOL triage

See `triage.md` — split registered (candidates vs. selector), CRT High/Low relationship frozen ("CAN function as", not "==").

## B. Candidate universe analysis

| Model | Definition | Verdict |
|---|---|---|
| **C1 — Previous candle only** | candidates = `{previous.high, previous.low}` | Minimal semantics, but **undershoots** the source: both worked examples show more than one draw, including a level beyond the immediate previous candle. |
| **C2 — Fixed recent lookback (N)** | candidates from `c-N .. c-1` | `N` does not exist in the source. Rejected — would be invented for convenience, exactly what was asked not to do. |
| **C3 — All prior candles** | candidates from the whole history | Unbounded growth, apparently contradicting "corto plazo". Rejected **as a claim about "the DOL universe"** — but see Design A below: the contradiction dissolves once existence is separated from selection. |
| **C4 — Structurally compressed (swing-based)** | candidates = confirmed `SwingPoint`s only | Imports an abstraction ("swing" = fractal-confirmed, multi-candle-visible extreme) the DOL definition never mentions, and it **under-counts** relative to "máximos o mínimos de velas previas" (every candle's high/low, not only fractal-confirmed ones). Rejected for V1 — not because it's a bad concept, but because it silently substitutes a different, narrower population than the one the literal definition names. |

**Resolution — the "corto plazo" trap has a way out.** None of C1-C4 is clean, because all four try to answer "which highs/lows are *in scope*" — but that IS the selection question, not the existence question (Section D above). Reframe: the candidate detector's job is a raw, honest fact stream — every closed candle's high and low, unfiltered, undeduplicated, with NO claim that this is already "the corto-plazo DOL universe". "Corto plazo" becomes a property of a future SELECTOR's windowing policy, not of existence. Under this reframing, **C3's mechanics** (every candle contributes) are correct, but **its framing changes**: it is not "the complete bounded DOL universe" (which would contradict "corto plazo"), it is "the raw observable population a selector will later window." This is Design A below.

## C. Identity/deduplication analysis

| Model | Rule | Verdict |
|---|---|---|
| **D1 — Observation identity** | `(kind, source_index)` — two highs at the same price from different candles are two distinct candidates | **Adopted.** Zero invented semantics — each observation is exactly the historical fact it is. |
| **D2 — Price-level identity** | same `kind` + same `price` collapses to one | Rejected — no source statement merges equal-price observations into one stronger "level" for DOL. This is the classic ICT "equal highs = liquidity pool" idea, but it is never stated for DOL in charters 1-7 (the one "equal lows" mention, charter-6 `[00:07:59]`, is about **Key Level** selection, not DOL identity) — importing it would be exactly the generic-ICT contamination this pass was told to avoid. |
| **D3 — Grouped liquidity pool** | cluster nearby (not just equal) prices into one pool | Rejected for the same reason as D2, plus it needs a tolerance parameter the source doesn't give — same shape of problem as C2's `N`. |

A candle's own high and low are trivially distinct (different `kind`), regardless of dedup policy — not a special case, just a consequence of `kind` being part of identity.

## D. Real-time/hindsight audit

This is the most consequential finding of the pass — it refines (not contradicts, but sharpens) the Track-B characterization that "both examples show 2 simultaneous draws in near-then-far sequence." Read at full precision, the two examples are NOT the same shape:

- **Example 1**, charter-3 `[00:10:32]`: "Cierre dentro del rango previo... se identifican dos draws on liquidity: **el alto de la vela previa** y, a continuación, **el alto de la vela siguiente a esa**." Parsed literally: "la vela siguiente a esa [vela previa]" is the candle chronologically after the previous one — i.e., the candle currently being analyzed itself (already forming/partially known). Both referenced candles are knowable at the narrated decision point. **Classification: REAL-TIME RULE-COMPATIBLE.**
- **Example 2**, charter-3 `[00:14:47]`: "precio operando **dentro de la vela actual**... se identifican dos draws on liquidity: **el alto de la vela actual**, seguido del **alto de la vela siguiente**." Here the reference point is explicitly the currently-forming candle ("operando dentro de"), and "la vela siguiente" is a candle strictly AFTER it — which, if we are still "dentro de la vela actual", has not happened yet. The only way Mado can point at its high is because the video is walking through an already-fully-formed historical chart with the benefit of hindsight. **Classification: HINDSIGHT EXAMPLE**, not an operational real-time rule.

Per the explicit instruction: the "vela siguiente" (Example 2) portion is **not copied literally into V1**. V1 has no mechanism for "the high of a candle that hasn't formed yet" — that would require lookahead by construction.

**Design consequence — this doesn't complicate V1, it simplifies it.** A detector that emits one HIGH+LOW candidate for every candle actually present in whatever `series.up_to(n)` view it receives is, by construction, incapable of anticipating a future candle's high — no special-casing is needed. As more candles close, the candidate set grows monotonically; Example 1's pattern falls out naturally (both of its candles are, at some point, "already present"); Example 2's apparent foresight is never reproduced, and is not supposed to be — it is retrospective narration over a historical chart, not a claim that a live detector could have known that price before it existed.

## E. CRT overlap analysis

If a candle is also the parent candle of a CRT range, should `LiquidityCandidateDetector` emit a separate `CRT_HIGH`/`CRT_LOW` candidate type in addition to the generic one?

**No — generic observation + semantic tags supplied elsewhere.** A dedicated CRT-aware type would require importing `primitives.crt_range`, breaking the single-dependency-on-`core.candle` pattern every other `primitives/` module in this repo shares (Bias, Order Flow's SwingPoint reuse aside, are all core-only at the primitive layer), for zero informational gain: a consumer that wants to know "is this candidate also a CRT High" can already join on `(source_index, price)` against `primitives/crt_range.py`'s own output. Duplicating the same observable price point under two types because a *different* subsystem assigns it meaning would be inventing a second identity for one fact.

## F. Counterexample matrix

Given the final model (Design A, Section G below): `detect_liquidity_candidates(series)` emits one HIGH and one LOW candidate for every candle in `series.candles`.

| # | Case | Result |
|---|---|---|
| LC1 | `N=1` candle | 2 candidates (HIGH@0, LOW@0) — a single candle's own high/low are still valid historical observations; there is no "previous candle" requirement here, unlike Bias's close-relation (which needs a pair). |
| LC2 | previous candle's high/low | Just two of the (many) candidates already in the stream — not special-cased. |
| LC3 | multiple prior candles, distinct highs/lows | One HIGH+LOW pair per candle, all preserved distinctly (`2N` candidates for `N` candles). |
| LC4 | same high price, two different candles | Two distinct candidates (D1 — observation identity, not deduplicated). |
| LC5 | same low price, two different candles | Mirror of LC4. |
| LC6 | flat candle (`H == L`) | Same price, but different `kind` — two distinct candidates, no ambiguity even under a stricter dedup rule. |
| LC7 | a future candle creates a new higher high | The earlier, already-emitted candidates are **unchanged** — new candles only ever ADD candidates, never mutate or remove prior ones (no-lookahead exact-equality property, REQ-LC-05). |
| LC8 | "still forming" / cutoff semantics | Not a detector concern — `OHLCSeries` represents known/closed data throughout this repo; the caller excludes a still-forming bar via `series.up_to(n)`, same convention as every other detector here. |
| LC9 | candidate coincides exactly with a CRT High | Emitted as a plain generic HIGH observation — no CRT-specific type (Section E). |
| LC10 | two sequential candidate highs, per charter-3's examples | Reproduced naturally by monotonic accumulation once both candles have actually closed (Example 1's shape) — Example 2's apparent foresight is explicitly NOT reproduced (Section D). |
| LC11 | an ancient high hundreds of candles back | **Included.** This is the direct, deliberate test of the "short term" deferral — V1 does not bound recency; that is the selector's job. |
| LC12 | a gap between candles | No special rule — each candle's high/low is computed identically regardless of adjacency to its neighbor. |

## G. Candidate lifecycle model

**Immutable historical observation, full stop.** No `active`/`inactive`, no `consumed`/`unconsumed` — consumption semantics are entirely under-specified (`triage.md` Section 5) and inheriting Order Flow's "unbroken" convention would be inventing a bridge the source doesn't build. `LiquidityCandidate` carries no lifecycle state at all, cleanly separating this (now design-complete) existence layer from the (deferred) selector/lifecycle layer.

## H. Proposed type/API (design only, not implemented)

```python
@dataclass(frozen=True)
class LiquidityCandidate:
    kind: Literal["high", "low"]
    price: float
    source_index: int


def detect_liquidity_candidates(series: OHLCSeries) -> list[LiquidityCandidate]: ...
```

No `direction` field: `kind` already IS the derivable directional fact (high↔BSL-type, low↔SSL-type per charter-1's own equivalence for CRT High/Low) — a separate `direction` field would duplicate `kind`, the same redundancy class as Bias's dropped wick booleans. No BSL/SSL label: the source makes that equivalence explicit only for CRT High/Low, never generalized to generic highs/lows — generalizing it silently would be unlicensed. No `rank`/`score`/`active`/`consumed`/`selected`/`distance`/`timeframe_priority` — all belong to the deferred selector. Location: `detector/primitives/` (imports only `core.candle`, same layer contract as Bias/Order Flow's primitives) — a full layer confirmation, like Bias's, would still go through triage classification once this design is accepted; not re-litigated here since the dependency shape is already unambiguous.

## I. Candidate REQ drafts (not signed — feed a future `sdd-spec`)

**REQ-LC-01 — Candidate emission**: one HIGH and one LOW candidate is emitted for every candle in the series, unconditionally.
Source: MENTORSHIP ("máximos o mínimos de velas previas") + DESIGN DECISION (every candle, not just "the previous one" — chosen because "corto plazo" is left unbounded rather than solved with an invented N; see Section B).

**REQ-LC-02 — Observation identity**: `(kind, source_index)` is the sole identity; no deduplication by price.
Source: DESIGN DECISION (Section C, D1).

**REQ-LC-03 — No semantic tagging**: candidates carry no BSL/SSL label and no CRT-relationship flag.
Source: DESIGN DECISION (Section E, H).

**REQ-LC-04 — No lifecycle**: candidates are immutable; no active/consumed/selected field exists.
Source: DESIGN DECISION, forced by `triage.md` Section 5's deferral.

**REQ-LC-05 — No-lookahead / timeframe-agnostic**: `detect_liquidity_candidates(series.up_to(n))` matches the full-series output for every candidate with `source_index < n`, exactly (k=0, same strictness class as Bias). Accepts a generic `OHLCSeries`, never branches on `.timeframe`.
Source: REPO CONVENTION.

## J. Source/design ledger

| Rule | Tag |
|---|---|
| Liquidity candidates come from candle highs/lows | MENTORSHIP |
| Every candle contributes, not just "the previous one" | DESIGN DECISION (Section B — the linchpin choice; makes "corto plazo" a selection-time property, not an existence-time bound) |
| No fixed lookback `N` | DESIGN DECISION (rejected C2 — no source support) |
| No swing-based compression | DESIGN DECISION (rejected C4 — imports an unlicensed abstraction, under-counts) |
| Observation identity = (kind, source_index), no price dedup | DESIGN DECISION (Section C, D1) |
| No CRT-specific candidate type | DESIGN DECISION (Section E) |
| No `direction`/BSL-SSL field | DESIGN DECISION (redundant with `kind` / unlicensed generalization) |
| Candidates are immutable, no lifecycle | DESIGN DECISION (forced by `triage.md` Section 5) |
| Example 2's "next candle" is hindsight, not reproduced | DESIGN DECISION, forced by the real-time/hindsight audit (Section D) |
| No-lookahead / timeframe-agnostic | REPO CONVENTION |

## K. Selector-deferred contract — what `DOLSelector` will need, that V1 will NOT decide

- Recency/"corto plazo" windowing policy (no bound exists yet).
- Ranking/ordering policy among simultaneous candidates (nearest-first is EXAMPLE-ONLY, not adopted).
- Deduplication/pooling policy, if ever adopted (D2/D3 stay rejected for V1; a selector MAY choose to pool nearby candidates when actually selecting — that is its call, not the candidate layer's).
- "Reached" criterion (wick vs. close).
- Consumption/replacement semantics after a candidate is reached.
- Any CRT-overlap-aware prioritization (joining against `primitives/crt_range.py`).
- Any Order-Flow-aligned or Bias-aligned filtering (both explicitly UNDER-SPECIFIED per `triage.md`).

## L. Final recommendation

```text
READY FOR SPEC
```

Applies to `LiquidityCandidateDetector` V1 only. Design A resolves the "corto plazo" tension by not attempting to bound it — existence stays unbounded and honest; every other sub-question (identity, CRT overlap, lifecycle, real-time safety) has a clean, minimal-invention answer with no forced arbitrary parameter. `DOLSelector` remains `DEFERRED`, per `triage.md`.

## Architecture status after this pass

```text
DIRECTION INPUTS
OrderFlowEvent       ✅ frozen + implemented
BiasEvidence         ✅ frozen + implemented
LiquidityCandidate   🟢 design-complete, READY FOR SPEC (not implemented)
DOLSelector          ⏸ deferred
DirectionContext     ⏳ waits
```
