# Explore: crt-detector-order-flow

**Triage**: M | **Goal**: transform the mentorship's single Order Flow definition into a deterministic spec, with an explicit ledger of where the source ends and our design begins. No implementation in this pass.

---

## A. Source boundary — what we literally know from Mado

The ENTIRE source material, across all 7 charters (confirmed by exhaustive grep — nothing else exists), is **charter-3 `[00:01:23]`**, inside "🧭 Higher Time Frame (HTF)":

> "Order Flow (Flujo de Órdenes): Identifica la dirección prevalente de la entrega del precio y la estructura del mercado."
> "Bullish Order Flow: Ocurre cuando el mercado rechaza por debajo de un bajo (low) y rompe por encima de un alto (high)."
> "Bearish Order Flow: Ocurre cuando el mercado rechaza por encima de un alto (high) y rompe por debajo de un bajo (low)."

Charter-4 `[00:00:51]` mentions "flujo de órdenes verdadero" tangentially with zero added mechanics. No other charter mentions it. The definition is used narratively (not re-specified) at charter-3 `[00:10:32]` and `[00:14:47]`.

**Literally absent from every charter**: which low/high qualifies; what "rechaza" (reject) means mechanically; whether "rompe" (break) is by close or wick; whether there's a time limit between rejection and break; whether Order Flow is a point-in-time event or a persistent state; any invalidation rule. All six are silently required by any implementation and are NOT in the source — they are this document's job to decide and label, never to attribute to Mado.

## B. Decision table

| # | Decision | Options considered | Chosen | Basis |
|---|---|---|---|---|
| 1 | Relevant low/high | A: confirmed SwingPoint (`primitives/swing.py`) · B: raw local extrema (undefined without confirmation) · C: CRT High/Low (BSL/SSL) · D: protected swing (Model-1 SL concept) | **A** | See below |
| 2 | Rejection mechanics | wick-crosses+close-returns · any excursion · multi-candle | **wick-crosses + close-returns, single candle** | See below |
| 3 | Break mechanics | wick break · close break · close break + buffer | **close break, no buffer** | See below |
| 4 | Sequencing / lookahead model | reference pair frozen before rejection · opposite reference may form after rejection | **may form after rejection** (bounded by its own confirmation index) | See below |
| 5 | Temporal window | unbounded · bounded N candles | **unbounded in candle-count; self-limiting via supersession** | See below |

### Decision 1 — relevant low/high

| Option | Source support | Determinism | Lookahead | Reuse | Counterexample behavior |
|---|---|---|---|---|---|
| A. Confirmed SwingPoint | None explicit — mentorship never says "swing" | Full — pure 3-candle fractal (`candles[i-1,i,i+1]`, strict `&gt;`/`&lt;`) | 1-candle confirmation lag (structural, not a leak — a swing at `i` is only knowable once `i+1` closes) | **Exact, zero new code** (`primitives/swing.py::detect_swings`, unmodified) | C5/C6 (multiple candidates): resolved by an ADDITIONAL rule (most-recent unbroken swing of that kind), not by this choice alone — flagged as a second, layered decision, not folded silently into "swing = solved" |
| B. Raw local extrema | Textually closer to charter-3's unqualified "low"/"high" | Only if a confirmation window is defined — and once defined, it is mathematically identical to Option A's 3-candle fractal, or degenerates into noise (every candle a "candidate") without one | Same as A once made precise, or worse (no lag = high false-positive rate, effectively meaningless as "reject/break" reference) | Would require new code duplicating Option A | C10 (flat candles): an underspecified "local extremum" test is exactly the shape of the existing, registered `test_alignment_detection_has_no_lookahead` bug class — reinventing this logic re-risks that class of defect where Option A's tested primitive does not |
| C. CRT High/Low (BSL/SSL) | Extensively used elsewhere (charter-1) but never equated to Order Flow's "low/high" (charter-3) | Deterministic, already implemented | Inherits CRT range's own known edge-case risk (the registered flat-candle tie-break issue, `sdd/crt-detector-key-level-confluence/v1-oos-pre-registration.md` Section E item 3) | Reuses `primitives/crt_range.py` | C7 (new high forms between rejection/break): CRT ranges are scoped to a SINGLE parent candle's own OHLC extent (charter-1's own CRT fundamentals), a fundamentally different granularity than a sequence of swing points across many candles — semantic mismatch, not a minor variant |
| D. Protected swing | charter-3 `[00:09:11]` — but for Model-1's STOP-LOSS placement (LTF execution risk management), not HTF direction | N/A (borrowed from wrong context) | N/A | Would misapply an LTF risk concept to an HTF structural concept | Rejected on conceptual-fit grounds before reaching a counterexample |

**Decision: Option A.** Best on determinism (exact, tested), minimal invented semantics (only "candidate stream = existing primitive," nothing new detected), architectural reuse (zero new detection code), and it avoids importing an unrelated concept's baggage (C's range-scoping mismatch, D's wrong-context borrowing). Requires ONE additional, explicitly separate rule (a swing is "the relevant low/high" only if it is the MOST RECENT confirmed swing of its kind that has not itself been broken) — labeled its own REQ, not folded into this one.

**Source label: DESIGN DECISION + REPO REUSE.**

### Decision 2 — rejection mechanics

Counterexamples (C1-C4 from the required matrix) discriminate directly:

- **C1** (wick below low, close above low, later close above high): under "wick-crosses+close-returns" → rejection VALID at the close-back candle; later close above high → Bullish Order Flow confirmed.
- **C2** (wick below low, close REMAINS below low, later breaks high): under "wick-crosses+close-returns" → rejection NEVER becomes valid (no close-back) → no Order Flow event, even though a high later breaks. Under "any excursion beyond reference" → rejection is considered valid from the mere wick dip, regardless of the close — a MATERIALLY more permissive reading that would flag C2 positive.
- **C3** (reject valid, high crossed only by wick): tests Decision 3, not this one — held constant here.

"Any excursion" is rejected: it fires on literally any wick poke with zero requirement that the market actually reversed, which fails to represent "rechaza" (reject) as ordinary language or as the recurring methodological pattern elsewhere in the source material (charter-6's Patience Rule, discussed for CRT↔Key-Level validation, not Order Flow directly: "a purge that doesn't close back inside doesn't confirm anything — could just be a liquidity run"). This is cited as **rationale by analogy**, not as direct mentorship evidence for Order Flow — the two contexts are not declared equivalent by any charter (per `sdd/crt-detector-key-level-confluence/order-flow-triage`'s own Task 6 finding), so this choice is NOT labeled MENTORSHIP.

"Multi-candle rejection" is deferred — it is not smaller/simpler than the single-candle definition (the instruction's own stated preference), and no counterexample in the required matrix demonstrates single-candle is inadequate for v1.

**Decision: single candle, wick crosses the reference AND that same candle's close returns past the reference (back on the origin side).**

**Source label: DESIGN DECISION** (rationale by analogy to a documented principle in a different, non-identical context — never cited as if Mado said this about Order Flow).

### Decision 3 — break mechanics

`composite/mss.py` (read directly, lines 118-131) uses close-only breaks (`resolves=lambda key, candle: key &lt;= candle.close`) with a `decisive_close_ratio=0.25` buffer (`core/config.py::MSSConfig`) — **neither is inherited automatically**, per explicit instruction.

- **C3** (reject valid, high crossed only by wick): under a wick-break rule → Order Flow WOULD confirm on the mere wick poke. Under a close-break rule → does NOT confirm; the sequence stays "pending" until (if ever) a close clears the high.
- **C4** (reject valid, high broken by close): confirms under both rules — non-discriminating.

Close-break is chosen for internal consistency with Decision 2: rejection required a close-back to count as genuine (a mere wick poke was explicitly rejected as too permissive there); using a mere wick poke to count as the OPPOSITE side's confirming "break" would apply an inconsistent standard to the two halves of the same definition ("rechaza... y rompe") without any documented reason to treat them asymmetrically. No buffer is added — no independent justification exists for Order Flow specifically (mss.py's `decisive_close_ratio` was invented for MSS, not sourced from any charter).

**Decision: close break, no buffer.**

**Source label: DESIGN DECISION** (symmetry/parsimony argument, NOT inherited from `mss.py`, whose specific ratio is explicitly rejected here).

### Decision 4 — sequencing / lookahead model (SUPERSEDED by the second design pass, see Section L below)

The critical question: must the high that eventually breaks already exist/be confirmed BEFORE the rejection happens?

- **Model (a) — reference pair frozen before rejection**: both the rejected low and the eventual break-high must already be confirmed swings at rejection time. Safest-looking, but excludes **C7** (a new high forms between rejection and break) entirely — a common, plausible real pattern (reject a low, rally, make a fresh local high in that very rally, later break it) that charter-3's text gives no reason to exclude.
- **Model (b) — opposite reference may form after rejection**: the break-high just needs to be a swing whose OWN confirmation index is `&lt;=` the break candle's index (trivially guaranteed — nothing is referenced before it exists in the detector's own swing list) — this remains fully no-lookahead-safe without requiring the high to predate the rejection. **C7 is naturally supported.**

Given charter-3's phrasing ("rechaza... y rompe") narrates a sequence of two events without ever claiming the second level was pre-identified, Model (a) adds a restriction the text doesn't ask for. Model (b) is chosen — it is no-lookahead-safe purely through each swing's own confirmation index, independent of which model is picked; safety does not favor (a) over (b), only plausibility and minimal-restriction do.

**Decision: Model (b)** — the break reference may be confirmed at any point up to and including the break candle's own index; only the FINAL break event's confirmation index must be `&gt;=` the rejection's own confirmation index (narrative ordering: rejection, then break — not the reverse).

**Source label: DESIGN DECISION.**

### Decision 5 — temporal window (SUPERSEDED by the second design pass, see Section L below)

The mentorship specifies no maximum (per `order-flow-triage`'s own Task 3 finding). Per the stated preference, no arbitrary N is introduced unless a counterexample demonstrates real ambiguity.

- **C8** (very long delay between rejection and break): an unbounded-by-candle-count rule alone risks combining a long-stale rejection with an unrelated later break. The fix is not a time window but a **structural validity rule**: at most one PENDING rejection is tracked per direction (bullish-candidate = pending low rejection awaiting a high break; bearish-candidate = pending high rejection awaiting a low break) at any time. A NEW rejection of the same kind (another low rejected, for the bullish candidate) REPLACES the previous pending one rather than stacking multiple simultaneously-live candidates. This naturally retires stale rejections once the market has since produced a fresher one of the same kind, without inventing a magic candle count.
- **C9** (bullish and bearish candidate sequences overlap): resolved for free by tracking the two directions' pending candidates independently — a live bullish-candidate and a live bearish-candidate coexist without conflict; whichever's break condition fires first produces that direction's `OrderFlowEvent`, and the other persists until its own break or its own supersession.

**Decision: unbounded in raw candle-count; self-limiting via same-direction supersession, not a fixed window.**

**Source label: DESIGN DECISION.**

## C. Counterexample matrix (all 12, resolved against the chosen v1 semantics)

| # | Scenario | Resolution under chosen semantics |
|---|---|---|
| C1 | wick below low, close above low, later close above high | Rejection confirmed at the close-back candle → Bullish `OrderFlowEvent` confirmed at the later close-above-high candle. |
| C2 | wick below low, close remains below low, later breaks high | No rejection ever confirmed (no close-back) → no `OrderFlowEvent`, regardless of the later break. |
| C3 | reject valid, high crossed only by wick | No break confirmed (close-only rule) → candidate stays pending. |
| C4 | reject valid, high broken by close | `OrderFlowEvent` confirmed at that close. |
| C5 | multiple lows available | Only the most-recent, not-yet-broken confirmed SwingLow is "the" rejected reference (Decision 1's companion rule) — older lows are not independently tracked as separate candidates. |
| C6 | multiple highs available | Symmetric to C5 for the break side — the break condition is evaluated against whichever confirmed SwingHigh is current at each candle, per Decision 4's model (b). |
| C7 | new high forms between rejection and break | Supported — Model (b) allows the break reference to be confirmed after the rejection (Decision 4). |
| C8 | very long delay between rejection and break | Allowed in raw candle-count terms, but only if no NEWER low-rejection has superseded the pending bullish candidate in the meantime (Decision 5). |
| C9 | bullish and bearish candidate sequences overlap | Tracked independently per direction — no conflict (Decision 5). |
| C10 | flat/equal candles | `detect_swings`'s strict `&gt;`/`&lt;` comparisons never register a swing on exactly-equal neighbors — no candidate reference exists in a fully flat region, rather than an ambiguous tie. Still flagged as a REQUIRED regression test (Section J), mirroring the project's own registered `test_alignment_detection_has_no_lookahead` flat-candle lesson. |
| C11 | future candles appended after cutoff | Must not change any event already confirmed at or before the cutoff — this is the incremental/no-lookahead invariant itself (Section H), not a semantic decision. |
| C12 | same candles reordered / invalid input | Out of scope for semantic design — an input-validation concern for the eventual implementation, not resolved here. |

## D. Recommended V1 semantics (complete definition)

> An `OrderFlowEvent` of direction D is confirmed at candle `c` when: (1) a confirmed `SwingPoint` of the kind opposite to D (a Low for bullish, a High for bearish) was rejected — some earlier candle's wick crossed that swing's price and that SAME candle's close returned to the origin side; (2) candle `c`'s close breaks a confirmed `SwingPoint` of the kind matching D (a High for bullish, a Low for bearish), where that swing's own confirmation index is `&lt;= c`'s index; (3) `c`'s index is `&gt;=` the rejection candle's index; (4) the rejected swing has not itself been superseded by a more recent rejection of the same kind since it was rejected.

## E. Mentorship-vs-design ledger

| Rule | Mentorship | Our design | Reason |
|---|---|---|---|
| Bullish = reject below a low, then break above a high (and mirror for bearish) | **MENTORSHIP** (charter-3 `[00:01:23]`, verbatim) | — | Direct quote |
| "Low"/"high" = a confirmed 3-candle fractal `SwingPoint` | — | **DESIGN DECISION + REPO REUSE** | Exact match to unqualified text, zero new code, avoids importing CRT-range or SL-protection semantics from unrelated contexts |
| Only the most-recent, unbroken swing of a kind is "the" candidate | — | **DESIGN DECISION** | Resolves C5/C6 without inventing a ranking/selection algorithm the mentorship never describes |
| Rejection = wick crosses + same-candle close returns | — | **DESIGN DECISION** | By analogy to charter-6's Patience Rule (a DIFFERENT context — CRT↔Key-Level, not Order Flow) — never claimed as Mado's own words for Order Flow |
| Break = close only, no buffer | — | **DESIGN DECISION** | Symmetry with the rejection rule; explicitly NOT `mss.py`'s `decisive_close_ratio` |
| Break-reference may be confirmed after the rejection | — | **DESIGN DECISION** | Minimal restriction beyond the source text; remains no-lookahead-safe via each swing's own confirmation index |
| Pending candidate replaced by a newer same-kind rejection, no fixed time window | — | **DESIGN DECISION** | Avoids an arbitrary N while still resolving C8's staleness concern structurally |
| Timeframe-agnostic `OHLCSeries` input | — | **REPO CONVENTION** | `swing.py`/`crt_range.py`/`mss.py` all take a generic series with no internal timeframe branching |
| No-lookahead via confirmation-index ordering, prefix-consistency property test | — | **REPO CONVENTION** | Matches `tests/property/test_no_lookahead.py`'s existing pattern and `series.up_to(n)` convention |

## F. Proposed requirements (DRAFT, unsigned — REQ-OF-02/03/04 SUPERSEDED by Section L's second design pass; REQ-OF-01/05/06 unaffected)

### REQ-OF-01: Bullish/Bearish Order Flow definition
The system MUST detect a bullish `OrderFlowEvent` when a confirmed SwingLow is rejected (a candle's wick crosses below it and that candle's own close returns above it) and a later-or-same-index candle's close breaks above a confirmed SwingHigh whose own confirmation index is at or before that break candle. Bearish is the direction mirror.
**Source: MENTORSHIP** (the reject+break shape) **+ DESIGN DECISION** (mechanical operationalization).
- **REQ-OF-01.1** (happy, bullish — C1): wick below a confirmed SwingLow, close back above it, later close above a confirmed SwingHigh → bullish event confirmed at the break candle.
- **REQ-OF-01.2** (edge, no close-back — C2): wick below a SwingLow with no close-back, WHEN a high later breaks, THEN no event is emitted for that rejection.
- **REQ-OF-01.3** (edge, wick-only break — C3): rejection valid, high crossed only by wick (no close beyond it), WHEN evaluated, THEN no event — the candidate remains pending.

### REQ-OF-02: Relevant low/high = confirmed SwingPoint, most recent unbroken
A "low" or "high" for REQ-OF-01 purposes is a `primitives.swing.SwingPoint` (unmodified reuse), restricted to the most recent one of its kind not yet broken by a prior confirmed opposite event.
**Source: DESIGN DECISION + REPO REUSE.**
- **REQ-OF-02.1** (edge, multiple candidates — C5/C6): GIVEN two or more confirmed SwingLows exist unbroken, WHEN a rejection is evaluated, THEN only the most recent qualifies as the rejection reference.

### REQ-OF-03: Break reference may post-date the rejection
The SwingPoint used to confirm a break MAY be confirmed at any index up to and including the break candle's own index, including one confirmed strictly after the rejection candle.
**Source: DESIGN DECISION.**
- **REQ-OF-03.1** (edge — C7): GIVEN a new SwingHigh forms and confirms after a qualifying rejection, WHEN that new high is later broken by close, THEN the bullish event confirms against it.

### REQ-OF-04: Pending-candidate supersession
At most one pending rejection candidate per direction exists at a time; a new rejection of the same kind (another SwingLow rejected, for the bullish candidate) replaces the previous pending one.
**Source: DESIGN DECISION.**
- **REQ-OF-04.1** (edge — C8): GIVEN a bullish candidate has been pending an unusually long time, WHEN a fresher SwingLow is rejected before any break occurred, THEN the older pending candidate is discarded, not carried forward.
- **REQ-OF-04.2** (edge — C9): bullish- and bearish-direction pending candidates are tracked independently and do not interfere with each other.

### REQ-OF-05: No lookahead / incremental result
`detect_order_flow_events(series.up_to(n))` MUST match the full-series output for every `OrderFlowEvent` whose confirmation index is `&lt; n`.
**Source: REPO CONVENTION** (mirrors `tests/property/test_no_lookahead.py`'s existing per-detector property, e.g. REQ-64 for `ICTOrderBlock`).
- **REQ-OF-05.1** (property test): prefix-consistency, using real and Hypothesis-generated series, INCLUDING an all-flat degenerate series (C10) as an explicit named case, not left to random search alone (the project's own registered lesson from `obs #303`/the `test_alignment_detection_has_no_lookahead` bug class).

### REQ-OF-06: Timeframe-agnostic
`detect_order_flow_events` accepts a generic `OHLCSeries`; it never branches on `.timeframe`. The caller decides which series represents "HTF" for a given analysis.
**Source: REPO CONVENTION.**

## G. Proposed types/API (design only, NOT implemented)

```python
@dataclass(frozen=True)
class OrderFlowEvent:
    direction: Literal["bullish", "bearish"]
    rejection_reference: SwingPoint   # opposite kind to direction (Low for bullish, High for bearish)
    break_reference: SwingPoint       # same kind as direction (High for bullish, Low for bearish)
    rejection_index: int              # candle whose close returned past rejection_reference
    confirmation_index: int           # candle whose close broke break_reference — the event's "confirmed at" index


def detect_order_flow_events(
    series: OHLCSeries, config: OrderFlowConfig = OrderFlowConfig()
) -> list[OrderFlowEvent]:
    """Reuses primitives.swing.detect_swings unmodified. Timeframe-agnostic —
    caller decides which series is HTF for their analysis."""


# DERIVED VIEW, not a formal claim of matching the mentorship's "prevailing
# direction" (Section J — persistence/invalidation are UNDER-SPECIFIED by
# the source, not resolved here):
def current_order_flow(
    events: list[OrderFlowEvent], cutoff_index: int
) -> Literal["bullish", "bearish"] | None:
    """Direction of the most recent event with confirmation_index &lt;= cutoff_index."""
```

`OrderFlowConfig` is likely an empty marker dataclass at v1 (no buffer, no window parameter was justified — Decisions 3 and 5) — mirrors the existing pattern of `SwingConfig` (also currently a placeholder).

## H. No-lookahead model

Every reference used by REQ-OF-01 is gated by an existing, already-knowable confirmation index:
- A `SwingPoint` at index `i` is knowable only once candle `i+1` closes (inherent to `swing.py`'s 3-candle fractal test — 1-candle structural lag, not a leak).
- The rejection candle's close-back is knowable only at its own index.
- The break candle's close is knowable only at its own index, and it may only reference a `SwingPoint` whose OWN confirmation index is `&lt;=` its own (Decision 4) — never a swing the detector could not yet know about.
- `OrderFlowEvent.confirmation_index` is therefore always the true "first knowable" index for that event — the same invariant `ICTOrderBlock`'s REQ-64 and every other detector in this codebase already commits to.
The required property test (REQ-OF-05.1) is the exact enforcement mechanism, following `test_no_lookahead.py`'s established `series.up_to(n)` prefix-consistency pattern.

## I. MSS/swing reuse decision (exact)

- **`primitives/swing.py::detect_swings`**: **EXACT REUSE**, unmodified, as the sole source of SwingPoint candidates.
- **`composite/mss.py::detect_mss_events`**: **NOT reused as the implementation.** Confirmed by direct code reading (lines 32, 118-131): it hard-codes a `decisive_close_ratio` buffer and a close-only break rule, AND requires a prior opposite swing to already exist before it will even consider a break (`_pending_breaks`'s `if opposite_swing is None: continue`) — a materially different (and stricter) precondition than Order Flow's own pending/supersession model (Decision 5). Its GENERAL PATTERNS (a pending-candidate bookkeeping pass over an ascending SwingPoint stream, resolving breaks in a second forward pass) are a reasonable architectural precedent for whoever eventually implements this — its specific numeric threshold and prior-swing precondition are explicitly NOT inherited.

## J. Open questions intentionally deferred

- Whether a rejection reference, once consumed by a confirmed `OrderFlowEvent`, may be reused by a later event of the same direction, or must be retired — not addressed here.
- Multi-candle rejection patterns (deferred at Decision 2).
- Bias, Draw on Liquidity, `DirectionContext` (the composite), TSQ-direction, `KeyLevelSelector` — explicitly out of scope; only the non-functional `current_order_flow` derived-view stub above hints at a future integration point.
- Whether `current_order_flow`'s "most recent confirmed event" view is an adequate proxy for the mentorship's "prevailing direction" language — UNDER-SPECIFIED by the source (Section A), not resolved by fiat here.

## K. Final recommendation (SUPERSEDED — see Section L.K)

~~NEEDS ANOTHER DESIGN PASS~~ — resolved by the second design pass below. Final verdict: **READY FOR SPEC SIGN-OFF** (Section L.K).

---

## L. Second design pass (2026-09-08) — resolving break-reference selection, "unbroken", and pending-candidate lifecycle

Decisions 1-3 (Section B above) remain provisionally accepted, unchanged, still labeled DESIGN DECISION. This pass resolves ONLY what Decisions 4 and 5 left open, using 11 new counterexamples (BR1-5, LC1-6) constructed specifically to discriminate between candidate models — no outcomes, no implementation.

### L.A — Break-reference models (A1/A2/A3) against BR1-BR5

| Model | BR1 (H1 pre-exists, breaks) | BR2 (only L1 pre-exists, H2 emerges after) | BR3 (H1 higher pre-exists, H2 lower emerges after, H2 breaks) | BR4 (H1 pre-exists, H2 higher emerges after, H1 breaks) | BR5 (multiple pre-existing highs) |
|---|---|---|---|---|---|
| A1 (strict pre-existing pair) | event | **no event** — too strict, excludes legitimate emergent structure | undefined | undefined | ambiguous (no selection rule given) |
| A2 literal ("most recent known") | event | event | **event on breaking H2 — WRONG**: H1, still unbroken and more significant, was never cleared | event on breaking H2 once confirmed (correct by coincidence here) | ambiguous |
| A3 (frozen at rejection) | event | same as A1 (nothing pre-exists to freeze) | same as A1 — freezes before H2 exists, doesn't help | same as A1 | resolves the pre-existing-selection ambiguity A1 lacked, but only for that case |

**BR3 is decisive: none of A1/A2/A3 as literally proposed gives the right answer.** Plain recency (A2) lets a smaller, more recent high satisfy the break condition while a larger, still-unbroken, older high stands — contradicting the intuitive reading of "breaking a high" as a genuine reversal signal.

**Resolution**: selection is by **magnitude, not recency** — the governing break reference at any point is the most extreme still-unbroken swing of the needed kind (highest unbroken SwingHigh for bullish, lowest unbroken SwingLow for bearish), evaluated dynamically (still in the A2 family — dynamic, not frozen — but with a corrected selection criterion). Re-scoring:
- BR3 corrected: H1 remains the highest-unbroken even after H2 (lower) confirms → breaking only H2 does NOT produce an event. Correct.
- BR4 corrected: once H2 (higher) confirms, H2 becomes the highest-unbroken → breaking only H1 does NOT produce an event; H2 must break. Now explicit, not accidental.
- BR2 corrected: with no pre-existing high, H2 is trivially the most extreme (only) candidate → breaking it produces an event. Emergent structure still supported.
- BR5 corrected: the most extreme pre-existing price governs, deterministic regardless of order; ties (near-unreachable) broken by highest `confirmation_index`, mirroring `nearest_ob_selection_v1`'s own existing tie-break convention.

This also answers Section 4's instruction directly: **recency is not the primary criterion — magnitude is.** Recency survives only as an exact-price tie-break.

### L.B — "unbroken" semantics (U1/U2/U3)

| Counterexample | U1 (wick invalidates) | U2 (close invalidates) | U3 (reuses the break predicate) |
|---|---|---|---|
| wick through, close back | **invalidates** — a single noise wick permanently destroys the reference | does not invalidate | does not invalidate |
| close exactly at the level | ambiguous | ambiguous unless strict inequality is fixed | resolved: strict inequality (consistent with `swing.py`'s own `&gt;`/`&lt;`) |
| close one tick beyond | invalidates | invalidates | invalidates |
| multiple wick violations before an eventual close break | invalidates on the first wick | stable until the real close | stable until the real close |

U1 is inconsistent with Decisions 2 and 3 (both already require a CLOSE, not a wick, to count as decisive) — using wick-based invalidation for "unbroken" would apply a different standard to the same class of event elsewhere in this same design.

**Chosen: U3** — "unbroken" reuses EXACTLY the break predicate (Decision 3: close crosses reference, strict inequality, no buffer). Numerically identical to U2, but stated as an explicit reuse contract (one rule, not two independently-specified ones that could silently drift), per instruction.

### L.C — Lifecycle models (L1/L2/L3) and the single-vs-independent-candidate question

Before scoring, LC6 forces a real reconsideration: **should bullish and bearish pending candidates coexist independently** (the first pass's design), or should they be mutually exclusive? The mentorship's own word is "dirección **prevalente**" — a singular notion, not two simultaneous narratives. A unified single-pending-candidate model (replaced by any qualifying rejection, either direction) is chosen as more faithful to that word, and it also reduces state (one candidate slot, not two) — Section L.G quantifies this.

Of the candidate structural invalidation triggers:
- **(i) the rejection_reference itself closes through again, in the original direction**: well-motivated — a rejection later contradicted by a real close-through retroactively falsifies it. Directly resolves **LC3**.
- **(ii) "opposite reference breaks first" (a plain break, not a full qualifying rejection, of some other level)**: **rejected** — no independent logical justification found; a bare close-through without the wick+close-back pattern doesn't carry the same narrative weight, and adopting it would just be a weaker restatement of (iii).
- **(iii) a qualifying rejection of the opposite direction**: subsumed entirely by the unified single-candidate model — ANY new qualifying rejection (same or opposite direction) replaces the pending candidate. Resolves **LC6** by taking "prevalente" seriously, not by implementation convenience.

**Chosen: L2, refined = L1 (replacement) + trigger (i), under the unified single-candidate model.** L3 (fixed window) is rejected outright — no counterexample demonstrates unbounded-with-structural-invalidation is ambiguous, and L3 would require an unjustified arbitrary N.

### L.D — Three finalist combinations

- **Design X (recommended)**: A2-refined (dynamic, magnitude-based selection) + U3 + L2-refined (unified single candidate, replacement + trigger (i) only)
- **Design Y (baseline = first pass's original design)**: A2 literal (recency-based) + U3 + L1 pure (independent per-direction tracking, no structural invalidation)
- **Design Z (control)**: A1 (strict pre-existing pair) + U2 + L3 (fixed window) — included to show why over-strictness + an arbitrary parameter is worse

### L.E — State machine (Design X)

```
IDLE
  │ qualifying rejection (either direction)
  ▼
PENDING(direction, rejection_reference, rejection_index)
  ├─ new qualifying rejection (either direction) → REPLACES, stays PENDING
  ├─ rejection_reference closed through again, original direction → IDLE (no event)
  ├─ close crosses the current most-extreme unbroken opposite-kind swing → EMIT OrderFlowEvent → IDLE
  └─ (otherwise) stays PENDING
```
Two states, one candidate slot — simpler than the first pass's per-direction sketch.

### L.F — Counterexample scorecard (BR1-5 + LC1-6)

| # | Design X | Design Y | Design Z |
|---|---|---|---|
| BR1 | event | event | event |
| BR2 | event | event | **no event (fails — too strict)** |
| BR3 | no event (H1 still governs) | **event, spurious (fails)** | ambiguous |
| BR4 | event only on breaking H2 | correct by coincidence | ambiguous |
| BR5 | deterministic by magnitude | ambiguous | ambiguous |
| LC1 (500-candle delay) | event (no structural invalidation fired) | event | would need an arbitrary N |
| LC2 (bearish rejection before bullish break) | bullish candidate replaced, no bullish event | **both coexist (fails "prevalente")** | n/a |
| LC3 (re-close through rejected low) | invalidated, no event | **spurious event (fails)** | n/a |
| LC4 (two rejections, same low) | most recent survives | same | n/a |
| LC5 (two rejections, different lows) | most recent survives | same | n/a |
| LC6 (opposing pending candidates) | mutually exclusive (faithful to "prevalente") | **allows both (fails)** | n/a |

**Design X resolves all 11 cleanly. Design Y fails 4 (BR3, LC2, LC3, LC6). Design Z fails BR2 and needs an unjustified parameter.**

### L.G — Complexity cost (Section 13)

| | Design X | Design Y | Design Z |
|---|---|---|---|
| Mutable pending fields | 1 slot (direction, rejection_reference, rejection_index) — break_reference is computed on demand, never stored | 2 slots (one per direction) | 1 slot + a window-expiry timer |
| Arbitrary parameters | 0 | 0 | 1 (fixed N) |
| Invented structural rules | 3 (magnitude-based selection; unified single-candidate replacement; rejection_reference re-break invalidation) | 2 (recency-based selection; per-direction independent replacement) | 2 (strict pre-existing pair; fixed window) |
| Counterexamples resolved | 11 / 11 | 7 / 11 | ~2 / 11 (most left ambiguous or failing) |

Design X costs one more invented rule than Y, but each is independently forced by a specific, named counterexample (BR3/BR4 → magnitude; LC6 → unified candidate; LC3 → re-break invalidation) — not added speculatively.

### L.H — Exact semantics (pseudocode, sufficient for two implementers to agree)

```python
def detect_order_flow_events(series):
    swings = detect_swings(series)          # exact reuse, unmodified
    events = []
    pending = None                          # (direction, rejection_reference, rejection_index) | None

    for c, candle in enumerate(series.candles):
        new_rejection = _check_rejection(swings, candle, c)     # either direction
        if new_rejection is not None:
            pending = new_rejection                              # always replaces, any direction

        if pending and _closed_through_original_direction(candle, pending):
            pending = None                                       # trigger (i)

        if pending:
            break_ref = _extreme_unbroken_swing(swings, opposite_kind_of(pending.direction), up_to=c)
            if break_ref and _closes_beyond(candle, break_ref):
                events.append(OrderFlowEvent(
                    direction=pending.direction,
                    rejection_reference=pending.rejection_reference,
                    break_reference=break_ref,
                    rejection_index=pending.rejection_index,
                    confirmation_index=c,
                ))
                pending = None                                   # consumed, at most one event
    return events
```

Helpers:
- `_extreme_unbroken_swing(swings, kind, up_to=c)`: among confirmed (`confirmation_index &lt;= c`), "unbroken" (L.B, U3) `SwingPoint`s of `kind`, return the most extreme price (max for high, min for low); tie-break by highest `confirmation_index`.
- `_check_rejection(swings, candle, c)`: for either direction, wick crosses the current extreme-unbroken opposite-kind swing AND this same candle's close returns to the origin side.
- `_closed_through_original_direction`: this candle's close crosses `pending.rejection_reference.price` in the direction the rejection had denied.
- `_closes_beyond`: strict close beyond the swing's price, no buffer.

**Residual open case, not resolved with false confidence**: a single candle qualifying as BOTH a bullish and a bearish rejection simultaneously (an "outside bar" straddling both a low and a high) has no tie-break rule yet — deferred (Section L.J).

### L.I — Requirements changes (REQ-OF-02/03/04, superseding Section F's originals)

```
REQ-OF-02 (rewritten): The rejection reference (a Low for bullish, a High for
bearish) and the break reference (opposite kind) are each selected by
MAGNITUDE, not recency: the confirmed, "unbroken" (REQ-OF-03) SwingPoint of
that kind with the most extreme price. Recency (highest confirmation_index)
breaks ties on an exactly-equal price only. The break reference is evaluated
DYNAMICALLY at every candle while a candidate is pending — never frozen at
rejection time.
Source: DESIGN DECISION.

REQ-OF-03 (new): A confirmed SwingPoint is "unbroken" as of candle c iff no
candle with index in (swing.index, c] has closed beyond its price (strict
inequality). Identical predicate to the break test — explicit reuse, not a
parallel rule.
Source: DESIGN DECISION.

REQ-OF-04 (rewritten): At most ONE pending candidate exists at any time,
regardless of direction. Any new qualifying rejection (same or opposite
direction) replaces the pending candidate. A pending candidate is
invalidated (no event) if a later candle closes beyond its own
rejection_reference in the original (pre-rejection) direction.
Source: DESIGN DECISION.
```

### L.J — Deferred semantics

- A single candle qualifying as both a bullish and bearish rejection simultaneously (outside bar) — no tie-break rule yet.
- Whether a consumed rejection_reference may be reused by a later event (deferred since the first pass).
- Bias, DOL, `DirectionContext`, TSQ-direction, `KeyLevelSelector` — still out of scope.
- Whether `current_order_flow` (Section G's derived view) is an adequate proxy for "prevalente" — still UNDER-SPECIFIED by the source, not resolved by this pass either.

### L.K — Final recommendation (SUPERSEDED — see Section M.K)

~~READY FOR SPEC SIGN-OFF~~ — this pass's two core choices (magnitude-based reference selection, unified single-pending-candidate) are themselves REVERSED by the third design pass below, on evidence, not preference.

---

## M. Third and final design pass (2026-09-08) — reversing two of Section L's own choices

Decisions 1-3, U3, and "no fixed N-candle timeout" (Sections B-D) remain accepted, unchanged. This pass stress-tested Section L's own two central choices against 5 new counterexamples (SS1-SS5) and 3 arbitration counterexamples (PC1-PC3), and found both insufficiently justified once "higher/lower = more significant" is disallowed as a bare intuition (per explicit instruction). **Both are reversed here, openly, with the specific evidence that forced it — not glossed over.**

### M.A — Structural scope: S1 (global extreme) reversed to S3 (most recent unbroken)

Section L's justification for magnitude-based selection ("H1 is more significant") could not survive being asked for a structural reason instead of an intuition. Re-examined without it:

| | S1 (global extreme, Section L's choice) | S3 (most recent unbroken, dynamic) |
|---|---|---|
| SS1/BR3 (old H1 higher, new H2 lower, H2 breaks) | no event (H1 still governs) | **event** — nothing in the source text requires "the ALL-TIME highest," only "a high" |
| SS5 (global extreme stands unbroken for thousands of candles) | **detector anchors indefinitely, goes silent** — a real, demonstrable functional defect, not a style preference | never occurs — the reference always tracks the freshest local structure |
| Reuse | no precedent in this codebase | **mirrors `composite/mss.py`'s own `_pending_breaks` pattern exactly** (`last_high`/`last_low`, "most recent opposite swing") — direct architectural precedent |
| Invented hierarchy | requires a running-maximum computation | none — a simple "latest by confirmation_index" pointer |
| Tie-breaking | needed (equal price is real and possible — a double top) | **not needed** — selection is keyed on `confirmation_index`, which IS guaranteed distinct per kind (a given index yields at most one SwingHigh and one SwingLow); equal price does not create ambiguity, it's simply irrelevant to selection now |

S1's ONLY real selling point was the "significance" intuition; once removed, SS5 is an objective defect S1 has and S3 doesn't, and S3 has direct reuse precedent S1 lacks. **Reversed: rejection_reference and break_reference are each the confirmed, unbroken SwingPoint of the required kind with the highest `confirmation_index`** (most recent), evaluated dynamically, using only swings confirmed strictly before the candle under evaluation.

### M.B — Pending-candidate arbitration: P1 (unified) reversed to P2 (per-direction independent)

**PC1** (pending bullish; a minor bearish rejection occurs; the bullish break later confirms) is decisive: under P1, the bearish rejection replaces the bullish candidate BEFORE its break arrives — **a fully-completed, legitimate bullish event is silently destroyed** by an unrelated later occurrence, purely to keep one global slot. This is precisely the mistake Section E's own framing warns against: conflating "what events occurred" (should be complete) with "what's the singular current direction" (a different, deferred question). Section B.2's key question, answered honestly: **yes, P1 was discarding valid historical events to make a future `current_order_flow()` convenient.**

**Reversed: pending candidates are tracked independently per direction (P2)** — bullish and bearish coexist without interference. Within one direction, a new qualifying rejection still replaces that direction's own previous pending candidate (unchanged); the rejection_reference-re-broken invalidation (Section L.C, trigger (i)) still applies per direction independently.

**Direct consequence — the outside-bar deferral closes itself**: Section L.J's "no tie-break yet" gap was an artifact of P1 (only one slot to contend for). Under P2 there is no conflict — a single candle qualifying as both a bullish and a bearish rejection simply seeds both direction's slots independently. No tie-break rule needed; none invented.

### M.C — Same-candle precedence (new problem, forced by the above reversals interacting)

Two-phase processing per candle, adopted:
- **Phase 1 (resolution)**: using only swings confirmed strictly before candle `c`, resolve each direction's existing pending candidate (invalidation, then break) independently.
- **Phase 2 (new rejection)**: using the same before-`c` swing set, check whether `c` itself creates a new rejection, independently per direction, for the NEXT candidate.

Two structural proofs justify this ordering rather than assuming it:
1. **A break and an invalidation can never both fire from the same candle's close** — given the new REQ-OF-02 guard that `break_reference` must sit on the correct side of `rejection_reference` (for bullish, strictly higher price), a single close value cannot simultaneously exceed the (higher) break target and fall below the (lower) rejection level.
2. **A SwingPoint can never be broken (or rejected) by the very candle that confirms it** — by `swing.py`'s own fractal definition, the confirming candle `i+1` necessarily has `high &lt; swing.price` for a SwingHigh at `i` (so `close &lt;= high &lt; swing.price`, breaking is impossible), and symmetrically `low &gt; swing.price` for a SwingLow (rejecting is impossible). The Phase 1/Phase 2 split therefore never discards a real case — it describes a boundary that was already structurally unreachable.

### M.D — Consumption/reuse (closed, no new invention)

A rejection event is keyed by `(SwingPoint, rejection_index)`, not by the SwingPoint alone — so a swing already consumed in a past event may participate in a genuinely new, later, independent rejection at a different `rejection_index`. Falls directly out of the existing definition; nothing added.

### M.E — Revised REQ-OF-02/04, and two new REQs

```
REQ-OF-02 (rewritten again): rejection_reference and break_reference are
each the confirmed, unbroken (REQ-OF-03) SwingPoint of the required kind
with the HIGHEST confirmation_index (most recent, not most extreme in
price), considering only swings confirmed strictly before the candle under
evaluation. break_reference must additionally sit on the correct side of
rejection_reference (bullish: strictly higher price) — if no opposite-kind
swing satisfies this, no break_reference is available yet.
Source: DESIGN DECISION.

REQ-OF-04 (rewritten again): pending candidates are tracked INDEPENDENTLY
per direction — bullish and bearish coexist without interference. Within
one direction, a new qualifying rejection replaces that direction's own
previous pending candidate. A candidate is invalidated (no event) if a
later candle closes beyond its own rejection_reference in the original
direction. A consumed rejection_reference may participate in a new,
independent rejection event at a later, distinct rejection_index.
Source: DESIGN DECISION.

REQ-OF-07 (new, same-candle precedence): for any candle c, existing
pending candidates (both directions) are resolved first, using only swings
confirmed strictly before c; only afterward is c evaluated for a new
rejection (both directions, independently), for the next candidate.
Source: DESIGN DECISION.

REQ-OF-08 (new, outside bar): a single candle may qualify as a new
rejection for both directions simultaneously; under REQ-OF-04 both are
accepted independently — no tie-break required.
Source: DESIGN DECISION (direct consequence of REQ-OF-04).
```

### M.F — Determinism audit (all required cases)

| Case | Resolved by | Status |
|---|---|---|
| ancient extreme | S3 (recency, not magnitude) | resolved |
| opposing pending candidates | P2 (independent) | explicitly permitted, not ambiguous |
| outside bar | consequence of P2 | both accepted, no tie-break |
| same-candle break + rejection (cross-direction) | P2 removes the conflict | resolved |
| same-candle invalidation + break | **proven impossible** (REQ-OF-02 guard) | resolved by proof |
| a candle's own newly-confirmed swing as its own target | **proven impossible** (swing fractal definition) | resolved by proof |
| future-appended candles | no-lookahead invariant, unchanged | resolved |
| equal-price swings (CORRECTED at sign-off — these CAN occur, e.g. a double top; the earlier wording wrongly said they couldn't) | selection by `confirmation_index` (distinct by construction) makes an equal price irrelevant, not impossible — REQ-OF-02.3 | resolved, no ambiguity, but not "eliminated" |

### M.G — Complete pseudocode

See the version delivered alongside this pass (two-phase, per-direction independent, magnitude replaced by recency, correct-side guard on `break_reference`) — functionally identical to Section L.H's structure with the reversals above applied throughout.

### M.K — Final recommendation

```
READY FOR SPEC SIGN-OFF
```

No remaining valid input was identified where two reasonable implementers would diverge — every ambiguity closed with either an explicit rule or a structural proof, not a preference. Two of this document's own earlier choices (Section L's magnitude-based scope and unified candidate) were reversed here on evidence (SS5's demonstrated anchoring defect; PC1's demonstrated event loss) rather than defended past the point the evidence supported them. **Not implemented in this pass, per instruction, regardless of readiness.**
