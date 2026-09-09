# Triage: crt-detector-bias

**Classification**: S | **work_type**: feature (second slice of the DIRECTION dimension) | **urgency**: normal
**Decided at**: 2026-09-08
**Program relationship**: standalone feature under `detector/`, same DIRECTION dimension as `crt-detector-order-flow` (closed 2026-09-08). No shared seam, no shared REQ — `BiasEvidence` and `OrderFlowEvent` are independent record types, not combined by this change.
**Sensitivity**: none — verified (not assumed) against `project/sensitive-areas` (engram #297): auth/payments/privacy/deployment all "None detected"; the two low-confidence anticipated rows (broker credentials, historical-data storage) are untouched by a pure in-memory transform over `OHLCSeries` with no I/O. `.sdd/sensitive-paths.txt` does not exist — no path-level rule to cross.

## Problem & scope

> The mentorship-vs-implementation gap analysis found the DIRECTION dimension (Order Flow / Bias / Draw on Liquidity) under-represented in `detector/`. Order Flow shipped first (`openspec/changes/crt-detector-order-flow/`). Bias is the second slice, following a closed, user-approved 3-pass semantic-design research thread (engram topic `sdd/crt-detector-bias/semantic-research`) that resolved every ambiguity in charter-3's Bias passage `[00:02:03]` down to two independent, unarbitrated evidence signals.

```yaml
scope:
  in_scope:
    - A deterministic BiasEvidence read per (previous, current) candle pair,
      over a timeframe-agnostic OHLCSeries, in detector/primitives/bias.py.
    - Two independent signal fields (close_signal, wick_signal) — no
      combination/arbitration between them, no final "direction".
    - A no-lookahead property entry at k=0 (strictest variant in the
      existing family — reads only candles i-1 and i).
  out_of_scope:
    - direction/confidence/score/weight/target_index/expiry/state fields.
    - Bias horizon interpretation (source-ambiguous, left unresolved).
    - Turtle Soup, Breaker, OTE, Kiss of Death, Model-1, TSQ phases
      ("TSQ/OHLC Path Model" — separate, DEFERRED for source contradictions).
    - DirectionContext (composite reconciling Order Flow + Bias + DOL).
    - Draw on Liquidity — not researched.
    - Any outcome/statistics work (WR, MeanR, PF, backtest, ablation, OOS).
    - BiasConfig — no discretionary parameter exists to hold (see Config below).
```

## Council: architect + pm (parallel, blind, opus) — independent convergence

Both personas scored the same rubric `crt-detector-order-flow/triage.md` used, against the actual codebase (not assumption), with no visibility into each other's work or any orchestrator opinion.

### Criteria evaluation

| Criterion | architect | pm | Evidence |
|---|---|---|---|
| Files affected | S | S | 3 files: `primitives/bias.py`, `tests/test_bias.py`, one additive entry in `tests/property/test_no_lookahead.py`. No CLI/viz/`DetectorConfig` wiring — `detect_order_flow_events` itself is wired into none of those either (grep-verified), so Bias inherits the same zero-wiring footprint. |
| Lines affected | S | S | ~50-70 production lines. Structural comparator `primitives/ict_order_block.py` (79 lines, stateless pair-scan) minus its forward invalidation scan — Bias needs none. Contrast `composite/order_flow.py` (183 lines, stateful two-phase machine). |
| New patterns | S | XS | One representational convention: the first record in this codebase to carry two independent, deliberately-unarbitrated opinions (`close_signal`, `wick_signal`) with two distinct absence semantics (`None` = no evidence, `"conflict"` = contradictory evidence — the token `"conflict"` appears nowhere else in `detector/**/*.py`). Zero algorithmic novelty — no state, no forward scan. Architect scores this S (a naming/shape decision, not XS); pm scores XS (mechanically templated). Both agree it is NOT the M-causing kind of novelty Order Flow's paired-pending state machine was (three design passes, two demonstrated defect modes) — Bias's semantics are already resolved and frozen upstream. |
| Bounded contexts | S | S | 1 (`primitives`). Imports only `core.candle` — no import-graph change; `.importlinter` already permits `primitives → core`. |
| Precedent | XS-S | XS | `ict_order_block.py::_match` is a near-exact structural template (candle-pair scan → `Literal` verdict → frozen record); `close_signal`'s inside-branch body-colour test is literally `_match`'s own `anchor.close < anchor.open` comparison. |

**Final classification: S** (both personas, independently). Order Flow's M rested entirely on one row — a stateful, defect-prone paired-pending state machine. Bias has no state at all; strip that row from the sibling's own table and it would have scored S too. Scoring Bias M would classify by DIRECTION-dimension *topic*, not by this change's actual complexity — both personas flagged this explicitly as the reasoning trap to avoid.

## Layer decision (architect, decided with evidence — not deferred to design)

**`detector/primitives/bias.py`**. Every `primitives/` module imports only `core.*`; every `composite/` module imports `primitives.*` (that dependency is what makes it composite). `detect_bias_evidence` imports only `core.candle` — the `primitives` signature exactly. Placing it in `composite/` "to keep DIRECTION together" would classify by topic over dependency direction, and would make a future accidental `primitives` import invisible to `lint-imports` (composite may legally import primitives; primitives may not import composite — `tests/test_fitness_imports.py` protects the restrictive placement for free). No `.importlinter` edit needed.

## Config decision

**No `BiasConfig`.** `OrderFlowConfig` (empty, "no discretionary threshold is justified") is defined but NOT wired into `DetectorConfig`; `ICTOrderBlockConfig` (also empty, same justification) IS wired. The precedent is mixed — there is no symmetry to preserve either way — so per the craftsman rule ("before writing any new field/config, name the behaviour it adds; if none, don't write it"), Bias gets no config object at all. `tests/test_fitness_config.py` scans only modules that import `core.config`; a config-free module is outside that fitness function by construction.

## Proportionality verdict (pm) — S classification, spec exception

Both personas independently flagged the same tension and it is being resolved here, on evidence, not on doubt (per CLAUDE.md's proportionality principle: "escalate only on evidence"):

- **Code complexity says S** → the generic S route is "light `sdd-explore`, then inline path, no spec artefact."
- **This repo's own established convention says otherwise for THIS specific artefact**: every DIRECTION/structural detector here carries REQ-ID anchors (`REQ-OF-01..09`, `REQ-61/62/63`, `REQ-47`) traced from mentorship source through a signed `spec.md`, and `openspec/specs/detector/spec.md` is the target of archive's delta-sync. A Bias detector with no REQ-IDs would be the only DIRECTION-dimension detector invisible to that traceability/drift-audit machinery (a drift-tracking change already exists in this repo's history for exactly that reason). The user also explicitly requested a formal spec with REQ-BIAS-* + Given/When/Then.
- **Resolution — S classification, unchanged, with one deliberate addition**: run a scoped `sdd-spec` (target ~50-70 lines, matching `crt-detector-order-flow/spec.md`'s size), skip `sdd-explore` (research already closed, re-opening it would re-litigate a signed decision), skip `sdd-propose` (the frozen scope above already states intent/scope), skip `sdd-design` (no ADR-worthy decision remains — shape and layer are already decided, with evidence, above), skip `sdd-slice` (one module is one unit of work), skip the plan-verify gate (S, and `spec_source: internal` means no publish to gate). TDD implementation follows directly from the signed spec, per this repo's Strict TDD convention.

This is a mechanism concession (this repo's own traceability convention, evidenced), not a re-scoring — the criteria table above stays S.

## Scope-cleanliness verdict (pm)

Audited the frozen `BiasEvidence` shape field-by-field against the out-of-scope list: no `direction`/`confidence`/`score`/`weight`/`target_index`/`expiry`/state field; `close_signal`/`wick_signal` stay separate and nullable, `"conflict"` preserved as a value rather than arbitrated; `observation_index` only, no forward scan; no `KeyLevel`/`SwingPoint`/`DirectionContext`/DOL/TSQ type in the signature or dependency set. **Clean — no scope creep.**

## Simplification finding (pm + architect, independently convergent) — applied at spec time

`upper_wick_present` and `lower_wick_present` are a bijection of `wick_signal` (4 boolean-pair states ↔ 4 `wick_signal` values, recoverable in both directions) — zero information beyond what `wick_signal` already carries. Per the "less code is better code" rule, these two fields are dropped from the frozen shape at spec time; `wick_signal` alone is preserved.

## Followups to register (pm) — not part of this change, tracked so they aren't lost

- `DirectionContext` (Order Flow + Bias + future DOL reconciliation) — currently unregistered in `openspec/pending-changes.md` despite two changes now depending on it for observable value.
- Draw on Liquidity — third DIRECTION slice, unresearched.
- Bias horizon — deliberately unresolved as source-ambiguous; tracked so the deferral doesn't get silently forgotten.
- Wiring — whether DIRECTION detectors ever surface in `detections.csv`/CLI, or stay library-internal until `DirectionContext` exists.

## Sensitivity

None. Confirmed against `project/sensitive-areas`, not assumed (architect). No auth/payments/PII/deploy surface — a stateless in-memory transform over `OHLCSeries`.

## Halts

None from either persona. No contradiction, no unsound ask, no missing information blocking classification.

## `ready_for_next_phase`

**READY FOR SPEC** — proceeding directly to a scoped `sdd-spec` (explore/propose/design/slice/plan-verify skipped per the Proportionality verdict above).
