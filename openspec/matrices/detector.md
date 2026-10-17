# Test Matrix — Detector

**Feature**: detector
**Prefix**: DETECTOR
**Status**: active
**Sources**: dukascopy-backtest-readiness / signed detector delta
**Last updated**: dukascopy-backtest-readiness

| ID | Flow | Rule (business language) | Level | Automation | Test ref | Risk |
|---|---|---|---|---|---|---|
| DETECTOR-01 | F1 — Build trade candidates | When an aligned signal has a retest, the backtest admits confirmed, invalidated, and pending signals using the same fill window; signals without a retest, without a CRT range, or without alignment receive their applicable exclusion result. (REQ-30, dukascopy-backtest-readiness) | unit | none | — | high |
| DETECTOR-02 | F2 — Resolve entry-fill candle exits | When an entry-fill candle exposes a trade to its stop loss, the backtest records an immediate loss; a take-profit or partial-profit touch without stop-loss exposure earns no favourable exit until a later candle, and a strict pre-entry opening beyond the stop is not treated as a loss. (REQ-33, REQ-37, dukascopy-backtest-readiness) | unit | none | — | high |
| DETECTOR-03 | F3 — Reconcile backtest population | When a backtest reports its filtered signal population, every considered signal appears exactly once as an opened trade or in one precedence-ordered exclusion result, and the reported totals reconcile exactly. (REQ-40, dukascopy-backtest-readiness) | unit | none | — | high |
| DETECTOR-04 | F4 — Resolve partial exits | When a trade reaches a partial-profit level after its fill candle, the backtest closes the configured fraction and preserves the original stop and target for the remainder; a stop-loss tie is a single-leg loss, and a zero partial fraction preserves single-leg results. (REQ-68, dukascopy-backtest-readiness) | unit | none | — | high |

## Coverage at a glance

| Flow | Auto | Manual | None |
|---|---:|---:|---:|
| F1 — Build trade candidates | 0 | 0 | 1 |
| F2 — Resolve entry-fill candle exits | 0 | 0 | 1 |
| F3 — Reconcile backtest population | 0 | 0 | 1 |
| F4 — Resolve partial exits | 0 | 0 | 1 |
