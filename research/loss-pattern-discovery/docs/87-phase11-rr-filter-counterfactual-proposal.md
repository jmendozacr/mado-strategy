# Phase 11 — RR 2.0 Filter Counterfactual Research Proposal

**Status: registered, NOT executed.** No code in this document's scope ran as part of Phase 10.
`min_risk_reward=2.0` was not changed anywhere in the repository. No new backtest ran. This is a
proposal only, per the Phase 10 brief's explicit instruction.

## Question

Does the Stage-6 RR floor (`min_risk_reward=2.0`, applied by `backtest.population._rr_floor_cut`)
discard opportunities that would have contributed positively to the system's economic performance,
or does it correctly filter out unfavorable setups? Phase 9 established that this single rule
accounts for 100% of Stage-6 attrition, both models, all three pairs: 1,087 of 1,805 confirmed
1AM signals (60.2%) and 1,505 of 3,311 confirmed 9AM signals (45.5%) -- 2,592 total confirmed
signals never became candidates, solely because of this one threshold.

## Hypotheses (to be pre-registered formally, with directionless framing, before Phase 11 runs)

- The discarded population's expected economic contribution is net negative (the filter is
  correctly protective).
- The discarded population's expected economic contribution is net positive (the filter discards
  value).
- The discarded population's contribution is heterogeneous by model/instrument/period (no single
  verdict applies uniformly).

## Sources

- `trades_d3_c2_2015plus_run2.csv` (read-only, unchanged) for the existing executed-trade ledger.
- `backtest/population.py::_rr_floor_cut`, `backtest/levels.py::risk_reward` (read-only) -- the
  EXACT RR formula must be re-verified (Unit I item 1 below) before any distributional claim about
  the 2,592 discarded signals' own RR values.
- `backtest/simulate.py::_resolve_exits`/`fill_pass_c` (reused unmodified, never a second
  implementation) for any contrafactual fill/outcome simulation, if and when authorized.

## Risks of bias (named upfront)

- **Survivorship/selection bias**: the 2,592 discarded signals never passed Stage 6, so they have
  no observed fill, entry, or outcome. Any economic claim about them requires a genuine
  contrafactual simulation (same engine, same rules, only the RR floor removed) -- never an
  extrapolation from the EXECUTED population's own historical win rate.
- **Fill-eligibility bias**: a signal clearing the RR floor does not guarantee it would have
  received a fill under the exact same causal fill rules (`fill_pass_c`) -- "candidate" and
  "filled" are materially different denominators (Phase 8's own finding).
- **Look-ahead risk in any contrafactual**: a counterfactual RR floor of e.g. 1.5 or 1.0 must be
  chosen BEFORE seeing that threshold's own resulting P&L -- a threshold search that tries many
  values and reports the best one is exactly the kind of post-hoc fishing this lab has refused
  since Phase 1.
- **Already-examined history**: 2015-2026 remains previously examined by this lab; nothing here
  would constitute genuine out-of-sample validation without a new temporal holdout.

## Recommended design (for Phase 11, if and when authorized)

1. Verify the exact RR formula `_rr_floor_cut`/`backtest.levels.risk_reward` uses -- raw planned
   reward-to-risk, or cost-inclusive -- before any claim about "RR < 2.0" populations.
2. Recover the full RR distribution of the 2,592 discarded confirmed signals (planned, pre-order
   quantities only -- never a result).
3. Explicitly distinguish: confirmed -> candidate-rejected (by RR) -> would-be-candidate -> would
   receive a fill (under the SAME `fill_pass_c` causal rules) -> executed. Each stage needs its
   own, separately reported denominator.
4. Verify the rejected signals carry sufficient causal data (entry geometry, stop/target, bar
   series) to construct a reproducible counterfactual at all -- report explicitly if some do not.
5. Reuse the SAME corrected D3/C2 engine, including `fill_pass_c`, byte-for-byte.
6. Hold every other rule fixed (entry type/price, Stop Loss, Take Profit, partial management,
   breakeven, trading costs, gap handling) -- vary ONLY the parameter under investigation.
7. Pre-register any threshold comparison (e.g. "RR >= 1.5" vs. the current "RR >= 2.0") BEFORE
   running it -- never a sweep that reports the best-performing threshold found after the fact.
8. Evaluate net profitability, trade frequency, exposure, drawdown, inter-trade dependence, and
   temporal stability -- never win rate alone.
9. Separate the effect of ACCEPTING MORE SIGNALS from the effect of a RISK-MANAGEMENT change --
   these are two different mechanisms a single RR-floor change would conflate if not designed to
   isolate them.
10. Design a genuinely independent temporal holdout for any performance claim -- 2015-2026 is not
    out-of-sample for this lab; a new validation window (or a formally pre-registered embargo
    scheme) is required before any forward-looking claim.

## Fundamental rule (restated, binding on Phase 11)

The 2,592 discarded signals are not 2,592 lost trades. They may not have received a fill. Their
win/loss outcome is unknown. **No rentability figure for this population may be computed by
inventing executions** -- any economic evaluation requires an authorized, reproducible,
causal counterfactual simulation, run under its own separate authorization, never assumed from
this proposal document alone.

## Validity criteria (for a future Phase 11 verdict)

- Every counterfactual number must reconcile against the real, unmodified ledger and funnel counts
  wherever they overlap (the executed-trade population is a shared boundary condition).
- Any RR-floor variant tested must use the SAME fill/exit engine, unmodified, with an equivalence
  test proving so -- the same discipline this lab has required since Phase 8.
- No conclusion may describe a backtested RR variant as "the new system" or "operable" -- only as
  a research finding about a counterfactual population, pending further validation.

## Conditions to begin

Explicit user authorization naming Phase 11 specifically, after this proposal (and any
amendments the user requests) is reviewed -- consistent with this lab's standing charter that no
phase begins without that authorization, and this phase's own closing instruction to register,
not execute, this investigation.
