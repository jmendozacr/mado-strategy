# Deliverable D — Failure Mechanism Explanation

## Is the Phase-4 path-integrity gap mechanical?

**Yes, confirmed exactly, not approximately.** `stats.early_stop_hypothesis.duration_explains_integrity`
recomputed `same_or_next_bar` for all 1262 confirmed-stop losses and compared it directly against
Phase 4's own `integrity != RECONSTRUCTIBLE` flag: **0 mismatches out of 1262**. The two are the
exact same fact, computed two different ways:

| | 9AM | 1AM |
|---|---|---|
| Phase 4: `ambiguous` + `insufficient` (of confirmed stops) | 15.3% | 31.2% |
| Phase 5: `same_or_next_bar` (of confirmed stops) | **15.33%** | **31.2%** |

**Phase 4's path-integrity metric was never independent information beyond duration -- it is
`duration_bars <= 1`, restated.** This directly confirms the exact explanation the brief itself
offered as a candidate: "El modelo 1AM tiene más Stop Loss tempranos y por eso presenta más
trayectorias no reconstruibles en M15." That explanation is correct as far as it goes.

## But the duration difference itself is not explained by risk sizing

Confirming the mechanical link does not make the underlying difference uninteresting -- it just
relocates the question from "why is 1AM's path-reconstruction rate different" (answer: because its
trades resolve faster, trivially) to "why do 1AM's trades resolve so much faster" (unanswered).
`docs/32-...` already showed this faster-resolution tendency survives `risk_atr` standardization.
`docs/30-...` showed it holds across BOTH wins and losses (median 6 vs. 21 bars), not just confirmed
stops -- so it is a property of the model's overall tempo, not specifically of its failures.

## What this phase does NOT claim

This is a restatement-and-persistence finding, not a causal one (section 11 of the brief). `risk_atr`
was the one candidate tested; `cost_to_risk_ratio` (also higher for 1AM, `docs/30-...`) and the
model's own feeder-candle/confirmation-window construction (not inspected this phase) remain
untested candidate explanations for a future unit.
