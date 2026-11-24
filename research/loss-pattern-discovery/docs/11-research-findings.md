# Deliverable E — Research Findings (Phase 2)

Per the user's explicit instruction, separated into five categories. **No exploitable advantage is
declared anywhere in this document.**

## Confirmed observations (high confidence, grounded in code/data, not just a backtest number)

1. **99.4% of the 1265 losses in the primary source are genuine, code-grounded Stop Loss executions**
   (`confirmed_stop_event`, 0.98 classifier confidence) — the Phase-2 premise question ("¿las pérdidas
   equivalen a SL ejecutados?") has a confident YES for this source, with the small remainder (0.2%
   ambiguous, 0.3% open-censored) explicitly separated out, never pooled in.
2. **`stop_after_partial_exit` is empirically ~0 for this source**, and this is explained, not a
   defect: `breakeven_after_partial=True` (a per-symbol production config, confirmed by code+config
   inspection, not assumption) means a partial-exit trade's worst case is only the trading cost at
   breakeven — arithmetically close to impossible to net to an overall loss given this reward
   structure.
3. **Price recovers to the original entry level after a stop-loss far more often, and far sooner,
   than intuition might suggest**: 25.4% within 1 hour, 48.7% within 4 hours, 75.4% within 1 day,
   85.4% within 3 days (all 90% CIs tight, n=1262). This is a robust, high-n descriptive fact about
   this dataset's stop-outs.

## Descriptive regularities (real patterns in this data, not yet tested against anything)

4. Across all four horizons (1h/4h/1d/3d), **price is modestly more likely to extend the move that
   caused the stop-loss (continuation) than to reverse back** — roughly 55-56% continuation vs.
   43-44% reversal, essentially flat across horizons (no meaningful change from 1h to 3d).
5. **The 1am session's post-stop excursions are materially larger and its recovery-to-entry rate
   materially higher than the 9am session's** (MAE 3.18R vs. 2.05R at 1d; recovery 88.0% vs. 70.0%),
   with clearly non-overlapping CIs — the one stratified cut in this phase with a result that is not
   just overlapping-CI noise.
6. Behavior is reasonably stable across the three pairs and across original direction (bullish vs.
   bearish) — no pair or direction stands out with a non-overlapping CI from the others.

## Hypotheses for a future phase (not evaluated here, explicitly deferred)

7. **Why does the 1am session show larger excursions and higher recovery than 9am?** (finding #5) —
   candidate explanations (different typical stop-distance geometry, different liquidity/volatility
   regime at that session) are not distinguished by this phase's data.
8. **Is the high recovery-to-entry rate (finding #3) exploitable net of realistic costs, if a
   hypothetical re-entry rule only triggers once price is confirmed back at/near the original entry
   level (satisfying the causal constraint that any such entry can't be known before that
   confirmation)?** This is the most concrete candidate for a future Line-C investigation — explicitly
   NOT designed, sized, or back-tested in this phase.
9. **Is the 2015-2017 vs. 2018-2020 continuation-rate gap (52.7% vs. 59.4%, borderline-overlapping
   CIs) a real regime shift or noise?** Not resolved by one-way stratification alone; would need a
   dedicated, pre-registered test, not a post-hoc deep-dive into this phase's own output.

## Inconclusive results (explicitly not findings, with the stated reason)

10. **The 1-day MAE difference between SL events and matched controls (-0.234R, CI
    [-0.407, -0.035], excluding zero)** is NOT treated as evidence. This phase ran 8 comparisons
    (4 horizons x 2 metrics) at 90% CI with no multiple-comparison correction; one borderline result
    out of 8 is within what noise alone produces. A dedicated, pre-registered single-hypothesis test
    on this specific horizon/metric would be needed before treating it as real.

## Evidence against the original hypothesis

11. **The continuation-vs-reversal split after a real stop-loss is statistically indistinguishable
    from a matched "ordinary market moment" control, at every horizon tested** (differences of
    -0.4 to +1.1 percentage points, every CI straddling zero). This is a direct, honest answer to the
    user's own worked example of an uninteresting result — the headline post-SL "continuation
    tendency" (finding #4) does NOT appear to be special to stop-loss events in this dataset; it looks
    like ordinary short-horizon FX behavior at a matched moment. **This is the single most important
    result of Phase 2**: the raw post-SL continuation tendency, on its own, is not distinguishable
    from normal market behavior, and must not be read as "losses contain exploitable directional
    information" without further, more targeted evidence.

## What Phase 2 does NOT claim

No strategy, entry rule, or parameter set is proposed as profitable. No claim is made that EURUSD,
USDCAD, or AUDUSD specifically benefit from a post-SL rule. The one borderline statistically-distinct
result found (the 1d MAE difference) is explicitly flagged as likely noise pending a dedicated test,
not promoted into a recommendation. See `docs/12-next-research-unit-recommendation.md` for what a
disciplined next step looks like given these results.
