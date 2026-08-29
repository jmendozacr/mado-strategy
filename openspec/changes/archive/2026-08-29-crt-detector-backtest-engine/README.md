# CRT Backtest Simulation Engine

**Status**: archived (delivered) | **Triage**: L | **Built** — `detector/backtest/` exists, 7/7 slices complete.

The v1 detector surfaces CRT/ICT setups (Model-1 signals, ~135/day measured) but gave no evidence whether following them would be profitable — no stop-loss, no take-profit, no win/loss outcome, no aggregate performance figure. This change closes that gap: it simulates each signal's full trade lifecycle (entry fill, SL, TP) over historical data and reports an honest, non-survivorship-biased performance read (win rate, per-trade and aggregate R-multiple, population reconciliation). Deliberately scoped to a single take-profit level; partial exits, equity curve, and drawdown are a follow-on change.

## Read in this order

1. [`triage.md`](./triage.md) — problem statement (reconstructed), in/out-of-scope contract
2. [`proposal.md`](./proposal.md) — intent, capabilities, risks, rollback plan
3. [`spec.md`](./spec.md) — 23 REQ-IDs (REQ-30 through REQ-52) with Given/When/Then scenarios (signed V10)
4. [`design.md`](./design.md) — architecture, file changes, 5 ADRs
5. [`slices.md`](./slices.md) — build order: 1 walking skeleton + 6 vertical slices, all complete
6. [`north-star.md`](./north-star.md) — the foresight checkpoint that caught the SL-as-constant defect before a line was written
7. [`verify-plan.md`](./verify-plan.md) — the multi-cycle adversarial plan review that hardened this plan before code
8. [`verify-report.md`](./verify-report.md) — final verification: 187/187 tests, 64/67 scenarios compliant
9. [`simplify-report.md`](./simplify-report.md) — cross-slice cleanup pass (9 findings, 8 applied)
10. [`outcome-verdict.md`](./outcome-verdict.md) — the steward reckoning that ran the tool on real 100k-candle EURUSD data

## What's deliberately NOT in this change

Partial exits, equity curve, max drawdown (need a concurrency/position-accounting policy first — deferred to `crt-detector-backtest-partial-exits`), real execution/broker integration, parameter optimization, dynamic position sizing, multi-strategy/portfolio backtesting, an interactive dashboard, London Kill Zone, non-EURUSD-shaped instruments. See `triage.md`'s Out of Scope and `openspec/pending-changes.md` for what's tracked as a follow-up.

## Next step

This change is closed. The next planned step is `crt-detector-backtest-partial-exits`, built on this change's validated single-target foundation.
