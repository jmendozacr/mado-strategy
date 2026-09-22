# EURUSD + GBPUSD statistical protocol

This is the signed operational protocol for the two-instrument preregistration. It is not an execution authorization and does not alter the frozen three-instrument protocol.

## Population and unit

- Population: eligible EURUSD and GBPUSD strategy windows in 2022-08-08 through 2026-08-19.
- Primary unit: each eligible 1 AM or 5 AM strategy window.
- Dependence cluster: instrument-day; windows from the same instrument-day are not treated as independent clusters.
- Confirmatory report: pooled EURUSD + GBPUSD, stratified by instrument in the same analysis.
- Secondary reports: EURUSD, GBPUSD, 1 AM, and 5 AM strata separately.

## Outcome and estimand

Use the existing strategy outcome and canonical EST-B definition; do not create a new outcome:

`EST-B = closed MeanR(ALIGNED) - closed MeanR(OPPOSED)`

The frozen `+0.20R` MEI is inherited as a fixed interpretation threshold. It is not recalibrated from this dataset and is not a promise of capturable return or trade permission.

## Inclusion rules

A window is eligible only when all required input, signal, alignment, and outcome records are present, finite, correctly ordered, and attributable to the same instrument and source file identity. The required 1 AM or 5 AM timing window must be fully represented in the retained minute series after EET-aware conversion.

The offline-domain receipt and the retained official-source comparison must classify the relevant interval as either documented unavailable or sufficiently evidenced. A confirmed unavailable interval makes the affected window ineligible; it is not treated as an open market.

## Exclusion and fail-closed rules

- Malformed rows, duplicate timestamps, hash drift, missing files, and boundary gaps affecting a signal or outcome are integrity failures.
- An unexplained gap or closure boundary affecting a window makes that window unresolved and ineligible; no interpolation, imputation, silent dropping, or open-market inference is allowed.
- Zero-volume rows are observations, not closure labels. If they affect required price continuity or outcome evidence, the window is unresolved and excluded; otherwise they remain in the descriptive data-quality report.
- Non-finite R, impossible zero-risk R, duplicate joins, unavailable provenance, and open/never-filled outcomes are fail-closed exclusions.
- The exclusion ledger must retain the instrument, date, setup, reason, source evidence, and whether the cause was data integrity or market unavailability.

## Dependence and uncertainty

Use the existing instrument-stratified cluster-bootstrap family and RNG contract where compatible, with instrument-day as the cluster key for this experiment. Materialize paired draws and apply the same draws to all reported estimands. Do not treat individual windows within one cluster as independent observations.

No inferential comparison to the original three-instrument experiment is permitted. Per-instrument and setup-stratum intervals are descriptive unless separately ratified.

## Power and stop conditions

Before execution, record the signal-rate source, expected eligible cluster count, target estimand, and the minimum detectable effect. If those quantities cannot be justified without looking at outcomes, label the run exploratory and make no powered claim.

Stop before confirmatory interpretation if any of the following occurs:

- unresolved protocol or dataset hash mismatch;
- any required boundary or closure interval cannot be reconciled;
- the pooled estimand is non-computable;
- the pre-registered exclusion threshold is exceeded;
- cluster counts are insufficient for the approved uncertainty procedure.

Exclusion of more than 30% of eligible instrument-days blocks a confirmatory conclusion and requires a protocol review.

## Reproducibility package

The run package must retain the exact input paths, file hashes, JForex/API versions, offline-domain probe hash, source commit, protocol hash, timezone conversion rule, exclusion ledger, RNG seed/version, code revision, and complete machine-readable outputs. Raw provider files remain outside the repository unless separately authorized.

## Signed ratification

1. The 30% instrument-day exclusion threshold is approved.
2. Without an external or holdout signal-rate source, the run is exploratory and makes no powered claim.
3. The compatible bootstrap/RNG contract uses instrument-day clusters.
4. The exact outcome adapter is the existing canonical EST-B path.

Status: signed protocol. No statistics, production changes, dataset mutation, or baseline update has occurred.
