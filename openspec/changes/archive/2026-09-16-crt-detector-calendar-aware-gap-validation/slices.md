# Slices: Calendar-Aware Dataset Gap Validation

**Triage**: L  
**Spec version**: V1 (signed)  
**Design version**: V1 (dormant documentation-only contract)  
**Total slices**: 1 (1 walking skeleton + 0 SPIDR)

---

## S-000: Approve the dormant evidence contract

**Scope**: walking-skeleton  
**Dimension**: —  
**Covers**: REQ-01, REQ-02, REQ-03, REQ-04, REQ-05  
**Requires**: nothing  
**Test layers**: approval review + repository-diff preservation check

**Demo**: A reviewer can verify that the signed contract preserves blocked preflight, rejects unevidenced closures, forbids dual authorities, and reserves activation for a separately authorised change.

**Acceptance**:
- GIVEN the signed V1 specs and design, WHEN the slice is reviewed, THEN all five requirements are traceable to a dormant, fail-closed contract.
- GIVEN the change diff, WHEN preservation is checked, THEN no runtime, manifest, protocol, dataset, B/A, or test path has changed and evidence-free gaps remain governed by current validation.
- GIVEN a proposed future activation, WHEN it lacks separate approval, admissible complete evidence, new lineage, baseline refresh, or sensitive re-triage, THEN this change provides no authority to accept a real closure.

### Tasks
- [x] S-000.1 Review signed REQ-01–05 against the proposal and design.
- [x] S-000.2 Confirm the future authority is exclusive per instrument/granularity and has no fallback.
- [x] S-000.3 Inspect the change diff for the documented no-runtime-drift boundary.
- [x] S-000.4 Record approval evidence through final verification; do not create or run real-data tests.

---

## Distribution

| Scope | Count | Slice IDs |
|---|---:|---|
| walking-skeleton | 1 | S-000 |
| happy-path | 0 | — |
| edge-case | 0 | — |
| spike | 0 | — |
| **Total** | **1** | **S-000** |

## SPIDR Dimensions Used

| Dimension | Count |
|---|---:|
| Path | 0 |
| Interface | 0 |
| Data | 0 |
| Rule | 0 |
| Spike | 0 |

## Build Order

1. S-000 — the entire authorised change. No further implementation slice exists because the signed design intentionally authorises no runtime behaviour.

## Anti-Pattern Check

Pass — one approval-testing walking skeleton is appropriate for a documentation-only, dormant contract. No horizontal work, invented implementation, standalone cleanup, or untraceable slice was introduced.

## Upstream Publication

N/A — `spec_source` is internal.
