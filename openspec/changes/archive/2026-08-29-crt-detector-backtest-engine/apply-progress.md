# Apply Progress: CRT Backtest Simulation Engine

All 7 slices (S-000..S-006) implemented under Strict TDD. Full detail lived in engram across several passes; curated summary below.

## Slice Execution Notes

- **Batch (S-001/S-002/S-004/S-005)**: ran as a parallelizable batch. Key discovery, confirmed by reading the code before writing any test: S-000's implementation of `_population_cuts`/`_fill_pass`, `stop_loss`, and `_dedup` was already written generically — no branch on `Model1Signal.status` or candidate type anywhere — because the design's binding directive required the full 7-stage pipeline to exist in S-000 for its own acceptance criteria to be verifiable. So S-001/S-002/S-004's remaining work was writing the missing regression-pinning tests, all of which passed immediately (no RED phase) — a deliberate, documented deviation from strict TDD's usual RED-first cycle, not a violation: each test pins a distinct REQ-ID sub-scenario with zero prior coverage. S-005 was the one slice with genuine new production code and followed the normal RED→GREEN cycle.
- **S-003**: `core/kill_zone.py`'s creation followed a genuine RED→GREEN cycle — repointing `test_cli.py`'s kill-zone tests to `core.kill_zone.in_ny_kill_zone` before the module existed produced a real `ModuleNotFoundError`, resolved by creating the module with the verbatim relocated body.
- **S-006**: implementation landed correctly during a session that hit a usage-limit interruption BEFORE reaching its own persistence steps (marking tasks complete, updating this artefact). A follow-up pass independently re-verified from scratch — fresh test run, full read of every touched file, every acceptance criterion checked against the actual code and the signed spec text — before marking the slice complete. Registered as a discovery: never trust a failed agent call's implicit claim about code state; re-verify independently.

## Post-Slice Fix Passes

### Simplify Gate (8/9 findings applied, 1 explicitly skipped — see `simplify-report.md`)

Fixed cross-batch duplication (`Direction` re-declaration, a 3-4x duplicated kill-zone-state `Literal`, sweep-shape duplication in `simulate.py`, `BacktestMetrics` duplicating `BacktestConfig` fields, hand-spelled `signal_id`, an `indices` list rebuilt every `stop_loss()` call, triplicated MT5 CSV test fixtures, a hand-rolled CSV writer). One item (the `two_heap_sweep` double-invocation) explicitly skipped as out-of-footprint — `core/sweep.py` is Read-only per this change's design.

### Judgment-Day Fix Passes (2 rounds, 3 batches — see `verify-report.md` and the judgment-day record)

**Round 1 (5 items)**: `--sl-buffer 0` uncaught `ZeroDivisionError` fixed; CLI numeric conversion moved off argparse's `type=` into the existing `ValueError`→exit-1 path (catches NaN/inf too); `--kill-zone-gated false/true` value-taking syntax restored alongside the existing valueless forms; `stop_loss()`'s swing-window lookup bisected on both bounds (perf) and `simulate()`'s redundant swing recomputation removed, with a subtle bug caught during implementation (not by a failing test): capturing `detections.swings` AFTER the CLI's `--types` filter chain could silently zero out the SL swing search under `--types model1`; `metrics_summary.txt`'s `Path.write_text()` calls gained explicit `encoding="utf-8"` (was locale-dependent, mojibaked the REQ-47 note's em dash on Windows).

**Round 2 (2 items)**: small price-unit config values rendering in scientific notation below ~1e-4 fixed with a `_fixed_decimal` helper; `outcome` (`win`/`loss`) was derived from which level resolved first rather than net profitability — a large `--trading-cost` override could label a net-losing trade `win`. Fixed to derive from `r_multiple`'s sign (already the net figure).

**Round 3 (1 item, scoped explicitly to this single issue by the user)**: a genuine lookahead-bias bug — `stop_loss`'s swing-window upper bound was `retest_index - 1`, but a swing at that index is only confirmable once candle `retest_index` closes, which is after a REQ-50.1 same-candle fill could already happen. Fixed to `retest_index - 2`, traced by hand and confirmed against a Hypothesis-found counterexample (reverting the fix reproduced the failure; re-applying it passed). New property test added: `test_stop_loss_swing_window_has_no_lookahead`.

## Final State

193/193 tests passing, `lint-imports` clean (1 kept, 0 broken) after all fix passes. Zero regressions in the pre-existing v1 suite throughout.
