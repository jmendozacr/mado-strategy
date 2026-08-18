# CRT/ICT Pattern Detector v1

**Status**: planned, ready for `/build` | **Triage**: L | **Not yet built** — `detector/` doesn't exist yet, this folder is the plan.

Stop manually scanning Forex charts by hand to find CRT/ICT setups. This change builds a Python tool that detects Swing High/Low, Fair Value Gaps, Market Structure Shift, CRT ranges, and Model-1 entries over historical MetaTrader OHLC data (EUR/USD, GBP/USD, DXY), with HTF↔LTF alignment tagging, and renders a chart image + companion table per run.

## Read in this order

1. [`triage.md`](./triage.md) — problem statement, in/out-of-scope contract
2. [`proposal.md`](./proposal.md) — intent, capabilities, risks, rollback plan
3. [`spec.md`](./spec.md) — 28 REQ-IDs with Given/When/Then scenarios (signed)
4. [`design.md`](./design.md) — architecture, file changes, every algorithm predicate pinned, 6 ADRs
5. [`slices.md`](./slices.md) — build order: 1 walking skeleton + 6 vertical slices
6. [`north-star.md`](./north-star.md) — the "why this matters" checkpoint, human-ratified
7. [`verify-plan.md`](./verify-plan.md) — the 3-round adversarial review that hardened this plan before any code was written

## What's deliberately NOT in v1

Standalone Order Block + Breaker Block detectors, SMT Divergence, Rejection Block, backtest simulation, live alerts, any interactive UI. See `triage.md`'s Out of Scope and the project's pending-changes log for what's tracked as a follow-up.

## Next step

`/build --scope=skeleton` — builds S-000 (the walking skeleton), which every other slice depends on.
