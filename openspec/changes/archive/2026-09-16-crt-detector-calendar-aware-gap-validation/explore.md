# Exploration: Calendar-Aware Dataset Gap Validation

**Triage**: L  
**Persona lens**: council synthesis

## Cross-Change Lessons Consulted

- Decisions #656 and #657: the historical Exness schedule is not sufficiently auditable; timestamp patterns do not establish broker truth. No relevant pattern or bugfix memory was found.
- CodeGraph was unavailable; council-supplied line evidence was used.

## Affected Flows

| Flow | Current E2E spec | Expected action |
|---|---|---|
| Discovery | none found | Modify |
| Preflight | none found | Modify |
| Dataset validation | none found | Modify |
| Stop/proceed decision | none found | Modify |

The flow is `run_discovery()` -> preflight -> dataset validation -> stop or proceed. This amendment authorises neither implementation nor a changed outcome.

## Current State (A2)

`run_discovery.py:71` preflights before processing; failure stops downstream work (`test_runner_discovery.py:273`). `dataset.py:81,94` allows starts only through the immutable exact allowlist; `gap_end` and reason are not enforced. The builder emits an empty allowlist (`manifest_builder.py:274`), so ordinary closures fail. Canonical bytes use sorted, compact UTF-8 JSON with a trailing newline (`serialization.py:24,53`).

## Architecture Touchpoints (A3)

| Layer/Component | Action | Why | Baseline fit |
|---|---|---|---|
| `adapter.manifest` | extend (future v2 only) | evidence-policy binding | aligns |
| `adapter.dataset` | extend (future) | deterministic validation | aligns |
| `runner.preflight` | extend (future) | fail-closed admission | aligns |
| `runner.serialization` | reuse (future) | canonical hashing | aligns |

The inert contract has no deviation. A calendar subsystem now would deviate and is rejected.

## Affected Areas (A4)

| Path | Impact | Why |
|---|---|---|
| `detector/runner/run_discovery.py` | Read-only | preflight gate |
| `detector/runner/preflight.py` | Read-only | validation sequence |
| `detector/adapter/dataset.py` | Read-only | allowlist authority |
| `detector/adapter/manifest.py` | Read-only | frozen fields |
| `detector/runner/manifest_builder.py` | Read-only | empty allowlist |
| `detector/runner/serialization.py` | Read-only | canonical hashing |
| `detector/tests/test_adapter_dataset.py` | Read-only | adapter coverage |
| `detector/tests/test_runner_preflight.py` | Read-only | integration gap |

## Sensitive Areas Crosscheck

This amendment is sensitive-adjacent: no protected decision changes. Future activation changes fail-closed preflight admission and needs separate sensitive re-triage and human authorisation.

## Approaches

### 1. Inert, append-only evidence contract

**Description**: Define a `ClosureEvidenceRecord` registry outside the current Manifest, protocol, and A/B lineage. Evidence IDs hash canonical claims; raw-source hashes remain distinct. Keep the exact allowlist operative.

**Pros**: preserves frozen contracts and fail-closed behaviour; supports deterministic mechanics without claiming external truth.  
**Cons**: does not unblock current real-data preflight.  
**Effort**: Low  
**Pattern fit**: matches immutable, hash-bound manifest/serialization practice.

### 2. Activate a calendar in the current manifest

**Description**: add optional calendar references or an active flag to current validation.

**Pros**: could unblock validation if evidence existed.  
**Cons**: changes frozen lineage and admission policy; fallback risks two authorities; evidence is insufficient.  
**Effort**: High  
**Pattern fit**: conflicts with the frozen-contract boundary.

### 3. Harden `gap_end` now

**Description**: make allowlist boundary metadata normative.

**Pros**: independently strengthens the existing mechanism.  
**Cons**: unrelated to proving closures and requires its own acceptance scope.  
**Effort**: Medium  
**Pattern fit**: local, but separate from this amendment.

## Recommendation

Adopt approach 1 only: a dormant, implementation-ready evidence contract. It does not unblock present data, activate a calendar, or modify the protocol, current manifest, B/A, datasets, tests, or validator. Activation must use manifest-v2, new lineage/B/A, evidence, sensitive re-triage, and human approval; it replaces the allowlist so each pair has one authority. Keep `gap_end` hardening separate.

## Risks

- Empty allowlists make closures fail: this is not an immediate operational fix.
- Fixtures prove deterministic mechanics, not Exness history: require authoritative evidence before activation.
- Dual authority/fallback would weaken fail-closed validation: require replacement and no configured-evidence fallback.

## Resolved Product Decisions

The human ratified the following package on 2026-09-16:

1. This change delivers a dormant, implementation-ready contract and does not unblock current preflight.
2. Future authority requires archived broker evidence or contemporaneous server/account records with original bytes, hashes, human verification, and complete authorised-window coverage.
3. Future activation replaces the allowlist per instrument/granularity; coexistence and fallback are forbidden.
4. `gap_end` hardening is a separate follow-up.
5. A future manifest-v2 contract may be described, but current manifest/protocol/B/A and datasets remain unchanged; activation requires separate authorisation and sensitive re-triage.

## Open Questions

- type: technical  
  question: "What are the canonical claim schema and field ordering, registry granularity, typed errors, boundary semantics, and manifest-v2 discriminator?"  
  why_it_matters: "These define deterministic future validation without activating it."

## Ready for Proposal

**Status**: yes  
**Reason**: the human ratified all product decisions; remaining questions are technical and belong in specification/design.  
**Recommended action**: proceed to `sdd-propose` for the inert contract only.
