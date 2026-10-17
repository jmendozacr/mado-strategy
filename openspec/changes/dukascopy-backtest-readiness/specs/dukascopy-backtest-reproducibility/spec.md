# Dukascopy Backtest Reproducibility Specification

**Spec version**: V2
**Status**: signed
**Change**: `dukascopy-backtest-readiness`

## Purpose

This capability provides a bounded, repeatable EURUSD and GBPUSD H4/M15 trading backtest whose evidence can inform a later decision about shadow-mode testing. It reports results without requiring a profitable outcome.

## Requirements

### REQ-01: Reproducible canonical two-pair backtest

The research run MUST execute the canonical H4/M15 trading rules for both EURUSD and GBPUSD from the approved Dukascopy inputs and MUST preserve enough evidence for another researcher to reproduce and compare the run. Its completion MUST depend on evidence completeness and input validity, never on whether the trading result is profitable.

#### Scenario REQ-01.1: Complete two-pair evidence

- GIVEN the approved EURUSD and GBPUSD H4/M15 inputs are available and valid
- WHEN the canonical research run completes
- THEN the preserved evidence identifies both pairs, the applied trading configuration and costs, the source inputs, and the resulting trades and reconciliation
- AND neither pair is omitted

#### Scenario REQ-01.2: Identical replay

- GIVEN the same approved inputs, trading configuration, and costs as a preserved run
- WHEN the canonical research run is repeated
- THEN the reproduced evidence and trade results are identical to the preserved run

#### Scenario REQ-01.3: Invalid evidence source

- GIVEN a required input is missing or differs from the approved source
- WHEN the canonical research run is requested
- THEN no completed backtest evidence is presented as valid
- AND the reason the source could not be accepted is reported

#### Scenario REQ-01.4: Unprofitable result remains valid evidence

- GIVEN a complete valid run whose trading result is unprofitable
- WHEN completion is evaluated
- THEN the run is preserved as valid research evidence
- AND profitability does not determine pass or fail

## Design Inputs

- Validate the frozen manifest and input hashes before outcome-producing execution.
- Record the command, configuration, costs, input hashes, reconciliation, and trade results in the receipt.
- Make identical replay deterministic, including receipt content.
- Keep provider ingress and orchestration research-only; production code must not depend on provider-specific research code.
- Preserve one canonical receipt for the EURUSD and GBPUSD run.

## Scope Boundaries

- No broker, demo, shadow-mode, or live execution.
- No EST-B statistical research or profitability threshold.
- No new strategy rules, 05:00 profiles, or Key-Level expansion.

## Sensitive Areas Coverage

No sensitive behaviour is changed. The inputs and receipt are research provenance, not production data ownership, authorisation, payment, privacy, security, or deployment controls.
