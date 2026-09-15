# Layer-3 Statistical Runner — Closeout

**Change:** `crt-detector-direction-policy-statistical-runner` — Layer 3
**Spec:** `openspec/changes/crt-detector-direction-policy-statistical-runner/spec.md` (V7, 65 requirements)
**Design:** `openspec/changes/crt-detector-direction-policy-statistical-runner-layer3/design.md`

---

## Objective

Implement the full discovery runner (`detector/runner/`) that:

- executes the 12-check preflight and authorization gate (REQ-STAT-48, REQ-STAT-49),
- drives the causal aligned-signal entrypoint per instrument (REQ-STAT-61, REQ-STAT-62),
- calls frozen Layer-1 statistics exactly once on the pooled observation set (REQ-STAT-50, REQ-STAT-51),
- publishes the five canonical artifacts with deterministic serialization (REQ-STAT-55),
- provides an offline reproducibility verifier isolated from execution modules (REQ-STAT-56), and
- runs a pre-baseline synthetic performance qualification (REQ-STAT-59).

---

## Commits

| Role | Hash | Message |
|---|---|---|
| Layer-3 implementation | `86908bc` | `feat(detector): implement statistical runner layer 3` |
| Test-only property fix | `4111691` | `test(detector): disambiguate alignment property signals` |
| **Baseline B (this commit)** | _(contains this document)_ | `docs(sdd): close out layer 3 statistical runner` |

The commit containing this document is **measurement execution baseline B** as required by REQ-STAT-43 step (3). Its hash is authoritative; it is not pre-recorded here to avoid a self-referential hash.

---

## Verification Evidence

All evidence collected on the working tree at commit `4111691` (immediately before this closeout commit).

### Full detector test suite

```
1028 passed in 202.26s
```

No failures. The previously documented sole failure
(`tests/property/test_no_lookahead.py::test_alignment_detection_has_no_lookahead`) was diagnosed as a
test-key collision — not a production defect — and corrected in commit `4111691` by adding `origin_index`
to the `_key` tuple. No production code was modified.

### Import-linter

```
Contracts: 11 kept, 0 broken
```

All layering contracts pass, including `upstream layers must not import the Layer-3 runner`.

### Offline reproducibility verifier (REQ-STAT-56)

```
28 passed (tests/test_runner_verify_reproducibility.py)
```

The verifier is confirmed isolated from detection/simulation modules and enforces: non-empty
`experiment_id`, exact four-artifact inventory, valid 64-character SHA-256 hex hash for every
artifact value, per-directory integrity verification, manifest `experiment_id` identity cross-check,
and canonical manifest comparison with only `run_started_utc`/`run_finished_utc` permitted to differ.

---

## REQ-STAT-59 Synthetic Performance Qualification

### Attestation

All observations are **synthetic only**. No real CSV files, no real datasets, no real outcomes were
loaded or inspected at any point during Layer-3 implementation or this qualification.

### Qualification script

`detector/tests/qualification/qualify_req_stat_59.py`

NOT part of the CI suite (REQ-STAT-59: "NOT a CI test — a one-time measurement").

### Report artifact

`detector/tests/qualification/req_stat_59_report.json`
SHA-256: `f821099afcebcfeddb6a7ccab8164157e6a537147fb22f74748030efd9fa70ff`

### Workload

| Dimension | Value |
|---|---|
| Instruments | `EURUSDm`, `GBPUSDm`, `DXYm` (3) |
| Policies | 4 (structural priority, corroboration, noncontradiction, bias veto) |
| Bootstrap replicates | 10,000 (frozen: `FROZEN_REPLICATES`) |
| Closed fraction | 1.0 (worst case — every observation CLOSED) |
| Cluster structure | 1:1 candidates-to-clusters (worst case for universe size K) |
| Synthetic data seed | 42 (separate from production bootstrap seed `[20260910]`) |

### Measured results

Environment: Python 3.12.14, numpy 2.5.2, Windows 11 (10.0.26100), AMD64 Family 23 Model 17.
Timing method: `time.perf_counter()`.
Memory method: `tracemalloc` (Python-managed heap only — see limitation below).

| N/instrument | Total observations | Wall-clock (s) | Peak tracemalloc (MB) |
|---|---|---|---|
| 50 | 600 | 45.52 | 15.956 |
| 100 | 1,200 | 88.62 | 26.366 |
| 200 | 2,400 | 180.19 | 49.274 |
| 500 | 6,000 | 451.92 | 340.534 |

Scaling is near-linear (≈ 2× wall-clock per 2× N), confirming the O(replicates × instruments × N)
cost shape identified in REQ-STAT-59 (`selection/bootstrap.py::apply_plan_to_policy`).

### Native RSS limitation

`ctypes PROCESS_MEMORY_COUNTERS` via `psapi.dll` was attempted but `PeakWorkingSetSize` returned null
at runtime on this machine (likely a process-handle permission constraint). Native numpy allocations
are therefore not captured. Actual peak RSS exceeds the tracemalloc figures. This limitation is
recorded in the report artifact and was disclosed to the human reviewer before operational acceptance.

### Human operational acceptance

The human reviewed the measured results, acknowledged the native-RSS limitation, and accepted the
operational cost. This acceptance is the prerequisite for creating baseline B per REQ-STAT-43.

---

## No-Real-Data Attestation

No real OHLC data, no real trade outcomes, no real bootstrap results, and no real discovery
statistics were loaded, executed, inspected, or used at any stage of the Layer-3 implementation,
testing, or qualification. All test fixtures are synthetic. Real-data discovery execution remains
unauthorized until authorization commit A is created.

---

## Status

Layer-3 implementation is **CLOSED**. Baseline B is established by the commit containing this
document. The next required gate is authorization commit A.
