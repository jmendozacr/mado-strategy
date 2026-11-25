# Deliverable E — Research Findings (Phase 4)

## Observaciones descriptivas sólidas

1. **Most reconstructible failures show real favorable movement before failing.** 71.7% of the 1009
   reconstructible confirmed stops reach at least `partial` (0.25R) favorable excursion before their
   final stop; only 28.3% go nearly straight to the stop. Median MFE pre-SL is 0.55R.
2. **20.05% of confirmed stops cannot have a pre-SL path reconstructed at all** (same-bar or
   adjacent-bar entry-to-exit) -- a real data-resolution ceiling at M15, not a modeling choice.
3. **Slow failures are not "slow deterioration"** -- the duration x excursion cross-tab shows slow
   failures (top duration tercile) are dominated by `partial`/`material` favorable excursion
   (224+159 of 417), never `unknown`, and rarely `none` (34/417). The category name offered as an
   example in the brief ("deterioro prolongado y progresivo") does not describe what slow failures
   in this dataset actually look like.
4. **No pre-entry feature shows a stark win/loss median separation** among ATR, risk-in-ATR, planned
   RR, NY hour, recent-range-ATR, or position-in-range (`docs/23-...`).

## Diferencias exploratorias

5. **1AM failures resolve with substantially less observable path than 9AM** (31.2% vs. 15.3%
   `ambiguous`+`insufficient`). Consistent in direction with Phase 2/3's own unexplained 1AM-vs-9AM
   post-SL difference (larger MAE, higher recovery) -- now a THIRD, independent signal pointing the
   same way, still not explained causally by any phase so far.
6. Pairs and the four predeclared periods show broadly overlapping failure-mode distributions -- no
   strong exploratory difference by instrument or era.

## Hipótesis candidatas para investigación posterior

7. **Does the 1AM model's structurally different failure/behavior profile share a common cause with
   its different post-SL behavior (Phase 2/3)?** A single underlying mechanism (e.g. typical stop
   distance geometry, or liquidity conditions specific to that session) could explain both -- not
   tested this phase.
8. **Is the "favorable excursion then failure" pattern (dimension 2, majority case) associated with
   a specific, observable PRE-ENTRY signature** that could flag it before it happens? This phase only
   established the pattern exists post-hoc; Layer A (pre-entry) features were not cross-tabulated
   against Layer B (failure path) outcomes, by design (section 10's Layer separation forbids using
   Layer B to pick a Layer A predictor without a dedicated, pre-registered study).

## Resultados inconclusos

9. The win/loss pre-entry comparison (`docs/23-...`) used medians only, no uncertainty intervals or
   formal significance testing -- "no stark difference" is a descriptive impression, not a
   statistically confirmed null result. A dedicated test would be needed before concluding no
   pre-entry predictor exists at all.

## Limitaciones de datos

10. L1 (Phase 1, unchanged): no table of valid-but-never-executed signals exists, so this entire
    phase describes EXECUTED winners vs. EXECUTED losers, not "every opportunity CRT produces."
11. Retracement-from-best-favorable-price is reported in raw price units (`docs/24-...`), not yet
    normalized by R or ATR -- comparable within one instrument's typical scale but not yet a clean
    cross-instrument or cross-regime metric.
