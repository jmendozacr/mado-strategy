# Apply Progress: crt-detector-order-flow

**Spec version applied**: V1 (signed, then corrected once pre-commit — see `spec.md` Revision History for REQ-OF-09).

## Implementation evidence — TDD process, stated exactly as it happened

**Fundamental behavior (REQ-OF-01, bullish and bearish)**: genuine red → green. The module started as a stub raising `NotImplementedError`; both fundamental tests were confirmed failing (red) before the algorithm was written; both passed (green) once the full two-phase, per-direction state machine was implemented.

**Not claimed**: this was NOT "19 independent red→green cycles," one per requirement. It didn't happen that way, and saying so would misrepresent the process. What actually happened: REQ-OF-01's own happy path already required the complete algorithm (reference selection, unbroken tracking, per-direction pending state, two-phase precedence) to pass at all — there was no smaller correct implementation to red-test incrementally against for the remaining requirements.

**What the remaining 19 tests (REQ-OF-01.2 through REQ-OF-09) actually are**: a **behavior-fixation suite** written against the already-passing implementation, each test targeting one specific requirement's scenario (see `spec.md`'s Given/When/Then for the exact scenarios). Confidence that each test genuinely exercises its requirement — rather than passing vacuously — comes from **mutation verification**, not from having watched each one go red first:

| Mutation applied | Test(s) that caught it |
|---|---|
| Recency-based reference selection → magnitude-based | `test_most_recently_confirmed_swing_governs_over_more_extreme_ancient_one` (fails: wrong reference selected) |
| Correct-side guardrail removed | No test failed (confirms REQ-OF-02.2 is redundant-but-harmless, per `spec.md`'s note — not a gap) |
| Both invalidation branches disabled | Both `test_*_candidate_invalidated_by_close_back_through_rejection_reference` tests fail (spurious event) |
| Phase 2 (new rejection) moved before Phase 1 (resolution) | `test_same_candle_resolves_existing_candidate_before_creating_a_new_one` fails |

Each mutation was applied, the specific test(s) confirmed failing, then reverted — this is the evidence that the fixation suite is load-bearing, not decorative.

**REQ-OF-09's own test** (`test_opposite_direction_events_never_share_a_confirmation_index`) was added in a follow-up pass, after the spec was corrected (see `spec.md` Revision History) — it is a genuine property invariant (2000 Hypothesis examples), not a fixation test, since REQ-OF-09 has no positive case to fixate against.

## Quality gates (final, before commit)

```
detector/tests/test_order_flow.py         21 passed
detector/tests/property/test_no_lookahead.py  (order-flow-relevant subset included)
full suite                                 331 passed, 1 pre-existing unrelated failure
                                            (test_alignment_detection_has_no_lookahead — registered, not touched)
lint-imports                               2 contracts kept, 0 broken
type-checker                               none configured in this project (confirmed, not applicable)
```

## Status

Implementation complete, spec-conformant (post-correction), ready for commit as two separate commits (spec, then implementation) per explicit instruction.
