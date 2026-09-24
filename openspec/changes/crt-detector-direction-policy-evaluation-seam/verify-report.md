# Verification Report: DirectionPolicy Evaluation Seam

**Change:** `crt-detector-direction-policy-evaluation-seam`  
**Mode:** Strict TDD  
**Verdict:** **PASS WITH WARNINGS**  
**adversarial_review:** not-required

## Executive Summary

The provenance repair is present and behaviorally covered: the public evaluator accepts only a `Stage6Population`, requires `population.series is evidence.series`, validates the M15 source and indices before producing labels, and simulation still sends the producer's unmodified candidate list directly to fill. All required focused gates passed; Import Linter retained all four contracts.

The full suite has one failure: `tests/property/test_no_lookahead.py::test_alignment_detection_has_no_lookahead`. The file is unmodified in the current diff and the failure is the explicitly allowed PREEXISTING / UNRELATED / NON-BLOCKING exception. No other failures occurred.

## Completeness

| Metric | Value |
|---|---:|
| Slice tasks total | 7 |
| Implementation tasks complete | 6 |
| Final-evaluator task | 1 |
| Uncompleted implementation tasks | 0 |

`S-000.7` is intentionally the final verification gate and is satisfied by this report.

## Build, Tests, and Quality Execution

| Gate | Command | Result |
|---|---|---|
| DirectionPolicy | `.\.venv\Scripts\python.exe -m pytest tests\test_direction_policy.py -q` | ✅ 194 passed, 0 failed (3.84s) |
| Evaluation / population / simulation / fitness | `.\.venv\Scripts\python.exe -m pytest tests\test_direction_evaluation.py tests\test_backtest_population.py tests\test_backtest_simulate.py tests\test_fitness_imports.py -q` | ✅ 71 passed, 0 failed (2.33s) |
| Full suite | `.\.venv\Scripts\python.exe -m pytest` | ⚠️ 606 passed, 1 allowed unrelated failure (202.41s) |
| Import Linter | `.\.venv\Scripts\python.exe -c "from importlinter.cli import lint_imports_command; lint_imports_command()"` | ✅ 4 kept, 0 broken; 47 files / 108 dependencies |
| Type checker | Not configured as an interpreter-runnable Python module | ➖ Not run |
| Coverage | No coverage tool or threshold configured | ➖ Not available |

### Failure Classification

`tests/property/test_no_lookahead.py::test_alignment_detection_has_no_lookahead` failed in the complete run. It is the permitted exception: the test file has no working-tree diff, its latest recorded revision predates this change (`7b09c318...`, 2026-09-09), and its failure concerns settled `Model1Signal` alignment state rather than the evaluation seam. Classification: **PREEXISTING / UNRELATED / NON-BLOCKING**.

## TDD Compliance

| Check | Result | Details |
|---|---|---|
| TDD evidence reported | ✅ | `apply-progress.md` contains RED/GREEN/triangulation records. |
| All tasks have tests | ✅ | Direction evaluation, producer/fill preservation, and import-firewall tests exist and passed. |
| RED confirmed | ✅ | Relevant test files exist; provenance API, producer, and firewall RED states are recorded. |
| GREEN confirmed | ✅ | 265 affected tests were previously recorded; independent focused rerun passed 71 relevant tests. |
| Triangulation adequate | ✅ | Relation pairs, K=3/K=10, future evidence, cross-series identity, loose input, ordering, and fill handoff are separately asserted. |
| Safety net for modified files | ⚠️ | The original candidate extraction lacks a pre-extraction baseline record; the provenance repair baseline and regression gates are recorded. |

**TDD Compliance:** 5/6 checks passed; the safety-net record is a non-blocking historical documentation warning.

### Test Layer Distribution

| Layer | Tests | Files | Tools |
|---|---:|---:|---|
| Unit / property | 265 affected (recorded); 71 independently rerun | 5 | pytest + Hypothesis |
| Integration | 0 | 0 | Not configured |
| E2E | 0 | 0 | Not configured |

### Assertion Quality

**Assertion quality (superseded; see 2026-09-11 correction addendum):** The prior review concluded that all reviewed seam assertions called production behavior and that no tautologies were present. A pre-commit audit subsequently found one tautological property test; the corrected conclusion is recorded below.

## Spec Compliance Matrix

| Requirement | Runtime evidence | Result |
|---|---|---|
| REQ-DIR-EVAL-01 | `test_direction_evaluation.py` fixed order / isolated policy tests; source `_POLICIES` is P1→P4 | ✅ |
| REQ-DIR-EVAL-02 | Public API rejects loose sequences; evaluates only `population.candidates` | ✅ |
| REQ-DIR-EVAL-03 | K≥3 and K−1 cutoff tests; no K/intrabar access test | ✅ |
| REQ-DIR-EVAL-04 | Exact `OHLCSeries` identity, M15, instrument, and bounds rejection tests | ✅ |
| REQ-DIR-EVAL-05 | Bias-at-K−1 and OF-through-K−1 tests | ✅ |
| REQ-DIR-EVAL-06 | Six direction-pair relation test | ✅ |
| REQ-DIR-EVAL-07 | Frozen evaluation record / no outcome fields test | ✅ |
| REQ-DIR-EVAL-08 | 4N, canonical order, and common candidate-universe tests | ✅ |
| REQ-DIR-EVAL-09 | Duplicate identity rejection test | ✅ |
| REQ-DIR-EVAL-10 | Producer-to-fill object-identity and preserved simulation result tests | ✅ |
| REQ-DIR-EVAL-11 | Loose input, distinct-series, malformed direction, index, and evidence failures raise named errors | ✅ |
| REQ-DIR-EVAL-12 | Four Import Linter contracts and AST firewall test | ✅ |
| REQ-DIR-EVAL-13 | Synthetic pytest/Hypothesis tests pass; no real data used | ✅ |
| REQ-DIR-EVAL-14 | Public package/source review exposes no runner, serialization, statistics, outcome joins, prevalence, or winner selection | ✅ |
| REQ-DIR-EVAL-15 | Focused gates pass; allowed unrelated full-suite failure is isolated | ✅ |

**Compliance summary:** 15/15 requirements compliant.

## Correctness and Design Coherence

| Decision | Status | Evidence |
|---|---|---|
| Canonical population boundary | ✅ | `evaluate_direction_policies(population, evidence)` requires `Stage6Population`; no compatibility overload. |
| Exact source identity | ✅ | `population.series is evidence.series` is enforced before labels. |
| Causal cutoff | ✅ | Every policy receives `K - 1`; Bias is dense/exact and OF is passed with that cutoff. |
| Policy isolation / determinism | ✅ | Frozen tuple order, sorted `(retest_index, signal_id)`, four rows per candidate, and no mutation. |
| Preserve fill behavior | ✅ | `simulate()` calls `_fill_pass(population.candidates, ...)` directly; identity test and simulation approval pass. |
| Outcome/research firewall | ✅ | Evaluation imports only the permitted producer boundary and policy/evidence layers; Import Linter passes. |

## Canonical Artifact and Scope

The amendment file is unmodified in the working tree. The frozen commit blob reports **7,737 bytes**, matching the supplied authority. Its frozen policy IDs are represented in the evaluator in the required P1→P4 order. The supplied SHA-256 authority is `47b17d7891f6f9a2d2d30f83df88b060840a895484a78e763c8f46da1ea8de4d`.

No real dataset, detector CLI, research execution, runner, serialization, outcome join, statistics, prevalence, MeanR, WR, PF, EST-B, bootstrap, winner-selection, or security capability was run or added. All evaluated fixtures were synthetic; no real-data or outcome conclusion is made.

## Exact Changed Files

```text
detector/.importlinter
detector/backtest/candidate.py
detector/backtest/population.py
detector/backtest/simulate.py
detector/evaluation/__init__.py
detector/evaluation/direction.py
detector/pyproject.toml
detector/tests/test_backtest_population.py
detector/tests/test_direction_evaluation.py
detector/tests/test_fitness_imports.py
.sdd/state/crt-detector-direction-policy-evaluation-seam.json
openspec/changes/crt-detector-direction-policy-evaluation-seam/apply-progress.md
openspec/changes/crt-detector-direction-policy-evaluation-seam/design.md
openspec/changes/crt-detector-direction-policy-evaluation-seam/exploration.md
openspec/changes/crt-detector-direction-policy-evaluation-seam/simplify-report.md
openspec/changes/crt-detector-direction-policy-evaluation-seam/verify-in-loop-1.md
openspec/changes/crt-detector-direction-policy-evaluation-seam/verify-in-loop-2.md
openspec/changes/crt-detector-direction-policy-evaluation-seam/verify-report.md
```

## Issues Found

**CRITICAL:** None.  
**WARNING:** The pre-extraction safety-net baseline is incomplete in the historical TDD record.  
**SUGGESTION:** Restore the unrelated alignment no-lookahead property separately; it is outside this change.

## Verdict

**PASS WITH WARNINGS.** The repaired seam meets all 15 requirements and its relevant execution gates pass. The sole complete-suite failure is explicitly permitted and unrelated.

## 2026-09-11 Pre-Commit Correction Addendum

The prior assertion-quality conclusion is historical verification evidence, not a claim that the newly discovered issue never existed. Pre-commit audit found one tautological property test at `tests/test_direction_evaluation.py:319-326`: it compared `_policy_relation(...)` with the identical `_policy_relation(...)` call and therefore did not observe the public evaluator.

It was replaced with a Hypothesis property that calls public `evaluate_direction_policies(...)`, covers all six valid candidate/policy-direction combinations, and compares each returned `DirectionEvaluation.relation` against a test-owned oracle: unresolved → `UNRESOLVED`, equal directions → `ALIGNED`, otherwise → `OPPOSED`. It also varies unrelated instrument, policy ID, reason, and signal-ID metadata across paired public evaluations and asserts that neither changes the oracle relation. The property does not call `_policy_relation()` for its expected or actual value.

Correction gate: `.\.venv\Scripts\python.exe -m pytest tests\test_direction_evaluation.py -q` → **36 passed**.

Sensitivity verification temporarily inverted the `ALIGNED`/`OPPOSED` branches in `evaluation/direction.py::_policy_relation()`. `.\.venv\Scripts\python.exe -m pytest tests\test_direction_evaluation.py -q -k relation_depends_only_on_candidate_and_decision_directions` then produced **1 failed, 35 deselected**; Hypothesis minimized the failing case to bullish candidate / bullish policy direction, where actual `OPPOSED` disagreed with oracle `ALIGNED`. The mutation was immediately reverted. The full corrected-file gate reran GREEN: `.\.venv\Scripts\python.exe -m pytest tests\test_direction_evaluation.py -q` → **36 passed**. No production mutation remains.

Narrow tautology audit result: no other evaluation-seam assertion self-compares, and no expected value is derived through the production helper under test. The existing six-pair example test uses literal expected relations; the corrected property is the public-API, independent-oracle guard.
