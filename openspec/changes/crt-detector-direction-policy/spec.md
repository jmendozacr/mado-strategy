# Formal Spec — `DirectionPolicy` V1 (Line B / Policy Layer)

**Change**: `crt-detector-direction-policy` · **Version**: V1 · **Status**: SIGNED
**Nature**: pre-registration of four research hypotheses *before* any outcome is observed. No outcome, backtest, prevalence, or performance claim appears anywhere in this document, by construction.

This is Line B (engineering/research policy) work, not mentorship semantic research. It consumes the frozen DIRECTION-dimension primitives (`OrderFlowEvent`, `BiasEvidence`) and arbitrates between them; it never redefines them. Full research trail: `sdd/crt-detector/mentorship-fidelity-boundary-v1`, `sdd/crt-detector/policy-layer-v1`, `sdd/crt-detector/policy-layer-v1/direction-policy-design`, `sdd/crt-detector/policy-layer-v1/direction-policy-spec`, `sdd/crt-detector/policy-layer-v1/direction-policy-implementation` (Engram).

## Provenance taxonomy in force

| Tag | Meaning |
|---|---|
| `MENTORSHIP` | The rule is stated in the charter corpus. Used **zero times** in this spec — everything below is ours. |
| `ENGINEERING POLICY` | A decision made by us to close a gap the source does not address. |
| `REPO LEGACY` | Inherited from an already-frozen artefact in this repo. |
| `RESEARCH HYPOTHESIS` | A choice made *in order to be tested*, whose truth is not asserted. |
| `REPO CONVENTION` | Mirrors an existing repo-wide contract (layering, no-lookahead, naming). |

Compatibility labels (weak, orthogonal to provenance): `SOURCE-COMPATIBLE` / `SOURCE-UNRESOLVED` / `SOURCE-TENSION` (caution without prohibition) / `SOURCE-CONTRADICTED` (reserved, unused — no rule here has an actual textual prohibition against it).

Lifecycle statuses for non-selected alternatives: `EXCLUDED` (structurally ruled out, e.g. `OF-C` — needs an unmotivated parameter), `COLLAPSED` (proven identical or cosmetic, e.g. `OF-B`→`OF-A`, `B-A`→`B-D`), `DEFERRED POLICY ALTERNATIVE` (coherent, not disproven, deliberately unused in V1, recoverable later — `DB-C`).

---

## A. Common Order Flow contract (DIR-P01) — shared by all four policies

```
eligible OF events := events where confirmation_index <= cutoff_index
relevant OF event  := the eligible event with maximum confirmation_index
                       (provably unique — REQ-OF-09 and its same-direction
                       companion invariant; no tie-break needed or permitted)
if no eligible events: OF direction = None, relevant event = None
same-direction newer eligible event -> REFRESHES the relevant reference (always argmax, never "sticks")
opposite-direction newer eligible event -> changes relevant direction (same argmax rule)
expiry/decay/timeout/window -> NONE in V1. COMMON V1 RESEARCH HYPOTHESIS, not architectural
                                truth, not mentorship-derived.
config -> NONE. No N, no window, no threshold.
```

`DirectionPolicy` never hardcodes the fact that `OrderFlowEvent`'s minimum possible `confirmation_index` is structurally `4` — that is a consequence of `OrderFlowEvent`'s own detection timing, cited only in comments, never a `DirectionPolicy`-level constant or branch.

### REQ-DIRPOL-01: Eligible `OrderFlowEvent`s at cutoff
An `OrderFlowEvent` is eligible at `cutoff_index` iff `event.confirmation_index <= cutoff_index`. No other eligibility criterion exists.
- **GIVEN** events `bullish@100`, `bearish@140`, `bullish@300` **WHEN** evaluated at `cutoff_index=220` **THEN** eligible = `{bullish@100, bearish@140}`.
- **REQ-DIRPOL-01.1**: boundary is inclusive — `confirmation_index == cutoff_index` is eligible.
- **REQ-DIRPOL-01.2**: no eligible events → OF direction = `None`.
- **REQ-DIRPOL-01.3 (added 2026-09-09, pre-commit consistency audit)**: `cutoff_index` MUST be `>= 0`. `cutoff_index < 0` does not name a valid `OHLCSeries` position under any circumstance and is rejected before any other check runs — see REQ-DIRPOL-05.4. No upper bound is validated (`DirectionPolicy` never receives the series or its length; an over-large cutoff yields no eligible OF events on its own, per REQ-DIRPOL-01.2, and the Bias side already fails loudly per REQ-DIRPOL-05 since dense evidence cannot exist beyond the series either).
- **Provenance**: `ENGINEERING POLICY` · `SOURCE-UNRESOLVED`.

### REQ-DIRPOL-02: Unique relevant/latest OF selection
The relevant `OrderFlowEvent` MUST be the eligible event with maximum `confirmation_index`. This maximum is provably unique (no two events, same or opposite direction, can share a `confirmation_index` — REQ-OF-09, test-locked, plus an independently re-derived same-direction companion proof, both pinned in `tests/test_order_flow.py`).
- **Provenance**: `REPO LEGACY` (uniqueness invariant) + `ENGINEERING POLICY` (selecting on it) · `SOURCE-UNRESOLVED`.

### REQ-DIRPOL-03: Same-direction refresh
The relevant reference MUST always be the argmax, including when the newest eligible event carries the same direction as the previous one — it MUST refresh, never stick to an older event.
- **GIVEN** `bullish@100, bullish@140`, cutoff 220 **THEN** `order_flow_confirmation_index == 140` (not 100).
- **Provenance**: `RESEARCH HYPOTHESIS` + `ENGINEERING POLICY` · `SOURCE-UNRESOLVED`. Explicitly **not** `MENTORSHIP`.

### REQ-DIRPOL-04: Unlimited V1 persistence — explicit common hypothesis
No V1 policy applies expiry, decay, timeout, or window to OF eligibility.
- **GIVEN** `bullish@100`, no later event, cutoff `10_000` **THEN** `relevant == @100` — permanent counterexample of record (DP14).
- **REQ-DIRPOL-04.1**: status is a **COMMON V1 RESEARCH HYPOTHESIS**, shared identically by P1–P4, not architectural truth. Any expiry/decay variant is V2 scope.
- **Provenance**: `RESEARCH HYPOTHESIS` · `SOURCE-UNRESOLVED`. Not `MENTORSHIP`.

---

## B. Bias alignment contract (corrected, final domain)

`BiasEvidence` supplied to a policy at `cutoff_index = c` MUST satisfy exact alignment, on a **three-way, no-implicit-path** domain:

```
cutoff_index < 0   ->  INVALID. Raises CutoffDomainError. Checked FIRST, before any
                        Bias-specific logic — a negative cutoff is invalid regardless
                        of what (if anything) the caller passes for bias_evidence.
cutoff_index == 0  ->  bias_evidence MUST be absent (None). Raises BiasAlignmentError
                        if present — no candle precedes index 0, so no BiasEvidence
                        can exist there (BiasEvidence is dense on 1..N-1 only).
cutoff_index >= 1  ->  bias_evidence MUST be present AND
                        bias_evidence.observation_index == cutoff_index.
                        Raises BiasAlignmentError otherwise (absent, stale, or future).
```

### REQ-DIRPOL-05: `BiasEvidence` alignment contract
- **REQ-DIRPOL-05.1**: stale evidence rejected — `cutoff=500`, `observation_index=220` → `BiasAlignmentError`. (The rejected weaker precondition `<=` would accept this, silently admitting 280-candle-stale evidence as an undocumented hidden policy — recorded here so the strict form is never relaxed by accident.)
- **REQ-DIRPOL-05.2**: future evidence rejected — `cutoff=220`, `observation_index=221` → `BiasAlignmentError`.
- **REQ-DIRPOL-05.3**: `cutoff_index == 0` is the sole legal absence (`BiasEvidence` never emits at index 0 — dense on `1..N-1`, `detect_bias_evidence`).
- **REQ-DIRPOL-05.4 (added 2026-09-09, pre-commit consistency audit — BLOCKER found and fixed)**: `cutoff_index < 0` is covered by **neither** `== 0` **nor** `>= 1` — an earlier report on this spec incorrectly asserted it "falls into the `>= 1` branch"; that is false (`-1 >= 1` is false). A negative cutoff is now rejected by its own explicit, dedicated check (`CutoffDomainError`, REQ-DIRPOL-01.3), checked **before** `BiasAlignmentError`'s logic runs, so it cannot be bypassed by an artificially constructed `BiasEvidence` whose `observation_index` also happens to be negative (a state the real `detect_bias_evidence` never produces, but the type alone does not forbid — tested explicitly).
- **REQ-DIRPOL-05.5**: the earliest structurally possible OF `confirmation_index` is `4` (cited from `OrderFlowEvent`'s own detection timing, never hardcoded in this module), so at `cutoff_index=0` the OF side is *also* necessarily empty — the `cutoff==0` carve-out is a type-level totality requirement with no reachable mixed state.
- **Error types**: `CutoffDomainError` (cutoff-domain violation, independent of bias) and `BiasAlignmentError` (bias-specific alignment violation) are kept **separate** — a negative cutoff is not a Bias-alignment problem, and conflating the two would misname the failure. Both follow the repo's actual convention (named `Exception` subclasses, e.g. `core.pairing_table.PairingError`, `ingestion.loader.LoadError`) — no bare `assert`, no bare `ValueError` outside the CLI boundary.
- **Provenance**: `ENGINEERING POLICY` · `SOURCE-UNRESOLVED`, resting on `REPO LEGACY` (`BiasEvidence` density) and `REPO CONVENTION` (named-exception style, positional indexing).

**Consequence audited and confirmed harmless**: tightening this domain makes "OF present + Bias absent" unreachable for any `cutoff_index >= 1` (the only cutoff where OF can be present at all). This does **not** remove any combiner table cell — the combiners' second axis is `{bullish, bearish, unresolved-or-absent}`; "absent" was never a separate column, it already collapses into `unresolved`. All 6 `DirectionReason` values and all 6 pairwise policy differences (Section E) were re-verified reachable/distinct under the corrected domain before this spec was signed.

---

## C. Bias-normalization truth tables (DIR-P03) — normative, complete

12 rows each, `close_signal ∈ {bullish,bearish,None} × wick_signal ∈ {bullish,bearish,conflict,None}`.

**B-B (strict agreement)**: resolves only when both axes are directional and equal. `bullish/bullish→bullish`; `bearish/bearish→bearish`; all other 10 rows→`unresolved`.

**B-C (non-contradiction)**: agreement→that direction; lone directional axis (other `None`)→that direction; `conflict` on either axis→`unresolved`; both directional and disagreeing→`unresolved`. `bullish/bullish→bullish`; `bearish/bearish→bearish`; `bullish/None→bullish`; `bearish/None→bearish`; `None/bullish→bullish`; `None/bearish→bearish`; remaining 6 rows (any `conflict`, or `bullish/bearish`, `bearish/bullish`, `None/None`)→`unresolved`.

**B-D (close-only, no fallback)**: `close_signal` alone decides. `bullish/*→bullish` (all 4 wick values); `bearish/*→bearish` (all 4); `None/*→unresolved` (all 4).

`B-A` (close priority with wick fallback) is **`COLLAPSED`** into B-D — historical note only, not a live normalizer, not publicly exported.

**Provenance**: `ENGINEERING POLICY` + `RESEARCH HYPOTHESIS` · `SOURCE-UNRESOLVED`. The only permitted claim about `wick_signal="conflict"`: it is a **normal, first-class, structurally valid state** (both wicks existing is ordinary OHLC geometry) — never a frequency/prevalence claim. B-B/B-C/B-D's differing treatment of `conflict` is justified purely by what each takes it to *mean*, never by how often it occurs.

---

## D. Combiner truth tables (DIR-P02) — normative, complete

9 cells each, `OF ∈ {bullish,bearish,None} × normalized bias ∈ {bullish,bearish,unresolved-or-absent}`.

**Reason rule** (governs all combiners): both absent/unresolved→`NO_EVIDENCE`; one present, output=that source→`SINGLE_SOURCE`; one present, output=unresolved→`CORROBORATION_MISSING`; both present+equal→`AGREEMENT`; both present+unequal+output unresolved→`CONFLICT_UNRESOLVED`; both present+unequal+output directional→`CONFLICT_RESOLVED_BY_PRIORITY`.

**DB-A (strict agreement required, used by P2)**: resolves only on both-present-and-equal; a single present source is never enough.

**DB-B (OF priority, used by P1)**: OF present → OF wins always (even conflict). Else Bias if present. Else unresolved.

**DB-D (evidence-preserving, used by P3 and P4)**: agreement→that direction; both present+disagreeing→unresolved; exactly one present→that one; neither→unresolved.

**DB-C (Bias priority)**: `DEFERRED POLICY ALTERNATIVE`, label `SOURCE-TENSION` (the corpus expresses caution — "Bias no es una regla absoluta" — without stating a rule that forbids Bias priority; no textual prohibition exists, so `SOURCE-CONTRADICTED` is not used). Excluded from V1 for parsimony + P1–P4 already spanning the behaviour space — **not** disproven. Not publicly exported; not a reachable production path.

**Provenance**: `ENGINEERING POLICY` + `RESEARCH HYPOTHESIS` · DB-A/B/D `SOURCE-UNRESOLVED`; DB-C `SOURCE-TENSION`.

---

## E. The four V1 policies — frozen composition and IDs

```
P1  direction_policy_structural_priority_v1   = (common OF, B-D, DB-B)
P2  direction_policy_corroboration_v1         = (common OF, B-B, DB-A)
P3  direction_policy_noncontradiction_v1      = (common OF, B-C, DB-D)
P4  direction_policy_bias_veto_v1             = (common OF, B-D, DB-D)
```

### REQ-DIRPOL-10: P1 — structural evidence decides whenever available; Bias fills only missing structural evidence.
### REQ-DIRPOL-11: P2 — direction only when independent evidence corroborates, per DB-A exactly. Never described as "more faithful" to anything — one hypothesis of four.
### REQ-DIRPOL-12: P3 — permit incomplete evidence, never emit a direction through explicit contradiction.
### REQ-DIRPOL-13: P4 — Bias cannot independently overrule structural direction, but explicit disagreement can veto a resolved decision.
- **REQ-DIRPOL-13.1 (CLARIFICATION-1, normative — table governs prose)**: under P4, Bias **IS** sufficient alone when OF is absent (DB-D's single-source cell); what it cannot do is **flip** a present OF direction. Never read "cannot overrule" as "can never resolve alone."

All four: `ENGINEERING POLICY` + `RESEARCH HYPOTHESIS` · `SOURCE-UNRESOLVED`. Truth table always governs over intent prose if any tension appears.

### F. Pairwise meaningful-difference — all 6 pairs, valid domain only
Re-derived using only present, exactly-aligned `BiasEvidence` at `cutoff_index >= 1` (per the corrected domain, Section B). All 6 pairs (P1≠P2, P1≠P3, P1≠P4, P2≠P3, P2≠P4, P3≠P4) confirmed genuinely distinct with a minimal concrete counterexample each; full detail in `sdd/crt-detector/policy-layer-v1/direction-policy-implementation` (Engram). P1≠P4 isolates the combiner axis (normalizer held constant); P3≠P4 isolates the normalizer axis (combiner held constant) — both design axes independently load-bearing, no collapse under the corrected domain.

---

## G. `DirectionDecision` contract

```python
@dataclass(frozen=True)
class DirectionDecision:
    policy_id: str                                                  # IS the version — no separate policy_version field (OMIT, approved)
    cutoff_index: int
    direction: Literal["bullish", "bearish", "unresolved"]          # unresolved is first-class, never None/False
    order_flow_confirmation_index: int | None                       # reference, not the embedded event
    order_flow_direction: Literal["bullish", "bearish"] | None
    normalized_bias_direction: Literal["bullish", "bearish", "unresolved"] | None
    reason: DirectionReason
```

No `bias_observation_index` field (OMIT, approved) — pinned to `cutoff_index` by the alignment invariant, carries zero information.

`DirectionReason` — six values, each reachable under the corrected valid domain: `NO_EVIDENCE`, `SINGLE_SOURCE`, `AGREEMENT`, `CONFLICT_UNRESOLVED`, `CONFLICT_RESOLVED_BY_PRIORITY` (P1 only), `CORROBORATION_MISSING` (P2 only).

### REQ-DIRPOL-14: `DirectionDecision` provenance/auditability. No free-text `reason` field ever.
### REQ-DIRPOL-15: `unresolved` is first-class — never `None`/`False`/a missing object/an exception for valid input.
### REQ-DIRPOL-16: No-lookahead / prefix invariance — a decision at cutoff `t` depends only on events with `confirmation_index <= t` and the single `BiasEvidence` at `observation_index == t`; appending candles after `t` never changes it. Discharged by existing property-test infrastructure (`tests/property/test_no_lookahead.py`) plus 2 DirectionPolicy-specific properties added at implementation.
### REQ-DIRPOL-17: `DirectionPolicy != trade permission`. A decision states what evidence supports at a cutoff; it authorizes nothing. `unresolved → skip/continue trade` is explicitly a `StrategyPolicy`/orchestration decision, never baked into `DirectionPolicy`.

---

## H. Provenance ledger integrity

**Zero rules in this spec carry `MENTORSHIP`.** Every arbitration rule between the frozen evidence primitives is ours, tagged as ours (`ENGINEERING POLICY` / `RESEARCH HYPOTHESIS` / `REPO CONVENTION` / `REPO LEGACY`). The mentorship corpus supplies the *evidence primitives and vocabulary*; it supplies no combination rule between them (`REQ-BIAS-04`, and the closed `DirectionContext`/`DOLSelector` research).

## I. Deferred (explicitly out of scope)

OF expiration/decay (V2+parameter required) · `unresolved → trade behaviour` (StrategyPolicy) · `DB-C` (`DEFERRED POLICY ALTERNATIVE`) · `DOLPolicy` · `KeyLevelPolicy` · orchestration · multi-timeframe mapping · `LiquidityCandidate`/`KeyLevel`/`DirectionContext`/`KeyLevelSelector` interaction · outcome evaluation of any kind (WR/MeanR/PF/backtest/OOS) · choosing a winner among P1–P4.

## J. Sign-off

Signed READY FOR IMPLEMENTATION (initial pass). Amended and re-confirmed 2026-09-09 after a pre-commit consistency audit found and fixed one BLOCKER (REQ-DIRPOL-01.3 / REQ-DIRPOL-05.4, the negative-cutoff domain gap) — no policy semantics changed, only the cutoff-domain precondition was made explicit and total. All 6 pairwise proofs and all 6 `DirectionReason` values re-verified under the corrected domain before this amendment.

**Four policy hypotheses: IMPLEMENTED, TESTED, NO OUTCOMES INSPECTED.**
