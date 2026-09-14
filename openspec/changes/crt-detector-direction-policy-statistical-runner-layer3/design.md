# Technical Design — DirectionPolicy Statistical Runner V1 Layer 3

**Change**: `crt-detector-direction-policy-statistical-runner-layer3`
**Artifact**: Implementation-ready design for `detector/runner/`
**Spec**: V7 (amended from V6), `openspec/changes/crt-detector-direction-policy-statistical-runner/spec.md` (65 REQs, REQ-STAT-01 through REQ-STAT-65)
**Scope**: REQ-STAT-36 through REQ-STAT-64 (29 requirements)
**Date**: 2026-09-13 (revised)

---

## A. Context & frozen baseline

### HEAD and working tree

- **Branch**: `docs/order-flow-triage`
- **HEAD**: `1dd0acc fix(detector): preserve causal context provenance in layer 2`
- **Working tree**: untracked files only (`?? .claude-layer3-design-review-2.md`, `?? .sdd/project.json`, `?? openspec/changes/crt-detector-direction-policy-statistical-runner-layer3/`) — no uncommitted modifications to any tracked file.

### Frozen predecessors

| Component | Freeze commit | Status |
|---|---|---|
| Layer-1 (`detector/selection/`) | `75d9c37` | Frozen, committed |
| Layer-2 (`detector/adapter/`) | `9644876` | Frozen, committed |
| Layer-2 causal provenance amendment | `1dd0acc` (code), `f09b838` (design) | Frozen, committed |
| Causal candidate generation | `2419381` (impl), `1f412e3` (spec), `8f1906e` (amendment) | Frozen, committed |

### REQ-STAT-65 status — SATISFIED

REQ-STAT-65 required a Layer-2 amendment adding `aligned_signals` to `InstrumentRunBundle` and replacing `reconstruct_context_clusters` with `build_cluster_map`. Commits `1dd0acc` (code) and `f09b838` (design) have performed this amendment:

- `InstrumentRunBundle` (`detector/adapter/bundle.py`, line 25) carries `aligned_signals: tuple[AlignedSignal, ...]` with a `__post_init__` invariant (lines 29-41) tying it to `population.candidates`.
- `build_direction_policy_observations` (`detector/adapter/build.py`, line 49) calls `build_cluster_map(bundle.instrument, bundle.aligned_signals)`.

**Status**: the spec's V7 amendment has corrected REQ-STAT-65's status from "DOCUMENTED, NOT IMPLEMENTED" to "SATISFIED by `1dd0acc`". This is no longer a status drift or closeout follow-up — the spec and code are in agreement. Layer-3 designs against the ACTUAL current code, which satisfies REQ-STAT-65.

### Known pre-existing test failure

`tests/property/test_no_lookahead.py::test_alignment_detection_has_no_lookahead` fails on the legacy `tag_alignment` path. This is documented in spec.md Section Q3/Q4 — the failure is on the LEGACY path, not the causal path. Layer 3 MUST NEVER touch the legacy path; it uses `causal.generate.generate_causal_aligned_signals` exclusively (REQ-STAT-62). This failure is classified separately from Layer-3 work and does not gate Layer-3 implementation.

---

## B. Module/file change table

### New files in `detector/runner/`

| File | Responsibility |
|---|---|
| `__init__.py` | Package marker only |
| `manifest_builder.py` | Construct a frozen `adapter.manifest.Manifest` from the protocol JSON + repo state + recorded baseline, deriving every field value from its canonical source |
| `git_ops.py` | Subprocess-based local git operations (allowlisted subcommands, `check=True`, argument lists, explicit `cwd`, no `shell=True`) — the only module in `runner/` that calls `subprocess` |
| `preflight.py` | Full REQ-STAT-48 preflight contract: manifest schema/parse + protocol hash + protocol-vs-manifest cross-consistency + config reconstruction equality + git baseline verification (checks 3-9) + dataset per-file existence/size/hash/gap validation — never loads a full series into the detection pipeline, never builds a population, never evaluates a policy, never computes a statistic |
| `environment.py` | `uv.lock` SHA-256, numpy version, Python version verification (REQ-STAT-42) |
| `config_fingerprint.py` | Reconstruct `DetectorConfig` from protocol JSON, assert equality against declared values, compute SHA-256 fingerprint of canonical serialization |
| `instrument_pipeline.py` | Per-instrument sequential pipeline: causal generation, cutoff filtering, swing detection, population build, simulation, evaluation, Layer-2 observation construction — one function, one set of local bindings |
| `candidate_fingerprint.py` | Candidate-universe fingerprint: sort by `(retest_index, signal_id)`, serialize via `repr()` floats, SHA-256 hash — outcome-free by construction (`Candidate` has no outcome field) |
| `statistics_bridge.py` | The ONLY module calling `frozen_rng()` — materializes one `ResamplePlan`, invokes Layer-1's stratify/EST-B/bootstrap/instrument-deltas/nomination exactly once on the full concatenated observation set, returns typed results with no logger and no print |
| `serialization.py` | Canonical JSON serialization (`sort_keys=True`, `separators=(",",":")`, `ensure_ascii=False`, `allow_nan=False`, trailing `\n`, UTF-8 with `newline="\n"`), `repr()` for floats, `.value` for enums |
| `artifacts.py` | Build the 5 result artifact dicts from typed Layer-1 results + manifest + fingerprints, plus the failure artifact builder |
| `publication.py` | Atomic temp-dir write + per-artifact hash + `run_status.json` written LAST + single `os.replace` to final path; failure artifact to separate `failed/` directory |
| `run_discovery.py` | Top-level orchestrator: preflight, instrument processing (check 12), single Layer-1 invocation, atomic publication — the discovery entrypoint |
| `progress.py` | Closed enum of progress events (REQ-STAT-57) — no statistical value in any event |
| `errors.py` | Runner-specific error types: `AuthorizationError`, `ReproducibilityError`, `PerformanceQualificationError` |

### `.importlinter` contract additions

The `runner` package sits ABOVE `adapter`, `selection`, `causal`, and `backtest` in the import hierarchy. Required additions:

```ini
[importlinter]
root_packages =
    ...existing...
    runner

[importlinter:contract:no-runner-in-upstream-layers]
name = upstream layers must not import the Layer-3 runner
type = forbidden
source_modules =
    evaluation
    backtest
    alignment
    policy
    selection
    adapter
    causal
forbidden_modules =
    runner
```

The `runner` package MAY import: `adapter` (manifest, bundle, build, dataset, cutoff, errors), `selection` (model, bootstrap, estimators, nomination, stratify), `causal` (generate), `backtest` (population, simulate), `core` (candle, config, key_level, kill_zone, pairing_table), `primitives` (swing, fvg, ict_order_block), `evaluation` (direction), `ingestion` (loader, pairing), `alignment` (htf_ltf — only for `AlignedSignal` type, never for `tag_alignment`).

Layer position: `runner` > `adapter` > `selection`; `runner` > `causal`. This mirrors the existing `adapter` > `selection` layering and extends it one level.

### Behavioral justification (no pass-through wrappers)

Every proposed function has a named behavior:

- `manifest_builder.build_manifest`: aggregates 20+ fields from 5 sources (protocol JSON, git state, environment, config, dataset records) into one `Manifest` instance — not a passthrough.
- `instrument_pipeline.process_instrument`: orchestrates causal generation + cutoff filter + swing + population + simulate + evaluate + Layer-2 build in one function scope to enforce same-object discipline (REQ-STAT-52(a)) — this binding discipline IS the behavior.
- `statistics_bridge.compute_all_statistics`: calls `frozen_rng()` once, generates one `ResamplePlan`, iterates 4 policies — the single-call-site enforcement IS the behavior (REQ-STAT-51).
- `candidate_fingerprint.compute_candidate_fingerprint`: deterministic sort + canonical serialization + SHA-256 — a composed behavior, not a wrapper over any single upstream function.

Note: `authorization.py` is REMOVED as a separate module. The authorization gate is not a separable concern from `run_discovery` — it is the two-phase structure of `run_discovery` itself (see Section C for the coherent orchestration).

---

## C. End-to-end execution flow

### Overview: two-phase gate before Layer-1

`run_discovery` freshly re-derives the full REQ-STAT-49 gate on every invocation. There is no cached marker, no persistent state, no `.preflight_passed` file, no environment variable, no "already validated" representation of any kind.

The execution has two phases, both of which must succeed before any Layer-1 / statistics call:

- **Phase 1 (Preflight — checks 1-11)**: Validates manifest, protocol, environment, git state, and dataset files. May load dataset files for existence/size/hash/gap validation, but NEVER loads a full series into the detection pipeline, NEVER builds a `Stage6Population`, NEVER evaluates a policy, NEVER computes any statistic.
- **Phase 2 (Instrument processing — check 12)**: Processes all three instrument bundles sequentially (causal generation → cutoff admission → `build_direction_policy_observations`). This is where the detection pipeline runs.

**No authorization receipt, authorization success, or any authorization-named object exists until BOTH phases complete.** If any check in Phase 1 fails, Phase 2 never starts. If any instrument in Phase 2 fails, no `AuthorizationReceipt` is created and Layer-1 is never called.

### Step 1 — Preflight: checks 1-11 (REQ-STAT-48, REQ-STAT-49 checks 1-11)

**Owner**: `run_discovery.py` calls `preflight.run_preflight(manifest, protocol_path, repo_root)`.

**PROPOSED function**: `run_preflight(manifest: Manifest, protocol_path: str, repo_root: str) -> PreflightResult`.

The preflight executes the following in order (matching REQ-STAT-48's required sequence verbatim):

#### 1a. Schema/parse validation (REQ-STAT-49 checks 1-2)
1. **Check 1**: `manifest.measurement_execution_baseline_commit is not None` (and per `Manifest.__post_init__` at line 86-93, both `layer2_implementation_commit` and `layer3_implementation_commit` must also be set).
2. **Check 2**: Every required manifest field present and non-empty — schema completeness validation.

#### 1b. Protocol hash check (REQ-STAT-49 check 9)
3. **Check 9**: `validate_protocol_hash(manifest, protocol_path)` — existing function at `detector/adapter/manifest.py`, line 96. **Signature**: `validate_protocol_hash(manifest: Manifest, protocol_path: str) -> None`. Raises `FrozenArtifactMismatchError` on mismatch. Validates both hash and byte length.

#### 1c. Protocol-to-manifest cross-consistency
4. Manifest's `policy_ids` == `FROZEN_POLICY_IDS` (from `detector/evaluation/direction.py`, line 28).
5. Manifest's `mei_r` == `0.20`.
6. Manifest's `bootstrap_config` values match protocol JSON's declared values.
7. Manifest's cutoff values, instrument order, and dataset records match protocol JSON's declared values.
8. Manifest's `population.config` values match protocol JSON.

#### 1d. DetectorConfig reconstruction equality (REQ-STAT-41)
9. `config_fingerprint.reconstruct_and_verify(manifest, protocol_path)` — **PROPOSED function** in `runner/config_fingerprint.py`. Reconstructs `DetectorConfig` from protocol JSON's `population.config`, asserts equality against defaults, computes SHA-256 fingerprint. Aborts on mismatch.

#### 1e. Git baseline verification (REQ-STAT-49 checks 3-8)
10. **Check 3**: Baseline commit B is a real, resolvable git commit: `git rev-parse --verify <B>^{commit}` — via `git_ops.py`.
11. **Check 4**: Baseline is an ancestor of HEAD: `git merge-base --is-ancestor <B> HEAD` — via `git_ops.py`.
12. **Check 5**: `git diff <B> HEAD -- <protected_paths>` is empty (committed state matches baseline) — via `git_ops.py`.
13. **Check 6**: `git diff <B> -- <protected_paths>` is empty (working tree matches baseline, catches unstaged edits) — via `git_ops.py`.
14. **Check 7**: `git diff --cached <B> -- <protected_paths>` is empty (catches staged-but-uncommitted edits) — via `git_ops.py`.
15. **Check 8**: `git status --porcelain=v1 --untracked-files=all -- <protected_paths>` is empty (catches untracked files under protected paths) — via `git_ops.py`.

Checks 5-8 are each individually necessary (spec Section U rationale). All git operations via `git_ops.py`.

#### 1f. Environment verification (REQ-STAT-49 check 10)
16. **Check 10**: `environment.verify(manifest)` — **PROPOSED function** in `runner/environment.py`. Checks `uv.lock` SHA-256, numpy version `== "2.5.2"`, Python `3.12.*` (REQ-STAT-42).

#### 1g. Dataset per-file validation (REQ-STAT-49 check 11, REQ-STAT-34/38)
17. **Check 11**: For each dataset file declared in the manifest's `dataset_records`: verify file existence, byte size, SHA-256 hash match, and gap validation against the manifest's `dataset_gap_allowlist`.

This step MAY load enough of each dataset file to compute its hash, verify its size, and validate gaps. This is NOT "loading a full series into the detection pipeline" — no `OHLCSeries` is constructed for the detection pipeline, no `Stage6Population` is built, no policy is evaluated, no statistic is computed. The data loaded here is for integrity checking only, and is discarded after validation completes.

**Preflight NEVER**: loads a full series into the detection pipeline, builds a `Stage6Population`, evaluates a policy, or computes any statistic. Preflight DOES NOT perform check 12 (instrument bundle processing) — that is Phase 2.

**Proposed type** — `PreflightResult`:
```python
@dataclass(frozen=True)
class PreflightResult:
    baseline_commit: str
    head_commit: str
    manifest_sha256: str
    protocol_sha256: str
    checks_passed: tuple[str, ...]  # checks 1-11 names, for provenance
```

`PreflightResult` is an INTERNAL intermediate — it records that checks 1-11 held but does NOT authorize anything. It is never exposed outside `run_discovery`, never persisted, and never treated as sufficient authorization.

### Step 2 — Instrument processing: check 12 (REQ-STAT-49 check 12, REQ-STAT-50, 58, 37)

**Owner**: `run_discovery.py` iterates `for instrument in manifest.instrument_order`.

Order is ALWAYS `("EURUSDm", "GBPUSDm", "DXYm")` — sourced from `manifest.instrument_order` (REQ-STAT-37), never from filesystem or dict/set iteration.

For each instrument, `instrument_pipeline.process_instrument(instrument, manifest, config)` executes:

**PROPOSED function**: `process_instrument(instrument: str, manifest: Manifest, config: DetectorConfig) -> InstrumentResult`.

**Proposed type** — `InstrumentResult` (per-instrument, no trades/outcomes exposed to caller):
```python
@dataclass(frozen=True)
class InstrumentResult:
    instrument: str
    observations: tuple[DirectionPolicyObservation, ...]
    candidate_count: int
    candidate_fingerprint: str  # SHA-256
```

#### 2a. Dataset load and validation
- Load LTF (15M), HTF (H4), and daily series from `manifest.dataset_records` entries, selecting by `instrument` and `granularity`.
- `dataset.validate_no_gaps_against_manifest(ltf_series, timedelta(minutes=15), manifest)` — existing function at `detector/adapter/dataset.py`, REQ-STAT-34.
- Same for HTF and daily series with their respective granularity intervals.

#### 2b. Causal generation (REQ-STAT-62)
- Exactly ONE call to the existing function `generate_causal_aligned_signals` at `detector/causal/generate.py`, line 39.
- **Signature** (lines 39-47): `generate_causal_aligned_signals(ltf_series: OHLCSeries, htf_series: OHLCSeries, crt_config: CRTRangeConfig = CRTRangeConfig(), model1_config: Model1Config = Model1Config(), htf_key_levels: list[KeyLevel] | None = None, daily_series: OHLCSeries | None = None, daily_key_levels: list[KeyLevel] | None = None) -> list[AlignedSignal]`
- Key levels sourced from `primitives.fvg.to_key_levels` and `primitives.ict_order_block.to_key_levels` — never an arbitrary external list (REQ-STAT-64(c)).
- No legacy fallback. Failure aborts the ENTIRE run (REQ-STAT-62).

#### 2c. Cutoff admission (REQ-STAT-36/61)
- Filter the returned `list[AlignedSignal]` ONCE:
  ```
  admitted = [s for s in causal_signals
              if ltf_series.candles[s.ltf_signal.retest_index].timestamp < candidate_cutoff_end_utc]
  ```
- `candidate_cutoff_end_utc` sourced from `manifest` (REQ-STAT-39), never a CLI override.

#### 2d. Swing detection
- `swings = detect_swings(ltf_series, config.swing)` — existing function at `detector/primitives/swing.py`. Computed ONCE, stored in a local binding.

#### 2e. Population construction
- `population = build_stage6_population(admitted, ltf_series, config, swings)` — existing function at `detector/backtest/population.py`, line 120.
- **Signature** (lines 120-124): `build_stage6_population(aligned_signals: list[AlignedSignal], ltf_series: OHLCSeries, config: DetectorConfig, swings: list[SwingPoint] | None = None) -> Stage6Population`
- `admitted`, `ltf_series`, `config`, `swings` are the SAME local bindings used in steps 2f-2g.

#### 2f. Candidate-universe fingerprint (REQ-STAT-53)
- Computed BEFORE `simulate()` runs. Over `population.candidates`, sorted by `(retest_index, signal_id)`.
- **PROPOSED function**: `candidate_fingerprint.compute_candidate_fingerprint(candidates: list[Candidate]) -> str` in `runner/candidate_fingerprint.py`. Returns SHA-256 hex string.

#### 2g. Simulation (REQ-STAT-52/61)
- `trades, reconciliation = simulate(admitted, ltf_series, config, swings)` — existing function at `detector/backtest/simulate.py`, line 282.
- **Signature** (lines 282-287): `simulate(aligned_signals: list[AlignedSignal], ltf_series: OHLCSeries, config: DetectorConfig, swings: list[SwingPoint] | None = None) -> tuple[list[Trade], ReconciliationReport]`
- The IDENTICAL `admitted`, `ltf_series`, `config`, `swings` objects from steps 2c-2e (same-object discipline, REQ-STAT-52(a)).
- `swings` is NEVER `None` at this call site — always the explicit binding from step 2d.
- `simulate()` internally calls `build_stage6_population(aligned_signals, ltf_series, config, swings)` at line 296, builds its own population, discards it, and returns only `(trades, report)`.

#### 2h. Reconciliation (REQ-STAT-52, V7 — one external build)
- No second explicit external `build_stage6_population` call. `simulate()` performs its own unavoidable internal build (step 2g) from the IDENTICAL `admitted`, `ltf_series`, `config`, `swings` bindings (same-object discipline, REQ-STAT-52(a)).
- The candidate-universe fingerprint from step 2f is the ONLY fingerprint — computed from the single external population before `simulate()` runs.
- After `simulate()` returns, `prove_functional_join` (Layer-2, existing) + REQ-STAT-25's cardinality identity corroborate that `simulate()`'s internal population is consistent with the external one.

#### 2i. Evaluation — CORRECTED

The existing function is `evaluate_direction_policies` at `detector/evaluation/direction.py`, line 118.

**Actual signature** (lines 118-120):
```python
def evaluate_direction_policies(
    population: Stage6Population, evidence: DirectionEvidence
) -> tuple[DirectionEvaluation, ...]:
```

This requires two arguments: a `Stage6Population` and a `DirectionEvidence`.

`DirectionEvidence` is defined at `detector/evaluation/direction.py`, lines 57-61:
```python
@dataclass(frozen=True)
class DirectionEvidence:
    series: OHLCSeries
    order_flow_events: tuple[OrderFlowEvent, ...]
    bias_evidence: tuple[BiasEvidence, ...]
```

The three fields of `DirectionEvidence` must be constructed pre-K (Candidate View), and their sources are:

| Field | Source function | File/line | Signature |
|---|---|---|---|
| `series` | The SAME `ltf_series` binding already in scope | `core/candle.py` — the `OHLCSeries` instance loaded in step 2a | Must be the IDENTICAL object as `population.series` (validated at `direction.py` line 84: `evidence.series is not candidate_series`) |
| `order_flow_events` | `detect_order_flow_events(ltf_series)` | `detector/composite/order_flow.py`, line 46 | `detect_order_flow_events(series: OHLCSeries, config: OrderFlowConfig = OrderFlowConfig()) -> list[OrderFlowEvent]` — wrap result as `tuple(...)` |
| `bias_evidence` | `detect_bias_evidence(ltf_series)` | `detector/primitives/bias.py`, line 15 | `detect_bias_evidence(series: OHLCSeries) -> list[BiasEvidence]` — wrap result as `tuple(...)` |

The corrected call in `instrument_pipeline.process_instrument`:
```python
order_flow_events = tuple(detect_order_flow_events(ltf_series))
bias_evidence = tuple(detect_bias_evidence(ltf_series))
evidence = DirectionEvidence(
    series=ltf_series,
    order_flow_events=order_flow_events,
    bias_evidence=bias_evidence,
)
evaluations = evaluate_direction_policies(population, evidence)
```

**Evidence construction ordering**: `detect_order_flow_events` and `detect_bias_evidence` are both computed from the same `ltf_series` object. Both are pure functions of the full series (order flow events and bias evidence are observable quantities, not candidate-derived). They are computed ONCE per instrument, before the evaluation call. The `evidence.series is candidate_series` identity check at line 84 ensures the evidence refers to the exact same `OHLCSeries` object stored in `population.series` — which it will, since both `population` and `evidence` are built from the same `ltf_series` local binding.

**Bias evidence validation** (line 89-91): requires entries at every index from 1 through `len(candidate_series.candles) - 1`, dense and ordered. `detect_bias_evidence` produces exactly this: one entry per `(previous, current)` pair, starting at index 1 (`bias.py` line 23: `for i in range(1, len(candles))`), with `observation_index = i`.

**Order flow events validation** (line 92-93): requires unique `confirmation_index` values, all within series bounds.

#### 2j. Layer-2 observation construction
- Assemble `InstrumentRunBundle`:
  ```python
  bundle = InstrumentRunBundle(
      instrument=instrument,
      population=population,
      evaluations=evaluations,
      trades=tuple(trades),
      reconciliation=reconciliation,
      aligned_signals=tuple(admitted),
      candidate_cutoff_end_utc=manifest_cutoff,
      outcome_followup_end_utc=manifest_followup,
  )
  ```
  - Existing type at `detector/adapter/bundle.py`, lines 18-28.
  - **Signature**: `InstrumentRunBundle(instrument: str, population: Stage6Population, evaluations: tuple[DirectionEvaluation, ...], trades: tuple[Trade, ...], reconciliation: ReconciliationReport, aligned_signals: tuple[AlignedSignal, ...], candidate_cutoff_end_utc: datetime, outcome_followup_end_utc: datetime)`
  - `aligned_signals=tuple(admitted)` creates a NEW tuple container from the same `admitted` list. The `AlignedSignal` element identities are preserved (same objects), but the container is a new tuple (required by the frozen dataclass field type). The `admitted` list binding itself is never copied or reassigned.
  - `__post_init__` (lines 29-41) validates: `instrument == population.series.instrument`, every candidate's `signal_id` present in `aligned_signals`.
- `build_direction_policy_observations(bundle)` — existing function at `detector/adapter/build.py`, line 22. **Signature** (lines 22-23): `build_direction_policy_observations(bundle: InstrumentRunBundle) -> tuple[DirectionPolicyObservation, ...]`.
- On success, emit `INSTRUMENT_BUNDLE_VALIDATED(instrument)` progress event.

If ANY instrument fails during Phase 2, the entire run aborts. No `AuthorizationReceipt` is created, and Layer-1 is NEVER called (REQ-STAT-50).

### Step 3 — Authorization receipt creation (REQ-STAT-49: all 12 checks passed)

**Owner**: `run_discovery.py`.

This step runs ONLY after:
- Phase 1 (preflight, checks 1-11) completed successfully, producing a `PreflightResult`.
- Phase 2 (instrument processing, check 12) completed successfully for ALL three instruments.

At this point — and ONLY at this point — the `AuthorizationReceipt` is created:

**Proposed type** — `AuthorizationReceipt`:
```python
@dataclass(frozen=True)
class AuthorizationReceipt:
    baseline_commit: str
    head_commit: str
    manifest_sha256: str
    protocol_sha256: str
    checks_passed: tuple[str, ...]  # all 12 check names, recorded for provenance
    instrument_results: tuple[InstrumentResult, ...]  # validated results from Phase 2
```

`checks_passed` truthfully contains all 12 check names because the receipt is constructed AFTER all 12 have actually passed. The `instrument_results` field retains the validated per-instrument results produced during check 12, so instruments are NOT processed a second time.

**No object or state named authorization receipt / success / authorized / partial-auth exists before this point.** The `PreflightResult` from Phase 1 is an internal intermediate that records which checks held, but it is not an authorization object — it cannot authorize anything because check 12 has not yet run.

### Step 4 — All-instrument cross-validation

**Owner**: `run_discovery.py`.

- Emit `ALL_INSTRUMENTS_VALIDATED` progress event.
- Extract all instrument observations from `receipt.instrument_results`.
- Concatenate all instrument observations via `itertools.chain.from_iterable`.
- Verify total observation count == `4 * sum(len(result.observations) / 4 for each instrument)` (sanity check on 4N cardinality).

### Step 5 — Single full-dataset Layer-1 statistical calculation (REQ-STAT-50, 51)

**Owner**: `run_discovery.py` calls `statistics_bridge.compute_all_statistics(all_observations, manifest.instrument_order)`.

This call occurs STRICTLY AFTER the `AuthorizationReceipt` exists (all 12 checks passed). If the receipt was never created (any check failed), this step is unreachable.

**PROPOSED function**: `compute_all_statistics(observations: Sequence[DirectionPolicyObservation], instruments: tuple[str, ...]) -> StatisticsResult`

**Proposed type** — `StatisticsResult`:
```python
@dataclass(frozen=True)
class StatisticsResult:
    strata: dict[str, PolicyStrata]           # per policy_id
    est_b_results: dict[str, ESTBResult]      # per policy_id
    bootstrap_results: dict[str, BootstrapResult]  # per policy_id
    instrument_deltas: dict[str, tuple[InstrumentDelta, ...]]  # per policy_id
    eligibilities: tuple[PolicyEligibility, ...]
    nomination: NominationResult
    plan: ResamplePlan
```

Inside `statistics_bridge`:
1. `rng = frozen_rng()` — existing function at `detector/selection/bootstrap.py`, line 28. **Signature**: `frozen_rng() -> np.random.Generator`. Returns `Generator(PCG64(SeedSequence([20260910])))`. Exactly ONE call in the entire `runner/` package.
2. `plan = generate_cluster_resample_plan(all_observations, instruments, rng, FROZEN_REPLICATES)` — existing function at `detector/selection/bootstrap.py`, line 57. **Signature**: `generate_cluster_resample_plan(observations: Sequence[DirectionPolicyObservation], instruments: Sequence[str], rng: np.random.Generator, replicates: int) -> ResamplePlan`. ONE plan.
3. For each `policy_id` in `FROZEN_POLICY_IDS` (declared order, from `detector/evaluation/direction.py`, line 28):
   - `strata = stratify(all_observations, policy_id)` — existing at `detector/selection/stratify.py`, line 72. **Signature**: `stratify(observations: Sequence[DirectionPolicyObservation], policy_id: str) -> PolicyStrata`
   - `est_b = compute_est_b(all_observations, policy_id)` — existing at `detector/selection/estimators.py`, line 28. **Signature**: `compute_est_b(observations: Sequence[DirectionPolicyObservation], policy_id: str) -> ESTBResult`
   - `bootstrap_result = bootstrap_est_b(all_observations, policy_id, plan)` — existing at `detector/selection/bootstrap.py`, line 146. **Signature**: `bootstrap_est_b(observations: Sequence[DirectionPolicyObservation], policy_id: str, plan: ResamplePlan) -> BootstrapResult`
   - `instrument_deltas = compute_instrument_deltas(all_observations, policy_id)` — existing at `detector/selection/estimators.py`, line 39. **Signature**: `compute_instrument_deltas(observations: Sequence[DirectionPolicyObservation], policy_id: str) -> tuple[InstrumentDelta, ...]`
   - `eligibility = evaluate_eligibility(policy_id, est_b, bootstrap_result, instrument_deltas)` — existing at `detector/selection/nomination.py`, line 37. **Signature**: `evaluate_eligibility(policy_id: str, est_b: ESTBResult, bootstrap: BootstrapResult, instrument_deltas: Sequence[InstrumentDelta]) -> PolicyEligibility`
4. `nomination = nominate(eligibilities)` — existing at `detector/selection/nomination.py`, line 77. **Signature**: `nominate(eligibilities: Sequence[PolicyEligibility]) -> NominationResult`. ONE call.
5. Emit `STATISTICS_COMPLETE` progress event.

`statistics_bridge` imports NO logger and NO `print` (REQ-STAT-57). It returns typed results only.

### Step 6 — Atomic publication / failure handling (REQ-STAT-56)

**Owner**: `run_discovery.py` calls `publication.publish(...)`.

**PROPOSED function**: `publish(artifacts: PublicationInputs, output_dir: str) -> str` (returns final path).

**Proposed type** — `PublicationInputs`:
```python
@dataclass(frozen=True)
class PublicationInputs:
    experiment_id: str
    manifest_dict: dict
    policy_summary_dict: dict
    bootstrap_summary_dict: dict
    nomination_trace_dict: dict
    run_started_utc: str
    run_finished_utc: str
```

**Success path**:
1. `tmp_dir = <out>/.tmp-<experiment_id>-<pid>-<monotonic>/`
2. Write each of the 5 artifacts (serialized via `serialization.py`) into `tmp_dir`.
3. Compute SHA-256 of each written file.
4. Write `run_status.json` with `status: COMPLETED` LAST.
5. `os.replace(tmp_dir, <out>/<experiment_id>/)` — single atomic rename.
6. Emit `PUBLISHED(path)` progress event.

If `<out>/<experiment_id>/` already exists, the run REFUSES outright (REQ-STAT-56(a)).

**Failure path**:
- Write `FailureReport` to `<out>/failed/<experiment_id>-<run_started_utc>/failure.json`.
- Contains: status (`FAILED_VALIDATION`|`FAILED_SOFTWARE`), failing check identity, typed error class/message, `manifest_sha256`, environment record, preflight results completed so far.
- NEVER contains: `realized_r`, `closed_outcome`, relation distributions, MeanR, WR, EST-B, CI bounds, instrument deltas, or any per-policy figure.
- MAY contain: integrity-diagnostic counts (candidate/trade/excluded counts from REQ-STAT-25).

---

## D. Data contracts between stages

### Candidate View vs. Outcome View

| Stage boundary | Type | View | Outcome-bearing? |
|---|---|---|---|
| `generate_causal_aligned_signals` output | `list[AlignedSignal]` | Pre-cutoff (full series for causal correctness, but R-strict/H-A guarantee causality internally) | No |
| After cutoff filter (`admitted`) | `list[AlignedSignal]` | Candidate View — the admissible subset | No |
| `build_stage6_population(admitted, ...)` | `Stage6Population` | Candidate View — Candidate identity/economics only | No (`Candidate` has no outcome field: `signal_id, anchor_index, origin_index, direction, entry_type, retest_index, entry_price, stop_loss, take_profit, partial_price`) |
| `simulate(admitted, ...)` | `(list[Trade], ReconciliationReport)` | Outcome View — fills/exits resolved against FULL series | Yes (`Trade.outcome`, `Trade.r_multiple`) |
| `evaluate_direction_policies(population, evidence)` | `tuple[DirectionEvaluation, ...]` | Candidate View — evidence at K-1 | No |
| `build_direction_policy_observations(bundle)` | `tuple[DirectionPolicyObservation, ...]` | Joined — Candidate identity + outcome + relation | Yes |
| `compute_all_statistics(all_observations, instruments)` | `StatisticsResult` | Final — pooled across all instruments | Yes |

Outcome-bearing values (`Trade.outcome`, `Trade.r_multiple`) first become accessible to the runner at step 2g (`simulate()` return). They are consumed ONLY by `InstrumentRunBundle` construction (step 2j) and NEVER logged, printed, or inspected by any runner module before `statistics_bridge` processes the joined observations.

### `aligned_signals` identity

The `admitted` list (the cutoff-filtered `list[AlignedSignal]`) is the EXACT SAME Python list object passed to:
1. `build_stage6_population(admitted, ltf_series, config, swings)` — step 2e
2. `simulate(admitted, ltf_series, config, swings)` — step 2g
3. `InstrumentRunBundle(..., aligned_signals=tuple(admitted), ...)` — step 2j

For (1) and (2), the `admitted` list object itself is passed — same Python identity. For (3), `tuple(admitted)` creates a new tuple container, but the `AlignedSignal` elements within it are the same objects by identity — the tuple conversion is required because `InstrumentRunBundle.aligned_signals` is typed as `tuple[AlignedSignal, ...]` (frozen dataclass). The `ltf_series`, `config`, and `swings` bindings are equally shared across (1) and (2). This is enforced by all living in the same function scope (`instrument_pipeline.process_instrument`), with NO intermediate reassignment.

---

## E. Causal signal lifecycle

### One generation call per instrument (REQ-STAT-61(2))

`instrument_pipeline.process_instrument` calls `generate_causal_aligned_signals(ltf_series, htf_series, crt_config, model1_config, htf_key_levels, daily_series, daily_key_levels)` EXACTLY ONCE. The returned `list[AlignedSignal]` is the sole source of all downstream Candidate data for that instrument.

### One cutoff-filtered list, reused everywhere (REQ-STAT-61(3/4))

```python
admitted = [s for s in causal_signals
            if ltf_series.candles[s.ltf_signal.retest_index].timestamp < candidate_cutoff_end_utc]
```

This is computed ONCE. The `admitted` binding is never reassigned, never re-derived. It feeds `build_stage6_population`, `simulate`, and `InstrumentRunBundle` (as `tuple(admitted)`).

### No `tag_alignment` fallback (REQ-STAT-62)

- The discovery entrypoint (`run_discovery`) has no `use_legacy` / `skip_causal` / `fallback_to_legacy` parameter.
- `instrument_pipeline.process_instrument` does NOT import `alignment.htf_ltf.tag_alignment`.
- If `generate_causal_aligned_signals` raises, the ENTIRE run aborts — no fallback, no retry with legacy.
- Structural fitness test: `runner/` MUST NOT contain any import of `tag_alignment` or `detect_model1_signals` (the two legacy entrypoints).

### No HTF-context reconstruction anywhere in Layer 3

Layer 3 never calls `adapter.cluster.reconstruct_context_clusters`. Cluster identity flows through the `aligned_signals` field on `InstrumentRunBundle` — the ALREADY-EXISTING `adapter.cluster.build_cluster_map(instrument, bundle.aligned_signals)` inside `build_direction_policy_observations` (line 49 of `detector/adapter/build.py`) handles it (REQ-STAT-28/65, already implemented at `1dd0acc`).

---

## F. Population construction — resolved decision (Option B: one external build)

### Decision record

**Decision**: Option B — one external `build_stage6_population` call per instrument.

**Human approval**: received 2026-09-13. The V7 spec amendment (REQ-STAT-52, REQ-STAT-61) reconciles the V5/V6 contradiction in place.

**Rationale**: `simulate()` performs its own unavoidable internal `build_stage6_population(...)` call (line 296 of `backtest/simulate.py`), which Layer-3 cannot prevent, inspect, or instrument. A second EXPLICIT external build would add a third total `build_stage6_population` invocation without providing a materially stronger guarantee than same-object discipline already does — since the thing Layer-3 cannot observe is `simulate()`'s internal population, and a second external build would only prove the external builds agree with EACH OTHER, not with `simulate()`'s internal one.

**Population build count per instrument**:
- 1 explicit external `build_stage6_population(admitted, ltf_series, config, swings)` — called by `instrument_pipeline.process_instrument`, producing the `Stage6Population` used for statistics (Layer-1/Layer-2).
- 1 internal `build_stage6_population(admitted, ltf_series, config, swings)` — called by `simulate()` at line 296, using the IDENTICAL objects passed to it (same-object discipline).
- **Total**: 2 `build_stage6_population` invocations (1 external, 1 internal). Zero second explicit external builds.

**Reconciliation mechanisms** (same-object discipline as enforcement):
1. **Same-object discipline** (REQ-STAT-52(a)): one causal generation call produces one `list[AlignedSignal]`; one cutoff filter produces one `admitted` list; one `detect_swings` call produces one `swings` list; one `DetectorConfig` binding. All four (`admitted`, `ltf_series`, `config`, `swings`) are the IDENTICAL Python objects passed to both the external `build_stage6_population` and `simulate`. Enforced by all living in the same function scope (`instrument_pipeline.process_instrument`), with NO intermediate reassignment. A fitness test asserts `swings is not None` at both call sites.
2. **Candidate-universe fingerprint** (REQ-STAT-53): computed from the single external population BEFORE `simulate()` runs. Outcome-free by construction.
3. **`prove_functional_join`** (existing Layer-2 cross-check): raises on any Trade whose join key matches no `CandidateIdentity` in the external population — proves the filled subset of `simulate()`'s internal population is consistent with the external one.
4. **REQ-STAT-25 cardinality identity**: `len(population.candidates) == len(trades) + reconciliation.excluded_never_filled` — proves total candidate count matches between the external population and `simulate()`'s internal one.

**Honest limitation**: same-object discipline ensures identical inputs reach both builds; `prove_functional_join` and cardinality identity corroborate agreement; but set identity between the external population and `simulate()`'s inaccessible internal population cannot be proven mechanically in a scenario where one never-filled candidate is silently swapped for another of equal count (undetected only if same-object discipline is violated). Achieving stronger proof would require modifying frozen `backtest` code, which is out of scope. This limitation is reported, not hidden.

---

## G. Manifest schema extension — resolved decision (Option A: additive extension)

### Decision record

**Decision**: Option A — extend the existing `adapter.manifest.Manifest` dataclass with Layer-3 required fields. SAME class, SAME frozen instance semantics. No wrapper, no subclass, no `DevelopmentManifest`, no `AuthorizationManifest`, no second source of truth.

**Human approval**: received 2026-09-13. Explicit approval to reopen the frozen Layer-2-owned `Manifest` schema for additive fields only. Precedent: `1dd0acc` already amended the Layer-2-owned `InstrumentRunBundle` via the same targeted-amendment pattern.

**Development/Layer-2 compatibility**: all new fields use neutral defaults (`None`, `()`) so existing Layer-2 code that constructs `Manifest` without them continues to work without modification. Layer-2 runtime behavior is unchanged.

**Layer-3 authorization**: every Layer-3-required field MUST be populated and non-empty. The `validate_authorization` (or equivalent) function MUST check all required fields before a real run proceeds.

### Additive fields table

| Field name | Type | Default | Authorizing REQ | Source |
|---|---|---|---|---|
| `instrument_order` | `tuple[str, ...] \| None` | `None` | REQ-STAT-37 | Amendment's `bootstrap.prng.stream_order`: `("EURUSDm", "GBPUSDm", "DXYm")` |
| `dataset_records` | `tuple[DatasetFileRecord, ...] \| None` | `None` | REQ-STAT-38 | Per-instrument: `(instrument, granularity, relative_path, byte_size, sha256, start_utc, end_utc)` — mirrors Amendment's `dataset.files` 7-tuple |
| `candidate_cutoff_end_utc` | `datetime \| None` | `None` | REQ-STAT-39 | Amendment's `dataset.candidate_cutoff_end_utc` |
| `outcome_followup_end_utc` | `datetime \| None` | `None` | REQ-STAT-39 | Amendment's `dataset.outcome_followup_end_utc` |
| `spec_sha256` | `str \| None` | `None` | REQ-STAT-40 | SHA-256 of the exact `spec.md` bytes the run was measured against |
| `statistical_spec_commit_chain` | `tuple[str, ...] \| None` | `None` | REQ-STAT-40 | Chronological ordered tuple of the distinct spec-file commits through the most recent amendment. At authorization time: `(dc8af7d, 6b48374, 86c9150, 8195ea9, edd6eef[, <v7-commit>])`. The V7 commit is included when it exists; authorization validation must check the chain is non-empty and all entries are non-empty strings |
| `detector_config_fingerprint` | `str \| None` | `None` | REQ-STAT-41 | SHA-256 of the reconstructed `DetectorConfig`'s canonical serialization |
| `uv_lock_sha256` | `str \| None` | `None` | REQ-STAT-42 | SHA-256 of `detector/uv.lock` |
| `causal_spec_commit` | `str \| None` | `None` | REQ-STAT-63(a) | `1f412e3675909a4da0046a1e72c45f6164acd232` |
| `causal_spec_amendment_commit` | `str \| None` | `None` | REQ-STAT-63(a) | `8f1906e` |
| `causal_implementation_commit` | `str \| None` | `None` | REQ-STAT-63(a) | `2419381` |
| `causal_source_inputs` | `tuple[CausalSourceInputRecord, ...] \| None` | `None` | REQ-STAT-63(c) | Sequence of 9 entries (3 instruments x 3 arguments). Each entry: `instrument` (str), `argument_name` (closed literal), `producer_id` (closed literal), `dataset_relative_path` (str, cross-references `DatasetFileRecord`). No `payload_sha256` — the dataset file SHA-256 already exists in `DatasetFileRecord`. See `CausalSourceInputRecord` definition below. |

`statistical_spec_v3_commit` is an existing Layer-2 compatibility field, retained unchanged; it is not counted as a new additive field. The additive field count is **12**, not 13.

**Supporting new type** (required by `dataset_records`):

```python
@dataclass(frozen=True)
class DatasetFileRecord:
    instrument: str
    granularity: str
    relative_path: str
    byte_size: int
    sha256: str
    start_utc: datetime
    end_utc: datetime
```

`DatasetFileRecord` is a data container used ONLY as the element type for `Manifest.dataset_records`. It is NOT a manifest type, subclass, or wrapper — it is a field-level struct analogous to the existing `GapAllowlistEntry` already used by `Manifest.dataset_gap_allowlist`.

**Supporting new type** (required by `causal_source_inputs`):

```python
@dataclass(frozen=True)
class CausalSourceInputRecord:
    instrument: str
    argument_name: Literal["htf_key_levels", "daily_series", "daily_key_levels"]
    producer_id: Literal[
        "primitives.fvg.detect_fvgs->primitives.fvg.to_key_levels",
        "ingestion.loader.load_mt5_csv",
        "primitives.ict_order_block.detect_ict_order_blocks->primitives.ict_order_block.to_key_levels",
    ]
    dataset_relative_path: str  # references exactly one Manifest.dataset_records entry
```

`CausalSourceInputRecord` captures per-input provenance for `generate_causal_aligned_signals`'s three caller-supplied dataset-derived arguments. It stores ONLY dataset file references — never raw candle or `KeyLevel` payloads. No `payload_sha256` field: the source dataset SHA-256 already exists in the referenced `DatasetFileRecord`.

`producer_id` is a **closed literal** — only these exact three strings are valid:

| `argument_name` | Dataset granularity | `producer_id` |
|---|---|---|
| `htf_key_levels` | H4 `DatasetFileRecord` | `primitives.fvg.detect_fvgs->primitives.fvg.to_key_levels` |
| `daily_series` | D1 `DatasetFileRecord` | `ingestion.loader.load_mt5_csv` |
| `daily_key_levels` | D1 `DatasetFileRecord` | `primitives.ict_order_block.detect_ict_order_blocks->primitives.ict_order_block.to_key_levels` |

For this frozen experiment, exactly **9 entries** are required (3 instruments x 3 arguments).

Authorization validation MUST require: (1) exactly 9 unique `(instrument, argument_name)` pairs (3 instruments x 3 arguments); (2) each entry's `producer_id` matches exactly the closed literal for that `argument_name`; (3) each entry's `dataset_relative_path` references a matching instrument/granularity entry in `Manifest.dataset_records`; (4) the referenced `DatasetFileRecord` must have passed preflight (existence/size/hash checks).

### Field ordering in the amended `Manifest`

All new fields are appended after the existing optional fields (`dataset_gap_allowlist`), each with its neutral default. The `__post_init__` method is unchanged — existing validation logic is not affected. Layer-3's `validate_authorization` performs the non-empty checks on the new fields, outside `__post_init__`.

---

## H. Five result artifacts

### Artifact list

| # | File | Content | Idempotency key |
|---|---|---|---|
| 1 | `run_manifest.json` | Frozen `Manifest` fields + `head_commit`, `manifest_sha256`, `protocol_sha256`, `uv_lock_sha256`, `numpy_version`, `python_version`, `detector_config_fingerprint`, `candidate_universe_fingerprint`, `instrument_order`, `dataset_records`, `run_started_utc`, `run_finished_utc` | `experiment_id` |
| 2 | `policy_summary.json` | Per P1-P4: total/CLOSED/OPEN/NEVER_FILLED N; per-stratum N/share/MeanR/WR; EST-B point+status; CI bounds+status; per-instrument deltas+status; eligibility+reasons; `profit_factor: "N/A"`; REQ-STAT-18 label; `trading_cost_price: 0.0` | `experiment_id` |
| 3 | `bootstrap_summary.json` | Replicate count, seed, CI method, family-wise correction, per-policy CI status/bounds, per-instrument universe size K | `experiment_id` |
| 4 | `nomination_trace.json` | Per policy: each SEL-A condition with evaluated value + pass/fail, full-precision ranking value, tie status, final nominee or `"NO POLICY NOMINATED"` | `experiment_id` |
| 5 | `run_status.json` | `status: "COMPLETED"`, `experiment_id`, `run_started_utc`, `run_finished_utc`, every artifact filename + its own SHA-256 — written LAST | `experiment_id` |

### Canonical serialization (REQ-STAT-55)

```python
def canonical_json(obj: Any) -> bytes:
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False,
                       default=_default_serializer) + "\n").encode("utf-8")
```

- Floats: Python's `repr()` (round-trip exact).
- Enums: `.value`.
- `NOT_ESTIMABLE` / `NOT_COMPUTABLE`: explicit string state alongside `null` value, never bare `null`.
- Collection order: instruments in `instrument_order`, policies in `FROZEN_POLICY_IDS` order, candidates by `(retest_index, signal_id)`, clusters lexicographically.

### Temporary-path transaction (REQ-STAT-56(b))

```
<out>/.tmp-<experiment_id>-<pid>-<monotonic>/
  run_manifest.json
  policy_summary.json
  bootstrap_summary.json
  nomination_trace.json
  run_status.json        <- written LAST
```

Then: `os.replace(tmp_dir, <out>/<experiment_id>/)` — atomic on the same filesystem.

A crash at any point before `os.replace` leaves only an incomplete `.tmp-*` directory.

### Experiment/attempt idempotency (REQ-STAT-56(a))

- Run directory: `<out>/<experiment_id>/` — no date, counter, or hostname.
- If directory exists, the run REFUSES outright (never "verify identical and continue").
- `attempt_id` MAY be recorded as operational metadata — never part of statistical identity.
- A successful rerun of the same authorized experiment MUST be deterministic (same core result hashes), or it is a `REPRODUCIBILITY FAILURE`.

### Failure artifact (REQ-STAT-56(c))

Written to `<out>/failed/<experiment_id>-<run_started_utc>/failure.json`.

**Allowed fields**: `status` (`FAILED_VALIDATION`|`FAILED_SOFTWARE`), failing check identity, typed error class/message, `manifest_sha256`, environment record, preflight results completed, integrity-diagnostic counts (candidate/trade/excluded from REQ-STAT-25).

**Forbidden fields**: `realized_r`, `closed_outcome`, relation distributions, MeanR, WR, EST-B, CI bounds, instrument deltas, any per-policy figure.

---

## I. RNG ownership

### Single call site (REQ-STAT-51)

`statistics_bridge.py` is the ONE AND ONLY module in `runner/` that calls `frozen_rng()`. It:

1. Calls `frozen_rng()` → `Generator(PCG64(SeedSequence([20260910])))` (at `detector/selection/bootstrap.py`, line 28).
2. Calls `generate_cluster_resample_plan(observations, instruments, rng, FROZEN_REPLICATES)` → one `ResamplePlan` (at `detector/selection/bootstrap.py`, line 57).
3. Passes that SAME `plan` object to `bootstrap_est_b(observations, policy_id, plan)` (at `detector/selection/bootstrap.py`, line 146) for each of the 4 policies.

No Layer-3 caller holds or reuses a `Generator` across policies. No code path constructs a second, per-policy generator.

### No alternate NumPy RNG path (REQ-STAT-51 fitness)

- `statistics_bridge.py` is the only `runner/` module importing `selection.bootstrap.frozen_rng`.
- No `runner/` module imports `numpy.random` directly or references `np.random`.
- Structural fitness test: `rg 'numpy\.random|np\.random' runner/` must return ZERO matches. The `frozen_rng` import is `from selection.bootstrap import frozen_rng` — this text does not contain `numpy.random` or `np.random`, so the fitness test is correctly formulated as a zero-match assertion.
- `rg 'frozen_rng' runner/` must match exactly one module (`statistics_bridge.py`).

---

## J. No-peeking controls

### Progress events (REQ-STAT-57) — allowed vs. forbidden

**Allowed** (closed enum in `progress.py`):

| Event | Fields |
|---|---|
| `PREFLIGHT_PASSED` | (none) |
| `INSTRUMENT_DATASET_VALIDATED` | `instrument: str` |
| `INSTRUMENT_BUNDLE_VALIDATED` | `instrument: str` |
| `ALL_INSTRUMENTS_VALIDATED` | (none) |
| `STATISTICS_COMPLETE` | (none) |
| `PUBLISHED` | `path: str` |

**Forbidden in any progress event**: `realized_r`, `closed_outcome`, any relation distribution, MeanR, WR, EST-B point or CI, instrument deltas, nomination result, candidate count (even aggregate), trade count, any N, any share, any per-policy figure.

### Statistics module: no output channel (REQ-STAT-57)

`statistics_bridge.py`:
- Imports NO logger (`logging`, `structlog`, any logging framework).
- Contains NO `print`, `sys.stdout.write`, `sys.stderr.write`, or equivalent.
- Returns typed results (`StatisticsResult` dataclass) ONLY to `run_discovery.py`, which passes them to `artifacts.py` (which builds dicts) and then `publication.py` (which writes files).
- The stage holding the numbers has no output channel. The stage with the output channel runs only after every decision is final.

### No per-instrument statistics (REQ-STAT-50)

There is NO call site at which a per-instrument statistic could be computed. `statistics_bridge.compute_all_statistics` accepts the CONCATENATED observation set (all instruments) and invokes Layer-1 ONCE. No intermediate per-instrument `stratify`, `compute_est_b`, `bootstrap_est_b`, or `nominate` call exists anywhere in `runner/`.

### No optional-stopping branch (REQ-STAT-17/57)

No "collect more data" branch. No `if est_b < threshold: retry`. No conditional instrument inclusion. All instruments validate, all observations concatenate, statistics run once, results are published or the run fails.

---

## K. Test derivation matrix

| REQ | Evidence type | Description | Status |
|---|---|---|---|
| REQ-STAT-36 | unit + property | Cutoff filter admits only signals with `retest_timestamp < cutoff`; the same filtered list reaches both `build_stage6_population` and `simulate` | `designed` |
| REQ-STAT-37 | unit | Manifest's `instrument_order` is the sole source for the instrument loop; scrambled order produces a different bootstrap draw (detected by `ResamplePlan` comparison) | `designed` |
| REQ-STAT-38 | unit | `DatasetFileRecord` fields round-trip through manifest construction and are individually validated against actual files | `designed` |
| REQ-STAT-39 | unit | Cutoff values sourced from manifest only; no CLI override parameter exists on the discovery entrypoint | `designed` |
| REQ-STAT-40 | unit | Manifest records `statistical_spec_commit_chain` (the actual distinct spec-file commits: `dc8af7d`, `6b48374`, `86c9150`, `8195ea9`, `edd6eef`, plus V7 when committed) and `spec_sha256`; a mutated spec file produces a different `spec_sha256`; chain validation checks non-empty and all entries non-empty strings | `designed` |
| REQ-STAT-41 | unit + integration | `DetectorConfig` reconstructed from protocol JSON equals the expected defaults; a drift in either direction (protocol or code default) is detected by the assertion | `designed` |
| REQ-STAT-42 | unit | `uv.lock` SHA-256 mismatch aborts; numpy version != `"2.5.2"` aborts; Python not `3.12.*` aborts | `designed` |
| REQ-STAT-43 | `manual-closeout` | Baseline B creation process is verified by integration test: Layer-3 closeout commit's hash equals the `measurement_execution_baseline_commit` recorded in the manifest. **Cannot be tested until the baseline commit actually exists.** | `manual-closeout` |
| REQ-STAT-44 | `manual-closeout` | Manifest constructed after B, citing B by value; commit A is chronologically after B; no self-reference in either direction. **Cannot be tested until the authorization commit A actually exists.** | `manual-closeout` |
| REQ-STAT-45 | unit + structural | Protected paths list matches the enumerated inventory; a new file under a protected prefix is detected by `git status --untracked-files=all` | `designed` |
| REQ-STAT-46 | integration | HEAD != B succeeds when all protected paths match; HEAD != B fails when any protected path differs | `designed` |
| REQ-STAT-47 | structural | No `DevelopmentManifest`/`AuthorizationManifest` type exists in `runner/`; only `adapter.manifest.Manifest` is used | `designed` |
| REQ-STAT-48 | unit + integration | Preflight executes the full REQ-STAT-48 sequence: schema/parse, protocol hash, cross-consistency, config reconstruction, git baseline checks 3-9, dataset existence/size/hash/gap validation. Preflight never calls `build_stage6_population` or `evaluate_direction_policies` (verified by mock). | `designed` |
| REQ-STAT-49 | unit + integration | Each of the 12 authorization checks is independently testable: baseline not declared -> abort; baseline not ancestor -> abort; protected path drift -> abort; staged edit -> abort; untracked file -> abort; etc. `AuthorizationReceipt` is created ONLY after all 12 checks pass (including check 12 = all instrument bundles validated). Bundle-3 failure -> no receipt created, zero Layer-1 calls. Successful execution -> one receipt covering all 12, one Layer-1 call after all bundles. | `designed` |
| REQ-STAT-50 | integration | One instrument failing validation -> entire run aborts, no Layer-1 call; verify by asserting `compute_all_statistics` is never called | `designed` |
| REQ-STAT-51 | structural + unit | `frozen_rng()` referenced by exactly one `runner/` module; that module contains no other `numpy.random` or `np.random` text reference; the `ResamplePlan` is constructed once and reused for all 4 policies | `designed` |
| REQ-STAT-52 | unit + integration | Same `admitted`/`ltf_series`/`config`/`swings` objects passed to both the single external `build_stage6_population` and `simulate`; candidate-universe fingerprint computed from the single external population before `simulate()` runs; `swings` is never `None` at either call site; `prove_functional_join` + REQ-STAT-25 cardinality corroborate consistency with `simulate()`'s internal build | `designed` |
| REQ-STAT-53 | unit | Candidate-universe fingerprint: sorted by `(retest_index, signal_id)`, `repr()` floats, SHA-256; computed before `simulate()` runs; outcome-free by construction (Candidate type has no outcome field) | `designed` |
| REQ-STAT-54 | integration | Run produces exactly 5 files with the correct names; each file's JSON structure matches the schema; `run_status.json` references all 4 other files with their SHA-256 | `designed` |
| REQ-STAT-55 | unit + property | Canonical JSON: `sort_keys=True`, `allow_nan=False` (NaN raises), trailing `\n`, UTF-8; byte-reproducible across re-serialization of the same input | `designed` |
| REQ-STAT-56 | integration | Existing directory -> run refuses; atomic rename on success; crash before rename leaves `.tmp-*` only; failure artifact in `failed/` directory with no statistical fields. Dataset tests use synthetic temporary files, never real discovery data. | `designed` |
| REQ-STAT-57 | structural + unit | Progress events carry no statistical value (closed enum verified); `statistics_bridge` imports no logger/print; no f-string in any `runner/` log call embeds a statistic | `designed` |
| REQ-STAT-58 | structural | Zero network imports in `runner/`; instruments processed sequentially in `instrument_order`; `subprocess` used only in `git_ops.py` with allowlisted subcommands | `designed` |
| REQ-STAT-59 | manual | Pre-baseline synthetic performance qualification: run Layer-1 on synthetic populations, measure runtime+memory, report results — must be COMPLETED before baseline B creation | `manual-closeout` |
| REQ-STAT-60 | unit + property | Candidate View contains no candle-at-or-after-K dependency; Outcome View does not redetect candidates, replace signal_id, or change identity/economics | `designed` |
| REQ-STAT-61 | integration | One causal generation call per instrument; one cutoff filter; same filtered list to both the single external `build_stage6_population` and `simulate`; `simulate` resolves against full series; no second explicit external build | `designed` |
| REQ-STAT-62 | structural | `runner/` contains no import of `tag_alignment` or `detect_model1_signals`; no `use_legacy`/`fallback_to_legacy` parameter on the discovery entrypoint | `designed` |
| REQ-STAT-63 | unit | Manifest records `causal_spec_commit`, `causal_spec_amendment_commit`, `causal_implementation_commit` (63(a)); no separate causal config fingerprint — REQ-STAT-41 covers it transitively (63(b)); `causal_source_inputs` is a `tuple[CausalSourceInputRecord, ...]` with exactly 9 entries (3 instruments x 3 arguments), each with 4 fields (`instrument`, `argument_name`, `producer_id` as closed literal, `dataset_relative_path` cross-referencing `dataset_records`); no `payload_sha256` — dataset SHA-256 already in `DatasetFileRecord` (63(c)). Authorization validation rejects wrong `producer_id`, missing entry, or unresolvable `dataset_relative_path`. | `designed` |
| REQ-STAT-64 | unit + structural | Key levels sourced from `primitives.fvg.to_key_levels` and `primitives.ict_order_block.to_key_levels` only; manifest records which sources were used via the 9-entry `causal_source_inputs` contract (REQ-STAT-63(c)); authorization validation rejects wrong `producer_id`, missing entry, or unresolvable `dataset_relative_path`; no arbitrary external `KeyLevel` list accepted | `designed` |

**Legend**: `designed` = flow and test strategy fully determined; `manual-closeout` = requires a real commit/baseline/deployment that does not exist yet.

**Counts**: 26 `designed` + 3 `manual-closeout` = 29 requirements in scope (REQ-STAT-36 through REQ-STAT-64). Zero `blocked`.

---

## L. External assumptions & build preflights

### Build preflights (non-blocking, executor-local)

| Preflight | What it checks | When to run |
|---|---|---|
| Import-linter | `runner` package + new contract pass `lint-imports` | Every slice |
| Test suite | All existing tests still pass | Every slice |
| Structural fitness: `tag_alignment` import | `rg 'tag_alignment\|detect_model1_signals' runner/` returns nothing | Slice containing instrument pipeline |
| Structural fitness: single `frozen_rng` | `rg 'frozen_rng' runner/` matches exactly one file | Slice containing statistics bridge |
| Structural fitness: no `numpy.random` / `np.random` | `rg 'numpy\.random\|np\.random' runner/` returns ZERO matches | Slice containing statistics bridge |
| Structural fitness: no logger in `statistics_bridge` | `rg 'logging\|print\|sys.stdout\|sys.stderr' runner/statistics_bridge.py` returns nothing | Slice containing statistics bridge |

### External assumptions

| Assumption | Failure consequence | Measured? |
|---|---|---|
| `os.replace` is atomic on the target filesystem | Partial result could appear complete | Not measured — assumed for same-filesystem POSIX rename, documented |
| `subprocess.run` with `check=True` raises on non-zero exit | Authorization gate silently passes a failing check | Guaranteed by Python stdlib contract |
| `uv.lock` SHA-256 transitively pins numpy 2.5.2 | Bootstrap draws may differ | Measured by independent numpy version check (REQ-STAT-42(b)) |

No severity claim depends on an unmeasured magnitude.

---

## M. Vertical implementation slices

### Slices — behavior-oriented, tests with each behavior

| # | Name | Behavior | Files (prod + test) | Depends on | Rollback |
|---|---|---|---|---|---|
| 1 | Package skeleton + error types + progress enum | Runner package exists, import-linter enforces layer boundary, progress events carry no statistical value | `runner/__init__.py`, `runner/errors.py`, `runner/progress.py`, `.importlinter` update; tests: structural assertion that progress enum has no statistical field, import-linter passes | None | Revert `.importlinter` + delete `runner/` |
| 2 | Canonical serialization | JSON serialization is deterministic, byte-reproducible, rejects NaN, uses `repr()` for floats | `runner/serialization.py`; tests: round-trip property tests, NaN rejection, float `repr()` fidelity, trailing newline, UTF-8 encoding | 1 | Delete file + tests |
| 3 | Candidate fingerprint | Fingerprint is outcome-free, deterministic, sort-order-stable | `runner/candidate_fingerprint.py`; tests: same candidates different order -> same fingerprint; different candidates -> different fingerprint; no outcome field in Candidate type (structural) | 1 | Delete file + tests |
| 4 | Environment + config fingerprint | Environment checks abort on version mismatch; config reconstructed from protocol JSON equals defaults | `runner/environment.py`, `runner/config_fingerprint.py`; tests: numpy version mismatch -> abort; Python version mismatch -> abort; uv.lock hash mismatch -> abort; config drift detected | 1, 2 | Delete files + tests |
| 5 | Git operations | Each git check independently detects its specific violation class | `runner/git_ops.py`; tests: baseline not reachable -> error; not ancestor -> error; committed diff -> error; staged diff -> error; untracked file -> error. Tests use `git init` in temporary directories, never real discovery data. | 1 | Delete file + tests |
| 6 | Preflight (checks 1-11) | Preflight executes the full REQ-STAT-48 sequence (schema/parse, protocol hash, cross-consistency, config reconstruction, git baseline checks 3-9, dataset existence/size/hash/gap validation). Preflight never calls `build_stage6_population` or `evaluate_direction_policies` (verified by mock). Each of checks 1-11 independently fails -> preflight aborts. All 11 pass -> `PreflightResult` returned. | `runner/preflight.py`; tests: mock-based preflight verifying no `build_stage6_population`/`evaluate_direction_policies` call; each check independently tested for failure detection | 4, 5 | Delete file + tests |
| 7 | Instrument pipeline (core binding discipline) | Same-object discipline enforced: one external `build_stage6_population` + `simulate` share identical bindings; evaluation call correct; candidate fingerprint computed before `simulate()`; `prove_functional_join` + cardinality corroboration after `simulate()`; causal-only (no `tag_alignment` import) | `runner/instrument_pipeline.py`; tests: synthetic `AlignedSignal` list -> process_instrument succeeds with correct types; `swings` never `None` at call sites; structural: no `tag_alignment` import; `DirectionEvidence` correctly constructed; no second explicit `build_stage6_population` call | 1, 3 | Delete file + tests |
| 8 | Statistics bridge (single RNG + Layer-1 invocation) | `frozen_rng()` called once; one `ResamplePlan`; 4-policy loop; no logger; returns typed result | `runner/statistics_bridge.py`; tests: structural (single `frozen_rng` call site, no `numpy.random`, no logger/print); synthetic observations -> `StatisticsResult` returned with correct structure | 1 | Delete file + tests |
| 9 | Artifacts + publication (atomic write) | 5 artifacts built from typed results; atomic temp-dir rename; existing directory refused; failure artifact has no statistical fields | `runner/artifacts.py`, `runner/publication.py`; tests: artifact schema validation; `run_status.json` written last; existing dir -> refusal; failure artifact field whitelist; synthetic temporary files only | 2, 8 | Delete files + tests |
| 10 | Run discovery orchestrator (end-to-end synthetic) | Full synthetic run: two-phase gate (preflight checks 1-11 then instrument processing check 12) before Layer-1. Tests: (1) full synthetic end-to-end with mocked git/dataset — all checks pass -> one `AuthorizationReceipt` covering all 12, one `compute_all_statistics` call, 5 correct artifacts published; (2) single-instrument failure (bundle 3) -> no receipt created, zero `compute_all_statistics` calls, zero Layer-1 calls; (3) preflight failure -> no instrument processing, no receipt, zero Layer-1 calls. Uses synthetic temporary files, never real discovery data. | `runner/run_discovery.py`; tests: full end-to-end, instrument failure abort, preflight failure abort | 6, 7, 8, 9 | Delete file + tests |

### No late test-only slices

Every slice above includes both production code and its tests. There are no separate "structural fitness test" or "integration test" slices — structural fitness assertions (import constraints, single-call-site, no-logger) are written as part of the slice that introduces the code they guard.

### Synthetic Layer-1 performance qualification (REQ-STAT-59)

**Pre-baseline gate**, executed AFTER slice 10, BEFORE baseline B creation. NOT a CI test — a one-time measurement.

**What it validates**:
- Layer-1's confirmed `O(replicates x instruments x observations)` bootstrap cost at the expected population scale.
- Runtime (wallclock) and peak memory for `bootstrap_est_b` on synthetic observations sized to exercise the algorithmic path.

**Thresholds**: None frozen — the qualification reports measured numbers. If the cost is operationally impractical, that STOPS baseline creation and opens a separate Layer-1 performance spec.

---

## N. Frozen scope declaration

The following files and semantics MUST remain frozen (no modification) throughout Layer-3 implementation:

### Files

| File/package | Freeze commit |
|---|---|
| `detector/selection/` (entire package) | `75d9c37` |
| `detector/adapter/` (entire package) | `1dd0acc` (latest, includes causal provenance) |
| `detector/causal/` (entire package) | `2419381` |
| `detector/backtest/candidate.py` | Latest HEAD |
| `detector/backtest/population.py` | Latest HEAD |
| `detector/backtest/simulate.py` | Latest HEAD |
| `detector/backtest/levels.py` | Latest HEAD |
| `detector/evaluation/direction.py` | Latest HEAD |
| `detector/policy/direction.py` | Latest HEAD |
| `detector/alignment/htf_ltf.py` | Latest HEAD |
| `detector/core/config.py` | Latest HEAD |
| `detector/core/candle.py` | Latest HEAD |
| `detector/research/direction_policy_discovery_v1_amendment_1.json` | `f542924` |
| `openspec/changes/crt-detector-direction-policy-statistical-runner/spec.md` | Current (V7) |
| `openspec/changes/crt-detector-causal-candidate-generation/spec.md` | `1f412e3` |

**NOTE**: Section G's decision (Option A, human-approved) authorizes a targeted un-freeze of `detector/adapter/manifest.py` for additive field additions only. All new fields carry neutral defaults (`None`, `()`) and do not alter existing Layer-2 runtime behavior. This follows the precedent set at `1dd0acc` (targeted `InstrumentRunBundle` amendment).

### Semantics

- `simulate()` signature (line 282-287 of `detector/backtest/simulate.py`): `(aligned_signals: list[AlignedSignal], ltf_series: OHLCSeries, config: DetectorConfig, swings: list[SwingPoint] | None = None) -> tuple[list[Trade], ReconciliationReport]` — Layer-3 MUST NOT alter its signature, add a return value, or modify its internal `build_stage6_population` call.
- `build_stage6_population()` signature (lines 120-124 of `detector/backtest/population.py`): `(aligned_signals: list[AlignedSignal], ltf_series: OHLCSeries, config: DetectorConfig, swings: list[SwingPoint] | None = None) -> Stage6Population`.
- `generate_causal_aligned_signals()` signature (lines 39-47 of `detector/causal/generate.py`): `(ltf_series: OHLCSeries, htf_series: OHLCSeries, crt_config: CRTRangeConfig = CRTRangeConfig(), model1_config: Model1Config = Model1Config(), htf_key_levels: list[KeyLevel] | None = None, daily_series: OHLCSeries | None = None, daily_key_levels: list[KeyLevel] | None = None) -> list[AlignedSignal]`.
- `build_direction_policy_observations()` signature (lines 22-23 of `detector/adapter/build.py`): `(bundle: InstrumentRunBundle) -> tuple[DirectionPolicyObservation, ...]`.
- `evaluate_direction_policies()` signature (lines 118-120 of `detector/evaluation/direction.py`): `(population: Stage6Population, evidence: DirectionEvidence) -> tuple[DirectionEvaluation, ...]`.
- `frozen_rng()` (line 28 of `detector/selection/bootstrap.py`): returns `Generator(PCG64(SeedSequence([20260910])))`.
- `FROZEN_POLICY_IDS` (line 28 of `detector/evaluation/direction.py`): the 4 frozen policy IDs.
- `FROZEN_REPLICATES`: 10,000.
- `MEI_R`: 0.20 (line 16 of `detector/adapter/manifest.py`).

---

## O. No-real-data attestation

No real market data, outcomes, backtest results, EST-B values, WR, PF, nomination results, or performance measurements were inspected or produced during this design pass. All code reads were of committed source files. No `simulate()`, `build_stage6_population()`, `generate_causal_aligned_signals()`, `stratify()`, `compute_est_b()`, `bootstrap_est_b()`, or `nominate()` call was executed. No CSV file was loaded. No `Trade` object carrying real `r_multiple` or `outcome` values was observed. This design is grounded entirely in reading frozen source code, the frozen V6 spec, and committed `.importlinter` contracts.

---

## P. Acceptance summary

### Requirement coverage

**29 requirements in scope**: REQ-STAT-36 through REQ-STAT-64.

### Coverage breakdown

- **`designed`**: 26 requirements (REQ-STAT-36, 37, 38, 39, 40, 41, 42, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 60, 61, 62, 63, 64)
- **`blocked`**: 0
- **`manual-closeout`**: 3 requirements (REQ-STAT-43, 44, 59 — require commits and baseline steps that do not yet exist; these are NOT implementation blockers, they are intrinsically post-implementation gates)

**Arithmetic check**: 26 designed + 0 blocked + 3 manual-closeout = 29.

### Resolved decisions (formerly blocking questions)

| # | Decision | Option chosen | Affected REQs | Resolution |
|---|---|---|---|---|
| 1 (was BQ-1) | **Population build count** | **B: one external build** | REQ-STAT-52, REQ-STAT-61 | Human-approved 2026-09-13. V7 spec amendment reconciles REQ-STAT-52/61. One explicit external `build_stage6_population` per instrument; `simulate()`'s internal build is unavoidable and inaccessible; same-object discipline is the enforcement mechanism. See Section F. |
| 2 (was BQ-2) | **Manifest field gap** | **A: additive extension** | REQ-STAT-37, 38, 39, 40, 41, 42, 63 | Human-approved 2026-09-13. V7 spec amendment authorizes additive extension of `adapter.manifest.Manifest`. Same class, same frozen-instance semantics. 12 new additive fields with neutral defaults (`statistical_spec_v3_commit` is an existing Layer-2 field, retained unchanged, not counted). V7.1 corrected: `CausalSourceInputRecord` now has 4 fields with closed `producer_id` literals, 9 entries total, cross-referencing `dataset_records`; no `payload_sha256`. Layer-2 runtime behavior unchanged. See Section G. |

### Open questions — non-blocking

1. **REQ-STAT-64(b)**: The Key Level source causality equivalence argument (extending REQ-CAUSAL-15 to `detect_fvgs`/`detect_ict_order_blocks`'s own `expiry_index`/`invalidation_index`) is not yet covered by a property test. The spec itself classifies this as "an open, non-blocking documentation gap" that real discovery MAY proceed without.

2. **REQ-STAT-65 status**: ~~Already implemented at `1dd0acc`/`f09b838`; the signed spec still says "NOT IMPLEMENTED." Reconciliation is a closeout follow-up.~~ **Resolved**: the spec's V7 amendment has corrected REQ-STAT-65's status to "SATISFIED by `1dd0acc`". No longer an open question.

3. **`os.replace` atomicity**: Assumed for same-filesystem POSIX rename semantics. On Windows, `os.replace` is atomic for file-to-file but directory-to-directory atomicity depends on the filesystem. The publication step should document this assumption.

4. **HTF and Daily series loading**: The exact file-to-series mapping (which `dataset_records` entry is LTF, HTF, Daily) is implied by `granularity` field values. This is an executor-local decision resolvable at implementation from the protocol JSON's `dataset.files` entries.

### Preserved design invariants

All of the following are unchanged by the V7 resolution:

- **Corrected `evaluate_direction_policies(population, evidence: DirectionEvidence)` with grounded evidence** (Section C, step 2i).
- **RNG fitness**: zero `numpy.random`/`np.random` text references across `runner/`; single `frozen_rng()` call site in `statistics_bridge.py` (Section I).
- **Tuple-container / element-identity wording**: `tuple(admitted)` creates a new container but preserves element identity (Section D).
- **Two-phase flow**: checks 1-11 (preflight) then check 12 (all three instrument bundles) before Layer-1 (Section C).
- **No authorization receipt before all 12 checks pass** (Section C, step 3).
- **Reuse validated instrument results**: `AuthorizationReceipt.instrument_results` retains Phase 2 results; instruments NOT processed twice (Section C, step 3).
- **No-real-data attestation** (Section O).

### Verdict

**`ready_for_implementation: yes`**

Reasons:
- Both design-blocking questions (population build count, manifest field gap) are resolved by human decision. The V7 spec amendment reconciles REQ-STAT-52/61 and authorizes additive Manifest extension (12 additive fields; `statistical_spec_v3_commit` is an existing Layer-2 field, not counted).
- 26 of 29 in-scope requirements are `designed` with full flow, data-contract, and test-strategy evidence.
- 3 requirements are `manual-closeout` (REQ-STAT-43, 44, 59) — these depend on commits/baseline steps that cannot exist until implementation is complete. They are NOT implementation blockers; they are intrinsically post-implementation gates (baseline B creation process, authorization commit A, and the pre-baseline performance qualification).
- The execution flow, evaluation call, preflight/authorization ordering, data contracts, additive Manifest fields (12 total: 10 unchanged + `statistical_spec_commit_chain` + `causal_source_inputs`), and one-external-build reconciliation are all fully designed with file/line evidence.
- REQ-STAT-65 is SATISFIED by `1dd0acc`/`f09b838` (confirmed by V7 spec correction). Zero forward dependencies remain.
