# Trusted Closure Classification

## Scope

Define a dormant, fail-closed contract for recognising an expected market closure. This specification does not activate runtime behaviour or assert any real broker history.

## Requirements

### REQ-01 — Preserve current validation until activation

The current validator MUST keep its existing outcome for every gap until a separately authorised activation exists. Evidence-only planning artifacts MUST NOT unblock current preflight.

#### Scenario: Evidence-free gap remains blocked

Given current validation encounters an evidence-free gap, when preflight runs without a separately authorised activation, then the gap remains unresolved and preflight remains blocked.

### REQ-02 — Admit only verifiable closure evidence

A future policy MUST classify a missing interval as an expected closure only when admissible evidence accounts for it. Evidence MUST be rejected when it is timestamp-only, lacks retained original bytes or a matching hash, has unverifiable or conflicting provenance/attestation, is malformed, or identifies the wrong broker, server/account, instrument, or granularity. Rejected evidence MUST leave the interval an unresolved data gap.

#### Scenario: Invalid evidence fails closed

Given candidate evidence has any listed defect, when a future policy assesses the corresponding interval, then it is not accepted as an expected closure.

### REQ-03 — Require complete, non-conflicting coverage

Completeness MUST be measured against an independently supplied, authoritative closure universe for the exact instrument and granularity across the inclusive window 2022-08-08 through 2026-08-19; evidence MUST NOT define its own expected set. Future closure evidence MUST account for every closure in that universe. Partial coverage, uncovered intervals, overlapping or conflicting claims MUST fail closed as unresolved gaps. The future evidenced-closure authority MAY classify only intervals within that declared inclusive historical window; intervals outside it MUST remain unresolved unless a separately authorised change declares another complete applicability window.

#### Scenario: Almost-complete evidence is insufficient

Given an evidence set omits or conflicts on one interval from the independently supplied authoritative closure universe, when coverage is evaluated, then the set is rejected and no omitted interval is accepted.

## Out of scope

Real broker-history acquisition or evaluation; detailed evidence schema, canonical ordering, hash algorithm, error taxonomy, and `gap_end` hardening.

## Test derivation

Use deterministic synthetic evidence only. Tests MUST cover valid complete evidence, each rejection defect, an entirely uncovered window, and an almost-complete window; assertions MUST verify unresolved-gap results rather than merely an error.
