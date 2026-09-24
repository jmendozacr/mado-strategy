# EURUSD + GBPUSD Dukascopy experiment preregistration

## Problem

The strategy needs a defensible empirical evaluation using Dukascopy evidence for market availability and closure handling. The original three-instrument experiment cannot be silently converted to two instruments because removing the dollar-index identity changes the population, estimand, exposure mix, and statistical power.

This experiment therefore asks whether a separately defined EURUSD + GBPUSD population can be evaluated reproducibly under the strategy's documented timing knowledge and the strict fail-closed closure policy.

## Objective

Determine whether EURUSD + GBPUSD, using the retained Dukascopy exports and offline-domain evidence, supports a statistically valid two-instrument strategy evaluation without claiming equivalence to the original three-instrument experiment.

## Scope

### In scope

- EURUSD and GBPUSD only.
- The inclusive strategy window 2022-08-08 through 2026-08-19.
- Dukascopy JForex 1-minute Bid exports and retained offline-domain probe evidence.
- Descriptive continuity, coverage, closure handling, and the pre-registered two-instrument statistical estimand.
- Charters 8–10 timing knowledge, preserved without reinterpretation.

### Out of scope

- `DOLLAR.IDX/USD` identity replacement or cross-broker equivalence.
- Exness access, communication, or data acquisition.
- Changes to production code, frozen datasets, original three-instrument baselines, or archived statistical protocols.
- Treating Dukascopy as a complete immutable closure calendar.
- Public redistribution or publication of provider data.

## Current evidence boundary

The validation branch established that EURUSD and GBPUSD exports are byte-identical across repeated downloads for the same request and that the JForex offline-domain probe returned 215 identical domains per instrument, including special Christmas and year-end intervals. These observations support a retained evidence package; they do not establish an authoritative, versioned closure schedule.

## Signed analysis contract

The experiment remains descriptive and fail-closed. The approved contract is:

1. Primary unit: one strategy signal/window per instrument; instrument-day coverage is secondary.
2. Report pooled EURUSD + GBPUSD results and separate per-instrument results.
3. Use the strategy's already-defined outcome; do not invent a new outcome for this experiment.
4. Do not make inferential comparisons against the original three-instrument experiment; any reference is descriptive and explicitly non-equivalent.
5. Use the retained Dukascopy files locally under the approved personal, non-commercial scope.
6. Inclusion/exclusion rules for incomplete minutes, zero-volume rows, and unexplained intervals must be written before the statistical run.
7. Multiple-comparison, dependence, power treatment, reproducibility package, and stop conditions must be written before the statistical run.
8. The frozen `+0.20R` MEI is inherited as a fixed economic-meaning threshold; it is not recalibrated for this two-instrument population.
9. Each eligible 1 AM or 5 AM strategy window is a separate primary unit; dependence is clustered by instrument-day, and 1 AM/5 AM results are reported separately as secondary strata.
10. Candidate admission is frozen at `2026-08-19T00:00:00Z`; outcome follow-up is frozen at `2026-08-19T20:30:00Z`. Both boundaries are recorded in the run manifest and the seam rejects caller-supplied values that differ from it.

No statistical result will be generated before those decisions are approved and recorded.

## Approved decisions

- Primary unit is signal/window; instrument-day coverage is secondary.
- Results are reported pooled and separately by instrument.
- The existing strategy outcome is primary; no new outcome is introduced.
- Comparisons to the three-instrument experiment are descriptive only and non-equivalent.
- Local personal, non-commercial use of retained files is approved.
- The frozen `+0.20R` MEI is inherited without recalibration.
- 1 AM and 5 AM windows are separate units with instrument-day clustering; setup-specific results are secondary.
- Candidate and outcome boundaries are fixed at the stated UTC instants before outcome execution.

## Status

Signed preregistration. No statistical run, production change, dataset mutation, or baseline update has occurred on this branch.
