# Status close-out - `crt-detector-direction-policy-evaluation-seam`

**Status**: implementation verified and committed; formal closeout recorded. Seam V1 experimental semantics are frozen. SDD archive has not run.

- spec commit: `6104343488cc0dd6df7b4d311dc2cdf6893f2ccb`
- implementation commit: `26d94be6eed49d1883f1454d2ceea0bc0e80b4ac`

Final gates:

- DirectionPolicy: 194 passed.
- Evaluation, population, simulation, and fitness: 71 passed.
- Full suite: 606 passed, with one known **PREEXISTING / UNRELATED / NON-BLOCKING** failure: `test_alignment_detection_has_no_lookahead`.
- Import Linter: 47 files, 108 dependencies, 4 contracts kept, 0 broken.

Canonical Amendment receipt:

- path: `detector/research/direction_policy_discovery_v1_amendment_1.json`
- commit: `f542924ea4280af384b298e6fc4b54dfb54a33e6`
- SHA-256: `47b17d7891f6f9a2d2d30f83df88b060840a895484a78e763c8f46da1ea8de4d`
- size: 7737 bytes

`Stage6Population` is the canonical policy-independent EP-C stage-6 boundary before fill. For each eligible `Candidate`, `K = retest_index`; policy evidence is bounded at `K-1`, Bias is exactly at `K-1`, and Order Flow is limited to confirmation indices `<= K-1`.

The fixed policy IDs, in P1-P4 order, are:

```text
P1 direction_policy_structural_priority_v1
P2 direction_policy_corroboration_v1
P3 direction_policy_noncontradiction_v1
P4 direction_policy_bias_veto_v1
```

Each eligible `Candidate` appears exactly once under each policy, so `N` candidates produce `4N` evaluations. Relations are exactly `ALIGNED`, `OPPOSED`, or `UNRESOLVED`. Execution and fill behavior are unchanged.

`DirectionEvaluation` is outcome-free measurement. `DirectionPolicy` is not trade permission. `OPPOSED` does not mean reverse, and `UNRESOLVED` does not mean skip.

The outcome firewall remains intact: **NO OUTCOMES INSPECTED**.

The corrected audit history is preserved. Audit detected a tautological relation property and replaced it with an independent oracle over the public API. A temporary production mutation proved the corrected property was sensitive, then was reverted. This was a test defect, not a production bug. Historical verification reports retain the original finding and their correction addenda.

No real history, discovery run, prevalence, MeanR, EST-B, WR, PF, bootstrap, nomination, or Line A inspection occurred. No policy is nominated.

Next work only: **DirectionPolicy statistical runner design**. DESIGN ONLY FIRST.
