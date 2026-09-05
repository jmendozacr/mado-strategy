## Verification Report

**Change**: crt-detector-backtest-partial-exits
**Mode**: final (Strict TDD — M/LIGHT)
**Spec version**: V2 (signed 2026-09-04, REQ-68 revised)

---

### Completeness
| Metric | Value |
|---|---|
| Slices total | 4 |
| Slices complete | 4 |
| Tasks total | 28 |
| Tasks complete | 28 |

### Build & Tests Execution

**Build**: N/A (no compiled build step — pure Python)
**Tests (full suite)**: ✅ 248 passed / ❌ 1 failed / ⚠️ 0 skipped
- The 1 failure (`tests/property/test_no_lookahead.py::test_alignment_detection_has_no_lookahead`) is PRE-EXISTING and unrelated — confirmed by `git log` on that file: last touched at `085da8c`, before this change's first commit (`d271056`). Not caused by this change; not part of its scope.

**lint-imports**: ✅ Clean — "Layered pipeline (ADR-01) KEPT", 1 kept / 0 broken, 30 files / 64 dependencies analyzed. No new cross-layer import.

**Coverage**: Project has no coverage tool configured — not available, reported cleanly (not a failure).

### Strict TDD (final audit) — M/LIGHT depth

**Verdict**: pass

- **TDD Cycle Adherence** (method: file-pairing + apply-progress narrative, git-history archaeology skipped per M-light gate): apply-progress (engram obs #499) documents explicit RED-before-GREEN discipline for S-003 (argparse-stub-first pattern to get past `SystemExit` before writing real assertions), and every implementation file in the diff has a corresponding, passing test file in the same commit set. No anti-TDD pattern (impl-then-test) detected in the diff.
- **Assertion Quality**: scanned all new/changed assertions across `test_backtest_levels.py`, `test_backtest_simulate.py`, `test_backtest_metrics.py`, `test_cli_backtest_e2e.py`, `tests/property/test_partial_price_ordering.py`. Zero banned patterns (no bare `toBeDefined`-equivalents, no `assert x` without a comparator, no mock-mirrors-implementation). All assertions pin concrete expected values (exact indices, exact prices, exact blended-R formulas cross-checked independently in each test body).
- **Triangulation** (business-rule conditionals only, per M-light gate): `partial_fires` branch — triangulated across 5+ distinct test cases (fires/doesn't-fire/gap-through/fraction-zero/tie). `_resolve_level_exit`'s SL-wins-tie logic — pre-existing, already triangulated, re-verified unchanged by the dedup refactor (S-simplify commit `ad5c6dc`). One gap found — see WARNING-1 below.
- **Mutation Testing**: not configured in this project (no `mutmut`/equivalent in `pyproject.toml` or `openspec/config.yaml`) — skipped cleanly, not a failure.
- **REQ-ID Coverage**: all 7 REQ-IDs touched by this change (REQ-38, REQ-45, REQ-49, REQ-51, REQ-68, REQ-69, REQ-70) have at least one passing test. Zero uncovered REQ-IDs.

### Adversarial Quality Gate (final mode)

**Code audit (pre-pr mode)**: 2 findings, 0 gating, 2 followups (both WARNING — evidenced but not outcome-blocking per the signed spec/problem_statement)

| Severity | File:Line | Finding |
|---|---|---|
| WARNING (Architecture — coherence) | `detector/backtest/simulate.py:351` | `leg2_tp_index = tp_index if tp_index is not None and tp_index >= partial_index else None` uses `>=`, i.e. a leg-2 TP touch on the SAME candle as the partial's own resolving index is kept. This diverges from the signed spec's literal text ("a second leg resolves... starting at the partial's resolving index **+ 1**") and design's Approach section ("sliced to indices **after** the partial"). The code comment (lines 345-349) explains the reasoning well (same-side/monotonic geometry means a candle touching TP necessarily also touches the partial level; using strict `>` would silently drop a genuine TP resolution). This is exercised in practice by the default e2e fixture (`test_trades_csv_partial_columns_populated_when_fired`'s docstring: "reaches take_profit within the same candle the partial level resolves") and produces a sensible, positive result — this reads as a deliberate, reasoned improvement over the spec's literal wording, not a bug. But the divergence was never fed back into the signed spec/design text (unlike the tracked REQ-68 V1→V2 correction), so a future reader of spec.md/design.md would not know this tie-break exists. **Fix option**: either amend REQ-68/design.md's prose to state the `>=` tie explicitly (mirrors how the V1→V2 correction was documented), or leave as a documented follow-up. |
| WARNING (Epic AC check — untested branch) | `detector/backtest/simulate.py:353-361` | The branch where the partial leg FIRES but the remainder (leg 2) never touches SL or TP by series end — i.e., an overall `outcome="open"` trade that nonetheless has non-null `partial_exit_index/price/r_multiple` — has ZERO test coverage in the diff. Manually reproduced during this verification (a series where partial fires at index 7, then neither SL nor TP is ever touched): the branch behaves correctly (`outcome="open"`, `exit_index/exit_price/r_multiple=None`, partial fields populated), but this exact state combination is not covered by REQ-38.1 (which only covers "neither SL, TP, nor partial ever touched") nor by any other signed scenario, and it surfaces a real disclosure ambiguity in REQ-49.5's text ("distinct from the open-trades count") — the implementation counts such a trade in BOTH `open trades: N` and `partial exits: N` in `metrics_summary.txt`, and no test asserts whether that double-counting is intended. The real-data evidence run shows this state is reachable (DXYm: 1 open trade among 1063 partial exits, pooled 1 open trade) — not a theoretical-only edge case. **Fix option**: add a unit test pinning this branch's exact fields, and either confirm the double-counting is intentional (add a line to REQ-49.5) or exclude open trades from the `partial_exits` count. |

Both findings pass the EVIDENCE filter (repro'd directly / read directly from the diff) but fail the OUTCOME filter (neither breaks a signed REQ scenario — REQ-38.1's precondition of "never touched" simply doesn't apply to WARNING-2's scenario, and REQ-49.5's scenario text is satisfied literally as written; the change's stated purpose — producing a valid winrate/R number for the two-stage model — is unaffected since `open` trades are already excluded from win/loss/R aggregation regardless of partial-field population). Neither is `Bug`/`Architecture`/`MAJOR` at a gating tier — both route to followups.

No scope-creep found: every file in the diff matches design's File Changes table exactly (6 source files + 5 test files, 1 created). No sensitive area touched (confirmed against `project/sensitive-areas`). No TODO/FIXME/banned-cast markers introduced. No dead duplication (the simplify-gate commit `ad5c6dc` already extracted the one duplication that existed, `_resolve_level_exit`).

**Live-app pass**: N/A — no UI changes (CLI/CSV/txt batch tool, no interactive surface).
**Adversarial review (judgment-day)**: not-required — triage M, no sensitive area altered (confirmed multiple times against `project/sensitive-areas`, obs #297).

### Spec Compliance Matrix
| Requirement | Scenario | Test | Result |
|---|---|---|---|
| REQ-68 | general (formula) | `test_backtest_levels.py::test_partial_price_is_entry_to_target_midpoint` | ✅ COMPLIANT |
| REQ-68.1 | two-leg win-then-win | `test_backtest_simulate.py::test_two_leg_trade_blends_partial_and_remainder_r_multiple` | ✅ COMPLIANT |
| REQ-68.2 | two-leg win-then-loss, unmoved stop | `test_backtest_simulate.py::test_two_leg_trade_leg2_uses_unmoved_original_stop` | ✅ COMPLIANT |
| REQ-68.3 | SL wins tie, no partial | `test_backtest_simulate.py::test_sl_wins_tie_against_partial_collapses_to_single_leg` | ✅ COMPLIANT |
| REQ-68.4 | gap-through partial | `test_backtest_simulate.py::test_partial_leg_gap_through_fills_at_open` | ✅ COMPLIANT |
| REQ-68.5 | `partial_fraction=0.0` regression | `test_backtest_simulate.py::test_partial_fraction_zero_reproduces_single_leg_output` | ✅ COMPLIANT |
| REQ-68.6 | never touched (incl. partial) | `test_backtest_simulate.py::test_open_trade_has_no_partial_leg_fields` | ✅ COMPLIANT |
| REQ-69.1 | blended R happy path | `test_backtest_simulate.py::test_two_leg_trade_blends_partial_and_remainder_r_multiple` | ✅ COMPLIANT |
| REQ-69.2 | cost-default neutrality | `test_backtest_simulate.py::test_two_leg_blended_r_zero_cost_is_bit_identical` | ✅ COMPLIANT |
| REQ-69.3 | single-leg unblended | `test_backtest_simulate.py::test_sl_wins_tie_against_partial_collapses_to_single_leg` | ✅ COMPLIANT |
| REQ-70.1 | ordering holds, real corpus | `tests/property/test_partial_price_ordering.py::test_partial_price_ordering_holds_across_real_corpus` | ✅ COMPLIANT (0 violations, 3 instruments) |
| REQ-70.2 | loud failure, named candidate | `tests/property/test_partial_price_ordering.py::test_ordering_violation_fails_loudly_naming_candidate` | ✅ COMPLIANT |
| REQ-38.1 | open trade, all fields empty | `test_backtest_simulate.py::test_open_trade_has_no_partial_leg_fields` | ✅ COMPLIANT |
| REQ-38.2 | blended sign sets outcome | `test_backtest_simulate.py::test_two_leg_trade_blends_partial_and_remainder_r_multiple` | ✅ COMPLIANT |
| REQ-38.3 | no-partial fields stay empty | `test_backtest_simulate.py::test_sl_wins_tie_against_partial_collapses_to_single_leg` / `test_partial_fraction_zero_reproduces_single_leg_output` | ✅ COMPLIANT |
| REQ-45.4 | 17-column header, in order | `test_cli_backtest_e2e.py::test_trades_csv_header_has_17_columns_in_order` | ✅ COMPLIANT |
| REQ-45.5 | trailing cells populated/blank | `test_cli_backtest_e2e.py::test_trades_csv_partial_columns_populated_when_fired` | ✅ COMPLIANT |
| REQ-49.5 | `partial exits: N` disclosure | `test_backtest_metrics.py::test_partial_exits_count_in_mixed_population` + `test_cli_backtest_e2e.py::test_metrics_summary_discloses_partial_exits_count` | ⚠️ PARTIAL — literal scenario passes; see WARNING-2 (open+partial double-counting untested) |
| REQ-51.4 | `--partial-fraction 0.0` CLI regression | `test_cli_backtest_e2e.py::test_partial_fraction_zero_cli_reproduces_pre_change_output` | ✅ COMPLIANT |
| REQ-51.5 | out-of-range rejection | `test_cli_backtest_e2e.py::test_invalid_partial_fraction_exits_1_naming_flag_and_constraint` | ✅ COMPLIANT |

**Compliance summary**: 19/20 rows fully compliant, 1/20 (REQ-49.5) compliant-with-a-caveat (its literal GIVEN/WHEN/THEN passes; a related untested state is flagged as a followup, not a scenario failure).

### Coherence (Design)
| Decision | Followed? | Notes |
|---|---|---|
| `partial_price(entry_price, take_profit)` signature (V2 revision) | ✅ Yes | Exact signature, exact formula, exact call site (`_build_candidate`) |
| Third `two_heap_sweep` pass via `_partial_sides()` mirroring `_tp_sides()` | ✅ Yes | Identical structure, `invert_bullish=True` |
| SL-wins-ties generalized to partial level | ✅ Yes | `partial_fires` guard matches REQ-68.3 exactly |
| Leg 2 reuses the SAME sweep results (no new sweep) | ✅ Yes | No additional `two_heap_sweep` call for leg 2 |
| Leg 2 restricted to "indices after the partial" | ⚠️ Partial | Implemented as `>=` (includes the tie), not strict `>` as design's prose states — see WARNING-1 |
| Blended R + proportional cost allocation (REQ-69) | ✅ Yes | `cost_leg1 + cost_leg2 == trading_cost_price` exactly; both legs measured against original entry/stop |
| `BacktestConfig.partial_fraction: float = 0.5`, single new field | ✅ Yes | No separate enable/disable flag, as designed |
| `trades.csv` 13→17 columns, append-only | ✅ Yes | Matches `detections.csv` precedent |
| No ADRs (architecture_impact: none) | ✅ Yes | No new module/dependency/boundary introduced; lint-imports confirms |
| Simplify-gate dedup (`_resolve_level_exit`) | ✅ Yes | Applied post-hoc (commit `ad5c6dc`), verified no behavior change (248/249 unchanged) |

### Drift / Cross-Change
| Module | Status | Notes |
|---|---|---|
| `.importlinter` ADR-01 layered pipeline | ✅ Held | 1 kept / 0 broken |
| `tests/property/test_no_lookahead.py` (sort-order invariance) | ✅ Held for the new pass | The new partial sweep is symmetric with SL/TP and doesn't alter sort-order preconditions; the one failing test in this file predates this change entirely |

### In-Loop History
No separate `verify-in-loop-{N}` artefacts were persisted this run — the orchestrator performed lightweight inline verification for S-000 (iteration 1: NEEDS_FIX → fixed → confirmed, per commit `0b16489`) and proceeded through S-001/S-002/S-003 without separate in-loop verify sub-agent calls, given straightforward TDD evidence in `apply-progress` (obs #499). This is disclosed per the launch context; this final-mode pass is the first comprehensive, full-suite verification of the complete change.

### Issues Found
**CRITICAL** (must fix before archive): None
**WARNING** (should fix): 2 — see Adversarial Quality Gate table above (WARNING-1: undocumented `>=` tie-break divergence from design prose; WARNING-2: untested partial-fires-then-open branch + REQ-49.5 double-counting ambiguity)
**SUGGESTION** (nice to have): None beyond the two WARNINGs
**IMPROVEMENTS** (real but not blocking for THIS problem): None identified beyond the followups above

### Verdict
**pass-with-followups**

Both WARNINGs are evidenced (one by direct code/spec-text comparison, one by a live repro of the untested branch) but neither breaks a signed REQ scenario or the change's stated purpose (producing a valid two-stage winrate/R number — confirmed via `evidence/real-data-two-stage-exit.md`: 40.0% pooled winrate, 0.297R average, up from the 23-27% single-TP baseline, across all 3 real instruments with zero REQ-70 ordering violations). 248/249 tests pass (1 pre-existing, unrelated failure), `lint-imports` clean, all 19 signed REQ scenarios have passing tests, no scope creep, no sensitive area touched, no lingering V1-formula references anywhere in code, tests, or docs. Route both WARNINGs to `project/pending-changes` as followups at archive.
