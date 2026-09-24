# Spec: crt-detector-order-flow

**Version**: V1 | **Status**: signed | **Change**: `crt-detector-order-flow`
**Derived from**: `explore.md` Sections A-M (three design passes, 2026-09-08), with two determinism clarifications incorporated at sign-off.

## Domain: order-flow-detection

### REQ-OF-01: Bullish/Bearish Order Flow definition
The system MUST detect a bullish `OrderFlowEvent` when a confirmed SwingLow is rejected (some candle's wick crosses below it and that same candle's own close returns above it) and a later-or-same-index candle's close breaks above a confirmed SwingHigh selected per REQ-OF-02. Bearish is the exact direction mirror (reject above a SwingHigh, break below a SwingLow).
**Source: MENTORSHIP** (charter-3 `[00:01:23]`, the reject-then-break shape) **+ DESIGN DECISION** (mechanical operationalization — the mentorship names no mechanism for "reject" or "break").
- **REQ-OF-01.1** (happy, bullish): GIVEN a confirmed SwingLow, WHEN a candle's wick crosses below it and that candle's close returns above it, AND a later candle's close breaks above the REQ-OF-02-selected SwingHigh, THEN a bullish `OrderFlowEvent` is emitted at the break candle.
- **REQ-OF-01.2** (edge, no close-back): GIVEN a candle wicks below a SwingLow with no close-back above it, WHEN a high later breaks, THEN no event is emitted for that non-rejection.
- **REQ-OF-01.3** (edge, wick-only break): GIVEN a valid rejection is pending, WHEN a candle's wick crosses the break reference but its close does not, THEN no event is emitted — the candidate remains pending.

### REQ-OF-02: Reference selection — most recent confirmed unbroken, correct-side guardrail
The rejection reference (a SwingLow for bullish, a SwingHigh for bearish) and the break reference (opposite kind) are each the confirmed, "unbroken" (REQ-OF-03) `SwingPoint` of the required kind with the **highest `confirmation_index`** (most recently confirmed) — **not** the most extreme price — considering only swings confirmed strictly before the candle under evaluation (REQ-OF-07). The break reference MUST additionally sit on the correct side of the rejection reference (bullish: break reference price strictly greater than rejection reference price; bearish: strictly less). If no opposite-kind swing satisfies this, no break reference is available yet and the candidate remains pending.
**Source: DESIGN DECISION** (reversed twice across the design passes — see `explore.md` Section M.A for the full evidentiary reasoning: magnitude-based selection was rejected for a demonstrated indefinite-anchoring defect, SS5).
- **REQ-OF-02.1** (edge, ancient extreme does not anchor the detector — SS1/SS5): GIVEN an old, more extreme SwingHigh and a newer, less extreme SwingHigh both confirmed and unbroken, WHEN a break is evaluated, THEN the newer SwingHigh governs, regardless of which has the more extreme price.
- **REQ-OF-02.2** (edge, correct-side guardrail): GIVEN the most-recently-confirmed unbroken opposite-kind swing sits on the WRONG side of the rejection reference (e.g., for a bullish candidate, a "SwingHigh" priced below the rejected SwingLow), WHEN evaluated, THEN it is NOT eligible as a break reference — the candidate remains pending until an eligible one is confirmed.
- **REQ-OF-02.3** (edge, equal-price SwingPoints — clarified at sign-off): Two or more `SwingPoint`s of the same kind MAY share an identical price (e.g., a double top) — this is not excluded by any rule in this spec and creates NO ambiguity, because selection is keyed on `confirmation_index`, which is guaranteed distinct for every swing of a given kind (a given series index produces at most one SwingHigh and one SwingLow, per `primitives/swing.py`'s own detection loop). GIVEN two eligible SwingHighs share an identical price at different confirmation indices, WHEN a break reference is selected, THEN the one with the greater `confirmation_index` (the most recently confirmed) governs. Mirror for SwingLow.
- **REQ-OF-02.4** (edge, dynamic reference — BR2/BR3/C7): GIVEN no eligible opposite-kind swing exists at the moment of rejection, WHEN one is confirmed later (at or before the eventual break candle), THEN it becomes eligible as the break reference once knowable, without lookahead.

### REQ-OF-03: Unbroken semantics
A confirmed `SwingPoint` is "unbroken" as of candle `c` if and only if no candle with index in `(swing.index, c]` has closed beyond its price, using the identical strict-inequality, no-buffer predicate as the "break" test itself (REQ-OF-01) — not a separately specified rule.
**Source: DESIGN DECISION** (explicit reuse contract with the break predicate).
- **REQ-OF-03.1** (happy): GIVEN a candle's close exactly equals a SwingPoint's price, WHEN evaluated, THEN it is NOT broken (strict inequality only).
- **REQ-OF-03.2** (edge, wick does not break): GIVEN a candle's wick crosses a SwingPoint's price but its close does not, WHEN evaluated, THEN it remains unbroken.
- **REQ-OF-03.3** (edge, one unit beyond): GIVEN a candle's close is strictly beyond a SwingPoint's price by any margin, WHEN evaluated, THEN it is broken, permanently, for that SwingPoint.

### REQ-OF-04: Independent pending-candidate lifecycle
Pending candidates are tracked **independently per direction** — a bullish and a bearish candidate MAY coexist without interference. Within one direction, a new qualifying rejection replaces that direction's own previous pending candidate (regardless of whether it references the same or a different underlying SwingPoint). A pending candidate is invalidated (no event) if a later candle closes beyond its own rejection reference in the original (pre-rejection) direction. A `SwingPoint` already consumed by a past event, or superseded by a replacement, MAY participate in a new, independent rejection at a later, distinct `rejection_index`.
**Source: DESIGN DECISION** (reversed once — see `explore.md` Section M.B: a unified single-candidate model was rejected for demonstrably discarding a legitimate, fully-completed event, PC1).
- **REQ-OF-04.1** (edge, same-direction replacement — LC4/LC5): GIVEN a bullish candidate is pending, WHEN a new qualifying bullish rejection occurs (same or different SwingLow), THEN it replaces the previous bullish candidate; the bearish candidate, if any, is untouched.
- **REQ-OF-04.2** (edge, cross-direction coexistence — PC1/PC2/PC3): GIVEN a bullish candidate is pending, WHEN a qualifying bearish rejection occurs, THEN a bearish candidate begins pending ALONGSIDE the bullish one — neither replaces nor invalidates the other.
- **REQ-OF-04.3** (edge, structural invalidation — LC3): GIVEN a bullish candidate is pending, WHEN a later candle's close crosses back below its own rejection reference (the originally-rejected SwingLow), THEN the candidate is discarded with no event.
- **REQ-OF-04.4** (edge, consumption — LC1 unbounded validity): GIVEN a candidate's break condition is met, WHEN the event is emitted, THEN exactly one event is emitted and the candidate is consumed (returns to no-candidate for that direction); a candidate with no invalidation and no break remains pending indefinitely (no arbitrary time window).
- **REQ-OF-04.5** (edge, reference reuse): GIVEN a SwingPoint was the rejection reference of a now-consumed or superseded candidate, WHEN a later, distinct candle independently satisfies the full rejection predicate against that SAME SwingPoint, THEN a new, independent rejection event is recorded (a different `rejection_index`), not a reuse of the prior one.

### REQ-OF-05: No lookahead / incremental result
`detect_order_flow_events(series.up_to(n))` MUST match the full-series output for every `OrderFlowEvent` whose `confirmation_index` is `< n`.
**Source: REPO CONVENTION** (mirrors `tests/property/test_no_lookahead.py`'s existing per-detector property, e.g. `ICTOrderBlock`'s REQ-64).
- **REQ-OF-05.1** (property test): prefix-consistency over real and Hypothesis-generated series, including an explicit all-flat degenerate series, equal-highs, equal-lows, and outside-bar cases as NAMED cases, not left to random search alone.

### REQ-OF-06: Timeframe-agnostic
`detect_order_flow_events` accepts a generic `OHLCSeries` and never branches on `.timeframe`; the caller decides which series represents "HTF" for a given analysis.
**Source: REPO CONVENTION** (matches `primitives/swing.py`, `primitives/crt_range.py`, `composite/mss.py`).

### REQ-OF-07: Same-candle two-phase precedence
For any candle `c`, existing pending candidates (both directions) are resolved FIRST (invalidation, then break), using only swings confirmed strictly before `c`; only afterward is `c` evaluated for creating a new rejection (both directions, independently), for use starting at candle `c+1`.
**Source: DESIGN DECISION**, backed by two structural proofs (not assumptions):
- **REQ-OF-07.1** (proof-backed invariant): a break and an invalidation can never both be triggered by the same candle's close, given REQ-OF-02's correct-side guardrail (a single close value cannot simultaneously exceed a higher break reference and fall below a lower rejection reference).
- **REQ-OF-07.2** (proof-backed invariant): a `SwingPoint` can never be broken, or serve as a rejection target, on the very candle that confirms it — by `primitives/swing.py`'s own fractal definition, the confirming candle's own high/low is structurally on the wrong side of the swing's price.

### REQ-OF-08: Outside-bar dual rejection
A single candle MAY qualify as a new rejection for BOTH directions simultaneously (e.g., an outside bar). Under REQ-OF-04's independence, both are accepted — no tie-break rule applies or is needed.
**Source: DESIGN DECISION** (direct, forced consequence of REQ-OF-04 — not an independently invented rule).

### REQ-OF-09: Simultaneous opposite `OrderFlowEvent`s — PROVEN IMPOSSIBLE (corrected post-implementation, 2026-09-08)
**Correction, stated plainly**: the original sign-off draft of this requirement claimed simultaneous opposite-direction breaks were "structurally constructible" and asked for a constructive test. That claim was **wrong** — verified independently (re-derived by hand, not just taken from the implementation report) and by a 20,000-trial randomized search in the implementation that found zero occurrences. **No arbitration policy is needed because the case cannot occur.**
**Source: DESIGN DECISION → corrected to PROOF** (same class as REQ-OF-07.1/07.2 — a structural invariant, not a rule to arbitrate).
- **Proof**: suppose a bullish break and a bearish break both fired on the same candle `F`. Let `P1` = the bullish `break_reference` price (a SwingHigh) and `P2` = the bearish `break_reference` price (a SwingLow). A simultaneous break requires `close(F) > P1` AND `close(F) < P2`, hence `P1 < P2`. Both `P1` and `P2` must have been confirmed strictly before `F` (REQ-OF-07), so both were still required to be "unbroken" (REQ-OF-03) as of candle `F-1` — which requires `close(F-1) ≤ P1` (P1 not yet broken above) AND `close(F-1) ≥ P2` (P2 not yet broken below) simultaneously, hence `P2 ≤ P1`. `P1 < P2` and `P2 ≤ P1` cannot both hold. Contradiction — the case is impossible for any choice of swings, not merely unlikely.
- **REQ-OF-09.1** (invariant, tested not fabricated): the test suite MUST verify this as a property/invariant (e.g., a large randomized search finding zero simultaneous-direction events, as already done in the implementation) rather than including a constructed "both events fire" test case, since no valid input for that case exists.

### Note on REQ-OF-02.2 (correct-side guardrail) — clarified post-implementation
The guardrail is **currently redundant as a deciding factor**, not incorrect: any swing on the wrong side of the rejection reference is already excluded by REQ-OF-03's "unbroken" test through an independent path (the same close that would need to "cross" a wrong-side swing already exceeds the rejection reference itself, which — given the rejection's own close-back condition — means the wrong-side swing was already broken beforehand). Confirmed via mutation testing (removing the guard changed zero test outcomes) and a 200-example property check. **Kept in the spec and implementation regardless** — it documents the intended invariant explicitly and remains a safeguard if any of REQ-OF-02/03's other rules are revised later; removing it would save no behavior and would cost self-documentation.

## Out of scope (explicit, per triage)
Bias, Draw on Liquidity, `DirectionContext`, TSQ-direction, `KeyLevelSelector`, Breaker Block, Rejection Block, FVG ranking, any `current_order_flow`-style prevailing-state view (state/persistence semantics belong to a future, separate change). No outcome/statistics work (WR, MeanR, PF, backtest, ablation, bootstrap, OOS) gates any decision in this spec.

## Revision History

- 2026-09-08 (sign-off): V1 signed at the end of the third design pass (`explore.md` Sections A-M), REQ-OF-01 through REQ-OF-08 plus two determinism clarifications added at sign-off time (REQ-OF-02.3 equal-price wording; REQ-OF-09, **initially specified as allowing simultaneous opposite-direction `OrderFlowEvent` confirmation on the same candle**, with a request to add a constructive test for that case).
- 2026-09-08 (implementation review, before the first implementation commit): while implementing REQ-OF-09's requested constructive test, the combination was found to be **structurally impossible** under the final REQ-OF-03 (unbroken) and REQ-OF-07 (same-candle visibility) semantics — not merely difficult to construct. Re-derived and verified independently (by hand, against a hand-built numeric example, and via a persisted 2000-example Hypothesis invariant test, `test_opposite_direction_events_never_share_a_confirmation_index`) before committing. REQ-OF-09 was corrected in place to state the proof and require an invariant test instead of a constructive one — **the requirement did not originate this way; it was corrected after being shown wrong, and this note exists so that correction is never mistaken for how the spec was originally written.** REQ-OF-02.2 (correct-side guardrail) was separately found redundant-but-harmless by the same review and left in place, documented as such. No other requirement changed between sign-off and implementation.
