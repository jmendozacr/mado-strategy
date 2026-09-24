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
| ~~Original baseline B~~ | ~~`b76a251`~~ | ~~`docs(sdd): close out layer 3 statistical runner`~~ |
| Authorization-binding correction | `12da590` | `fix(detector): bind manifest to authorization commit` |
| Path-correction code change | `af7124b` | `fix(detector): correct dataset path prefix for detector-root resolution` |
| **Replacement baseline B (this commit)** | _(contains this document)_ | `docs(sdd): rebaseline path-corrected statistical runner` |

`b76a251` was initially recorded as baseline B but is superseded because `12da590` changed
protected runner code after it — `detector/runner/` is a protected path. Baseline B must
post-date all protected-code changes; `12da590` is therefore the last code commit that
qualifies as the anchor for the new B.

The authorization-binding correction (`12da590`) adds only authorization and provenance
enforcement around the runner. It does not alter direction-policy semantics, statistics,
OOS methodology, candidate generation, or the measured Layer-1 cost path.

The path-correction code change (`af7124b`) updates the 9 dataset file paths declared in
the protocol JSON from `pairs/_discovery_snapshot/...` to `../pairs/_discovery_snapshot/...`
so that they resolve correctly when joined against the runner's `detector_root`. It also
updates the two corresponding constants in `manifest_builder.py` (`CANONICAL_PROTOCOL_SHA256`
and `CANONICAL_PROTOCOL_BYTE_SIZE`) and the test assertion that checks the first dataset
record's `relative_path`. This change does not alter strategy semantics, statistical
methodology, or dataset contents — only the declared relative paths in the protocol to match
the runner's detector-root resolution convention.

The commit containing this document is **measurement execution baseline B** as required by
REQ-STAT-43 step (3). Its hash is authoritative; it is not pre-recorded here to avoid a
self-referential hash.

---

## Verification Evidence

All evidence collected on the committed tree at `af7124b` (immediately before this closeout commit).

### Full detector test suite

```
1045 passed in 275.33s (0:04:35)
```

No failures. Command: `.venv/Scripts/python.exe -m pytest --tb=short -q --basetemp=.pytest-tmp-baseline-b`

The test count grew from 1028 (original B) to 1045 because `12da590` added
`detector/tests/test_runner_authorization_binding.py` (17 new behavioral tests covering
REQ-STAT-44/46) and expanded authorization coverage in four existing test files.

### Import-linter

```
Contracts: 11 kept, 0 broken
Analyzed 86 files, 242 dependencies
```

All layering contracts pass, including `upstream layers must not import the Layer-3 runner`.

### Offline reproducibility verifier (REQ-STAT-56)

Included in the 1045 full-suite count above (`tests/test_runner_verify_reproducibility.py`).

The verifier is confirmed isolated from detection/simulation modules and enforces: non-empty
`experiment_id`, exact four-artifact inventory, valid 64-character SHA-256 hex hash for every
artifact value, per-directory integrity verification, manifest `experiment_id` identity cross-check,
and canonical manifest comparison with only `run_started_utc`/`run_finished_utc` permitted to differ.

---

## REQ-STAT-59 Synthetic Performance Qualification

### Rerun status

The qualification was **not rerun** for this replacement baseline. The authorization-binding
correction (`12da590`) adds only authorization and provenance enforcement; it does not touch
`selection/bootstrap.py`, the Layer-1 statistics path, or any code on the measured algorithmic
cost path. Because the measured Layer-1 code path did not change, the measurement evidence and the
human's prior operational acceptance remain applicable.

The report artifact at `detector/tests/qualification/req_stat_59_report.json` is unchanged.
SHA-256 verified at replacement-B time: `f821099afcebcfeddb6a7ccab8164157e6a537147fb22f74748030efd9fa70ff`
(identical to the value recorded under original baseline B).

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
testing, qualification, authorization-binding correction, or replacement-B closeout. All test
fixtures are synthetic. Real-data discovery execution remains unauthorized. Authorization
commit A is a technical prerequisite for execution, but creating A does not itself constitute
authorization — real-data execution requires separate explicit human approval.

Authorization commit A (committing `authorization_manifest.json`) does not itself require
real-data access — only runtime preflight execution does.

---

## Status

Layer-3 implementation is **CLOSED**. Replacement baseline B is established by the commit
containing this document (original `b76a251` superseded — see Commits table above). The next
required gate is generation and commit of `authorization_manifest.json` as authorization commit A,
which requires no real-data access.
