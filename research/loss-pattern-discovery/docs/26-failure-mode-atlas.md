# Deliverable D — Failure Mode Atlas

1262 confirmed-stop losses, 2047 total executed trades (778 wins). Full numbers in
`artifacts/phase4_failure_mode_atlas.json` (regenerate with `uv run --project detector python
research/loss-pattern-discovery/stats/failure_mode_atlas.py`).

## Answers to the 10 questions (section 8)

1. **¿Qué proporción de SL ocurre rápidamente?** 10% resolve within 1 bar (15 min), 25% within 2
   bars; median duration is 6 bars (~1.5h). "Fast" has no single definition here -- reported as a
   continuous distribution, not a binary split.
2. **¿Cuántos tuvieron movimiento favorable importante antes de invalidarse?** 17.75% of all 1262
   (22.2% of the 1009 reconstructible ones) reach `material` (>=1R); a further 39.54% (49.5% of
   reconstructible) reach `partial` (0.25-1R). **Combined, the majority of reconstructible failures
   (71.7%) show at least SOME real favorable movement before failing** -- a straight slide to the
   stop (`none`, 28.3% of reconstructible) is the minority pattern.
3. **Distribución del MFE pre-SL**: median 0.55R, P10=0.00R, P25=0.21R, P75=0.94R, P90=1.35R
   (reconstructible population, n=1009).
4. **¿Cómo varía la duración?** Heavily right-skewed: P10=1 bar, median=6 bars, P90=45 bars.
5. **Duración vs. excursión favorable (cross-tab, tercile bins for readability only)**:

   | Duration tercile | none | partial | material | unknown |
   |---|---|---|---|---|
   | fast | 126 | 71 | 7 | 253 |
   | mid | 126 | 204 | 58 | 0 |
   | slow | 34 | 224 | 159 | 0 |

   Fast failures are dominated by `unknown` (insufficient bars to reconstruct, by construction) and
   `none`; almost none show material excursion (7/457). **Slow failures are NEVER `unknown`** (always
   enough bars to reconstruct) and are dominated by `partial`/`material` (224+159 of 417) -- slow
   failures look much more like "ran in profit for a while, then reversed" than "ground down
   slowly," contrary to the "Slow Deterioration" category name offered as an example in the brief.
6. **¿Diferencias entre 1AM y 9AM?** Yes, a real one: 1AM shows a much higher `insufficient`+
   `ambiguous` rate (31.2% vs. 9AM's 15.3%) and correspondingly more `unknown` excursion (31.2% vs.
   15.3%) -- 1AM failures resolve with less observable path, consistent with Phase 2/3's own
   (unexplained) finding that 1AM behaves differently from 9AM post-SL too.
7. **¿Diferencias entre EURUSD/USDCAD/AUDUSD?** No clear ones: `reconstructible` 78.3-81.7%,
   `material` excursion 14.2-20.2% across the three pairs -- overlapping, no pair stands out.
8. **¿Qué dimensiones muestran estabilidad temporal?** The excursion-class mix is reasonably stable
   across the four predeclared periods (`partial` 35-44%, `material` 14-19%, `none` 19-26%) -- no
   period stands out as a regime break.
9. **¿Qué variables pre-entrada distinguen descriptivamente ganadoras y perdedoras?** None show a
   stark median separation (`docs/23-...`): ATR, risk-in-ATR, planned RR, NY hour, recent-range-ATR
   and position-in-range are all close between the 778 wins and 1265 losses. This is itself a
   descriptive finding, not proof no predictor exists (no formal test was run, per this phase's own
   scope).
10. **¿Qué proporción tiene información insuficiente?** 20.05% of confirmed stops (`ambiguous` +
    `insufficient` combined) cannot have a primary pre-SL path reconstructed at all.

## By instrument / model / period (one-way only, no combinatorial grid)

Full tables in `docs/24-...` (duration/MFE) and the JSON artifact; headline differences are items 6
(1AM/9AM) and 7-8 (pair/period stability) above.
