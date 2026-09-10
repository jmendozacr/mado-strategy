# Status close-out — `crt-detector-direction-policy`

**Status**: closed — V1 implementation complete.

- spec commit: `13184cbf0329f25c242e9632409194e4d052648a`
- implementation commit: `7b09c31877a5e5978e10b6832f5b7f3010276f1d`

Quality gates green: 566 passed, 1 pre-existing unrelated failure
(`test_alignment_detection_has_no_lookahead`, same assertion/location as the
failure already known before this change — reconfirmed unchanged, not
touched). `lint-imports`: 3 kept, 0 broken.

Pre-commit consistency audit found and fixed one BLOCKER (negative-cutoff
domain gap — `cutoff_index < 0` was not actually covered by the `>= 1`
branch as an earlier report claimed) before this close-out. No policy
arbitration semantics changed as a result; all 6 pairwise policy
differences and all 6 `DirectionReason` values were re-verified under the
corrected domain.

**FOUR POLICY HYPOTHESES: IMPLEMENTED, TESTED, NO OUTCOMES INSPECTED.**

```
direction_policy_structural_priority_v1
direction_policy_corroboration_v1
direction_policy_noncontradiction_v1
direction_policy_bias_veto_v1
```

These four policy IDs are frozen. No semantic change under any of them is
permitted once a discovery comparison has inspected outcomes — a future
revision needs a new id/version.

No winner chosen. No discovery run. No outcome, backtest, prevalence, win
rate, MeanR, PF, or market dataset was inspected at any point in this
change's spec, implementation, or close-out.

Next DIRECTION-dimension work is a separate thread: pre-registering the
DirectionPolicy discovery comparison protocol (not running it). DOLPolicy
and KeyLevelPolicy remain untouched, unopened.
