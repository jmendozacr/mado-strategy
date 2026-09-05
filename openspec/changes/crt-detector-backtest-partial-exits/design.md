# Design: Backtest Two-Stage (Partial) Exit Model

**Design version**: V1 | **Spec**: signed (2026-09-04) | **Triage**: M
**Architecture impact**: none — every touched module stays in its existing `.importlinter` layer; no new module/dependency/boundary, no `deviates` touchpoint.

## 4.1 — Architecture Overview

Extends `backtest/`'s sweep-and-resolve pipeline (ADR-02, archived `crt-detector-backtest-engine` design) with a THIRD `two_heap_sweep` pass for the equilibrium (50%-of-range) partial level — same eligibility/geometry as TP. `_resolve_trade` gains one branch: when the partial resolves strictly before the original stop (SL still wins ties, generalizing REQ-33), leg 1 closes at the partial price and leg 2 re-evaluates the SAME, unmoved SL/TP sweep results (no new sweep, no re-based risk). `net_r_multiple` runs once per leg; `_resolve_trade` blends per REQ-69. Stays inside `backtest/`, `core/config.py` (one field), `viz/trades_table.py` (append-only) — no boundary/dependency change; `take_profit()`/`min_risk_reward` untouched.

## 4.1b — Pattern Check

**Pattern**: existing — matches `simulate.py`'s sweep-and-resolve structure (ADR-02: ambiguity resolved by ORDERING). The third level reuses `two_heap_sweep` unchanged and extends the SAME SL-wins-ties rule, per REQ-68's own text. Blended-R and non-rebased-leg convention are spec-level (REQ-69), not design choices. No new pattern; no ADR (4.5).

## 4.2 — File Changes

| Path | Action | Purpose |
|---|---|---|
| `detector/backtest/levels.py` | Modify | `partial_price()` (REQ-68) |
| `detector/backtest/simulate.py` | Modify | `Candidate.partial_price`; `_partial_sides()` + 3rd sweep; two-stage `_resolve_trade`; `Trade` +4 fields (REQ-68/38/69) |
| `detector/backtest/metrics.py` | Modify | `BacktestMetrics.partial_exits: int` (REQ-49.5) |
| `detector/core/config.py` | Modify | `BacktestConfig.partial_fraction: float = 0.5` (REQ-51) |
| `detector/viz/trades_table.py` | Modify | header 13→17 cols, trailing cells, summary line (REQ-45/49) |
| `detector/cli.py` | Modify | `--partial-fraction` flag + validation (REQ-51) |
| `detector/tests/test_backtest_levels.py` | Modify | `partial_price()` coverage |
| `detector/tests/test_backtest_simulate.py` | Modify | REQ-68/69/38 scenarios; fix affected default-config fixtures |
| `detector/tests/test_backtest_metrics.py` | Modify | `partial_exits` count coverage |
| `detector/tests/test_cli_backtest_e2e.py` | Modify | REQ-45.4/45.5, REQ-49.5, REQ-51.4/51.5; fix affected assertions |
| `detector/tests/property/test_partial_price_ordering.py` | Create | REQ-70 property test |

## 4.2b — Flow Changes

Not applicable — backend batch-simulation/reporting change (CLI flags + CSV/txt columns extend); no interactive user journey. Observable output covered directly in Test Derivation, matching precedent for every prior `--backtest` REQ.

## 4.2c — Architecture Touchpoints

No `sdd/{project}/architecture` baseline exists; governing contract is `.importlinter`'s ADR-01 layered pipeline.

| Layer/Component | Action | Why | Baseline fit |
|---|---|---|---|
| `backtest` (levels/simulate/metrics) | modify | partial derivation, third sweep, two-stage resolution, blended R | aligns |
| `core` (config.py) | modify | new `partial_fraction` field | aligns |
| `viz` (trades_table.py) | modify | trailing columns + metrics line | aligns |

`cli.py` sits outside `.importlinter` entirely (archived ADR-01 rejected it as a layer member); its flag wiring is File-Changes-only. No `new`/`deviates` rows.

## 4.3 — Data Model

```python
# simulate.py
@dataclass(frozen=True)
class Candidate:
    take_profit: float
    partial_price: float  # NEW — REQ-68

@dataclass(frozen=True)
class Trade:
    ambiguous_bar: bool
    gap_filled: bool
    partial_exit_index: int | None    # NEW — REQ-38
    partial_exit_price: float | None  # NEW
    partial_r_multiple: float | None  # NEW
    partial_gap_filled: bool          # NEW

# core/config.py
@dataclass(frozen=True)
class BacktestConfig:
    max_fill_wait: int = 20
    partial_fraction: float = 0.5  # NEW — REQ-68/51, range [0.0, 1.0)

# backtest/metrics.py
@dataclass(frozen=True)
class BacktestMetrics:
    reconciliation: ReconciliationReport
    partial_exits: int  # NEW — REQ-49.5
```

No new dataclass types. New fields carry no defaults (`_resolve_trade`/`_build_candidate` are each type's only construction site).

## 4.4 — Interface Contracts

```python
def partial_price(htf_context: CRTRange, direction: Direction) -> float:
    """REQ-68: (high+low)/2, direction-independent value; direction kept
    only for signature symmetry with take_profit()."""

def _partial_sides() -> tuple[SweepSide, SweepSide]: ...  # mirrors _tp_sides()

def _resolve_exits(filled, candles, trading_cost_price: float, partial_fraction: float) -> list[Trade]: ...

def _resolve_trade(
    candidate: Candidate, fill_index: int, sl_index: int | None, tp_index: int | None,
    partial_index: int | None, candles: tuple, trading_cost_price: float, partial_fraction: float,
) -> Trade: ...
```

**`trades.csv`**: 17 columns (append-only, mirrors `detections.csv`'s `key_level_source` precedent) — existing 13 + `partial_exit_timestamp, partial_exit_price, partial_r_multiple, partial_gap_filled`. Trailing cells blank/`False` when no partial fired.

**`metrics_summary.txt`**: new literal line `partial exits: {N}` — exact wording is the test contract; exact position is executor-local.

**CLI**: `--partial-fraction FLOAT`, default `0.5`, valid `[0.0, 1.0)`; out-of-range rejected exit 1, naming flag+constraint (mirrors the 5 existing flags).

## 4.5 — Architecture Decisions (ADRs)

None. The sweep/tie-break mechanism is REQ-68's own text (reusing ADR-02/REQ-33 precedent — not a new pattern). Blended-R and cost allocation are fully specified by REQ-69 (spec-level, not a design tradeoff). An ADR for either would paperwork a decision design didn't make — consistent with `architecture_impact: none`.

## 4.6 — Test Derivation

| REQ-IDs / scenarios | Behaviour covered | Level | Test |
|---|---|---|---|
| REQ-68 (general) | `partial_price()` = range midpoint, direction-independent | unit | `test_backtest_levels.py::test_partial_price_is_range_midpoint` |
| REQ-68.1, REQ-69.1, REQ-38.2 | two-leg win-win; blended R = `0.5*R_leg1+0.5*R_leg2`; sign sets outcome | unit | `test_backtest_simulate.py::test_two_leg_trade_blends_partial_and_remainder_r_multiple` |
| REQ-68.2 | two-leg win-loss; leg 2 uses ORIGINAL unmoved stop | unit | `test_backtest_simulate.py::test_two_leg_trade_leg2_uses_unmoved_original_stop` |
| REQ-68.3, REQ-38.3, REQ-69.3 | SL wins tie vs partial → single-leg loss, unblended REQ-48 R | unit | `test_backtest_simulate.py::test_sl_wins_tie_against_partial_collapses_to_single_leg` |
| REQ-68.4 | partial gap-through fills at open, not `partial_price` | unit | `test_backtest_simulate.py::test_partial_leg_gap_through_fills_at_open` |
| REQ-68.5, REQ-38.3 | `partial_fraction=0.0` byte-identical to pre-change output | unit | `test_backtest_simulate.py::test_partial_fraction_zero_reproduces_single_leg_output` |
| REQ-68.6, REQ-38.1 | never touched (incl. partial) → open, partial fields None/False | unit | `test_backtest_simulate.py::test_open_trade_has_no_partial_leg_fields` |
| REQ-69.2 | default cost 0.0 → blended R bit-identical to zero-cost | unit | `test_backtest_simulate.py::test_two_leg_blended_r_zero_cost_is_bit_identical` |
| REQ-70.1 | ordering holds for every real RR-floor survivor, 3-instrument corpus | property | `tests/property/test_partial_price_ordering.py::test_partial_price_ordering_holds_across_real_corpus` |
| REQ-70.2 | a deliberately-violating candidate fails loudly, naming it | unit | `tests/property/test_partial_price_ordering.py::test_ordering_violation_fails_loudly_naming_candidate` |
| REQ-45.4 | `trades.csv` header exactly 17 columns, in order | e2e | `test_cli_backtest_e2e.py::test_trades_csv_header_has_17_columns_in_order` |
| REQ-45.5 | trailing cells populated when fired, blank/`False` otherwise | e2e | `test_cli_backtest_e2e.py::test_trades_csv_partial_columns_populated_when_fired` |
| REQ-49.5 (count) | `partial_exits` counts correctly in a mixed population | unit | `test_backtest_metrics.py::test_partial_exits_count_in_mixed_population` |
| REQ-49.5 (disclosure) | `metrics_summary.txt` includes literal `partial exits: N` | e2e | `test_cli_backtest_e2e.py::test_metrics_summary_discloses_partial_exits_count` |
| REQ-51.4 | `--partial-fraction 0.0` reproduces pre-change output trade-for-trade | e2e | `test_cli_backtest_e2e.py::test_partial_fraction_zero_cli_reproduces_pre_change_output` |
| REQ-51.5 | negative or `>=1.0` rejected, exit 1, naming flag+constraint | e2e | `test_cli_backtest_e2e.py::test_invalid_partial_fraction_exits_1_naming_flag_and_constraint` |

All 19 scenarios (REQ-68.1-6, REQ-69.1-3, REQ-70.1-2, REQ-38.1-3, REQ-45.4-5, REQ-49.5, REQ-51.4-5) covered by 16 rows above.

## 4.7 — Fitness Functions

None new. Relies on `.importlinter`'s layers contract (unchanged) and the existing sweep-order-invariance property (`tests/property/test_no_lookahead.py`) — the new pass is symmetric with SL/TP and doesn't alter sort-order preconditions.

## 4.8 — Migration / Rollout

No migration needed (pure Python, no persisted state — plain `git revert` per proposal's Rollback Plan). Note: `partial_fraction` DEFAULTS to `0.5` — every run/test not overriding it will differ from pre-change output for any TP-reaching trade. Intended headline effect, not a regression, but pre-existing tests asserting exact single-leg values under a default config need updating (Executor Notes).

## 4.9 — Performance Considerations

No significant impact — one added `two_heap_sweep` pass, same `O(n + m log m)` class as the existing two.

## 4.10 — Architecture Impact

**Architecture impact**: none
**Rationale**: all three touched layers are `modify`/`aligns` (4.2c) — no `new`, no `deviates`, no boundary/dependency change. Consistent with 0 ADRs.

## 4.11 — Open Questions and Executor Notes

**Blocking questions**: None — the signed spec resolves every product/technical decision.

**Executor-local notes**:
- `partial exits: N` line position in `metrics_summary.txt` (recommended near `open trades: N`) — non-binding beyond the literal substring.
- Pre-existing tests building a winning trade under default config will now see blended-R output (any TP-reaching trade also crosses partial). Fix via `partial_fraction=0.0` or updated expected values — expected work, already flagged in the proposal's Affected Areas.
- REQ-45.5's "partial fired" fixture may reuse the existing default-config e2e fixture (its candidate already reaches take_profit, hence crosses `partial_price` first); build a dedicated one only if needed.
- REQ-70's property test loads the real corpus as this session's CLI runs did (`load_pair` H4+M15, `load_mt5_csv` D1), reimplementing the population/RR-floor filter with PUBLIC functions only (`backtest.levels.*`, `detect_swings`) — no private-helper imports, matching this codebase's test convention.

**Build preflights**: None — `pairs/{M15,H4,D1}/{EURUSDm,GBPUSDm,DXYm}_*.csv` already present in the repo.
