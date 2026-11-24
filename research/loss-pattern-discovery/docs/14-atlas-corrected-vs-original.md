# Deliverable B — Atlas: Corrected vs. Original (`4aadf26`)

Same hypotheses, same horizons (1h/4h/1d/3d), same 0.25R continuation/reversal threshold as Phase 2 --
**none recalibrated**. Only the control-matching defect and the three post-stop timing defects
(`docs/13-phase3-corrections-report.md`) changed. Original numbers are read verbatim from the
committed `docs/09-atlas-results.md` / `docs/10-control-comparison.md` (commit `4aadf26`) -- never
overwritten.

## Eligible population ("overall") -- barely moved except at 1h

| Metric | Horizon | Original (4aadf26) | Corrected | Change |
|---|---|---|---|---|
| n | all | 1262 | 1262 | none |
| MAE (R) | 1h | 0.49 [0.45, 0.52] | **0.43** [0.40, 0.46] | -0.05R -- Defect B drops the 4th, not-yet-closed bar from a 4-bar 1h window |
| MAE (R) | 4h | 0.91 [0.83, 0.96] | 0.90 [0.82, 0.95] | negligible |
| MAE (R) | 1d | 2.34 [2.20, 2.49] | 2.32 [2.19, 2.48] | negligible |
| MAE (R) | 3d | 3.63 [3.40, 3.97] | 3.63 [3.40, 3.97] | none |
| P(continuation) | 1h | 55.3% | 54.8% | negligible |
| P(continuation) | 4h/1d/3d | 55.6/55.7/55.9% | 55.6/55.7/55.9% | **unchanged** |
| P(recovered to entry) | 1h | 25.4% | **22.4%** | -3.0pp -- same Defect-B 1h effect |
| P(recovered to entry) | 4h | 48.7% | 47.2% | -1.5pp |
| P(recovered to entry) | 1d | 75.4% | 75.3% | negligible |
| P(recovered to entry) | 3d | 85.4% | 85.5% | negligible |

**Why only 1h moved materially**: a 1h window holds exactly 4 M15 bars; Defect B's fix (a bar must
fully CLOSE by the horizon boundary, not merely OPEN before it) removes exactly one of those four --
a 25% reduction in bar count, which is why both MAE and recovery drop measurably at 1h specifically.
Longer horizons lose the same ONE bar out of 16/96/288, a negligible fraction -- explaining why 4h/1d/3d
barely moved. This is the expected, mechanical consequence of the fix, not a surprise.

## Control comparison -- **this is where the conclusion changes materially**

| Metric | Horizon | Original (4aadf26) | Corrected | 95%/90% CI excludes 0? |
|---|---|---|---|---|
| P(continuation) diff (SL-control) | 1h | +1.1pp [-2.0,+4.3] | -1.4pp [-4.5,+1.9] | No |
| P(continuation) diff (SL-control) | 4h | -0.4pp [-3.6,+2.8] | **-4.4pp [-7.5,-1.4]** | **Yes** |
| P(continuation) diff (SL-control) | 1d | -0.4pp [-3.6,+2.8] | **-4.4pp [-7.5,-1.4]** | **Yes** |
| P(continuation) diff (SL-control) | 3d | -0.3pp [-3.5,+2.9] | **-4.4pp [-7.6,-1.3]** | **Yes** |
| MAE diff (SL-control) | 1h | +0.029R [-0.02,+0.08] | **+0.056R [0.010,0.093]** | **Yes** |
| MAE diff (SL-control) | 4h | -0.074R [-0.17,+0.02] | +0.071R [-0.02,+0.15] | No |
| MAE diff (SL-control) | 1d | **-0.234R [-0.41,-0.04]** | -0.032R [-0.22,+0.18] | No (Phase-2's own borderline result is GONE) |
| MAE diff (SL-control) | 3d | -0.335R [-0.70,+0.06] | -0.139R [-0.54,+0.23] | No |

**Phase 2's headline conclusion ("post-SL continuation is statistically indistinguishable from a
matched control at every horizon") does NOT survive the control-matching fix, without a favorable
spin applied either way.** Once controls are actually filtered to a comparable NY hour (Defect 1 --
Phase 2's controls were never hour-filtered despite the docs claiming otherwise), the continuation
comparison flips from "no difference anywhere" to a **consistent ~-4.4 percentage-point gap at
4h/1d/3d, CI excluding zero**: SL events show LESS continuation (relatively more reversal) than a
properly NY-hour/volatility-matched ordinary moment. The 1h value differs from 4h/1d/3d because
`first_move_direction` is set once per event and then carried forward -- by ~4h most events have
resolved it, so 4h/1d/3d largely repeat the same underlying classification rather than providing three
independent confirmations; treat this as ONE finding, not three.

Separately, Phase 2's own single borderline-significant control-comparison result (1d MAE,
`-0.234R`, already flagged in `docs/11-research-findings.md` as likely noise from running 8
untested-for-multiplicity comparisons) **disappears entirely in the corrected run** (`-0.032R`, CI
comfortably crossing zero) -- consistent with that original flag of caution having been the right call.
A NEW, small (CI-excluding-zero but only +0.056R) MAE difference appears at 1h instead.

**What this does NOT mean**: a ~4.4-point continuation gap is a descriptive, directional finding about
first-move classification -- not a sized, cost-aware, tradeable edge, and it says nothing about the
recovery-to-entry question specifically (see Deliverable D). It is reported here because the user
explicitly asked whether the corrected control materially changes the continuation conclusion, and it
does.

## Why the control-matching fix moved this and not the overall-population numbers

The eligible population's OWN behavior (MAE, continuation, recovery) is unaffected by how controls are
sampled -- that's why "overall" barely changed except at 1h (a measurement-only fix). The
CONTROL-COMPARISON numbers, by contrast, depend entirely on what the control group's distribution looks
like, and Phase 2's un-filtered-by-hour control pool was drawing from a materially different (hour-
mixed) population than this fix's properly hour-matched one -- see Deliverable C for direct evidence
that Phase 2's implicit claim ("matched by session") was not actually enforced in code.
