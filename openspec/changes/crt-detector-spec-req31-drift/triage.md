# Triage: crt-detector-spec-req31-drift

**Classification**: XS | **work_type**: bug (spec/code drift, not a functional defect) | **urgency**: low
**Decided at**: 2026-09-08
**Sensitivity**: none — pure documentation drift in a signed spec, no behavior change, no auth/payments/PII/deploy surface.

## Problem

`openspec/specs/detector/spec.md` REQ-31 still documents `BacktestConfig.sl_buffer_price = 0.0002` as "a raw PRICE-UNIT offset (2 pips)." The actual shipped code (`detector/core/config.py`) has used `sl_buffer_atr_multiple = 0.3` (an ATR-relative multiplier) since commit `53a6514` (`fix(detector): make stop-loss buffer ATR-relative, not a raw price constant`, from `crt-detector-scale-aware-risk-params`, an S-classified bug fixed inline — no spec-update step in that change's own routing, since it ran the S-inline path without a `sdd-spec` phase).

Root cause is already known and not in question: the S-inline fix changed the field and its semantics but never updated the consolidated spec text describing it. This is a documentation-consistency defect, not a runtime bug — the code has been correct since `53a6514`; the spec is what's stale.

## Discovery context

Surfaced as a collateral finding (not the target of the task) during a mentorship-vs-implementation-vs-research gap analysis (`sdd/crt-detector-key-level-confluence/mentorship-gap-analysis`) and re-confirmed independently during the Order Flow triage's repository inventory. Registered here on explicit instruction to keep it tracked without fixing it inside either of those unrelated threads.

## Scope

```yaml
scope:
  in_scope:
    - Update REQ-31's prose and any example values in openspec/specs/detector/spec.md
      to describe sl_buffer_atr_multiple=0.3 accurately, replacing the stale
      sl_buffer_price=0.0002 text.
  out_of_scope:
    - Any code change (code is already correct)
    - Re-litigating the sl_buffer_atr_multiple value itself
    - The two other same-category dormant fields already logged separately
      (trading_cost_price, respect_rule_tolerance — project/pending-changes)
```

## Recommended path

S → inline path when picked up (orchestrator-executed, mechanical spec-text edit, no design/slice ceremony needed — this is strictly syncing prose to already-shipped, already-tested behavior).

## Status

`pending` — not started. Do not fix inside `crt-detector-key-level-confluence` (Line A/B research) or any other unrelated change.
