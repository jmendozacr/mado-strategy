# Design: Calendar-Aware Gap Validation

**Spec**: V1 (signed)  
**Triage**: L  
**Delivery boundary**: dormant, documentation-only contract

## Architecture Overview

This change records the contract that a future activation must satisfy; it does not add a calendar subsystem or alter `adapter.dataset`, `adapter.manifest`, `runner.preflight`, the frozen protocol, lineage B/A, datasets, or tests. Current exact-allowlist validation remains the only runtime authority and current blocked preflight outcomes remain blocked.

The future seam is a per-instrument/per-granularity authority selection at dataset validation. An activated evidence authority would replace, never supplement, the legacy allowlist for its pair. Evidence admission is a separate trust boundary: retained source bytes, hashes, provenance, attestation, identity and complete-window coverage must be validated before any closure claim can affect admission.

**Pattern**: existing — matches the repository's immutable, hash-bound manifest/serialization practice described in `detector/runner/serialization.py`; no new abstraction is introduced by this amendment.

## File Changes

| Path | Action | Purpose |
|---|---|---|
| `openspec/changes/crt-detector-calendar-aware-gap-validation/design.md` | Modify | Replace the stale calendar-construction draft with this signed-spec-aligned dormant contract |

No runtime or test file is authorised for modification in this change.

## Flow Changes

| Flow | Action | REQ-IDs | Verification target | Notes |
|---|---|---|---|---|
| Planning and approval | Modify | REQ-01–05 | signed specs plus this design | Records gates only; no runtime outcome changes |
| Discovery → preflight → dataset validation → stop/proceed | Modify | REQ-01, REQ-05 | existing preflight regression evidence | Observable behaviour must remain unchanged |

The second row is a preservation constraint, not an implementation change.

## Architecture Touchpoints

| Layer/Component | Action | Why | Baseline fit |
|---|---|---|---|
| repository documentation knowledge base | extend | Records the dormant authority and activation contract | aligns |

The 2026-08-29 baseline predates some adapter/runner detail, but that staleness is non-blocking because no code component is changed. Future activation must refresh the baseline before design approval.

## Data Model

No current data model changes.

A future activation must define a canonical evidence claim containing: broker, server/account identity, instrument, granularity, closure interval, inclusive policy window, source-byte hash, canonical-claim hash, provenance, independent attestation, and activation identity. It must also define deterministic ordering, duplicate/overlap rules, hash algorithm and canonical bytes. Those shapes belong to the separately authorised activation design and MUST NOT be inferred here from real or synthetic timestamps.

## Interface Contracts

No current external or runtime interface changes.

Future activation must expose one deterministic result for a pair: legacy authority when no evidence authority is activated, or the activated evidence authority otherwise. Failure variants must distinguish malformed evidence, identity mismatch, hash mismatch, unverifiable/conflicting provenance, incomplete coverage, overlapping/conflicting claims, and unjustified interval. Every failure leaves the gap unresolved; no fallback is permitted.

## Architecture Decisions

### ADR-01: Keep the Evidence Contract Inert

**Status**: Accepted by the signed specification.

**Context**: Repository evidence cannot establish historical Exness session truth, while current validation is fail-closed and lineage-bound.

**Decision**: This change records constraints only. It creates no runtime evidence authority and accepts no real closure.

**Consequences**:
- Current preflight remains blocked where it is blocked today.
- A later activation needs a separate change and approval.
- The immediate operational pain is not removed.

**Alternatives Considered**:
- **Activate from observed timestamps**: rejected because observations do not prove broker truth.
- **Construct a calendar now**: rejected because authoritative historical evidence is absent.

### ADR-02: Future Authority Is Exclusive Per Pair

**Status**: Accepted as a constraint on a future activation.

**Context**: Consulting an allowlist after evidence rejection creates two authorities and converts fail-closed behaviour into fallback acceptance.

**Decision**: Activation for one instrument/granularity replaces the legacy authority for that pair; other pairs remain unchanged.

**Consequences**:
- Authority selection is deterministic and auditable.
- Incomplete evidence blocks rather than falling back.
- Activation requires complete evidence before cutover.

**Alternatives Considered**:
- **Union both authorities**: rejected because either source could bypass the other.
- **Fallback to allowlist**: rejected because evidence failure would cease to be fail-closed.

## Test Derivation

All future tests use synthetic evidence only. They prove mechanics, never broker history.

| REQ-IDs / scenarios | Behaviour covered | Level | Future test target | Flow ref |
|---|---|---|---|---|
| REQ-01; REQ-05 planning artifacts do not activate | Existing outcome remains unchanged without separate activation | integration | `detector/tests/test_runner_preflight.py` | Discovery/preflight preservation |
| REQ-02 invalid evidence | Parameterised rejection of every listed defect; gap remains unresolved | unit | `detector/tests/test_adapter_dataset.py` | — |
| REQ-03 almost-complete evidence | Omission, overlap and conflict reject the complete set across both inclusive boundaries | unit | `detector/tests/test_adapter_dataset.py` | — |
| REQ-04 all three scenarios | Exactly one authority; legacy before activation, replacement after activation, no fallback | integration | `detector/tests/test_runner_preflight.py` | Discovery/preflight preservation |
| REQ-05 incomplete and fully gated activation | Each missing gate stays inert; approved pair is isolated from all others | contract | future activation contract suite, exact path set by that change | Planning and approval |

## Fitness Functions

- **No current runtime drift**: repository diff for this change contains no paths under `detector/`, no protocol/manifest/dataset artifacts, and no B/A changes.
- **One authority per pair**: the future activation contract suite must prove no execution path consults both authorities.

## Migration / Rollout

No migration or rollout occurs. A future activation requires a new authorised change, admissible complete evidence for 2022-08-08 through 2026-08-19 inclusive, new lineage/B/A, baseline refresh, sensitive-area re-triage, synthetic verification, and pair-scoped cutover. `gap_end` hardening remains separate.

## Performance Considerations

No current performance impact. Future evidence size, validation complexity and startup cost must be measured in the activation design; no budget is asserted here.

## External Assumptions

| Assumption | Status | Gate |
|---|---|---|
| Historical broker closures can eventually be supported by retained original records with verifiable provenance | assumed | Blocks activation until externally evidenced |
| Synthetic fixtures represent broker history | rejected | Fixtures may prove mechanics only |
| Current screenshots or timestamp patterns establish historical schedules | rejected | Never admissible evidence |

## Architecture Impact

**Architecture impact**: none  
**Rationale**: the sole touchpoint extends the documentation knowledge base; no code module, dependency, ownership boundary or baseline component changes. The ADRs constrain a future change rather than establish a runtime boundary now.

## Open Questions and Executor Notes

**Blocking questions**: None for this dormant contract.  
**Executor-local notes**: The future activation change owns canonical schema/order, hashes, typed errors, boundary semantics, manifest-v2 discriminator and exact test paths.  
**Build preflights**: None; real data and external broker evidence are prohibited in this change.

## Sensitive Areas Crosscheck

No registered sensitive behaviour is altered. `detector/runner/preflight.py` and adapter data surfaces are future read-only touchpoints, not File Changes. Any activation would alter fail-closed admission and therefore requires sensitive re-triage before design.
