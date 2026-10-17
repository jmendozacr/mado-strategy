# Test Matrix — Dukascopy Backtest Reproducibility

**Feature**: dukascopy-backtest-reproducibility  
**Prefix**: REPRO  
**Status**: active  
**Sources**: dukascopy-backtest-readiness (signed V2 specification)  
**Last updated**: dukascopy-backtest-readiness

| ID | Flow | Rule (business language) | Level | Automation | Test ref | Risk |
|---|---|---|---|---|---|---|
| REPRO-01 | F1 — Produce validated two-pair evidence | A researcher who completes a canonical EURUSD and GBPUSD H4/M15 backtest from approved inputs receives evidence for both pairs, including the applied configuration and costs, source inputs, trades, and reconciliation. (REQ-01.1, dukascopy-backtest-readiness) | integration | none | `research/dukascopy_eurusd_gbpusd/tests/test_backtest.py` (planned) | high |
| REPRO-02 | F1 — Produce validated two-pair evidence | A researcher requesting a canonical two-pair backtest with a missing or unapproved input receives the rejection reason and no evidence presented as valid. (REQ-01.3, dukascopy-backtest-readiness) | integration | none | `research/dukascopy_eurusd_gbpusd/tests/test_backtest.py` (planned) | high |
| REPRO-03 | F1 — Produce validated two-pair evidence | A researcher preserves a complete, valid canonical two-pair backtest as research evidence even when its trading result is unprofitable. (REQ-01.4, dukascopy-backtest-readiness) | integration | none | `research/dukascopy_eurusd_gbpusd/tests/test_backtest.py` (planned) | high |
| REPRO-04 | F2 — Replay canonical two-pair evidence | A researcher repeating a preserved canonical two-pair backtest with the same approved inputs, configuration, and costs receives identical evidence and trade results. (REQ-01.2, dukascopy-backtest-readiness) | integration | none | `research/dukascopy_eurusd_gbpusd/tests/test_backtest.py` (planned) | high |

## Coverage at a glance

| Flow | Auto | Manual | None |
|---|---:|---:|---:|
| F1 — Produce validated two-pair evidence | 0 | 0 | 3 |
| F2 — Replay canonical two-pair evidence | 0 | 0 | 1 |
