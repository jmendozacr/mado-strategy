# Simplify Report: CRT Backtest Simulation Engine

4 parallel blind lenses (reuse, simplification, efficiency, altitude) over the full diff (7 slices, S-000..S-006), run once after the Executor↔Evaluator loop closed, before verify --mode=final. The diff was built across 4 separate apply batches by different sub-agent runs that couldn't see each other's work — cross-batch duplication was the expected defect class this gate exists to catch.

## Findings (10 raw, deduped to 9 unique) — 8 applied, 1 skipped

| # | Angle(s) | Finding | Outcome |
|---|---|---|---|
| 1 | reuse | `Direction` re-declared in `simulate.py` instead of imported | applied |
| 2 | reuse + altitude (corroborated by 2 lenses) | Kill-zone 3-state `Literal` duplicated across 4 sites | applied — `KillZoneGateState` alias |
| 3 | simplification | `BacktestMetrics` duplicates 4 `BacktestConfig` fields verbatim | applied — holds `config: BacktestConfig` |
| 4 | simplification | `signal_id` derivable but hand-spelled at 9 sites | applied — derived in `__post_init__` |
| 5 | simplification + altitude (corroborated) | Sweep-shape duplication in `simulate.py` | applied — factored `_directional_sides()` |
| 6 | efficiency | `stop_loss()` rebuilt an `indices` list every call | applied — hoisted to once per `simulate()` run |
| 7 | efficiency | `two_heap_sweep` called twice sequentially | **skipped — out of footprint**: `core/sweep.py` is Read-only per this change's design. Candidate for a future change. |
| 8 | altitude | MT5 CSV test fixtures triplicated across 3 test files | applied — extracted `tests/fixtures/mt5_csv.py` |
| 9 | altitude | `write_trades_csv` hand-rolled `write_detections_csv`'s shape | applied — verified identical shape, factored `write_csv()` |

## Result

8/9 applied, 1 explicitly skipped (design constraint, not a failure), 0 reverted. 187/187 tests passing after every fix, `lint-imports` clean throughout. Both corroborated findings (kill-zone Literal, sweep-shape duplication) were independently caught by 2 of 4 lenses — the exact signal this gate exists to surface.
