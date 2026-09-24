# Triage: crt-detector-draw-on-liquidity

**Classification**: **S** (resolved post-design). `explore.md`'s Design A locked the shape: one stateless per-candle transform, `2N` candidates for `N` candles, single dependency on `core.candle`, zero new state-tracking pattern — strictly simpler than `crt-detector-bias` (no cross-candle relation at all, not even a pairwise close-vs-previous read) and `crt-detector-order-flow` (no pending-candidate state machine). Same S rubric outcome as Bias, on stronger grounds (even less novelty).
**work_type**: feature (third DIRECTION-dimension slice, semantic-triage stage) | **urgency**: normal
**Decided at**: 2026-09-08
**Program relationship**: standalone feature under `detector/`, same DIRECTION dimension as `crt-detector-order-flow` and `crt-detector-bias` (both closed). No shared seam, no shared REQ.
**Sensitivity**: none anticipated — stateless read over `OHLCSeries`, same category as every other DIRECTION-dimension primitive in this repo.

## Problem & scope

> `sdd/crt-detector-dol/semantic-research` (full re-read of `docs/charter-1..7.md`, from scratch, for every Draw on Liquidity / liquidity-target passage) found the mentorship's own formal definition is grammatically PLURAL ("puntos de liquidez... hacia los **cuales**"), and both worked examples in charter-3 identify **two** simultaneous draws on liquidity, never reduced to one. This is convergent textual evidence that DOL is a candidate SET, not a single scalar target — the architecture must split into (1) candidate existence and (2) candidate selection, and only (1) is in scope for this change.

```yaml
scope:
  in_scope:
    - Registering the conceptual split (this triage) and, pending its
      acceptance, a design pass for LiquidityCandidateDetector V1
      (existence only — see explore.md).
  out_of_scope:
    - DOLSelector (see Section 4 below) — no ranking/selection rule.
    - DirectionContext, KeyLevelSelector — not touched.
    - Implementation, signed spec — this stage is triage + design pass only.
    - Any outcome/statistics work (WR, MeanR, PF, backtest, ablation, OOS).
    - Line A (nearest_ob_selection_v1, daily_displacement_v1, factorial OOS) — untouched.
```

## 1. Source boundary

Formal definition, charter-3 `[00:11:29]`:

> "Identificación de **puntos** de liquidez clave en el corto plazo (como los máximos o mínimos de velas previas) hacia los **cuales** se dirige el precio."

The plural ("puntos"/"cuales") is load-bearing, not incidental — it is confirmed by both worked examples (`[00:10:32]`, `[00:14:47]`), each of which identifies **two** draws on liquidity, never one. "Nearest first" is a PATTERN observed in these two examples, not a stated rule — it stays EXAMPLE-ONLY and is not promoted to a selection rule at this stage.

## 2. DOL vs Key Level boundary

Frozen: DOL = "hacia los cuales **se dirige** el precio" (directional/target relation); Key Level = "zonas donde el mercado **decide expandirse o revertir**" (reaction/location relation, charter-1 `[00:11:48]`, charter-3 `[00:11:52]`). This is a textual separation (different verbs, consecutive checklist items #3/#4 in charter-3), not merely a conceptually appealing inference.

**Caveat, registered explicitly**: charter-6 `[00:02:19]` narrates "expandiéndose... hacia un key level de premium" — the same directional verb applied to a Key Level, without using the word DOL. The formal definitions are separate; narrative usage in the corpus is not perfectly consistent with that separation everywhere. Both facts stand; neither is suppressed.

## 3. CRT High/Low relationship

Frozen: charter-1 `[00:03:35]` — CRT High = BSL, CRT Low = SSL — CRT High/Low **are** liquidity pools by definition. charter-4 `[00:09:37]`/`[00:13:28]` present DOL and CRT High/Low as **parallel alternative** target categories ("el target puede ser el próximo DOL **o** un CRT High/Low claro"), never as synonyms.

**Approved classification**: `CRT High/Low CAN function as DOL, but DOL is not synonymous with CRT High/Low.` Not "ARE", not "AMBIGUOUS" — the source actively distinguishes them as alternative categories while acknowledging overlap.

## 4. Selector deferred

No source support exists for any universal selection rule among simultaneous candidates:

```text
nearest              → EXAMPLE-ONLY (pattern in 2 examples, never a stated rule)
most recent          → NOT SUPPORTED
highest/lowest        → NOT SUPPORTED
HTF priority          → NOT SUPPORTED
OrderFlow-aligned     → NOT SUPPORTED
Bias-aligned          → NOT SUPPORTED
unbroken              → NOT SUPPORTED (Order Flow's semantics never extended to DOL)
```

**`DOLSelector` status: DEFERRED / UNDER-SPECIFIED.** Not designed in this pass or the next.

## 5. Lifecycle deferred

Under-specified, registered without invention:

```text
wick vs close for "reached"   → not addressed anywhere in charters 1-7
candidate consumption          → not addressed
post-reach behavior            → not addressed
candidate replacement          → not addressed
```

Order Flow's "unbroken" semantics are NOT inherited — no textual bridge connects the two concepts.

## 6. Stage-1 recommendation

```text
LiquidityCandidateDetector → READY FOR DESIGN (not implementation)
DOLSelector                → DEFERRED
```

Design pass in `explore.md`.

## Status (2026-09-08, final)

**V1 implementation complete, human-approved READY TO COMMIT.** `detector/primitives/liquidity.py` + `detector/tests/test_liquidity.py` (13 tests) + a no-lookahead property entry (`_LIQ_K=0`) in `detector/tests/property/test_no_lookahead.py`, all TDD (red confirmed before implementation, green on first pass — the spec left no ambiguity). Full `detector/` suite: 369 passed, 1 pre-existing unrelated failure (`test_alignment_detection_has_no_lookahead`, same one already confirmed pre-existing during `crt-detector-bias`'s closeout — not touched here either). `lint-imports`: 2 kept, 0 broken. No source/design ledger changes were forced during implementation.

## LiquidityCandidateDetector V1 closeout

```text
candidate emission     COMPLETE
price exactness        COMPLETE
identity/no-dedup       COMPLETE
flat-candle distinctness COMPLETE
no-lookahead            COMPLETE
timeframe agnostic     COMPLETE
deterministic ordering COMPLETE
no CRT duplication      COMPLETE

DOLSelector             DEFERRED
short-term scope        DEFERRED
candidate ranking       DEFERRED
active target           DEFERRED
reach semantics         DEFERRED
consumption             DEFERRED
OrderFlow<->DOL         DEFERRED
Bias<->DOL              DEFERRED
DirectionContext        DEFERRED
KeyLevelSelector        DEFERRED
```

No V2 opened. `detect_liquidity_candidates` is closed as an existence-only primitive — no ranking, no selection, no prevalence/performance measurement started or implied. The next DIRECTION-dimension work (`DOLSelector`) is a separate, from-scratch semantic/design research thread, not a continuation of this change.
