# Outcome Verdict: Calendar-Aware Gap Validation

**Checkpoint**: reckoning  
**Verdict**: delivered-pending-activation

## Objective Revisited

The stated problem is that fixed-cadence validation treats legitimate market closures as missing data, blocks statistical-runner preflight including DXYm/D1, and leaves no safe way to distinguish closures without weakening validation or inventing broker history.

The North Star committed this change to a narrower outcome: establish a durable, dormant, fail-closed contract for a future calendar-aware authority while leaving current runtime behaviour and the blocked preflight unchanged until admissible evidence and renewed lineage exist.

## Delivered Result

The documentation-only result delivers that dormant contract. Final verification found that the signed requirements consistently preserve evidence-bound closure classification, exclusive authority selection without union or fallback, and a separately authorised activation gate. It also found no changes to runtime code, manifests, protocols, datasets, lineage B/A, or tests, and no representation of synthetic fixtures or timestamp patterns as broker truth.

This resolves the immediate governance problem: the repository now has a safe contract for how legitimate closures may eventually be recognised without fabricating historical truth or weakening unresolved-gap rejection. It does not resolve the operational pain today: DXYm/D1 preflight remains blocked by design.

## Promise-to-Delivery Drift

None detected. The North Star explicitly promised a dormant documentation contract rather than runtime relief, and the delivered result matches that boundary. Final verification appropriately limits its pass to contract and preservation evidence and does not claim implementation or behavioural proof.

## Deferred Outcome

**Deferred until**: a separately authorised activation change obtains complete admissible broker/server closure evidence for the inclusive 2022-08-08 through 2026-08-19 window and completes the required lineage, architecture, and sensitive-area gates.

At activation, check that:

- retained evidence identity and hashes validate and cover the complete inclusive window;
- the approved authority exclusively replaces the legacy authority for the activated instrument/granularity, with no union or fallback;
- renewed lineage and architecture review exist and sensitive-area re-triage has completed;
- the intended real-data preflight becomes usable for legitimate closures;
- unresolved or unjustified gaps still fail closed;
- no synthetic fixture or timestamp pattern is treated as historical broker truth.

Register one `outcome-check` follow-up in `project/pending-changes` so this outcome is reassessed after activation.

## Conscience Questions

Human confirmation is required before archive:

1. Is the delivered dormant contract usable by the people who must plan and approve the future activation, despite providing no practical DXYm/D1 preflight relief today?
2. Do you accept archiving this change with the operational problem explicitly still open until the evidence-backed activation and outcome check occur?

## Reckoning

All pre-archive-evaluable commitments pass. The delivered result is honest and internally useful as a future activation contract, but the user-facing outcome remains pending activation. Archive may proceed only after the human engages with the usability questions and the deferred outcome check is registered.
