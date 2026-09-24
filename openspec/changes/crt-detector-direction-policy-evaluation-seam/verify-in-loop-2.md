# Verification Report: DirectionPolicy Evaluation Seam — In-Loop 2

**Change:** `crt-detector-direction-policy-evaluation-seam`  
**Mode:** Strict TDD  
**Verdict:** PASS WITH ONE PREEXISTING, NON-BLOCKING FAILURE

## Executive summary

The revised producer boundary is correct: `build_stage6_population()` performs the unchanged stages 1–6 in their original order, `simulate()` passes `population.candidates` by identity directly to the unchanged `_fill_pass`, and evaluation independently consumes those candidates with caller-owned evidence. The repaired import-fitness test uses `sys.executable -c ...`, passes, and no longer spawns the blocked console-script wrapper.

All seam-relevant tests and Import Linter pass. The full suite has one explicitly allowed failure, `tests/property/test_no_lookahead.py::test_alignment_detection_has_no_lookahead`; its standalone rerun reproduced the identical assertion failure, so it is classified PREEXISTING/UNRELATED/NON-BLOCKING.

## Authority

The frozen canonical Git artifact was independently read as raw bytes from commit `f542924ea4280af384b298e6fc4b54dfb54a33e6`: 7737 bytes; SHA-256 `47b17d7891f6f9a2d2d30f83df88b060840a895484a78e763c8f46da1ea8de4d`.

## Completeness

| Metric | Value |
|---|---:|
| Slice tasks | 7 |
| Marked complete | 6 |
| Marked incomplete | 1 |

`S-000.7` remains unchecked in the stored slices artifact, but this evaluator executed its required full-suite gate below. This is a non-blocking artifact-status warning, not an implementation gap.

## Executed gates

| Command | Result |
|---|---|
| `.\.venv\Scripts\python.exe -m pytest tests\test_direction_policy.py -q` | 194 passed, exit 0 |
| `.\.venv\Scripts\python.exe -m pytest tests\test_direction_evaluation.py -q` | 33 passed, exit 0 |
| `.\.venv\Scripts\python.exe -m pytest tests\test_backtest_population.py tests\test_backtest_simulate.py tests\test_fitness_imports.py -q` | 34 passed, exit 0 |
| `.\.venv\Scripts\python.exe -m pytest -q` | 602 passed, 1 failed, exit 1 — allowed unrelated failure below |
| `.\.venv\Scripts\python.exe -c "from importlinter.cli import lint_imports_command; lint_imports_command()"` | 4 contracts kept, 0 broken, exit 0 |
| `.\.venv\Scripts\python.exe -m pytest tests\property\test_no_lookahead.py::test_alignment_detection_has_no_lookahead -q` | 1 failed, exit 1 — reproduced identically |

The first combined full-suite/import-linter invocation exceeded the 120-second command limit after reaching the known failure; both gates were then run independently to completion. No configured type checker or coverage tool exists in `detector/pyproject.toml`, so neither gate is available. No real data, CLI, build, install, security change, or bypass was used.

## Compliance matrix

| Requirement | Result | Runtime/static evidence |
|---|---|---|
| REQ-01 frozen P1→P4 identity | ✅ | `FROZEN_POLICY_IDS` and `_POLICIES` are fixed in `evaluation/direction.py:19-30`; direction-policy and evaluation suites pass. |
| REQ-02 policy-independent stage-6 population | ✅ | `population.py:119-143`; producer-to-fill/evaluation test passes. |
| REQ-03 K≥3 and K−1 cutoff | ✅ | `direction.py:109,128-136`; timing tests pass. |
| REQ-04 provenance/bounds | ✅ | Exact same M15 object, instrument, timeframe, dense Bias, candidate and OF bounds are fail-closed; 33 evaluation tests pass. |
| REQ-05 Bias/OF cutoff | ✅ | Bias is selected at `K−1`; policies receive that cutoff and future OF is excluded; focused tests pass. |
| REQ-06 total three-state relation | ✅ | `PolicyRelation` has exactly ALIGNED/OPPOSED/UNRESOLVED; six-pair and property tests pass. |
| REQ-07 immutable outcome-free rows | ✅ | Frozen `DirectionEvaluation`; no outcome fields; immutability/firewall tests pass. |
| REQ-08 deterministic 4N/shared universe | ✅ | Candidate `(retest_index, signal_id)` ordering then P1→P4; cardinality and shared-universe tests pass. |
| REQ-09 identity/duplicates | ✅ | `(instrument,timeframe,signal_id,retest_index)` duplicates raise `DuplicateCandidateError`; tests pass. |
| REQ-10 isolation | ✅ | Evaluation sorts a copied tuple and does not mutate candidates; simulation receives producer list by identity; tests pass. |
| REQ-11 fail-closed validation | ✅ | Named provenance/index/duplicate/evidence/integrity errors cover malformed direction, K, candidate order/bounds, empty instrument, and OF failures. |
| REQ-12 import/outcome firewall | ✅ | Import Linter reports four kept contracts, including evaluation→outcome modules and research→evaluation. |
| REQ-13 synthetic Strict TDD | ✅ | Focused synthetic unit/property tests pass; no real data required. |
| REQ-14 no runner/outcome/statistics API | ✅ | Public evaluation surface is only evidence, relation rows, and batch evaluation; source and fitness checks find no forbidden capability. |
| REQ-15 quality gates | ✅ | All seam gates pass; the only full-suite failure is independently reproduced and explicitly allowed. |

## Producer and semantic-drift judgment

`backtest.population.build_stage6_population()` contains the original sequence `_population_cuts → _build_candidate → _dedup → _kill_zone_cut → _rr_floor_cut` and carries each original exclusion count. `backtest.simulate.simulate()` calls it once, forwards `population.candidates` unchanged to `_fill_pass`, then sources `ReconciliationReport` fields from the same result. Its input/return signature and fill/exit lifecycle are unchanged; the 30 existing simulation tests pass together with the two boundary tests. Evaluation neither imports nor is invoked by simulation, and it has no outcome, runner, callback, statistics, serialization, simulation, or research semantic surface.

The repaired `tests/test_fitness_imports.py` invokes Import Linter through `sys.executable` and asserts its successful subprocess result. The 34-test affected gate proves it no longer spawns the blocked `lint-imports.exe` wrapper.

## Strict TDD

| Check | Result | Details |
|---|---|---|
| TDD evidence reported | ✅ | `apply-progress.md` contains RED/GREEN evidence for each implementation group. |
| RED confirmed | ✅ | `test_direction_evaluation.py`, `test_fitness_imports.py`, and `test_backtest_population.py` exist. |
| GREEN confirmed | ✅ | Relevant focused/affected gates: 33 + 34 passed. |
| Triangulation | ✅ | Relation pairs, cutoff values, invalid input variants, ordering/cardinality, firewall, and producer identity are separately asserted. |
| Safety net | ⚠️ | Apply record lacks a pre-extraction baseline for modified `backtest/simulate.py`; post-change affected legacy tests pass. |

**Assertion quality (superseded; see 2026-09-11 correction addendum):** The historical in-loop review concluded that no tautology was present. A later pre-commit audit found one tautological property test; the corrected conclusion is recorded below.

### Test layer distribution

| Layer | Tests | Files |
|---|---:|---:|
| Unit/property/fitness | 67 focused/affected | 4 |
| Integration | 0 | 0 |
| E2E | 0 | 0 |

## Issues

**CRITICAL:** None.

**WARNING:** The slices artifact still leaves `S-000.7` unchecked despite this completed gate; synchronize its status in the executor record.

**PREEXISTING/UNRELATED/NON-BLOCKING:** `tests/property/test_no_lookahead.py::test_alignment_detection_has_no_lookahead` fails at its existing full-versus-truncated `AlignedSignal` equality assertion. The standalone gate reproduced the same generated EURUSD 1H/5M example and assertion location (`test_no_lookahead.py:547`); no changed seam module is in its traceback.

## Verdict

**PASS WITH WARNINGS.** The stage-6 producer boundary, evaluation firewall, frozen timing/identity/relation behavior, and repaired import-fitness gate satisfy the signed spec. The known unrelated property failure does not block this in-loop verification.

## 2026-09-11 Pre-Commit Correction Addendum

The assertion-quality statement above remains historical evidence and is superseded only for the newly found test issue. Audit found that `tests/test_direction_evaluation.py:319-326` self-compared `_policy_relation(...)`, so it was tautological. The test now observes public `evaluate_direction_policies(...)`, covers all six valid candidate/policy-direction pairs, compares `DirectionEvaluation.relation` to the test-owned unresolved/equal/opposed oracle, and varies unrelated instrument, policy ID, reason, and signal-ID metadata without changing the expected relation. It does not call `_policy_relation()` for expected or actual values.

`.\.venv\Scripts\python.exe -m pytest tests\test_direction_evaluation.py -q` → **36 passed**. Sensitivity was proven with a temporary inversion of `_policy_relation()`'s `ALIGNED`/`OPPOSED` branches: `.\.venv\Scripts\python.exe -m pytest tests\test_direction_evaluation.py -q -k relation_depends_only_on_candidate_and_decision_directions` → **1 failed, 35 deselected**; after immediate reversion, the corrected-file gate returned **36 passed**. No production mutation remains.

Narrow evaluation-seam tautology audit: no other self-comparison or expected value derived through the production helper was found. The six-pair example test uses literal expected relations.
