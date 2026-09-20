# Exclusive Gap Authority

## Scope

Define the future authority-selection rule for an instrument/granularity pair. This contract is dormant and does not modify the current manifest, protocol, datasets, or runtime.

## Requirements

### REQ-04 — Exactly one authority with replacement

For each instrument and granularity, future validation MUST use exactly one approved source of gap decisions. When an evidenced-closure authority is activated for a pair, it MUST replace the legacy exception authority for that pair only within its declared complete applicability window. For intervals outside that window, the evidenced-closure authority MUST leave the interval unresolved unless a separately authorised change declares another complete applicability window. Authorities MUST NOT be unioned, layered, or used as fallback.

#### Scenario: Activated authority is exclusive

Given an evidenced-closure authority is separately activated for a pair, when a gap is assessed, then only that authority decides the result and the legacy authority is inapplicable.

#### Scenario: No activated calendar preserves legacy authority

Given no evidenced-closure authority is activated for a pair, when a gap is assessed, then the existing exception authority remains the sole authority.

#### Scenario: Selected authority cannot justify a gap

Given the selected authority cannot justify a missing interval, when validation assesses it, then the interval remains unresolved and no other authority is consulted.

## Out of scope

Manifest-v2 field design, registry implementation, runtime wiring, migration, and changes to the current allowlist.

## Test derivation

Synthetic tests MUST prove replacement, no coexistence, no fallback, and pair-specific instrument/granularity selection. Mutating a sole-authority decision to consult a second source MUST fail the tests.
