# Proposal: CRT Backtest Simulation Engine — Single-Target

**Triage**: L | **Final version**: V2 (re-entered after Plan Verify iteration 1 returned `gaps` on 4 problem-fit findings, ratified via 4 product decisions)

## Intent

The v1 detector surfaces CRT/ICT setups (Model-1 signals, ~135/day measured on real data) but gives no evidence whether following them would be profitable — no SL, no TP, no metrics. v1's own steward reckoning already established the trader cannot judge that volume by eye. This change gives an honest first read — a non-survivorship-biased trade population, correctly-placed SL/TP, methodology-faithful filters, and an aggregate expectancy figure — on whether the methodology, as coded, would have made money historically. Deliberately scoped to a single take-profit level; partial exits, equity curve and drawdown split into a follow-on change.

## Scope

### In Scope

- Candle-by-candle trade lifecycle simulation, one TP level
- Tradeable population: signals eligible to fill (CONFIRMED, INVALIDATED or PENDING with `retest_index` set) whose entry level is then actually simulated as touched — avoids survivorship bias in both directions
- Simulated entry fill: a candidate opens only when price touches its entry level within `max_fill_wait` candles of `retest_index`; otherwise excluded as `never_filled`
- Entry price decoupled from `Model1Signal.entry_price`/`detections.csv`: retest price for wick-type, candle open for body-type. SL anchored to protected extreme or a deeper swing extreme, offset by a configurable buffer, computed relative to that entry so risk varies per setup. TP = HTF CRT range opposite extreme (pair mode required, hard-fails without it)
- Configurable per-trade trading cost, default zero, net-deducted from `r_multiple`, always disclosed
- R:R floor (1:2 default), kill-zone gating (NY only), `fvg_fill` exclusion, signal deduplication (QA measured 1.44x inflation), pessimistic same-candle SL+TP tie-break, gap-through-both-levels fill at gap-open
- CLI flags for all 5 `BacktestConfig` fields — configurability a trader can exercise, not a source edit
- Signal/anchor ID on `Model1Signal` + `detections.csv` (absorbs v1 followup #3), plus `confirmation_index`
- Metrics: win rate, per-trade R-multiple, AND an aggregate profitability figure — average R-multiple across closed trades and total R
- Population-reconciliation report over `signals_considered`
- Output: `trades.csv` + `metrics_summary` (mirrors `detections.csv`)

### Out of Scope

- Instruments other than EURUSD-shaped 5-digit FX: `sl_buffer_price`/`trading_cost_price` are raw price units. JPY pairs, indices, and pip-normalization are explicitly deferred and documented as a known limitation.
- Partial exits, equity curve, max drawdown — deferred to `crt-detector-backtest-partial-exits`
- Real execution/broker integration, parameter optimization, dynamic position sizing, multi-strategy/portfolio backtesting, interactive UI, London Kill Zone

## Capabilities

### New Capabilities

- `backtest-simulation`: candle-by-candle entry-fill + SL/TP trade lifecycle from Model-1 signals
- `backtest-metrics`: win rate, per-trade and aggregate R-multiple, population-reconciliation reporting
- `signal-traceability`: stable signal/anchor identifier joining detection rows to trade rows

### Modified Capabilities

- `model1-entry-detection`: `Model1Signal` gains a confirmation-index field — data-contract change only, detection behaviour unchanged
- `cli-output-filtering`: gains `--backtest` plus 5 `BacktestConfig` flags, reuses the existing `--session`/`--types`/`--from-date`/`--to-date` chain as the cohort definition

## Approach

Pure-function `backtest/` package, new layer above `alignment` (`core→primitives→composite/entries→alignment→backtest→viz/cli`), mirroring the existing detector shape: frozen `Trade`/`BacktestMetrics` dataclasses, `BacktestConfig` in `core/config.py`, SL/TP/entry touch resolution via the existing `core.sweep.two_heap_sweep` (already used by `fvg.py`/`mss.py` — no new algorithm class, no perf-regression risk by construction).

Fill is simulated, never assumed — a candidate opens only if the series touches its entry level in `[retest_index, retest_index + max_fill_wait]`; otherwise counted `excluded_never_filled`. `signals_considered` is the post-CLI-filter population. Exclusion buckets are evaluated in a fixed 7-stage precedence order (no_crt_range → unaligned → never_confirmed → duplicate → kill_zone → rr_floor → never_filled), each stage a population-status or structural cut that makes "exactly one bucket" derivable. `--session` supplied means the kill-zone stage auto-disables (no double-filtering).

One unavoidable contract change: `Model1Signal` gains a confirmation-index field, rippling into `viz/table.py`, `alignment/htf_ltf.py`, and 3 no-lookahead property-test key tuples.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `detector/backtest/` (new) | New | `simulate.py`, `metrics.py`, `levels.py` — pure-function fill/SL/TP simulation + metrics |
| `detector/entries/model1.py` | Modified | `Model1Signal` gains confirmation-index + signal ID |
| `detector/core/config.py` | Modified | new `BacktestConfig` (5 fields) |
| `detector/core/kill_zone.py` (new) | New | relocated `in_ny_kill_zone` |
| `detector/viz/` | Modified | new `trades_table.py` writer |
| `detector/cli.py` | Modified | `--backtest` + 5 config flags, reuses existing filter chain |
| `detector/.importlinter` + `pyproject.toml` | Modified | new `backtest` layer/root_package/wheel entry |
| `detector/alignment/htf_ltf.py` | Modified | consumes new `Model1Signal` fields |
| `detector/tests/property/test_no_lookahead.py` | Modified | new backtest monotonicity property; key tuples updated |
| `detector/tests/test_model1.py` | Modified | 12 existing tests updated for new fields |
| `openspec/specs/detector/spec.md` | Modified | new REQ domains for backtest |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| `Model1Signal` contract change breaks v1 behavior | Medium | Additive fields only; full v1 suite re-run as acceptance gate |
| Naive O(n·m) simulation regresses proven 100k-row perf | Low | `two_heap_sweep` reuse mandated structurally |
| Simulated fill drops so many candidates the sample loses statistical meaning | Medium | `excluded_never_filled` a first-class reported bucket; real-data review bar catches a degenerate sample |
| `max_fill_wait` becomes an unexamined magic number that tunes results | Medium | Exposed as a CLI flag, disclosed per run |
| EURUSD-only price-unit assumption silently misused on JPY/indices | Medium | Documented limitation in `metrics_summary` |
| Scope re-balloons toward partials mid-design | Low | Split decision persisted, user-confirmed |

## Rollback Plan

Purely additive at the CLI surface — `--backtest` is opt-in; omitting it reproduces today's exact byte-for-byte output. `Model1Signal` field additions are additive. Rollback = revert the branch's commits; no persisted state or data migration exists.

## Dependencies

None — `zoneinfo`/pandas/numpy/matplotlib already present. The real-data "done" bar requires the human's local `pairs/` EURUSD MT5 export (gitignored) — automated acceptance runs on synthetic fixtures.

## Success Criteria

- `--backtest` produces `trades.csv` + `metrics_summary` without changing `detections.csv`/`overlay.png` output
- `metrics_summary` reports an aggregate profitability figure alongside win rate, net of the disclosed trading cost
- Reconciliation report accounts for 100% of `signals_considered` in exactly one bucket
- All 5 `BacktestConfig` fields settable from the CLI, measurably change results
- Every trade row's signal ID joins to exactly one `detections.csv` row
- Win rate, per-trade R and aggregate R correct against hand-computed golden-master scenarios; differential test vs. naive reference
- Zero regressions in the existing v1 suite
- A real EURUSD MT5 run against `pairs/` completes and the human reviews win rate / average R / reconciliation and judges them plausible — a green test suite alone does NOT make this change done

## Outcome

Delivered. See `outcome-verdict.md` — real 100k-candle EURUSD run confirmed all 7 north-star criteria, human-ratified as complete (not phase 1 of N).
