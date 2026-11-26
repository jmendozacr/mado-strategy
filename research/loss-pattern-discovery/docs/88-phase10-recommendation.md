# Deliverable I — Recommendation

## Options considered

A. A further, out-of-sample validation of the confirmation-path association found in 9AM.
B. The Phase 11 RR 2.0 filter counterfactual investigation (registered in `docs/87`, not run).
C. A correction to this phase's own causal reconstruction.
D. Closing the confirmation-path hypothesis as not worth further investment.

## Recommendation: **Phase 11 (B) is the single priority next unit.**

**Option C does not apply**: every equivalence test in this phase passed (Deliverable B), coverage
was 100% (Deliverable C), and the one identity reconciliation gap found in Phase 9 (`signal_id`
collisions) does not affect `stable_id`-keyed joins, which this phase used exclusively. There is
no known reconstruction defect to correct.

**Option A is not the priority**, even though `MODEL_SPECIFIC_ASSOCIATION` is a genuine, non-null
finding, for a concrete, numeric reason: Deliverable G's own honest effect-size characterization
shows NEITHER model's point difference (1AM +1.11pp, 9AM +3.39pp) clears this lab's own 5pp
relevance bar (Phase 5's pre-registered minimum economically meaningful difference). Investing a
dedicated out-of-sample validation phase in a statistically-real-but-below-the-relevance-bar
association has a lower expected payoff than resolving a question that affects a MUCH larger share
of the funnel.

**Option D is premature**: the association is real in 9AM and directionally consistent everywhere
checked -- "not worth further investment NOW, given a higher-priority alternative" is different
from "closed." This phase does not close the hypothesis; it deprioritizes it relative to B.

**Why B wins**: the Stage-6 RR floor (`min_risk_reward=2.0`) is, by construction (Phase 9), 100%
of Stage-6 attrition, discarding 2,592 of the 5,116 confirmed signals (60.2% of 1AM's, 45.5% of
9AM's) -- an order of magnitude larger share of the funnel than the confirmation-path contrast
touches. Whether that filter discards economic value or correctly protects against unfavorable
setups is a question this lab has never yet investigated, the user has EXPLICITLY requested it be
prioritized, and its answer could materially change how much of the funnel the system is even
allowed to consider -- a far larger-scope question than refining the confirmation-path finding.

## What NOT to do next

Do not begin Phase 11's execution from this recommendation alone -- `docs/87` is a proposal, and
this phase's own closing instruction is to register it, not run it. Do not retroactively use this
phase's `MODEL_SPECIFIC_ASSOCIATION` finding as a filter or feature in any system -- it remains an
association within the already-selected executed population, per Deliverable G's own explicit
disclaimers.
