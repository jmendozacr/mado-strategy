# Controlled Calendar Activation

## Scope

Define governance and lineage gates for any future activation. This change remains documentation-only; no activation is authorised by signing this specification.

## Requirements

### REQ-05 — Separate activation and renewed lineage

An evidenced-closure authority MUST remain inert until a separate activation is explicitly authorised. Activation MUST require admissible complete evidence from REQ-02 and REQ-03, including its declared complete applicability window, newly recorded lineage, refreshed architecture/baseline review, and sensitive-area re-triage before any runtime or preflight outcome can change. Without all gates, real historical closures MUST NOT be accepted.

#### Scenario: Planning artifacts do not activate behavior

Given synthetic evidence and a drafted authority exist but no separate activation is authorised, when current preflight runs, then its existing outcome is unchanged.

#### Scenario: Incomplete activation remains inert

Given an activation proposal lacks complete evidence, new lineage, baseline refresh, or required re-triage, when activation is considered, then it is rejected or remains inert and no real closure is accepted.

#### Scenario: Fully gated activation changes only its pair

Given separate approval and all required gates are recorded, when the authority is activated for one instrument and granularity, then only that pair may use the newly approved authority and all other pairs retain their existing authority.

## Out of scope

Obtaining broker calendars; inspecting, hashing, or executing real CSV/OHLC data; changing B/A, frozen protocol, manifest, datasets, or current tests; implementing activation; `gap_end` hardening.

## Test derivation

Synthetic acceptance MUST prove dormant behavior, rejection of missing gates, pair isolation, and preservation of current outcomes. No test may represent synthetic fixtures as real broker history.
