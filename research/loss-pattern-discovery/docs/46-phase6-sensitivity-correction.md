# Deliverable A (Phase 7) — Phase 6 Sensitivity Correction

An independent review found a mathematical error in Phase 6's S2 partial-identification bounds
(`docs/40-sensitivity-analysis.md`). This document corrects it, before any Phase 7 analysis runs,
per the brief's explicit requirement.

## The error

`stats/sensitivity_scenarios.py::scenario_s2` computed, for each model independently, a "min" rate
(NOT-sequence-verifiable same-bar events excluded from the early-stop numerator) and a "max" rate
(the engine's own convention). The bug: it then paired **the same scenario on both models** --
`lower_bound = rate_1am_min - rate_9am_min` and `upper_bound = rate_1am_max - rate_9am_max` -- and
reported those as the bounds on the DIFFERENCE `Gap = rate_1am - rate_9am`.

That is not what bounds a difference of two independently-uncertain quantities. For
`Gap = A - B` with `A in [A_min, A_max]` and `B in [B_min, B_max]` (independently), the correct
extrema are `Gap_min = A_min - B_max` and `Gap_max = A_max - B_min` -- minimizing a subtraction
means maximizing what is subtracted, not pairing "both at their own minimum."

## Red test (reproduced before fixing anything)

A fixture with NOT-verifiable same-bar events in BOTH models (`1am`: rate_min=0.50, rate_max=0.75;
`9am`: rate_min=0.40, rate_max=0.80 -- the original fixture had zero such events in 9AM, which
masked the bug entirely) was run against the pre-fix code
(`git show 986f3be:research/loss-pattern-discovery/stats/sensitivity_scenarios.py`):

```
OLD (buggy) lower_bound diff: 0.09999999999999998
OLD (buggy) upper_bound diff: -0.050000000000000044
Expected CORRECT Gap_min: -0.3, Gap_max: 0.35
```

The buggy pairing does not just produce the wrong magnitude -- it inverts which value is larger
than the other, relative to the true identified interval. After the fix, the same fixture returns
exactly `gap_min=-0.30`, `gap_max=0.35` (`tests/test_sensitivity_scenarios.py::test_s2_difference_bounds_use_cross_model_pairing_not_same_scenario_pairing`).

## The fix

`scenario_s2` now computes each model's own `rate_min`/`rate_max` independently
(`_model_rate_bounds`), then reports:

- **`identified_interval`**: `{gap_min: rate_1am_min - rate_9am_max, gap_max: rate_1am_max -
  rate_9am_min}` -- pure identification uncertainty, no sampling noise (requirement 5).
- **`ci_for_identified_set`**: a separate, explicitly-named outer-envelope block-bootstrap
  construction -- `ci_low` = 2.5th percentile of the resampled `Gap_min` distribution, `ci_high` =
  97.5th percentile of the resampled `Gap_max` distribution. This is NOT simply reusing either
  individual scenario's own 95% CI (requirement 6) -- it is necessarily at least as wide as the
  identified interval itself (verified by test), because it must cover the whole identified set,
  not one point inside it. It is a documented, simpler substitute for a formally calibrated
  Imbens-Manski interval, not claimed to achieve that construction's exact coverage.

Tests added (requirements 1-4): a dedicated fixture with ambiguous events in BOTH models
(requirement 3), a test proving the four extreme-combination containment property (requirement 4),
and determinism/CI-separation tests. All 10 tests in `tests/test_sensitivity_scenarios.py` pass;
the full 150-test suite (Phase 1-6) re-run clean (see docs/55 checkpoint).

## Corrected numbers

| | Original (buggy) report (docs/40) | Corrected |
|---|---|---|
| S2 lower/`gap_min` | +8.50pp | **+8.22pp** |
| S2 upper/`gap_max` | +9.35pp | **+9.63pp** |
| 95% CI for the identified set | (not reported this way) | **[+4.78pp, +12.81pp]** |

`docs/40-sensitivity-analysis.md` is preserved UNCHANGED as historical reference (requirement 7) --
its S2 numbers are now known to be wrong and must not be cited going forward; this document is the
corrected source of truth for S2.

## Impact on the Phase 6 verdict

**`NEXT_BAR_DIFFERENCE_PERSISTS` is unaffected.** The verdict criteria (`docs/37` section 6) never
depended on S2's specific numbers -- they depended on S0 (unchanged: +9.35pp) and S1 (unchanged:
+5.38pp, E1 alone) clearing the relevance/CI bars, and on Unit C's NOT-verifiable share staying
under 50% (unchanged: 15.6%/8.5%). S2 was supporting evidence for "the finding isn't fragile to the
same-bar convention" -- the corrected band (+8.22pp to +9.63pp) is slightly wider than originally
reported (+8.50pp to +9.35pp) but says the exact same thing: even the most conservative treatment of
the 11 genuinely ambiguous same-bar events barely moves the result. No Phase 6 conclusion changes;
only the magnitude of this one supporting number is corrected.
