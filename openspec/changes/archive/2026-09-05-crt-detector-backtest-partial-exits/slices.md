# Slices: Backtest Two-Stage (Partial) Exit Model

**Triage**: M
**Spec version**: signed (2026-09-04)
**Design version**: V1
**Total slices**: 4 (1 walking skeleton + 3 SPIDR)

---

## S-000: Walking Skeleton — Two-leg partial exit resolves and blends

**Scope**: walking-skeleton
**Dimension**: —
**Covers**: REQ-68.1, REQ-69.1, REQ-38.2
**Requires**: nothing
**Test layers**: unit

**Acceptance**:
- GIVEN a candidate whose partial level resolves before SL, then the remainder hits the original take-profit
- WHEN resolved
- THEN leg 1 closes at `partial_price`, leg 2 closes at `take_profit`, and `r_multiple` is the fraction-weighted blend of both legs' `net_r_multiple`

### Tasks
- [x] S-000.1 `levels.py`: `partial_price(htf_context, direction) -> float` = range midpoint
- [x] S-000.2 `simulate.py`: `Candidate.partial_price` field + `_partial_sides()` (mirrors `_tp_sides()`) + wire 3rd `two_heap_sweep` pass into `_resolve_exits`
- [x] S-000.3 `simulate.py`: `Trade` gains `partial_exit_index/price/r_multiple/gap_filled` fields
- [x] S-000.4 `core/config.py`: `BacktestConfig.partial_fraction: float = 0.5`
- [x] S-000.5 `_resolve_trade`: SL-wins-tie check extended to partial index; leg 1 closes at `partial_price` (or gap-open via existing `_exit_gap_beyond`)
- [x] S-000.6 `_resolve_trade`: leg 2 re-resolves the SAME unmoved SL/TP from `partial_index+1`; blend `r_multiple` per REQ-69, proportional cost allocation
- [x] S-000.7 `test_backtest_levels.py::test_partial_price_is_range_midpoint`
- [x] S-000.8 `test_backtest_simulate.py::test_two_leg_trade_blends_partial_and_remainder_r_multiple`

---

## S-001: Resolution edge cases and the ordering safety net

**Scope**: edge-case
**Dimension**: R (Rule)
**Covers**: REQ-68.2, REQ-68.3, REQ-68.4, REQ-68.5, REQ-68.6, REQ-69.2, REQ-69.3, REQ-38.1, REQ-38.3, REQ-70.1, REQ-70.2
**Requires**: S-000
**Test layers**: unit + property

**Acceptance**:
- GIVEN each resolution edge case (tie-break, gap, zero-fraction, never-touched, zero-cost)
- WHEN resolved
- THEN behavior matches REQ-68/69/38 exactly, AND `partial_price` ordering holds across the real 3-instrument corpus with zero violations

### Tasks
- [x] S-001.1 `test_two_leg_trade_leg2_uses_unmoved_original_stop` (REQ-68.2)
- [x] S-001.2 `test_sl_wins_tie_against_partial_collapses_to_single_leg` (REQ-68.3/38.3/69.3)
- [x] S-001.3 `test_partial_leg_gap_through_fills_at_open` (REQ-68.4)
- [x] S-001.4 `test_partial_fraction_zero_reproduces_single_leg_output` (REQ-68.5/38.3) — found+fixed the real `partial_fires` bug (missing `partial_fraction > 0.0` guard)
- [x] S-001.5 `test_open_trade_has_no_partial_leg_fields` (REQ-68.6/38.1)
- [x] S-001.6 `test_two_leg_blended_r_zero_cost_is_bit_identical` (REQ-69.2)
- [x] S-001.7 Create `tests/property/test_partial_price_ordering.py::test_partial_price_ordering_holds_across_real_corpus` — real EURUSDm/GBPUSDm/DXYm corpus, public functions only (REQ-70.1) — resolved: REQ-68 V2 corrected `partial_price` to the trade's own entry-to-target midpoint; the test's helper now calls `partial_price(ep, tp)` (was the old `partial_price(htf_context, direction)` signature) and passes with zero ordering violations across all 3 instruments, by construction.
- [x] S-001.8 `test_ordering_violation_fails_loudly_naming_candidate` (REQ-70.2)

---

## S-002: `trades.csv` and `metrics_summary` disclose the partial leg

**Scope**: happy-path
**Dimension**: I (Interface)
**Covers**: REQ-45.4, REQ-45.5, REQ-49.5
**Requires**: S-000
**Test layers**: unit + e2e

**Acceptance**:
- GIVEN any `--backtest` run
- WHEN `trades.csv`/`metrics_summary.txt` are inspected
- THEN the header is exactly 17 columns, trailing cells reflect the partial leg (populated/blank), and the partial-exit count is reported explicitly

### Tasks
- [x] S-002.1 `metrics.py`: `BacktestMetrics.partial_exits: int` + counting logic
- [x] S-002.2 `trades_table.py`: header 13→17 cols (4 trailing partial columns)
- [x] S-002.3 `trades_table.py`: write trailing cell values (blank/`False` when no partial)
- [x] S-002.4 metrics summary writer: emit literal `partial exits: {N}` line
- [x] S-002.5 `test_trades_csv_header_has_17_columns_in_order` (REQ-45.4)
- [x] S-002.6 `test_trades_csv_partial_columns_populated_when_fired` (REQ-45.5)
- [x] S-002.7 `test_partial_exits_count_in_mixed_population` (REQ-49.5)
- [x] S-002.8 `test_metrics_summary_discloses_partial_exits_count` (REQ-49.5)

---

## S-003: `--partial-fraction` CLI flag and validation

**Scope**: edge-case
**Dimension**: R (Rule)
**Covers**: REQ-51.4, REQ-51.5
**Requires**: S-000, S-001
**Test layers**: e2e

**Acceptance**:
- GIVEN `--backtest --partial-fraction 0.0`
- WHEN the run executes
- THEN it reproduces the pre-change single-TP output trade-for-trade; an out-of-range value is rejected exit 1, naming the flag and constraint

### Tasks
- [x] S-003.1 `cli.py`: wire `--partial-fraction` to `BacktestConfig.partial_fraction`
- [x] S-003.2 `cli.py`: validate range `[0.0, 1.0)`, mirroring REQ-51.3's rejection pattern
- [x] S-003.3 `test_partial_fraction_zero_cli_reproduces_pre_change_output` (REQ-51.4)
- [x] S-003.4 `test_invalid_partial_fraction_exits_1_naming_flag_and_constraint` (REQ-51.5)

---

## Build Order

1. S-000 (skeleton — implicit blocker for all others)
2. S-001, S-002 — independent, can be built in parallel
3. S-003 — requires S-000 and S-001 (mirrors REQ-68.5's regression at the CLI entry point)

## Real-Data Evidence (not a slice)

Success Criteria's real-data run (EURUSDm/GBPUSDm/DXYm, `partial_fraction=0.5` default) is verification/evidence, not a REQ-covered deliverable — it runs after S-003 (once the CLI flag and full resolution logic exist) as an acceptance step during `/build`'s in-loop verify or `/evaluate`, producing the winrate/R comparison number in the change's evidence file. No REQ invented for it.
