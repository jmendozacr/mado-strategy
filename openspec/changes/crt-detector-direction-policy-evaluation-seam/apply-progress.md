# Apply Progress: DirectionPolicy Evaluation Seam

**Change:** `crt-detector-direction-policy-evaluation-seam`  
**Slice:** S-000  
**Mode:** Strict TDD  
**Status:** complete — provenance-bound evaluation repair and final verification passed.

## Completed work

- [x] S-000.1 Synthetic relation, cutoff, no-lookahead, cardinality, ordering, immutability, unresolved, opposed, and isolation tests.
- [x] S-000.2 Synthetic provenance, M15, K floor, duplicate identity, dense Bias, and Order Flow integrity tests.
- [x] S-000.3 Synthetic outcome-firewall and import-fitness configuration tests.
- [x] S-000.4 Extracted the unchanged immutable `Candidate` record from `backtest.simulate`.
- [x] S-000.5 Added the outcome-free batch evaluation seam and fixed P1–P4 ordering.
- [x] S-000.6 Added import-linter firewall rules and the change-local design record.
- [x] S-000.7 Final verification passed all relevant gates; the sole full-suite failure is pre-existing, unrelated, and non-blocking.

## Verifier follow-up

- [x] Replaced the repository fitness test's blocked console-script invocation with the approved current-interpreter module call.
- [x] Added synthetic fail-closed coverage for empty instruments, malformed candidate directions, unordered/out-of-range candidate indices, and duplicate/out-of-range Order Flow confirmation indices.
- [x] Extracted `build_stage6_population()` as the canonical outcome-free stage-1–6 boundary; `simulate()` passes its returned candidates directly to the unchanged fill pass, and evaluation consumes that same candidate output independently.

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|---|---|---|---|---|---|---|---|
| S-000.1–.5 | `tests/test_direction_evaluation.py` | Unit + property | Existing simulation baseline was not captured before the extraction; post-change affected legacy run: 224 passed | `python -m pytest tests\\test_direction_evaluation.py -q` → collection error: `No module named 'backtest.candidate'` | 26 passed | Six relation pairs, K=3/K=10, future evidence, 4N, and arbitrary valid batches | Candidate type extraction kept behavior unchanged |
| S-000.6 | `tests/test_direction_evaluation.py` | Fitness | N/A (new configuration) | 25 passed, 1 failed: missing `evaluation` import-linter configuration | 26 passed; direct module-form Import Linter: 4 kept, 0 broken | Direct forbidden-edge test plus package/config assertions | Removed Candidate's transitive `backtest.levels` dependency to satisfy the firewall |

| Verifier findings 1–2 | `tests/test_fitness_imports.py`, `tests/test_direction_evaluation.py` | Unit + fitness | Fitness: 1 passed; evaluation: 26 passed; simulation: 30 passed | Fitness: 2 failed (`_lint_imports_command` absent and legacy helper removed). Evaluation: 1 failed (`sideways` direction did not raise); 32 passed | Fitness: 2 passed. Evaluation: 33 passed | Empty instrument, three bounds/order cases, two invalid OF cases, and malformed direction | No refactor needed |
| Verifier finding 3 | `tests/test_backtest_population.py` | Unit | `tests\\test_backtest_simulate.py tests\\test_direction_evaluation.py tests\\test_fitness_imports.py`: 65 passed | Collection failed: `ModuleNotFoundError: No module named 'backtest.population'`; count test then failed `excluded_duplicate == 1` vs `2` | 2 population tests passed; affected suite: 67 passed | Direct producer→fill identity, independent evaluator consumption, survivor identity, duplicate and R:R exclusions | Moved only stages 1–6 into `backtest.population`; fill/exit logic unchanged |

## Scoped Gates

```text
.\\.venv\\Scripts\\python.exe -m pytest tests\\test_direction_evaluation.py -q
26 passed in 1.14s

.\\.venv\\Scripts\\python.exe -c "from importlinter.cli import lint_imports_command; lint_imports_command()"
Contracts: 4 kept, 0 broken.

.\\.venv\\Scripts\\python.exe -m pytest tests\\test_backtest_simulate.py tests\\test_direction_policy.py tests\\test_fitness_imports.py -q
224 passed, 1 failed.

.\\.venv\\Scripts\\python.exe -m pytest tests\\test_direction_evaluation.py tests\\test_fitness_imports.py tests\\test_backtest_simulate.py -q
65 passed in 2.20s

.\\.venv\\Scripts\\python.exe -c "from importlinter.cli import lint_imports_command; lint_imports_command()"
Contracts: 4 kept, 0 broken.

.\\.venv\\Scripts\\python.exe -m pytest tests\\test_backtest_population.py -q
2 passed in 0.60s

.\\.venv\\Scripts\\python.exe -m pytest tests\\test_backtest_population.py tests\\test_backtest_simulate.py tests\\test_direction_evaluation.py tests\\test_fitness_imports.py -q
67 passed in 2.19s

.\\.venv\\Scripts\\python.exe -c "from importlinter.cli import lint_imports_command; lint_imports_command()"
Contracts: 4 kept, 0 broken.
```

The former legacy failure was `tests/test_fitness_imports.py::test_import_linter_layers_contract_holds`: Windows Application Control blocked its direct `lint-imports.exe` subprocess (`WinError 4551`). It is resolved without bypassing Application Control: the fitness test now invokes `importlinter.cli.lint_imports_command()` through `sys.executable`, the approved interpreter path.

## Finding 3 resolution

`build_stage6_population()` now owns only the policy-independent stage-1–6 sequence and its reconciliation counts. `simulate()` calls it once and passes `population.candidates` by identity to `_fill_pass`; it neither imports evaluation nor changes its inputs or return type. Evaluation accepts the outcome-free `Stage6Population` and same-object evidence series without importing simulation or outcome modules.

## Authority

Canonical provenance: `detector/research/direction_policy_discovery_v1_amendment_1.json` at commit `f542924ea4280af384b298e6fc4b54dfb54a33e6`, SHA-256 `47b17d7891f6f9a2d2d30f83df88b060840a895484a78e763c8f46da1ea8de4d`, 7737 bytes.

## Final-verification provenance repair

- [x] `Stage6Population` retains the exact source `OHLCSeries` object and remains the sole public batch-evaluation input.
- [x] Evaluation rejects loose candidate sequences, cross-series evidence, and invalid provenance before it labels `population.candidates`.
- [x] `simulate()` still hands the producer's exact candidate list directly to `_fill_pass`; synthetic approval coverage preserves its trade and reconciliation result.
- [x] The outcome firewall permits the intended indirect producer dependency while still prohibiting direct evaluation imports of outcome-bearing backtest modules and research.

### TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|---|---|---|---|---|---|---|---|
| Provenance-bound batch API | `tests/test_direction_evaluation.py`, `tests/test_backtest_population.py` | Unit | 67 passed | 30 failed: `Stage6Population` lacked `series` and evaluator still required loose arguments | 38 passed | Loose input, equal-but-distinct series identity, population-only rows, source identity, K−1/order/4N regressions | Minimal signature and source-reference change; no new abstraction |
| Simulation preservation | `tests/test_backtest_population.py` | Unit approval | Included in 67-pass baseline | Approval assertion first exposed the actual established fill index (4), then was corrected to its observed behavior | 3 population tests passed | Existing direct producer-to-fill identity plus exact trade/report approval | None needed |
| Import firewall boundary | `tests/test_direction_evaluation.py`, `tests/test_fitness_imports.py` | Fitness | 38 focused tests passed before config adjustment | 1 failed: required indirect-import allowance absent; firewall then reported producer's transitive `backtest.levels` dependency | 265 affected tests passed; Import Linter 4 kept, 0 broken | Static config assertion plus runtime direct forbidden-edge contract | Allowed only the intended indirect producer path |

## Final-verification repair gates

```text
.\\.venv\\Scripts\\python.exe -m pytest tests\\test_direction_evaluation.py tests\\test_direction_policy.py tests\\test_backtest_population.py tests\\test_backtest_simulate.py tests\\test_fitness_imports.py -q
265 passed in 6.25s

.\\.venv\\Scripts\\python.exe -c "from importlinter.cli import lint_imports_command; lint_imports_command()"
Contracts: 4 kept, 0 broken.
```
