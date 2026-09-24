# Design: DirectionPolicy Evaluation Seam

## Technical Approach

Use the canonical outcome-free `Stage6Population` as the evaluator input, rather than loose candidates and a separately supplied series. Add its source `OHLCSeries` by reference (not copied) to the existing frozen result. `simulate()` keeps its direct `population.candidates → _fill_pass` handoff and unchanged inputs/outputs. Evaluation receives `Stage6Population` plus `DirectionEvidence`, requires `population.series is evidence.series`, then labels exactly that population.

This closes REQ-DIR-EVAL-02/04/11 without policy execution or outcome coupling. Canonical authority remains `detector/research/direction_policy_discovery_v1_amendment_1.json` at `f542924ea4280af384b298e6fc4b54dfb54a33e6`, SHA-256 `47b17d7891f6f9a2d2d30f83df88b060840a895484a78e763c8f46da1ea8de4d`.

## Architecture Touchpoints

| A3 touchpoint | Baseline relation | Decision |
|---|---|---|
| `backtest` stage-6 producer before fill | aligns | `Stage6Population` owns the canonical candidates, counts, and one series reference. |
| `evaluation` above `backtest`/`policy` | aligns | Import `backtest.population.Stage6Population`; remain forbidden from simulation, levels, metrics, and research. |
| Import-layer firewall | aligns | Preserve layer direction and extend the existing fitness assertion for the allowed producer import. |

`architecture_impact: modifying` — the producer result becomes the evaluation boundary; no layer reversal, external simulation signature, or detector semantics changes. No ADR is required.

## Decision and Alternatives

| Option | Tradeoff | Decision |
|---|---|---|
| Loose candidates + explicit series | Cannot prove one producer or series identity. | Reject. |
| Add per-candidate provenance fields/tokens | Duplicates series metadata and falsely implies Python objects are unforgeable. | Reject. |
| Pass provenance-bearing `Stage6Population` | Small API correction; shares one canonical universe and exact series reference. | Choose. |

The repository contract rejects manually assembled candidate sequences because the public evaluator accepts only `Stage6Population`. It does not claim callers cannot construct Python objects outside that API contract.

## Flow Changes

```text
aligned signals + M15 series + config → build_stage6_population()
  → Stage6Population(series, candidates, exclusions) ─┬→ _fill_pass → trades/report
                                                        └→ evaluate_direction_policies(population, evidence)
```

Evaluation validates the one series reference and bounds before its small batch adapter invokes pure single-candidate row construction. It sorts by `(retest_index, signal_id)`, emits P1→P4 for each, and neither filters nor mutates the population.

## File Changes

| File | Action | Description |
|---|---|---|
| `detector/backtest/population.py` | Modify | Add `series: OHLCSeries` to `Stage6Population`; return the exact input object. |
| `detector/evaluation/direction.py` | Modify | Accept `Stage6Population`; validate its exact series identity against evidence and retain private single-candidate plus batch logic. |
| `detector/tests/test_direction_evaluation.py` | Modify | Replace loose-candidate fixtures with producer populations; add manufactured sequence and cross-series fail-closed cases. |
| `detector/tests/test_backtest_population.py` | Modify | Assert result retains the input series object and direct fill handoff remains unchanged. |
| `detector/.importlinter`, `detector/tests/test_fitness_imports.py` | Modify only if required | Keep forbidden outcome/research edges; do not prohibit the intended evaluation→population edge. |

## Contracts and Exact TDD Fix Instructions

1. RED: change evaluation tests to call `evaluate_direction_policies(population, evidence)`. Assert a population built from series A labels; evidence for equal-valued series B raises `CandidateProvenanceError`; a loose sequence is rejected by the public contract (no compatibility overload).
2. GREEN: add `series: OHLCSeries` to frozen `Stage6Population` and set it to the exact `ltf_series` object. Do not add series/instrument/timeframe to `Candidate`, hashes, registries, or serializers.
3. GREEN: change the evaluator signature to `(population: Stage6Population, evidence: DirectionEvidence)`. Validate `population.series is evidence.series`, M15/instrument, candidate bounds, and duplicates before rows. Factor only the existing per-candidate P1→P4 construction into a private pure helper; the batch adapter owns validation/order.
4. RED/GREEN: prove candidate membership, 4N/order, P1–P4, K−1, isolation, and direct fill handoff are unchanged; prove cross-series and manufactured-candidate input fail closed. Keep all fixtures synthetic.
5. Run focused pytest and import-linter. Do not modify `simulate()` behavior, policy code, canonical amendment, or outcome-facing modules.

## Test Derivation

| Requirement | Test |
|---|---|
| REQ-02, -04, -11 | Only producer result is accepted; exact source/evidence object mismatch and loose/manufactured candidates abort. |
| REQ-03, -05–10, -13 | Retain K−1, total relation, 4N/order, duplicate, bounds, immutability, and non-mutation tests through population input. |
| REQ-12, -14 | Import Linter/AST checks preserve the outcome and research firewall; no runner/statistics surface. |
| Existing backtest behavior | Simulation tests keep direct population-to-fill handoff and existing fill/exit outcomes. |

## Migration / Rollout

No migration or rollout; this is an internal evaluation API correction.

## External Assumptions

`external_assumptions: none — repository-local contract; no external system, real data, or outcome claim is involved.`

## Open Questions

None. Existing signed requirements already require canonical population and identical-series fail-closed provenance; no spec refinement is needed.
