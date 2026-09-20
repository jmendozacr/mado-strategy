# North Star: Calendar-Aware Gap Validation

**Checkpoint**: foresight  
**Verdict**: aligned, pending human significance ratification

## Intent

Establish a safe, dormant contract for a future calendar-aware gap authority without claiming broker history the repository cannot prove. Until a separately authorised activation has complete admissible evidence and renewed lineage, current fail-closed preflight behaviour remains unchanged.

## Problem Fit

The design addresses the unsafe choice created by the current pain: it defines how legitimate closures could eventually be recognised without weakening validation or fabricating historical truth. It deliberately does not remove today's DXYm/D1 preflight block. That operational relief is deferred because the required broker evidence is not owned.

The design is the shortest safe path to the stated outcome now: preserve current behaviour and record the evidence, exclusivity, and activation boundaries. Runtime code, a calendar subsystem, inferred schedules, and synthetic claims of broker truth would add work without safely resolving the evidence gap.

## Architectural Fit

This change extends only the repository documentation knowledge base. It leaves the detector's layered pipeline, manifest and serialization practices, datasets, lineage B/A, and exact-allowlist runtime authority unchanged. A future activation would introduce pair-scoped authority selection at dataset validation and must refresh the architecture baseline before approval.

## Pre-Archive Commitments

Reckoning can evaluate that:

- the signed specification and design consistently describe a dormant, fail-closed contract;
- no file under `detector/`, frozen protocol or manifest, dataset, or lineage B/A is changed;
- no real historical closure or synthetic fixture is represented as broker truth;
- exactly one future authority is required per instrument/granularity, with replacement and no fallback;
- activation remains a separate authorised change with complete evidence, new lineage, baseline refresh, and sensitive-area re-triage.

## Deferred Outcome

The user's blocked preflight can improve only at the separately authorised activation, not when this documentation-only change closes. At that activation, verify that complete retained broker/server evidence covers the inclusive 2022-08-08 through 2026-08-19 window, evidence identity and hashes validate, the approved authority exclusively replaces the legacy authority for its pair, renewed lineage and architecture review exist, and the intended real-data preflight outcome changes without weakening unresolved-gap rejection.

## Conscience Question

Human ratification required before slicing: **Is preserving this evidence and activation boundary worth completing as a durable contract now, even though it intentionally leaves the current DXYm/D1 preflight blocked until a separately authorised, evidenced activation?**

