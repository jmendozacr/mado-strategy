# Exploration: DirectionPolicy Evaluation Seam

## Canonical protocol audit

**Verdict: PASS — no preregistration contradiction or population mismatch.** The worktree is clean at commit `f542924ea4280af384b298e6fc4b54dfb54a33e6`; that commit contains the canonical amendment blob `d2b759320ed9017eec53eff24f924dd18c8e4ec8`. Its byte length is `7737` and SHA-256 is `47b17d7891f6f9a2d2d30f83df88b060840a895484a78e763c8f46da1ea8de4d`. Its `artifact.status` is `FROZEN_NO_OUTCOMES_INSPECTED` (the canonical machine-readable form of “FROZEN — NO OUTCOMES INSPECTED”), with `authority_model=GIT_BLOB_BYTES`.

The authority explicitly defines `EP-C_STAGE6_CANDIDATES_V1` as “one stage-6 Candidate before fill”, with this exact order: `population cuts → build → dedup → kill-zone → R:R floor → classify`. It requires the frozen policy order P1–P4, identity `(instrument, timeframe, signal_id, retest_index)`, M15 provenance, `K = Candidate.retest_index >= 3`, Bias at `K−1`, and eligible Order Flow at `confirmation_index <= K−1`. It forbids origin, anchor, later Model-1 endpoint, fill, and exit evidence.

## Current State

`backtest.simulate.simulate()` is the only actual EP-C population path. It receives `list[alignment.htf_ltf.AlignedSignal]` and the LTF `core.candle.OHLCSeries`, then performs the canonical stage sequence before any fill or exit work. No executable path currently invokes the new DirectionPolicies, Bias, or Order Flow during population selection; `policy.direction` is consumed only by its tests. The existing population therefore is policy-independent, but intentionally retains the canonical HTF/LTF, Key Level, deduplication, kill-zone, and R:R filters.

### Exact Candidate → fill trace

1. `detector/cli.py:149–179` creates `detections` with `_detect_all()`, snapshots `detections.aligned_signals` as `population` before display-only confluence/type filtering, and calls `simulate(population, ltf_series, ...)` only for `--backtest`.
2. `detector/cli.py:240–244` builds `AlignedSignal` through `alignment.htf_ltf.tag_alignment()` from HTF and LTF series. `detector/alignment/htf_ltf.py:79–107` marks each signal `aligned`, `unaligned`, or `insufficient_htf_data` and supplies the Key Level.
3. `detector/backtest/simulate.py:420–429` applies `_population_cuts` (lines 174–197), `_build_candidate` (89–112), `_dedup` (200–208), `_kill_zone_cut` (211–223), and `_rr_floor_cut` (226–235). The surviving list on line 429 is exactly the stage-6 population.
4. `Candidate` is `@dataclass(frozen=True)` in `detector/backtest/simulate.py:24–39`; it carries `signal_id`, `anchor_index`, `origin_index`, `direction`, `entry_type`, `retest_index`, and price levels, but not instrument, timeframe, or series.
5. `detector/backtest/simulate.py:430` hands only the stage-6 survivors to `_fill_pass`; lines 238–252 sort by `retest_index` and call `two_heap_sweep` eligible at K. This is the fill boundary. Lines 432–434 resolve exits only after a fill exists.

### Population re-audit

| Concern | Evidence | Verdict |
|---|---|---|
| New DirectionPolicies P1–P4 | `backtest/simulate.py` does not import `policy`; repository search finds policy functions only in `policy/direction.py` and policy tests. | Not filtered. |
| Bias | `backtest/simulate.py` has no `primitives.bias` import or Bias branch. | Not filtered. |
| Order Flow | `backtest/simulate.py` has no `composite.order_flow` import or Order Flow branch. | Not filtered. |
| HTF/LTF alignment | `_population_cuts` excludes `tagged.aligned != "aligned"` at lines 186–187. | Filtered, as canonically specified population cut. |
| Direction | `Candidate.direction` is copied from `Model1Signal.direction` at lines 92–107; it selects execution geometry but has no policy/Bias/Order-Flow direction filter. | Present as candidate attribute, not a new-policy filter. |
| Other canonical cuts | `fvg_fill`, missing retest, missing Key Level, deduplication, kill-zone, and R:R are applied before fill. | Filtered, exactly matching the canonical stage order/configuration. |

**Contamination verdict: CLEAN for the required evaluation input.** Stage-6 candidates are selected before `_fill_pass`, `_resolve_exits`, `Trade`, metrics, and output writers. Their current producer does, however, live in the outcome-bearing `backtest.simulate` module, so an evaluation layer must not import that module merely to obtain `Candidate`.

## Affected Areas

- `detector/backtest/simulate.py` — owns the canonical population stages and currently co-locates `Candidate` with fill/outcome code.
- `detector/backtest/candidate.py` (new) — smallest safe home for the unchanged immutable candidate type; prevents an outcome-bearing import edge.
- `detector/evaluation/direction.py` (new) — evaluation-only batch seam consuming pre-fill candidates plus separately validated series/evidence.
- `detector/policy/direction.py` — already supplies the fixed P1–P4 decisions and correctly honors a supplied cutoff.
- `detector/primitives/bias.py` and `detector/composite/order_flow.py` — precomputed, causal evidence sources; no production population dependency today.
- `detector/.importlinter` and `detector/tests/test_fitness_imports.py` — must enforce that evaluation cannot import simulation, metrics, levels, research, or a runner, and research cannot import evaluation.

## Approaches

1. **Extract only the Candidate type, then evaluate an explicitly supplied stage-6 batch**
   - Pros: minimal import change; no change to fill/candidate semantics; evaluation remains outcome-free and testable with synthetic batches.
   - Cons: no existing public producer exposes the exact stage-6 list; a later caller must obtain it without importing simulation.
   - Effort: Low.

2. **Extract the complete stage-1–6 producer with Candidate as an outcome-free backtest boundary**
   - Pros: exposes the exact frozen population deterministically and lets evaluation consume the actual pre-fill boundary.
   - Cons: larger refactor; must pin sequence/count semantics against existing simulation to avoid a population drift.
   - Effort: Medium.

## Recommendation

Adopt Approach 2 only if the seam must itself source the real EP-C population; otherwise retain Approach 1 for the specified evaluation-only deliverable. In either case, put evaluation above `policy` and the outcome-free Candidate module, never above `backtest.simulate`. Validate the candidate batch against an explicitly supplied identical M15 `OHLCSeries` and instrument/timeframe before computing each P1–P4 label at K−1. Do not add a runner, data access, fill join, or statistics surface.

## Import-boundary assessment

The current `.importlinter` makes `backtest` a higher layer than `alignment | policy`, with `research` barred from `policy`. It has no `evaluation` package yet. A clean seam adds `evaluation` as a top layer allowed to import `policy`, primitives/composites, and the extracted Candidate type, while explicitly forbidding `evaluation -> backtest.simulate`, `backtest.metrics`, `backtest.levels`, and `research`, and forbidding `research -> evaluation`. An AST/import-fitness allowlist is still needed because the layer contract cannot prove symbol-level isolation.

## Risks

- The only current stage-6 producer is private and co-located with `Trade`; importing it would contaminate the firewall even if no fill is executed.
- A producer extraction can accidentally alter the frozen sequence or filters; preserve `_population_cuts → build → dedup → kill-zone → R:R floor` byte-for-behavior and test it as a boundary.
- `Candidate` lacks provenance fields. The seam must receive and validate the exact series/instrument/timeframe as explicit inputs rather than infer them from outcome-bearing objects.
- CodeGraph initialization was attempted as required but `gentle-ai` reported `unknown command "codegraph"`; filesystem inspection was used only after that failure.

## Open Questions

open_questions: none — the canonical amendment itself resolves the apparent stage-6 ambiguity by naming the exact stage order and configuration. The choice between a type-only extraction and producer extraction is an implementation scope choice, not a preregistration question.

## Ready for Proposal

Yes — canonical authority, stage-6 population, timing cutoff, and clean import seam are verified. Preserve the strict no-outcomes/no-runner boundary and do not treat the historical Engram #574 digest as authority.
