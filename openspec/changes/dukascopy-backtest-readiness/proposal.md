# Proposal: Dukascopy Backtest Readiness

## Intent

Produce an auditable EURUSD/GBPUSD H4/M15 backtest to inform a shadow-mode decision. Current evidence is a statistical experiment, while the canonical report mislabels confirmed signals without retests and ignores fill-candle stop-loss touches.

## Scope

### In Scope

- Add the missing deterministic two-pair backtest path and receipt to the already-adopted Dukascopy work.
- Report confirmed signals without a retest as `confirmed_no_retest`.
- Record a fill-candle stop-loss touch as an immediate loss.
- Preserve one canonical two-pair run with entries, SL, TP, costs, configuration, hashes, and results.

### Out of Scope

- Shadow mode, broker integration, demo or live execution.
- EST-B research, profitability thresholds, new strategy rules, 05:00 profiles, or Key-Level expansion.
- Wholesale merge of the obsolete experiment branch.

### Scope Admission

| Candidate | Admission | Reason |
|---|---|---|
| `confirmed_no_retest` classification | product-guarantee | Stops confirmed setups being reported as never confirmed. |
| Fill-candle SL is an immediate loss | safety-guarantee | Retains adverse intrabar movement. |
| Research runner and hashed receipt | design-control | Enables repeatability outside production. |
| Preserved two-pair run | test-evidence | Proves execution on the target corpus. |
| Demo, live, EST-B, profit gate | follow-up | Unneeded for trustworthy evidence. |

## Capabilities

### New Capabilities

- `dukascopy-backtest-reproducibility`: Reproduce a bounded two-pair trading run.

### Modified Capabilities

- `detector`: Correct no-retest classification and fill-candle SL outcomes.

## Approach

Correct classification, simulation, metrics, and published text at their canonical owners. Extend the existing research seam with a thin deterministic command that invokes production pure functions and fails closed on input or hash mismatch. Preserve a distinct trading receipt.

Design must formalise an ADR keeping provider ingress and orchestration under `research/`, never imported by production. It must define boundary handling when SL equals the candle extreme or SL and TP are both reachable; immediate loss takes precedence.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `detector/backtest/` | Modified | Population, simulation, metrics. |
| `detector/viz/trades_table.py` | Modified | Published reconciliation. |
| `detector/tests/` | Modified | Behavioural evidence. |
| `research/dukascopy_eurusd_gbpusd/` | Modified/New | Runner and receipt. |
| `openspec/specs/detector/spec.md` | Modified | Contract delta. |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Output consumers expect the old bucket | Medium | Treat the renamed classification as an explicit contract migration. |
| Intrabar data cannot reveal event order | High | Apply the agreed deterministic immediate-loss rule. |
| Missing or changed raw inputs | Medium | Fail closed before producing results; record hashes. |
| Research code leaks into production | Low | Enforce the ADR and dependency direction. |

## Rollback Plan

Revert the semantics, report fields, runner, receipt, detector requirement blocks, and tests together. No migration or user data is involved. Validate with the pre-change backtest suite and confirm legacy output contracts. Raw inputs and earlier receipts remain unchanged.

## Dependencies

- Existing Dukascopy seam and frozen EURUSD/GBPUSD inputs with matching hashes.
- Existing canonical H4/M15 backtest pipeline.

## Success Criteria

- [ ] Confirmed signals with no retest appear only as `confirmed_no_retest`.
- [ ] Every fill-candle SL touch resolves as an immediate loss, including boundary equality and same-candle SL/TP reachability.
- [ ] One command reproduces both EURUSD and GBPUSD H4/M15 runs from validated inputs.
- [ ] The receipt records command, configuration, input hashes, costs, reconciliation, and trade results for both pairs.
- [ ] Repeating the run with identical inputs produces identical receipt content.
- [ ] No profitability value controls pass/fail, and no production module imports provider-specific research code.
