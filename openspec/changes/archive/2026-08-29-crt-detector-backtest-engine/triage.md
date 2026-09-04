# Triage: CRT Backtest Simulation Engine

**Classification**: L
**Final version**: V6, reconstructed and reconciled after two Plan Verify cycles surfaced that the original problem statement had degraded through repeated "unchanged, see revision history" elisions (a structural limitation of the memory backend used mid-pipeline — only an observation's latest revision is retrievable). V6 reconstructs the problem statement in full from the proposal's Intent, the exploration synthesis, and the session's original framing, cross-checked for consistency across all three sources.

## Problem & Scope

The v1 CRT/ICT pattern detector surfaces Model-1 trade signals against real market data (~135 signals/day, measured) but gives no evidence whether following them would be profitable: no stop-loss, no take-profit, no win/loss outcome, no aggregate performance figure. v1's own steward reckoning already established that a trader cannot judge that signal volume by eye. That leaves the person who built and runs the detector unable to answer the one question that matters before risking real capital on it — would this methodology, as coded, have made money historically? This change closes that gap: it simulates each signal's full trade lifecycle (entry fill, SL, TP) over historical data and reports an honest, non-survivorship-biased performance read (win rate, per-trade and aggregate R-multiple, population reconciliation), giving the trader real evidence instead of an unvalidated stream of setups. Deliberately scoped to a single take-profit level; partial exits, equity curve, and drawdown are a follow-on change.

### In Scope

- Candle-by-candle trade lifecycle simulation, ONE take-profit level (no partials — deferred)
- Tradeable population: any `AlignedSignal` that is aligned (HTF context present) whose `ltf_signal` is CONFIRMED, or INVALIDATED with `retest_index` set, or PENDING with `retest_index` set — all three admitted types flow through the identical candidate/fill/SL/TP pipeline. Admitting PENDING+retest closes a survivorship-bias gap: those are setups that touched entry and never followed through, exactly the setups most likely to resolve as losses or stay open.
- Entry-fill simulation anchors uniformly at `retest_index` for all three candidate types — never at `confirmation_index`. The fill window searches `[retest_index, retest_index + max_fill_wait]` for a touch of the entry price; a candidate never touched is excluded as `never_filled`, never forced into a loss.
- Backtest entry price decoupled from `Model1Signal.entry_price`/`detections.csv` — retest-side body-zone boundary for wick-type signals, candle open for body-type signals.
- Stop-loss anchored to the purge candle's protected extreme, or the deepest qualifying swing extreme when one exists beyond it, offset by a fixed price-unit buffer — computed relative to the backtest entry price, never equal to it.
- `confirmation_index` on `Model1Signal` is traceability/audit-only — not consumed by the fill/SL/TP simulation, which uses `retest_index` uniformly.
- `sl_buffer_price` (default `0.0002`) is a raw price-unit offset, never a pip count.
- Configurable per-trade trading cost (spread+slippage+commission), default zero, net-deducted from `r_multiple`, always disclosed.
- Take-profit = CRT range level (HTF pair mode REQUIRED — no LTF fallback).
- Same-candle SL+TP ambiguity: pessimistic tie-break, counted and surfaced.
- R:R minimum filter (1:2 default, configurable), hard filter pre-simulation, on signed distance.
- Kill-zone gating ON by default (NY only), auto-disables when `--session` already narrowed the population, with a third explicit "disabled" state for the flag-without-session case.
- `fvg_fill`-confirmed signals excluded (no CRT range), counted in reconciliation.
- Gap-through-both-levels: fill at actual gap-open price for EXITS only.
- Signal/anchor ID added to `Model1Signal`, formula includes originating `CRTRange` to avoid cross-range collisions. `detections.csv`'s `signal_id` column is conditional on `--backtest`.
- Signal deduplication before simulation — colliding candidates collapse to one, lowest-origin-index wins, run before the kill-zone/R:R cuts.
- Metrics: win rate, per-trade R-multiple net of trading cost, aggregate profitability (average R-multiple + total R), explicit open-trades disclosure.
- Population-reconciliation report: `signals_considered` → `trades_opened` + 7 exclusion buckets, fixed precedence order.
- CLI override flags for all 5 `BacktestConfig` fields, 1:1 mapping.
- Output: `trades.csv` (13-column contract) + metrics summary.
- Small, mechanical, authorized refactor: relocate `in_ny_kill_zone` from `cli.py` into `core/kill_zone.py`, remove the dead `types` CLI parameter.

### Out of Scope

- Partial exits (fraction + breakeven-stop rule unspecified in source) — deferred to `crt-detector-backtest-partial-exits`
- Equity curve, max drawdown — deferred (needs a concurrency/position-accounting policy first)
- Real execution / broker integration
- Parameter optimization (grid search, walk-forward)
- Dynamic position sizing / account-level risk management
- Multi-strategy / portfolio backtesting
- Interactive dashboard/UI (CSV output only)
- London Kill Zone (not implemented, separate registered gap)
- Sensitivity-study mode across multiple SL-buffer values
- Non-EURUSD-shaped instruments (JPY pairs, indices, pip-normalization)

## Classification Rationale

L: new bounded context (`backtest/` package + layer), `Model1Signal` contract change rippling into existing tests and property-test key tuples, new fitness-function needs, no precedent for the core simulation algorithm.

## Recommended Path

Full Planner with Council → propose → spec (V1..V10, signed) → design (V1-V6) → slice (7 slices) → verify plan gate (2 cycles) → build → simplify → verify final → judgment-day (2 rounds, APPROVED) → steward reckoning (delivered) → archive.

## Follow-on change registered

`crt-detector-backtest-partial-exits` (working name): partial exits, equity curve, max drawdown, concurrency/position-accounting policy — built on this change's validated single-target foundation.
