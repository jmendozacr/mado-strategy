# Verification Report: DirectionPolicy Evaluation Seam — In-Loop 1

**Change:** `crt-detector-direction-policy-evaluation-seam`  
**Mode:** Strict TDD  
**Verdict:** FAIL

## Executive summary

The isolated evaluator correctly implements the K−1 calculation, four frozen policies, ordering, immutable result rows, and the import-linter contract under synthetic tests. Verification halts because the changed import-firewall fitness test is still blocked by its direct `lint-imports.exe` subprocess, and the seam is not connected to the actual stage-6-to-pre-fill boundary, so it cannot prove or enforce that its supplied candidates are that population.

## Authority

`detector/research/direction_policy_discovery_v1_amendment_1.json` matches the required Git authority: commit `f542924ea4280af384b298e6fc4b54dfb54a33e6`, blob `d2b759320ed9017eec53eff24f924dd18c8e4ec8`, SHA-256 `47b17d7891f6f9a2d2d30f83df88b060840a895484a78e763c8f46da1ea8de4d`, and 7737 bytes. The local design references this canonical path and commit, not the obsolete Engram digest.

## Execution

| Command | Result |
|---|---|
| `.\\.venv\\Scripts\\python.exe -m pytest tests\\test_direction_policy.py -q` | 194 passed, exit 0 |
| `.\\.venv\\Scripts\\python.exe -m pytest tests\\test_direction_evaluation.py -q` | 26 passed, exit 0 |
| `.\\.venv\\Scripts\\python.exe -m pytest tests\\test_backtest_simulate.py tests\\test_fitness_imports.py -q` | 30 passed, 1 failed, exit 1 |
| `.\\.venv\\Scripts\\python.exe -m pytest -q` | 592 passed, 1 failed, exit 1 |
| `.\\.venv\\Scripts\\python.exe -m pytest tests\\property\\test_no_lookahead.py::test_alignment_detection_has_no_lookahead -q` | 1 failed, exit 1; reproduces the explicitly allowed unrelated failure |
| `.\\.venv\\Scripts\\python.exe -c "from importlinter.cli import lint_imports_command; lint_imports_command()"` | 4 kept, 0 broken, exit 0 |

No configured type checker was found in `detector/pyproject.toml` or project type-checker configuration; no type-check command was run. No coverage tool is configured.

## Compliance

| Area | Result | Evidence |
|---|---|---|
| Frozen P1→P4 identity, 4N cardinality, deterministic candidate/policy order | Compliant | `evaluation/direction.py:19-30,115,125-145`; evaluation tests pass |
| K≥3, exact Bias@K−1, no K/future OF usage | Compliant | `direction.py:107-110,126-134`; timing tests pass |
| M15/same-object series provenance, bounds, duplicate identity, OF index checks | Partial | Core checks exist and focused tests pass; malformed direction, empty instrument, candidate-order/bounds, and OF duplicate/out-of-range paths lack direct tests |
| Three-state relation, immutable rows, unresolved/opposed preservation, candidate non-mutation | Compliant | `direction.py:53-82,66-75`; focused tests pass |
| Outcome/import firewall | Partial | Direct module-form Import Linter passes; the repository fitness test does not run under Windows Application Control |
| Stage-6 → pre-fill placement | Missing | `simulate()` passes stage-6 survivors directly from `_rr_floor_cut` to `_fill_pass` at `backtest/simulate.py:413-414`; it never invokes the evaluator |
| Policy isolation and no candidate population filtering | Partial | Evaluator sorts a copied sequence and does not filter or mutate it; however, no provenance-bearing boundary connects supplied candidates to the canonical stage-6 population |

## TDD compliance

The apply artifact records genuine RED/GREEN evidence and the new test file exists. GREEN is confirmed for its 26 focused tests. The safety-net record is incomplete for modified `backtest/simulate.py` (no pre-extraction baseline), a warning. Assertions in `tests/test_direction_evaluation.py` invoke production code and assert observable values; no trivial assertion was found.

## Critical issues

1. **Import-firewall fitness test fails:** `tests/test_fitness_imports.py::test_import_linter_layers_contract_holds` directly launches `.venv\\Scripts\\lint-imports.exe`, which Windows Application Control blocks with `OSError: [WinError 4551]`. This is not the permitted `test_alignment_detection_has_no_lookahead` failure. Because S-000 explicitly includes import-firewall coverage, update this fitness test to invoke the approved module-form Import Linter through `sys.executable -c ...`, then retain an assertion on its exit status.
2. **No actual stage-6/pre-fill seam placement:** the new evaluator is an uncalled API. It cannot establish that inputs are the canonical policy-independent EP-C stage-6 candidates, contrary to REQ-DIR-EVAL-02 and the required placement check. Introduce the smallest outcome-free boundary that exposes the existing stage-6 survivors immediately after `_rr_floor_cut` and before `_fill_pass`, preserving the existing candidate list, filters, and fill behavior; feed that boundary to evaluation only through explicit caller-owned evidence.

## Warnings

- Add synthetic fail-closed tests for all validation branches claimed by the apply report: empty instrument, malformed candidate direction, index/order/out-of-range candidate, duplicate/out-of-range Order Flow, and dense/ordered Bias violations.
- Mark S-000.7 complete only after the required full-suite result is recorded; it remains unchecked in `slices`.

## Routing

`halt: verify-failed` — category `implementation`. Fix the two critical issues, then re-run this in-loop verification.
