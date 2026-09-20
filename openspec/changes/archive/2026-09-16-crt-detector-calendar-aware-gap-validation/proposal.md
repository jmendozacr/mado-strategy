# Proposal: Calendar-Aware Dataset Gap Validation

## Intent

Define a dormant fail-closed contract for classifying evidenced closures without fabricating broker history. Current preflight remains blocked because evidence is insufficient.

## In Scope

- Define admissible evidence and complete coverage for 2022-08-08 through 2026-08-19 inclusive.
- Define fail-closed outcomes for absent, incomplete, conflicting, or unverified evidence.
- Require one approved gap authority per instrument/granularity, with replacement and no fallback.
- Preserve current behavior; describe a separately authorised future activation boundary.
- Reconcile stale planning claims with the dormant, evidence-limited status.

## Out of Scope

- Runtime or frozen manifest/protocol/B/A/dataset/test changes.
- Historical Exness calendar construction, evidence acquisition, activation, or real-data acceptance.
- Timestamp or current-screenshot inference; non-UTC, DST, seasonal, or cross-midnight machinery.
- `gap_end` hardening, which remains a separate follow-up.

### Scope Admission

| Discovery | Admission | Destination |
|---|---|---|
| Only fully evidenced closures may excuse gaps | product-guarantee | Scope and capability |
| Complete verified authorised-window coverage | safety-guarantee | Scope and capability |
| One authority; no coexistence or fallback | safety-guarantee | Scope and capability |
| Future manifest-v2 semantics and canonical identity | design-control | Approach/ADRs |
| Synthetic deterministic examples | test-evidence | Success criteria |
| `gap_end` enforcement | follow-up | Out of scope |
| Historical inference or evidence acquisition | reject | Out of scope |

## New and Modified Capabilities

### New Capabilities

- `trusted-closure-classification`: Excuses gaps only with fully admissible evidence.
- `exclusive-gap-authority`: Allows one approved gap policy per instrument/granularity.
- `controlled-calendar-activation`: Keeps validation unchanged until separate approval.

### Modified Capabilities

None.

## Approach

Specify evidence admissibility, canonical identity, coverage, conflicts, and fail-closed outcomes. Describe manifest-v2 as a future binding, not a migration. Design formalises evidence identity, exclusive transition, and activation lineage. Activation requires approval, new B/A, baseline refresh, and sensitive re-triage.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| Proposal/spec/design artifacts | New | Dormant semantic contract |
| `detector/adapter/{dataset,manifest}.py` | Read-only | Future policy boundary |
| `detector/runner/{preflight,manifest_builder,serialization}.py` | Read-only | Future gate and hashing |
| `detector/tests/` | Read-only | Future synthetic evidence |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Contract mistaken for operational support | Medium | State dormancy and blocked preflight |
| Fixtures mistaken for broker truth | Medium | Require hashes, verification, and full coverage |
| Dual authority weakens fail-closed behavior | Medium | Require replacement; forbid fallback |
| Activation changes frozen lineage | Low | Require approval, new lineage, refresh, re-triage |

## Rollback Plan

Withdraw this proposal and downstream references to its three capabilities. Confirm the current allowlist, manifest, protocol, B/A, datasets, runtime, and tests are unchanged and evidence-free gaps still fail preflight. No runtime state or user data needs recovery.

## Dependencies

- Current dormant contract: none.
- Future activation: admissible archived broker/server evidence with original bytes, hashes, human verification, and complete authorised-window coverage.

## Success Criteria

- [ ] Current manifest, protocol, B/A, datasets, runtime, and tests remain byte-identical.
- [ ] Current preflight remains blocked for evidence-free gaps, including DXYm/D1.
- [ ] No real dataset or historical closure is accepted by this change.
- [ ] Evidence rules require original bytes, hashes, human verification, and complete inclusive-window coverage.
- [ ] Exactly one gap authority is permitted per instrument/granularity, with no fallback.
- [ ] All acceptance examples are synthetic and claim no Exness or historical truth.
- [ ] `gap_end` hardening and activation remain explicit separate follow-ups.
- [ ] Future activation requires separate approval, new lineage/B/A, baseline refresh, and sensitive re-triage.
