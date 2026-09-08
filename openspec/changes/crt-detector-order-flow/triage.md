# Triage: crt-detector-order-flow

**Classification**: M | **work_type**: feature (new primitive, first slice of "Line B" DirectionContext research) | **urgency**: normal
**Decided at**: 2026-09-08
**Program relationship**: standalone feature under `detector/`, NOT part of `crt-detector-key-level-confluence` (that program's scope is Key Level / LOCATION; this is DIRECTION). No shared seam, no shared REQ.
**Sensitivity**: none — stateless detection-logic addition, no auth/payments/PII/deploy surface. Confirmed against `project/sensitive-areas` (same conclusion as every prior detector-addition triage in this repo).

## Problem & scope

> The mentorship-vs-implementation gap analysis (`sdd/crt-detector-key-level-confluence/mentorship-gap-analysis`) found the DIRECTION dimension (Order Flow / Bias / Draw on Liquidity) has ZERO representation in the codebase, more fundamental than the LOCATION-selection gap that originally motivated the Order Block investigation. Order Flow was selected (`sdd/crt-detector-key-level-confluence/order-flow-triage`) as the first implementable slice of that dimension: the only one of the three with a mechanically complete-enough mentorship definition and near-total architectural reuse available (`primitives/swing.py`).

```yaml
scope:
  in_scope:
    - A deterministic OrderFlowEvent detector, reusing primitives/swing.py's
      SwingPoint stream unmodified, over a timeframe-agnostic OHLCSeries.
    - Formalizing every UNDER-SPECIFIED mechanical term from the mentorship's
      single definition (charter-3 [00:01:23]) as an explicit, labeled design
      decision (MENTORSHIP / DESIGN DECISION / REPO REUSE / REPO CONVENTION).
    - A no-lookahead / incremental-result property test, matching this
      project's existing convention (tests/property/test_no_lookahead.py).
  out_of_scope:
    - Bias, Draw on Liquidity, DirectionContext (the composite), TSQ-direction,
      KeyLevelSelector, Breaker Block, Rejection Block, FVG ranking — only
      non-functional future-interface notes are allowed to mention them.
    - Any outcome/statistics work (WR, MeanR, PF, backtest, ablation, bootstrap,
      OOS). This change is not evaluated by predictive performance.
    - Reusing composite/mss.py as the implementation (semantic mismatch,
      see explore.md Decision analysis) — its architectural PATTERNS may
      inform the eventual design, its specific thresholds may not.
```

## Criteria evaluation

| Criterion | Evidence | Score |
|---|---|---|
| Files affected | Likely 3-5: one new primitive module + its test file + `core/key_level.py`-adjacent future-interface note (comment only) + property test | M |
| Lines affected | Small — the core loop is a state machine over an existing SwingPoint stream (`primitives/swing.py`, 26 lines, unmodified), closer in shape to `primitives/fvg.py` than to `composite/mss.py`'s heap-based scale optimization (not needed at v1's expected volumes) | M |
| New patterns | One: a "paired pending rejection per direction, superseded by a newer rejection of the same kind" state-tracking rule — not precedented elsewhere in this codebase (mss.py's own pending-tracking requires a PRIOR opposite swing to exist, a different rule) | M |
| Bounded contexts | 1 (`primitives`) | S |
| Precedent | `primitives/swing.py`, `composite/mss.py` establish the fractal-swing + structural-event detection pattern this mirrors (architecturally, not semantically — see explore.md) | M (precedent modifier does not downgrade below M given the genuinely new state-tracking rule) |

**Final classification**: M — single bounded context, moderate new logic, strong architectural precedent, but a genuinely new (undocumented-elsewhere) state-tracking rule keeps it from S.

## Recommended path

M-light: this triage + `explore.md` (already produced, see below) stand in for the merged propose+spec step's exploration half. A follow-up `sdd-spec`/`sdd-design` pass should formalize `explore.md`'s Section F (proposed REQs) into a signed spec before any `sdd-apply` — **not done in this pass**, per explicit instruction not to implement.

## Sensitivity

None. No auth/payments/PII/deploy surface — a stateless HTF structural-direction detector, same category as every other primitive in `detector/`.

## `ready_for_next_phase`

**READY FOR SPEC SIGN-OFF** (resolved 2026-09-08, third design pass — see `explore.md` Section M). The second pass's own two central choices (magnitude-based reference selection; unified single pending candidate) were themselves reversed here on evidence — a demonstrated indefinite-anchoring defect (magnitude selection can permanently freeze on a stale ancient extreme) and a demonstrated event-loss defect (a unified candidate silently discards a legitimate completed event when an unrelated opposite-direction rejection occurs first). Final design: reference selection by RECENCY (most recent confirmed unbroken swing, not most extreme), pending candidates tracked INDEPENDENTLY per direction, a same-candle two-phase resolution order, and two structural proofs (not assumptions) ruling out same-candle invalidation+break and a candle targeting its own just-confirmed swing. REQ-OF-02/04 rewritten a second time; REQ-OF-07/08 added. No remaining input was identified where two implementers would diverge. `sdd-spec` may now formalize `explore.md` into a signed spec.
