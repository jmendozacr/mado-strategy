# Design — crt-detector-statistical-runner-layer2-causal-provenance

**Status**: DESIGN COMPLETE (rev 2 — technical-lead review corrections applied).
**Normative source**: `openspec/changes/crt-detector-direction-policy-statistical-runner/spec.md` V6,
REQ-STAT-28 (AMENDED V6) and REQ-STAT-65.
**HEAD at design time**: `edd6eef7e5a19d83570d76346c017e52cb828a91` (branch `docs/order-flow-triage`).
**Frozen constraints**:
- Layer-1 (`detector/selection/`, commit `75d9c37`) — MUST NOT change.
- Current Layer-2 (`detector/adapter/`, commit `9644876`) — this design defines its amendment; current
  code is the pre-amendment baseline.
- Causal generation (`causal/generate.py`, spec `1f412e3`, amendment `8f1906e`, impl `2419381`) — MUST
  NOT change.
**Scope**: design and artifact only. No Python source or tests were edited. No real data, outcomes,
backtest results, baselines, authorization commits, or repository commits were produced.

---

## A. Problem statement (code-grounded)

`build_direction_policy_observations` (Step 5, `adapter/build.py:49`) calls:

```python
cluster_map = reconstruct_context_clusters(bundle.instrument, bundle.htf_series, series, bundle.config)
```

`reconstruct_context_clusters` (`adapter/cluster.py:45-53`) re-runs `alignment.htf_ltf.tag_alignment()`
on the full series and feeds its output to `build_cluster_map`. For a causally-generated population
this is wrong: `tag_alignment()`'s HTF-selection rule (`_enclosing_htf_index` + `_purge_index_map`'s
global-earliest-start-index winner for a shared purge candle) is a DIFFERENT function from the causal
H-A rule (`causal.htf.select_htf_context`: largest purge_index among resolved-and-closed ranges
observable at each signal's own event time `t`).

**Proof from existing test** (verified at HEAD, zero real data):
`tests/test_causal_key_level_causality.py::test_key_level_credited_from_a_stale_global_winner_ignores_the_signals_own_htf_context`
uses a 7-candle HTF fixture with two ranges sharing purge_index 5 (range@4 resolving at index 5,
range@3 resolving at index 6). A late-`t` LTF signal's H-A `htf_context` is range@3 (`start_index=3`),
while legacy `_purge_index_map`'s global map resolves the same purge_index to range@4 — a different
`context_cluster_id` entirely (`context_cluster_id = (instrument, start_index, end_index,
resolved_at_index)`, so `start_index` alone distinguishes the two).

`InstrumentRunBundle` carries neither `aligned_signals` nor any reference to the causal generator's
per-signal `htf_context`. The gap is:

| What is missing | Where |
|---|---|
| `aligned_signals: tuple[AlignedSignal, ...]` field | `adapter/bundle.py::InstrumentRunBundle` |
| Call to `build_cluster_map(bundle.instrument, bundle.aligned_signals)` | `adapter/build.py` Step 5 |

`build_cluster_map` (`adapter/cluster.py:19-34`) already exists and is already correct: it reads
`.htf_context`/`.ltf_signal.signal_id` off whatever `AlignedSignal` sequence it receives, with zero
assumption about how the sequence was produced.

---

## B. Decision 1 — `InstrumentRunBundle.aligned_signals` type and invariant

### Type

```python
aligned_signals: tuple[AlignedSignal, ...]
```

`AlignedSignal` is `alignment.htf_ltf.AlignedSignal` — the exact type `generate_causal_aligned_signals`
already returns (REQ-CAUSAL-12/13 guarantee). No new type is introduced. The field is `tuple` (immutable,
consistent with all other `InstrumentRunBundle` sequence fields).

### `__post_init__` invariant

```python
signal_ids_in_aligned = {s.ltf_signal.signal_id for s in self.aligned_signals}
for candidate in self.population.candidates:
    if candidate.signal_id not in signal_ids_in_aligned:
        raise AdapterIntegrityError(
            f"candidate signal_id {candidate.signal_id!r} absent from aligned_signals"
        )
```

### What the invariant proves — and what it does not

**Proved**: every `Candidate.signal_id` in `population.candidates` is present in the SET of signal_ids
drawn from `aligned_signals`. Failure at bundle construction gives a clear, early error: a candidate
signal_id that is entirely absent from the supplied list means the list cannot be the causal generator
output that produced this population.

**NOT proved** — three explicit limitations:

1. **`htf_context` non-null**: A signal_id that IS present in `aligned_signals` but whose corresponding
   `AlignedSignal.htf_context is None` will be absent from `build_cluster_map`'s output dict (cluster.py:26
   `if tagged.htf_context is None: continue`), and `lookup_context_cluster` will raise
   `ClusterReconstructionError`. This is correct fail-closed behavior, not a gap. In a consistent
   build the situation cannot arise: `backtest/population.py::_population_cuts` (lines 72-73) excludes
   every signal with `aligned != "aligned"`, and `tag_alignment()`/`generate_causal_aligned_signals`
   only set `aligned="aligned"` when `htf_context is not None` — so no Candidate admitted to Stage6
   can have a null `htf_context` in the generator output. The fail-closed downstream path remains the
   safety net for inconsistent callers.

2. **Python object identity**: the subset check cannot prove that the list passed to
   `build_stage6_population` and `simulate()` is the SAME Python list object as `aligned_signals`.
   A caller could supply two different lists that produce the same set of signal_ids. The orchestration
   guarantee — that the causal generator output is used consistently for all three: generate →
   build_stage6_population → simulate → bundle.aligned_signals — lives at Layer-3, which is the
   intended caller. Layer-2 cannot enforce this without inventing a fingerprint or a new type, both
   of which REQ-STAT-65 explicitly prohibits ("not the 'provenance sidecar' this spec's Section K/Q
   previously rejected").

3. **Extra signals**: signals in `aligned_signals` that have no matching Candidate are allowed.
   `build_cluster_map` maps them; `lookup_context_cluster` is never called for them. No validation
   is added for extras — they are the excluded-at-Stage6 signals the generator also emitted.

### What the invariant does NOT check (and why no check is needed)

| Edge case | Disposition | Reason |
|---|---|---|
| `htf_context is None` for a present signal_id | Not checked at bundle | `lookup_context_cluster` raises `ClusterReconstructionError` downstream (fail-closed, correct); see limitation 1 above. |
| Cross-instrument signals in `aligned_signals` | No check | `AlignedSignal` carries no instrument field. Bundle already proves `instrument == population.series.instrument`. Correct sourcing is Layer-3's responsibility. |
| Duplicate `signal_id` with identical `htf_context` | No check | `build_cluster_map` deduplicates silently (same value → no conflict). |
| Duplicate `signal_id` with inconsistent `htf_context` | No check | `build_cluster_map` raises `ClusterReconstructionError` — already enforced downstream. |
| Extra signals not in `population.candidates` | Allowed | Generator output includes excluded signals. `lookup_context_cluster` is only called for Candidates actually in the pipeline. |
| Ordering of `aligned_signals` | Not required | `build_cluster_map` builds a dict — emission order is irrelevant. |
| Empty `aligned_signals` with empty population | No check | Vacuously valid — the loop body never executes. |
| Empty `aligned_signals` with non-empty population | Caught | First `candidate.signal_id not in set()` raises `AdapterIntegrityError`. |

**No check is added for anything `build_cluster_map` already enforces** — the boundary invariant adds
only the presence-linkage check. All downstream consistency gates are retained.

---

## C. Decision 2 — Production call path replacement

In `build_direction_policy_observations` (Step 5):

```python
# BEFORE (current HEAD 9644876, adapter/build.py:49):
cluster_map = reconstruct_context_clusters(bundle.instrument, bundle.htf_series, series, bundle.config)

# AFTER (this amendment):
cluster_map = build_cluster_map(bundle.instrument, bundle.aligned_signals)
```

**Import correction** (this was wrong in rev 1): `build_cluster_map` is NOT currently in `build.py`'s
import. The current import reads:

```python
# build.py:9 (current HEAD):
from adapter.cluster import lookup_context_cluster, reconstruct_context_clusters
```

The amendment ADDS `build_cluster_map` and REMOVES `reconstruct_context_clusters`:

```python
# AFTER:
from adapter.cluster import build_cluster_map, lookup_context_cluster
```

**No production path may call `tag_alignment()` to derive causal cluster provenance.** This is enforced
structurally: `reconstruct_context_clusters` — the only production-path caller of `tag_alignment()` in
`adapter/` — is removed (Decision 3). The import `from alignment.htf_ltf import AlignedSignal,
tag_alignment` in `adapter/cluster.py` is trimmed to `from alignment.htf_ltf import AlignedSignal`.
The new import-linter contract (Decision 4) prohibits `adapter` from importing `causal`, closing any
attempt to self-generate signals inside the adapter.

---

## D. Decision 3 — Dead code removal

### Evidence that `htf_series`, `config`, and `reconstruct_context_clusters` are dead after the amendment

**`adapter/build.py` step 5** — only call site of `reconstruct_context_clusters` (line 49):
```python
cluster_map = reconstruct_context_clusters(bundle.instrument, bundle.htf_series, series, bundle.config)
```
After replacing with `build_cluster_map(bundle.instrument, bundle.aligned_signals)`:
- `bundle.htf_series` is no longer referenced anywhere in `build_direction_policy_observations`.
- `bundle.config` is no longer referenced anywhere in `build_direction_policy_observations`.
- Verified by reading all 91 lines of `adapter/build.py`: `bundle.htf_series` appears only at line 49;
  `bundle.config` appears only at line 49.

**`adapter/bundle.py` `__post_init__` lines 38-42**:
```python
if self.htf_series.instrument != self.instrument:
    raise AdapterIntegrityError(...)
```
This check exists only to validate the `htf_series` field. With the field removed, the check goes away.

**`adapter/cluster.py::reconstruct_context_clusters`** (lines 45-53):
```python
def reconstruct_context_clusters(
    instrument: str, htf_series: OHLCSeries, ltf_series: OHLCSeries, config: DetectorConfig
) -> dict[str, ContextClusterId]:
    tagged = tag_alignment(htf_series, ltf_series, config.crt_range, config.fvg, config.model1)
    return build_cluster_map(instrument, tagged)
```
After removing the call in `build.py`, this function has no production caller. Its only remaining
callers are the two tests that explicitly test the legacy reconstruction path — both become moot.

### Verdict: remove all three

| Symbol | Verdict | Justification |
|---|---|---|
| `InstrumentRunBundle.htf_series` | **Remove** | Only used at build.py:49. No other reference in any `adapter/` module. Layer-3 holds `htf_series` on its own side for Key Level detection. |
| `InstrumentRunBundle.config` | **Remove** | Only forwarded to `reconstruct_context_clusters` at build.py:49. `config` is Layer-3's operational input. |
| `adapter.cluster.reconstruct_context_clusters` | **Remove** | Zero production callers after the amendment. Keeping it invites a future caller to use the wrong (legacy) path — exactly the error this amendment closes. |

Removing these reduces `InstrumentRunBundle` to 7 fields (from 9). `cluster.py` becomes two pure
immutable functions (`build_cluster_map`, `lookup_context_cluster`). The fail-closed paths are
preserved: `ClusterReconstructionError` on absent or null-htf_context signal_id still fires through
`lookup_context_cluster`; the new bundle-boundary invariant catches complete signal_id absence earlier.

---

## E. File change table

| File | Change | Must remain unchanged? |
|---|---|---|
| `detector/adapter/bundle.py` | **Modify**: add `aligned_signals: tuple[AlignedSignal, ...]`; remove `htf_series` and `config`; update `__post_init__`; add `from alignment.htf_ltf import AlignedSignal` import | — |
| `detector/adapter/build.py` | **Modify**: replace Step 5 call; update import (add `build_cluster_map`, remove `reconstruct_context_clusters`); update Step 5 comment | — |
| `detector/adapter/cluster.py` | **Modify**: remove `reconstruct_context_clusters`; trim `from alignment.htf_ltf import AlignedSignal, tag_alignment` → `from alignment.htf_ltf import AlignedSignal`; remove `from core.config import DetectorConfig` and `from core.candle import OHLCSeries` (now unused); update module docstring | — |
| `detector/.importlinter` | **Modify**: add `no-causal-in-adapter` contract (see Decision 4) | — |
| `detector/tests/test_adapter_bundle.py` | **Modify**: all 4 `InstrumentRunBundle(...)` calls — remove `htf_series=...` and `config=...`; add `aligned_signals=()`; add 2 new invariant tests | — |
| `detector/tests/test_adapter_build.py` | **Modify**: `_build_synthetic_bundle()` — remove `htf_series=htf_series, config=config,`; add `aligned_signals=tuple(tagged),`; add 1 new source-of-truth regression test | — |
| `detector/tests/test_adapter_cluster.py` | **Modify**: remove `reconstruct_context_clusters` import and its 2 tests; update structural guard (see Section I) | — |
| `detector/adapter/errors.py` | **Documentation only**: update `ClusterReconstructionError` docstring to describe lookup from the supplied `AlignedSignal` sequence instead of the superseded `tag_alignment()` re-run. The public exception class name is intentionally preserved. | — |
| `detector/tests/property/test_adapter_properties.py` | **No change** — imports `_build_synthetic_bundle` from `test_adapter_build`; inherits the bundle fix transitively | — |
| All files under `detector/selection/` | **Must not change** | Layer-1, frozen commit `75d9c37` |
| All files under `detector/causal/` | **Must not change** | Causal generation, frozen commit `2419381` |
| All files under `detector/alignment/` | **Must not change** | Frozen |
| `detector/backtest/candidate.py` | **Must not change** | `Candidate` type is frozen |
| `openspec/changes/crt-detector-direction-policy-statistical-runner/spec.md` | **Must not change** | V6 normative spec, frozen commit `edd6eef` |
| `.sdd/project.json` | **Must not change** | User-owned untracked file |

---

## F. Decision 4 — New import-linter contract

Add to `detector/.importlinter`:

```ini
[importlinter:contract:no-causal-in-adapter]
name = Layer-2 adapter must not import the causal candidate-generation path
# REQ-STAT-65: the adapter RECEIVES aligned_signals as an explicit bundle field,
# supplied by Layer-3. It must never call generate_causal_aligned_signals itself —
# that would silently duplicate Layer-3's responsibility and violate the layering
# defined in REQ-STAT-33/65.
type = forbidden
source_modules =
    adapter
forbidden_modules =
    causal
```

This makes it structurally impossible for a future implementer to have the adapter generate its own
aligned signals. It mirrors `no-causal-in-evaluation` in spirit.

---

## G. Precise `__post_init__` for the amended `InstrumentRunBundle`

```python
def __post_init__(self) -> None:
    if self.instrument != self.population.series.instrument:
        raise AdapterIntegrityError(
            f"bundle.instrument {self.instrument!r} must equal "
            f"population.series.instrument {self.population.series.instrument!r} "
            f"— never diverge from the Stage6Population it was built for"
        )
    signal_ids_in_aligned = {s.ltf_signal.signal_id for s in self.aligned_signals}
    for candidate in self.population.candidates:
        if candidate.signal_id not in signal_ids_in_aligned:
            raise AdapterIntegrityError(
                f"candidate signal_id {candidate.signal_id!r} absent from aligned_signals"
            )
```

The removed `htf_series.instrument` check is not replaced — it guarded a field that no longer exists.

---

## H. Amended `build_direction_policy_observations` Step 5

```python
# 5) Cluster identity from AlignedSignal.htf_context supplied by the caller.
cluster_map = build_cluster_map(bundle.instrument, bundle.aligned_signals)
```

---

## I. Test plan

### Tests to remove

| File | Test | Reason |
|---|---|---|
| `test_adapter_bundle.py` | `test_bundle_rejects_htf_series_instrument_mismatch` | Guards a field being removed; no equivalent needed. |
| `test_adapter_cluster.py` | `test_reconstruct_delegates_to_tag_alignment_on_full_series` | Tests the removed function. |
| `test_adapter_cluster.py` | `test_cluster_module_never_truncates_the_series` | Replaced by a more precise structural guard; see below. |

### Tests to update (constructor call changes only, logic unchanged)

| File | What changes |
|---|---|
| `test_adapter_bundle.py` (3 remaining tests) | `InstrumentRunBundle(...)` calls: remove `htf_series=..., config=...`; add `aligned_signals=()`. `test_bundle_is_immutable` also updates its constructor call. |
| `test_adapter_build.py` | `_build_synthetic_bundle()`: remove `htf_series=htf_series, config=config,`; add `aligned_signals=tuple(tagged),` (`tagged` is already in scope at line 63). |

### New tests — bundle invariant (`test_adapter_bundle.py`)

```
test_bundle_rejects_candidate_with_missing_signal_id
    population has 1 Candidate with signal_id="sig-A"
    aligned_signals is ()
    → AdapterIntegrityError

test_bundle_permits_extra_aligned_signals
    population has 0 candidates
    aligned_signals has 1 AlignedSignal with an arbitrary signal_id
    → no error (extras are permitted; lookup_context_cluster is never called for them)
```

### New structural guard — `test_adapter_cluster.py`

Replace the removed `test_cluster_module_never_truncates_the_series` with an AST-based guard:

```python
def test_adapter_cluster_does_not_reference_tag_alignment():
    """AST guard: cluster.py must not import or attribute-reference tag_alignment."""
    import ast
    import importlib.util
    import pathlib

    spec = importlib.util.find_spec("adapter.cluster")
    source = pathlib.Path(spec.origin).read_text()
    tree = ast.parse(source)
    imported = [
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    ]
    attributes = [
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
    ]
    assert "tag_alignment" not in imported
    assert "tag_alignment" not in attributes
```

The guard checks both imported alias names and `ast.Attribute` nodes, so its name and claim
(`does_not_reference`) exactly matches the evidence it produces. The `.up_to(` / `.candles[` guards
from the original test are not carried forward — they were motivated exclusively by
`reconstruct_context_clusters`'s obligation not to truncate the series; with that function removed,
the guards have no remaining referent.

### New source-of-truth regression test — `test_adapter_build.py`

#### Name

```
test_context_cluster_id_uses_supplied_aligned_signal_context
```

#### Purpose

Prove, at the adapter boundary, that `context_cluster_id` in the output observations is determined
by the `AlignedSignal.htf_context` stored in `bundle.aligned_signals`, not by a `tag_alignment()`
re-run. REQ-STAT-28 (AMENDED V6) / REQ-STAT-65.

#### Fixture construction (no real data; uses only functions already called by `_build_synthetic_bundle`)

1. Call `_build_synthetic_bundle()` — produces one admitted Candidate; `bundle.aligned_signals` is
   `tuple(tagged)` where `tagged` came from `tag_alignment(htf_series, ltf_series, ...)`. The fixture
   uses 6 Daily HTF candles (indices 0–5), so every real CRT range has `start_index ∈ {0,1,2,3,4,5}`.

2. Locate the `AlignedSignal` in `bundle.aligned_signals` whose `ltf_signal.signal_id` matches
   `bundle.population.candidates[0].signal_id`. Call it `original`.

3. Assert `original.htf_context is not None` — it must be non-null for the Candidate to have been
   admitted (Stage6 admission gate `_population_cuts` at `population.py:76` excludes `key_level is None`,
   and `aligned != "aligned"` is excluded at line 72; a signal admitted to Stage6 must have
   `aligned=="aligned"` and `htf_context is not None`).

4. Create a synthetic `CRTRange` with `start_index=99` (impossible for a 6-candle series, uniquely
   identifiable):
   ```python
   synthetic_context = CRTRange(
       model="2-candle", high=1.5, low=0.5,
       start_index=99, end_index=100, resolution="true_break", resolved_at_index=100,
   )
   ```

5. Build an amended `AlignedSignal`:
   ```python
   amended_signal = replace(original, htf_context=synthetic_context)
   ```
   `replace` is `dataclasses.replace`; `ltf_signal` is unchanged, so `signal_id` is unchanged.

6. Build an amended bundle:
   ```python
   amended_signals = tuple(
       amended_signal if s.ltf_signal.signal_id == original.ltf_signal.signal_id else s
       for s in bundle.aligned_signals
   )
   amended_bundle = replace(bundle, aligned_signals=amended_signals)
   ```

7. Assert bundle invariant passes (the `signal_id` is still present — `amended_signal` has the same
   `ltf_signal` as `original`).

8. Call `build_direction_policy_observations(amended_bundle)`.

9. Assert non-vacuity:
   ```python
   assert len(observations) == 4  # 4 policies × 1 Candidate
   ```

10. Assert source of truth:
    ```python
    assert all(obs.context_cluster_id[1] == 99 for obs in observations)
    ```

#### Why `start_index[1] == 99` passes under new code but not old

**New code path** (`build_cluster_map(bundle.instrument, bundle.aligned_signals)`):
- `build_cluster_map` iterates `amended_signals`; for the matched signal it reads
  `tagged.htf_context.start_index` directly (cluster.py:29: `tagged.htf_context.start_index`).
- Result: `cluster_id = (instrument, 99, 100, 100)`.
- `lookup_context_cluster` returns `(instrument, 99, 100, 100)`.
- `obs.context_cluster_id[1] == 99` ✓

**Old code path** (`reconstruct_context_clusters(bundle.instrument, bundle.htf_series, ltf_series, bundle.config)`, hypothetically, if those fields still existed):
- `tag_alignment(htf_series, ltf_series, ...)` runs on the ORIGINAL series and returns the REAL
  CRTRange — its `start_index ∈ {0,1,2,3,4,5}` for the 6-candle HTF fixture, never 99.
- `cluster_id[1] != 99` → test fails ✓ (discriminating)

The amended bundle passes the bundle invariant because `signal_id` is unchanged; no other validation
gate reads `htf_context` from the bundle — `build_direction_policy_observations` is the only consumer.

#### Feasibility — traced through `build_cluster_map`

`build_cluster_map` (cluster.py:19-34):
```python
for tagged in tagged_signals:
    if tagged.htf_context is None:
        continue
    signal_id = tagged.ltf_signal.signal_id          # ← unchanged from original
    cluster_id = (
        instrument,
        tagged.htf_context.start_index,              # ← 99, from synthetic_context
        tagged.htf_context.end_index,                # ← 100
        tagged.htf_context.resolved_at_index,        # ← 100
    )
    ...
    mapping[signal_id] = cluster_id
```

With `synthetic_context.start_index=99`, the mapping entry is `signal_id → (instrument, 99, 100, 100)`.
`lookup_context_cluster` returns that tuple. `DirectionPolicyObservation.context_cluster_id` is set to
it. `obs.context_cluster_id[1] == 99` is therefore structurally guaranteed by the code path —
no approximation, no hidden assumption.

The fixture does NOT produce a `ClusterReconstructionError` at the lookup step because `synthetic_context
is not None`; `build_cluster_map` includes the entry. The `_build_synthetic_bundle` assertion
`len(population.candidates) == 1` ensures non-vacuity before any adaptation; `len(observations) == 4`
confirms 4N cardinality holds for the amended bundle.

#### What this test does NOT cover (and where those cases live)

- **Causal H-A vs. legacy disagreement on real OHLC data**: the disagreement is proven by the existing
  test in `test_causal_key_level_causality.py` at the causal-generator level, not repeated here. The
  adapter regression above proves that the adapter's source-of-truth is `aligned_signals`, regardless
  of what `tag_alignment()` would produce.

---

### Existing tests that need no change

- `test_adapter_cluster.py`: `test_cluster_id_shape_is_instrument_start_end_resolved`,
  `test_unaligned_signal_has_no_cluster_entry`,
  `test_duplicate_signal_id_with_inconsistent_htf_context_fails_closed`,
  `test_absent_signal_id_lookup_fails_closed`,
  `test_missing_htf_context_means_absent_from_map_and_lookup_fails_closed` — test `build_cluster_map`
  and `lookup_context_cluster` directly, which are unchanged.
- `test_adapter_identity.py`, `test_adapter_cutoff.py`, `test_adapter_trade_join.py`,
  `test_adapter_dataset.py`, `test_adapter_manifest.py` — no `InstrumentRunBundle` construction.
- `test_adapter_build.py` (all tests other than `_build_synthetic_bundle` helper update and the one
  new regression).
- `test_adapter_properties.py` — inherits via `_build_synthetic_bundle`.

---

## J. Open questions

**None blocking.** One documented gap inherited from the spec:

**Key Level source causality property test** (REQ-STAT-64(b)): the spec flags as an open non-blocking
documentation gap that no property test formally proves `detect_fvgs`/`detect_ict_order_blocks`'s
full-vs-truncated equivalence. This design neither extends nor closes that gap.

---

## K. Compatibility and migration impact

| Caller | Impact |
|---|---|
| Layer-3 runner (`detector/runner/`, not yet created) | **Must pass `aligned_signals`** — the causal generator output used to build the population and simulate. No migration needed (package does not exist). |
| `test_adapter_build.py::_build_synthetic_bundle` | **Minimal**: remove `htf_series=..., config=...`; add `aligned_signals=tuple(tagged)` — `tagged` is already in scope. |
| `test_adapter_bundle.py` (3 surviving + 1 removed test) | **Minimal**: remove `htf_series=..., config=...`; add `aligned_signals=()` from constructor calls. |
| `test_adapter_properties.py` | **No change** — inherits via `_build_synthetic_bundle`. |
| Future callers that stored `bundle.htf_series` or `bundle.config` | **Breaking** — fields are removed. Layer-3 must hold these on its own side; they are not Layer-2 adapter invariants. |

---

## L. Constraint confirmations

- No real market data, outcomes, backtest results, prevalence, EST-B, win rate, profit factor, or
  performance results were inspected.
- No measurement baseline, authorization commit, or repository commit was produced.
- Strategy semantics, OOS protocol, statistical interpretation, Candidate identity,
  cutoff semantics (REQ-STAT-29/36/61), trade reconciliation, causal generation rules, Layer-1
  (`detector/selection/`), and Layer-3 (unimplemented) were not changed.
- REQ-STAT-65's normative meaning was not expanded. All design decisions are traceable to
  REQ-STAT-28 (AMENDED V6) and REQ-STAT-65 items 1–3.
- No new provenance type introduced. `AlignedSignal` (existing) and `build_cluster_map`
  (existing, `adapter/cluster.py:19-34`) are reused without modification.
- `.sdd/project.json` was not touched.
- Working tree state outside `openspec/changes/crt-detector-statistical-runner-layer2-causal-provenance/`
  is unmodified.

---

## M. Changes made in rev 2 vs. rev 1

| Finding | Rev 1 error | Rev 2 correction |
|---|---|---|
| **Blocking: regression fixture** | Used 7-candle causal fixture from `test_causal_key_level_causality.py`; late-`t` signal has `key_level is None` → excluded by `_population_cuts:76` → zero Candidates → vacuously true assertion | Replaced with direct adapter-boundary approach: start from `_build_synthetic_bundle()` (which does admit one Candidate); inject synthetic `CRTRange(start_index=99)` into the matched AlignedSignal; assert non-vacuously `len(observations)==4` then `cluster_id[1]==99`. Feasibility traced through `build_cluster_map:28-30`. |
| **Invariant overclaim** | "invariant proves every Candidate has a cluster_map entry" | Narrowed: invariant proves signal_id is not absent. A signal with `htf_context=None` is present but absent from cluster_map → `ClusterReconstructionError` downstream (correct fail-closed). Orchestration guarantee (same list used for population+simulate+bundle) lives at Layer-3. |
| **Import claim** | "build_cluster_map is already imported in build.py" | Corrected: NOT in current build.py import. Amendment ADDS it while REMOVING `reconstruct_context_clusters`. |
| **Structural test coupling** | `"tag_alignment" not in inspect.getsource(cluster_module)` — fails on current module docstring line 4 which contains "tag_alignment()" in explanatory text | Replaced with AST import inspection: walks the parse tree for `ImportFrom` nodes targeting `alignment.htf_ltf`, asserts `"tag_alignment"` not in the imported names list. |

---

## N. Artifacts produced by this design pass

```
openspec/changes/crt-detector-statistical-runner-layer2-causal-provenance/design.md  ← this file
```

Expected `git diff --stat` after a future implementation session:

```
detector/adapter/bundle.py              |  ~17 lines changed
detector/adapter/build.py              |   ~5 lines changed
detector/adapter/cluster.py            |  ~15 lines removed
detector/adapter/errors.py             |   ~4 lines changed
detector/.importlinter                 |  ~10 lines added
detector/tests/test_adapter_bundle.py  |  ~22 lines changed
detector/tests/test_adapter_build.py   |  ~25 lines changed
detector/tests/test_adapter_cluster.py |  ~15 lines changed
```

Total estimated diff: ~113 lines across 8 files. No new files in the production codebase.
