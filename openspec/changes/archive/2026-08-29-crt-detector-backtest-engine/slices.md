# Slices: CRT Backtest Simulation Engine

**Triage**: L | **Spec**: V10 | **Design**: V6 | **Total**: 7 (skeleton + 6 SPIDR)
**Status**: ALL 7/7 SLICES COMPLETE — change is implementation-complete.

## S-000: Simulate one trade end-to-end via `--backtest` — walking skeleton

Covers: REQ-30.1, 31.1, 32.1-32.2, 33.1, 33.3, 34.1, 37.1-37.2, 38.1, 41.1, 43.1, 44.1, 45.1-45.2, 47.1-47.2, 47.5, 48.2, 50.1-50.3, 52.2.

`BacktestConfig` (5 fields), `Model1Signal` +3 fields, `backtest/levels.py` (entry/SL/TP/R:R/net-R), `backtest/simulate.py` (Candidate/Trade/ReconciliationReport, unified fill, SL/TP sweep, open→tie-break→gap order), `backtest/metrics.py`, `viz/trades_table.py` (both writers, complete), `cli.py` population binding + dead-param removal, `backtest` package registration. Built the full 7-stage pipeline generically from the start — deliberate, since every later slice's acceptance criteria needed the whole pipeline to exist.

## S-001: Admit every eligible signal-status variant

Dimension: Data | Covers: REQ-30.2-30.6, 40.4, 44.2, 50.4.

Admission logic was already status-blind from S-000 (built generically). Added 7 regression-pinning tests, no production code change.

## S-002: Anchor stop-loss to real market structure

Dimension: Rule | Covers: REQ-31.2-31.4, 47.3-47.4.

Swing-lookup branch already implemented by S-000. Added a no-lookahead property test plus 4 doji/tie-break tests.

## S-003: Reject setups failing rule cuts (R:R floor + kill zone)

Dimension: Rule | Covers: REQ-35.1-35.3, 36.1, 36.3, 52.1.

Genuine RED→GREEN cycle for `core/kill_zone.py`'s creation (relocating `in_ny_kill_zone` from `cli.py`, removing the temporary duplicate S-000 had left in `backtest/simulate.py`). 5 new rule-cut tests.

## S-004: Collapse duplicate signals into one economic trade

Dimension: Data | Covers: REQ-46.1-46.2.

Dedup logic already implemented by S-000. Added 2 tests (3-way collapse, differing-entry-type both-survive).

## S-005: Trace a trade back to its detection row

Dimension: Interface | Covers: REQ-41.2-41.3, 42.1-42.2, 45.3.

Genuine new production code: `viz/table.py`'s conditional `signal_id` column (runtime `include_signal_id` flag, not a static header change) + `cli.py` wiring. Rewrote one S-000-era test whose premise (byte-identity between plain/backtest runs) the signed V9 spec fix made incorrect.

## S-006: Make backtest behavior configurable and fully disclosed

Dimension: Rule | Requires: S-003 | Covers: REQ-33.2, 36.2, 36.4-36.5, 39.1-39.2, 40.1-40.3, 48.1, 48.3, 49.1-49.4, 51.1-51.3.

All 5 `BacktestConfig` CLI flags + validation, 3-state kill-zone gate resolution, trading-cost/open-trades disclosure lines, `test_backtest_metrics.py` (new, 182 lines). This slice's first apply pass was interrupted by a session usage-limit error before its own persistence step completed — a follow-up pass independently re-verified every acceptance criterion from scratch against the actual code and the signed spec before marking it complete (see Apply Progress).

## Build Order

1. S-000 (blocks all)
2. S-001, S-002, S-004, S-005 (parallelizable)
3. S-003 (before S-006)
4. S-006 (requires S-003)

**Final state**: 185 tests passing at slice-complete (187 after the simplify-gate fix pass, 193 after judgment-day). `lint-imports` clean throughout.

## Distribution / SPIDR

walking-skeleton 1 (S-000); happy-path 6 (S-001…S-006); edge-case/spike 0. Data 2, Rule 3, Interface 1, Path/Spike 0. All 23 REQ-IDs / 67 sub-scenarios placed exactly once. No slice depends on more than 2 others.
