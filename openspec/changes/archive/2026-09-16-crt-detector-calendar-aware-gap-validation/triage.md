# Triage: Calendar-Aware Dataset Gap Validation

**Classification**: L
**Decided at**: 2026-09-16T14:03:41Z
**Change name**: `crt-detector-calendar-aware-gap-validation`

## Problem & Scope

> The current fixed-cadence validator treats legitimate market closures as missing data, blocking the statistical-runner preflight (including DXYm/D1) and making the dataset unusable without either weakening validation or supplying evidence the repository does not own. We need a fail-closed validation contract that can distinguish expected closures from missing candles without fabricating historical broker truth.

```yaml
scope:
  in_scope: [separate fail-closed amendment, hash-bound closure evidence, allowlist transition, synthetic acceptance and external gates, reconcile stale planning inputs]
  out_of_scope: [historical Exness calendar, real-data inspection/execution, baseline/protocol/manifest/dataset changes, timestamp-pattern proof, implementation/tests]
```

## Description Received

> Specify deterministic, calendar-aware gap validation; authoritative evidence must be hash-bound, and timestamp patterns are never authoritative.

## Criteria Evaluation

| Criterion | Evidence | Score |
|---|---|---|
| Files affected (estimated) | ~7 planning and eventual validator/manifest/test artifacts | M |
| Lines affected (estimated) | ~400 contract, validation, and tests | M |
| Bounded contexts | dataset validation and frozen experiment metadata | M |
| New patterns | hash-bound external closure-evidence contract | L |
| Test types | deterministic synthetic pytest cases; external-evidence gate | M |
| Precedent (before overrides) | greenfield; exact allowlist is not a calendar-evidence precedent | no change |

### Overrides Triggered
None. This alters dataset-validation policy, not an authorization, privacy, payment, deployment, or production-data mechanism.

**Final classification**: L — a new fail-closed, evidence-bound validation contract with consequential transition rules requires full design review.

## Recommended Path

- Phase: full Planner with Council
- Skills to invoke (in order): `sdd-explore` → `sdd-propose` → `sdd-spec` → `sdd-design` → `sdd-slice`
- Slice maximum guardrail: 7 — fewer cohesive slices preferred

## Recommended Personas

| Role | Reason |
|---|---|
| Business Analyst | Acceptance behavior and scope boundaries |
| PM | Keep unsupported historical evidence out of scope |
| QA Engineer | Fail-closed synthetic and external-gate cases |
| Architect | Evidence, manifest, and allowlist transition design |

## Spec Reference

`spec_source: internal` — no reference captured.

## Risks Flagged at Triage

- Historical broker evidence may remain unavailable; real-data acceptance must stay blocked.
- Existing unsigned inputs contain stale contradictions that must be reconciled before signing.
- An allowlist-to-calendar transition could accidentally weaken validation if coexistence is unspecified.

## Halt?

No.

## Notes for Next Phase

Treat timestamp patterns as non-authoritative; separate deterministic synthetic behavior from evidence required for real-data validation.
