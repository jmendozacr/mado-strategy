# Deliverable H — Recommendation for Phase 8 (not executed this phase)

One recommendation, per the brief's instruction.

## Recommended: close the confirmation-timing hypothesis as a predictor; return to pre-entry geometry

Phase 7 tested the one verified structural difference between 1AM and 9AM (confirmation-window
timing, `docs/47`) as an explanation for the E1 gap, using the one stratifying variable
(`confirmation_relative_position`) that is actually comparable across the two differently-sized
windows (`docs/50`). The gap did not move. Combined with Phase 5/6's own `risk_atr` result, THREE
candidate explanatory variables (`risk_atr`, absolute window position -- inconclusive due to
support, relative window position) have now been tested against this same gap, and none has
reduced it.

**Close this specific sub-line (timing-of-confirmation as the mechanism) -- do not re-test it with
a fourth variant of the same idea.** The two remaining untested candidates named back in Phase 5
(`docs/41`/`docs/35`'s own recommendation) are `cost_to_risk_ratio` and `atr_m15_at_entry`, both
shown to differ materially between models (`docs/30`/`docs/31`) and never yet tested as
standardization variables for ANY endpoint. A Phase 8 that standardizes the E1 (or combined E0+E1)
gap on `atr_m15_at_entry` specifically -- the volatility REGIME at entry, not the risk-to-ATR RATIO
already tested -- would close out the full pre-registered candidate list from Phase 5 before this
line either produces a surviving explanation or is declared exhausted.

## Why not the other options named in the brief

- **Contrafactually re-simulating the window**: not justified yet. This phase deliberately avoided
  it (brief section 10's own boundary); running it now, having already found timing POSITION
  doesn't explain the existing gap, would answer a different question (does window WIDTH change
  the population) that isn't yet motivated by anything this phase found.
- **Expanding to non-executed signals**: `docs/51`'s funnel audit shows the data exists
  (`funnel_2015plus_run2.csv`) but the ambiguous `candidates_built`/`filled` columns would need
  their own validation pass before being trustworthy for any comparison -- worth doing eventually,
  but it is a data-quality unit, not a hypothesis test, and shouldn't be bundled with one.
- **A new pre-entry predictive variable (`atr_m15_at_entry`)**: recommended above, as the most
  direct continuation of Phase 5's own unfinished candidate list.

This is a recommendation only. Per the brief, Phase 8 does not start without separate, explicit
authorization.
