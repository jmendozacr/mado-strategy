# Formal Spec — DirectionPolicy Statistical Runner V1 (Line B / Policy Layer)

**Change**: `crt-detector-direction-policy-statistical-runner` · **Version**: V1 · **Status**: SPEC ONLY — NOT IMPLEMENTED — NO OUTCOMES INSPECTED
**Nature**: freezes HOW the already-preregistered DirectionPolicy Discovery experiment will be measured, joined, clustered, bootstrapped, and nominated. No outcome, backtest, prevalence, EST-B value, WR, PF, or performance claim appears anywhere in this document, by construction. This document is sufficient by itself to implement the runner — it does not depend on any chat transcript or Engram summary for normative text.

This is Line B (engineering/statistics layer) work, consuming the already-frozen `DirectionEvaluation` outcome-free evaluation seam and the already-frozen `Trade`/outcome layer, without altering either. Predecessor artefacts (Engram): `sdd/crt-detector/policy-layer-v1/direction-policy-statistical-runner-design` (design pass), `sdd/crt-detector/policy-layer-v1/direction-policy-statistical-runner-spec` (this spec's handoff pointer). Frozen predecessors this spec consumes without modification:

- Evaluation seam: spec commit `6104343488cc0dd6df7b4d311dc2cdf6893f2ccb`, implementation commit `26d94be6eed49d1883f1454d2ceea0bc0e80b4ac`, closeout commit `7775a25c011254555c74021e83a4dad044700d83`.
- DirectionPolicy P1–P4: spec commit `13184cbf0329f25c242e9632409194e4d052648a`, implementation commit `7b09c31877a5e5978e10b6832f5b7f3010276f1d`.
- Canonical Amendment: `detector/research/direction_policy_discovery_v1_amendment_1.json`, commit `f542924ea4280af384b298e6fc4b54dfb54a33e6`, SHA-256 `47b17d7891f6f9a2d2d30f83df88b060840a895484a78e763c8f46da1ea8de4d`, 7737 bytes.

## Provenance taxonomy in force

| Tag | Meaning |
|---|---|
| `PREREGISTERED PROTOCOL` | Stated byte-for-byte in the canonical Amendment JSON. We do not choose it, we transcribe it. |
| `HUMAN DECISION` | A choice explicitly made by the user in this or a prior session, resolving something the protocol left open. |
| `ENGINEERING DECISION` | A choice made by us to close an implementation gap the protocol does not address, constrained by (never overriding) any `PREREGISTERED PROTOCOL` or `HUMAN DECISION` item. |
| `REPO CONVENTION` | Mirrors an existing repo-wide contract (import-linter layering, naming, error-type style). |

Zero rules in this spec carry `MENTORSHIP` — this is pure statistics/engineering, not CRT/ICT domain content.

---

## A. Canonical Candidate identity vs. operational Trade join key

**This section is the reason for this hardening pass. Read it before any other section.**

The canonical Amendment freezes the Candidate identity as a 4-tuple (`population.key`):

```python
@dataclass(frozen=True)
class CandidateIdentity:
    instrument: str
    timeframe: str      # always "15M" for this protocol
    signal_id: str
    retest_index: int
```

This is the ONLY identity `DirectionPolicyObservation.candidate_id` may carry. It MUST NOT be narrowed to `(instrument, signal_id)` anywhere in the statistical domain model — that narrowing is a *join-key* concern, not an *identity* concern, and conflating them was the defect this hardening pass corrects.

Separately, and only for the purpose of locating a `Trade` record (which carries neither `timeframe` nor `retest_index`), the adapter derives an operational join key:

```python
@dataclass(frozen=True)
class TradeJoinKey:
    instrument: str
    signal_id: str

def trade_join_key(candidate_id: CandidateIdentity) -> TradeJoinKey:
    return TradeJoinKey(instrument=candidate_id.instrument, signal_id=candidate_id.signal_id)
```

`TradeJoinKey` is a *reduction* of `CandidateIdentity`, used exclusively to look up a `Trade`. It is never stored as `candidate_id`, never substituted for `CandidateIdentity` in any manifest, report, or test fixture, and never treated as if it were the canonical identity.

- **Provenance**: `CandidateIdentity` → `PREREGISTERED PROTOCOL` (`population.key`, verbatim). `TradeJoinKey` reduction → `ENGINEERING DECISION`, constrained by (derived from, never contradicting) `CandidateIdentity`.

### Note: no 23rd requirement is created here

The requirement count stays at 22 (per the original spec's scope). This section's content hardens the wording of REQ-STAT-01, 02, 03, 19, and 20 below — it does not add a 23rd requirement.

---

## B. Outcome state semantics

```text
OutcomeState = CLOSED | OPEN | NEVER_FILLED

CLOSED:        a Trade exists whose TradeJoinKey matches; Trade.outcome ∈ {win, loss}; Trade.r_multiple != None
OPEN:          a Trade exists whose TradeJoinKey matches; Trade.outcome == "open"; Trade.r_multiple == None
NEVER_FILLED:  the Candidate exists in Stage6Population.candidates; NO Trade exists whose TradeJoinKey matches
```

`NEVER_FILLED` is a valid, expected, non-error outcome state — see Section C for the exact boundary between "no Trade found" (valid → `NEVER_FILLED`) and "join integrity broken" (invalid → `DATA QUALITY FAILURE`).

## C. The statistical observation record

```python
@dataclass(frozen=True)
class DirectionPolicyObservation:
    candidate_id: CandidateIdentity     # full 4-tuple — see Section A. NEVER the reduced TradeJoinKey.
    context_cluster_id: tuple[str, int, int, int]   # (instrument, htf_context.start_index, htf_context.end_index, htf_context.resolved_at_index)
    policy_id: str                      # one of the 4 frozen DirectionPolicy IDs
    relation: Literal["ALIGNED", "OPPOSED", "UNRESOLVED"]
    outcome_state: OutcomeState
    realized_r: float | None
```

Invariant enforced at construction, fail-closed: `realized_r is not None  ⟺  outcome_state == CLOSED`.

### Join integrity: NEVER_FILLED vs. a real failure

Both of these produce `NEVER_FILLED` (valid, expected, no error):
- The Candidate's `TradeJoinKey` maps to zero Trades because the entry order never filled (`backtest.simulate._fill_pass`'s `excluded_never_filled` population).

Both of these produce a `DATA QUALITY FAILURE` (invalid, MUST raise, never silently resolved — see Section N):
- A `DirectionEvaluation` row references a `signal_id`/`CandidateIdentity` that cannot be reconciled against `Stage6Population.candidates` for the same run (upstream integrity break between the evaluation seam and the population it was built from).
- A single `TradeJoinKey` maps to more than one distinct `CandidateIdentity` within the run (ambiguous join — see Section D).
- A single `TradeJoinKey` maps to more than one `Trade` (duplicate join).

The absence of a Trade is never, by itself, evidence of a data-quality problem — it is the defining condition of `NEVER_FILLED`.

## D. Deterministic join contract

1. `CandidateIdentity` is read directly off `Stage6Population.candidates` (via `Candidate.signal_id`/`retest_index`) and the owning `OHLCSeries.instrument`/`.timeframe`, exactly as validated today by `evaluation.direction._validate_candidates`.
2. For each `CandidateIdentity`, derive `TradeJoinKey = (instrument, signal_id)` (Section A).
3. **Before** using any join result, the adapter MUST prove, for the whole run: `TradeJoinKey → CandidateIdentity` is a function (at most one `CandidateIdentity` per `TradeJoinKey`). If violated → `DATA QUALITY FAILURE`, no arbitrary selection.
4. Look up `Trade` by `TradeJoinKey`. Zero matches → `NEVER_FILLED`. Exactly one match → `OPEN` or `CLOSED` per `Trade.outcome`. More than one match → `DATA QUALITY FAILURE` (duplicate Candidate→Trade join).
5. Every joined `Trade` MUST map back to exactly the `CandidateIdentity` expected from step 1 — the adapter re-derives `TradeJoinKey` from the `CandidateIdentity` it started with and asserts the `Trade` it retrieves reports the same `signal_id`; a mismatch is a `DATA QUALITY FAILURE`, not a silent correction.

---

## E. Canonical statistical contract (unchanged from the design pass — reference only)

### EST-B
```text
EST-B(P) = mean(realized_r | policy=P, outcome_state=CLOSED, relation=ALIGNED)
         - mean(realized_r | policy=P, outcome_state=CLOSED, relation=OPPOSED)
```
Unweighted arithmetic mean, no trimming/winsorizing/weighting. `UNRESOLVED` excluded from numerator/denominator, reported separately (N/share/MeanR/WR). If `closed_ALIGNED == 0` or `closed_OPPOSED == 0` on the observed sample → `EST-B = NOT ESTIMABLE` (explicit typed state, never `0R`/silently-propagated `NaN`/`±inf`).

### MEI
`+0.20R` — minimum economically meaningful directional discrimination. NOT a capturable-return promise, NOT trade permission, NOT expected uplift.

### Context cluster identity
`context_cluster_id = (instrument, htf_context.start_index, htf_context.end_index, htf_context.resolved_at_index)`. Reconstructed by re-running `alignment.htf_ltf.tag_alignment()` with the identical series+config used to build the `Stage6Population` under evaluation, joined by `signal_id` — provenance reconstruction, never a recomputation of `DirectionPolicy`.

### U-1 — bootstrap cluster universe (HUMAN DECISION, frozen)
Per instrument, the bootstrap universe is every distinct `context_cluster_id` containing **at least one CLOSED observation**. A cluster containing only OPEN and/or NEVER_FILLED observations is excluded from the universe but remains available for descriptive reporting. Within an eligible (sampled) cluster, only its CLOSED observations feed EST-B/bootstrap; OPEN/NEVER_FILLED rows in that same cluster are never imputed as 0R.

### Bootstrap algorithm
```text
algorithm:    paired instrument-stratified HTF-context cluster bootstrap
replicates:   10,000
RNG:          numpy.random.Generator(PCG64(SeedSequence([20260910])))
numpy:        2.5.2
sampling:     per replicate, per instrument (fixed order EURUSDm, GBPUSDm, DXYm):
                K = |eligible CLOSED-containing clusters for that instrument|
                draw = generator.integers(0, K, size=K, endpoint=False)   # ONE draw
                apply the SAME `draw` unchanged to P1, P2, P3, P4 (paired — no policy consumes RNG)
CI:           two-sided percentile, 98.75% per policy (95% family-wise via Bonferroni across 4 policies)
percentiles:  [0.625%, 99.375%] via numpy.percentile(values, [0.625, 99.375], method="linear")
```
The `linear` interpolation method is an `ENGINEERING DECISION` (numpy's default; the protocol pins the RNG/library to numpy but does not separately pin an interpolation method) — frozen now, not reopened by this hardening pass.

### U-2 — undefined replicate (HUMAN DECISION, frozen)
For policy P, in any of the 10,000 fixed replicates, if `closed_ALIGNED == 0 OR closed_OPPOSED == 0`, that replicate is `UNDEFINED`. If even one such replicate exists among the fixed 10,000 → `CI(P) = NOT COMPUTABLE` (the entire interval, not just that replicate). No drop, no retry, no reseed, no imputation.

### Instrument-delta guard
```text
instrument_delta(P, instrument) = mean(realized_r | P, instrument, CLOSED, ALIGNED) - mean(realized_r | P, instrument, CLOSED, OPPOSED)
```
Only a **computable** instrument delta participates in the veto (`selection.rule`'s exact wording: "no computable instrument delta <= -0.20R"). A non-computable instrument delta (empty stratum in that instrument) does not trigger the veto — this is stated directly in the canonical protocol text, not inferred.

### SEL-A nomination
```text
Policy P eligible iff ALL of:
  1. observed EST-B(P) is computable
  2. EST-B(P) point >= +0.20R
  3. CI(P) is computable AND its lower bound > 0R
  4. no COMPUTABLE instrument_delta(P, i) <= -0.20R
  5. data-quality checks (Section N) pass

Among eligible policies: rank by full-precision CI lower bound, descending.
  exactly one at the top           -> NOMINATE it
  exact tie at full precision      -> NO POLICY NOMINATED
  zero eligible                    -> NO POLICY NOMINATED
No secondary tiebreak. No threshold relaxation.
```
A policy with `CI = NOT COMPUTABLE` is automatically ineligible (fails condition 3) but still appears in reporting with point estimate (if computable), counts, coverage, stratum metrics, and an explicit `CI status = NOT COMPUTABLE`.

### Cost assumptions
`trading_cost_price = 0.0`; spread/commission/slippage unmodeled/absent. Every report MUST carry the label "frictionless label, not net economic validation" — never "net performance".

---

## F. Requirements

### REQ-STAT-01 — Observation/outcome states (HARDENED)
**Given** a Stage6 `CandidateIdentity` and its join result against `Trade` (Section D), **when** building a `DirectionPolicyObservation`, **then** `outcome_state` MUST be exactly one of `CLOSED|OPEN|NEVER_FILLED` per Section B, `candidate_id` MUST be the full `CandidateIdentity` (never the reduced `TradeJoinKey`), and `realized_r is not None ⟺ outcome_state == CLOSED`.
- **Provenance**: `ENGINEERING DECISION` (record shape), constrained by `PREREGISTERED PROTOCOL` (`population.key` defines `candidate_id`'s shape).

### REQ-STAT-02 — Deterministic join (HARDENED)
**Given** a `DirectionEvaluation` row (identity = `CandidateIdentity`) and the `Trade` population for the same run, **when** joining them, **then** the adapter MUST (a) derive `TradeJoinKey = (instrument, signal_id)` from `CandidateIdentity`, (b) prove `TradeJoinKey → CandidateIdentity` is a function for the whole run before using any join result, (c) look up `Trade` by `TradeJoinKey`, and (d) classify zero matches as `NEVER_FILLED` (valid), never as a failure. A `TradeJoinKey` mapping to more than one `CandidateIdentity`, or to more than one `Trade`, MUST raise `DATA QUALITY FAILURE` — never silently resolved.
- **Provenance**: `CandidateIdentity` → `PREREGISTERED PROTOCOL` (`population.key`). `TradeJoinKey` derivation + its fail-closed uniqueness proof + the `NEVER_FILLED`-is-not-a-failure clarification → `ENGINEERING DECISION`.

### REQ-STAT-03 — Same economic outcome across policies (HARDENED)
**Given** one Candidate C (one `CandidateIdentity`) with 4 `DirectionEvaluation` rows (one per policy), **when** joined to its outcome, **then** all 4 `DirectionPolicyObservation` rows for C MUST carry the identical `candidate_id`, `outcome_state`, and `realized_r`; only `relation` may differ across the 4 rows.
- **Provenance**: `PREREGISTERED PROTOCOL` (4N invariant, evaluation seam) + `ENGINEERING DECISION` (this follows mechanically once `candidate_id` is the full `CandidateIdentity`, since one `CandidateIdentity` yields exactly one join result).

### REQ-STAT-04 — CLOSED eligibility
**Given** a joined `Trade`, **when** `outcome ∈ {win, loss}`, **then** it is `CLOSED` and its `r_multiple` enters EST-B computation; **when** `outcome == "open"` or no `Trade` exists for the `TradeJoinKey`, **then** it is excluded from EST-B and reported separately as `OPEN`/`NEVER_FILLED` respectively.
- **Provenance**: `PREREGISTERED PROTOCOL` (`selection.primary_estimand`, "closed MeanR") + engineering audit of `backtest/metrics.py::compute_metrics`.

### REQ-STAT-05 — EST-B arithmetic
**Given** CLOSED observations for policy P, **when** computing `EST-B(P)`, **then** it MUST equal the unweighted arithmetic mean of `realized_r` where `relation=ALIGNED` minus the same where `relation=OPPOSED`, with no trimming/winsorizing/weighting.
- **Provenance**: `PREREGISTERED PROTOCOL` (`selection.primary_estimand`).

### REQ-STAT-06 — UNRESOLVED exclusion/reporting
**Given** observations with `relation=UNRESOLVED`, **when** computing EST-B, **then** they MUST be excluded from numerator/denominator; **when** reporting, **then** they MUST appear as their own stratum (N/share/MeanR/WR), never imputed as 0R/loss/skip.
- **Provenance**: `PREREGISTERED PROTOCOL` (`selection.reporting`).

### REQ-STAT-07 — Cluster identity
**Given** a CLOSED observation, **when** assigning `context_cluster_id`, **then** it MUST equal `(instrument, htf_context.start_index, htf_context.end_index, htf_context.resolved_at_index)`, reconstructed via `tag_alignment()` re-run with the frozen series+config, joined by `signal_id`.
- **Provenance**: `PREREGISTERED PROTOCOL` (`selection.cluster_key`).

### REQ-STAT-08 — Closed-containing cluster universe (U-1)
**Given** the per-instrument set of clusters, **when** building the bootstrap universe, **then** it MUST include exactly the clusters containing ≥1 CLOSED observation; OPEN-only and NEVER_FILLED-only clusters MUST be excluded from the universe but retained for descriptive reporting.
- **Provenance**: `HUMAN DECISION` (this pass' predecessor session, confirmed unreopened here).

### REQ-STAT-09 — Instrument-stratified paired resampling
**Given** a bootstrap replicate, **when** drawing cluster indices, **then** sampling MUST occur independently per instrument stratum, and the SAME drawn indices MUST be applied unchanged to all 4 policies within that replicate.
- **Provenance**: `PREREGISTERED PROTOCOL` (`bootstrap.sampling`, `bootstrap.paired`).

### REQ-STAT-10 — Frozen RNG/replicates
**Given** any real bootstrap execution, **when** drawing replicate samples, **then** it MUST use exactly `numpy.random.Generator(PCG64(SeedSequence([20260910])))`, numpy 2.5.2, 10,000 replicates — none of which may change after outcomes are known.
- **Provenance**: `PREREGISTERED PROTOCOL` (`bootstrap.prng`, `bootstrap.replicates`).

### REQ-STAT-11 — Undefined replicate fail-closed (U-2)
**Given** a policy P and a replicate where `closed_ALIGNED == 0 OR closed_OPPOSED == 0`, **when** that replicate is aggregated into the CI, **then** its contribution is `UNDEFINED`, and the presence of even one such replicate among the fixed 10,000 MUST make `CI(P) = NOT COMPUTABLE` — no drop/retry/reseed/impute.
- **Provenance**: `HUMAN DECISION` (this pass' predecessor session, confirmed unreopened here) + `PREREGISTERED PROTOCOL` (`bootstrap.undefined`, "no imputation").

### REQ-STAT-12 — Simultaneous CI
**Given** 10,000 valid replicate EST-B values for policy P, **when** deriving its confidence interval, **then** the CI MUST be the two-sided `[0.625%, 99.375%]` percentile interval (linear interpolation, `numpy.percentile` default), giving 98.75% per-policy / 95% family-wise across the 4 policies (Bonferroni).
- **Provenance**: `PREREGISTERED PROTOCOL` (`bootstrap.ci`) + `ENGINEERING DECISION` (interpolation method — frozen, not reopened by this pass).

### REQ-STAT-13 — MEI
**Given** an EST-B point estimate, **when** interpreting it against the MEI threshold, **then** `+0.20R` is the minimum economically meaningful directional discrimination threshold — NOT a capturable-return promise, NOT trade-eligibility, NOT expected uplift.
- **Provenance**: `PREREGISTERED PROTOCOL` (`selection.mei_r`, human decision obs #563).

### REQ-STAT-14 — Instrument delta guard
**Given** a policy P eligible on pooled EST-B, **when** checking per-instrument deltas, **then** nomination MUST fail if any COMPUTABLE `instrument_delta(P, i) <= -0.20R`; a non-computable instrument delta (empty stratum) MUST NOT trigger this guard.
- **Provenance**: `PREREGISTERED PROTOCOL` (`selection.rule`, "computable" qualifier — resolved directly from the canonical text, not inferred).

### REQ-STAT-15 — Nomination/ranking
**Given** the set of eligible policies, **when** ranking them for nomination, **then** ranking MUST use each policy's full-precision CI lower bound, descending, with no rounding before comparison.
- **Provenance**: `PREREGISTERED PROTOCOL` (`selection.rule`, "rank full-precision lower bound").

### REQ-STAT-16 — Tie behavior
**Given** two or more eligible policies, **when** their full-precision ranking value is an exact tie, **then** the result MUST be `NO POLICY NOMINATED` — no secondary tiebreak, no discretionary pick.
- **Provenance**: `PREREGISTERED PROTOCOL` (`selection.rule`, "exact tie ... => NO POLICY NOMINATED").

### REQ-STAT-17 — NO POLICY NOMINATED
**Given** the nomination process, **when** zero policies are eligible, the ranking is undefined, or any quality-check fails, **then** the result MUST be `NO POLICY NOMINATED` — never a relaxed threshold, never an optional-stopping "collect more data" branch.
- **Provenance**: `PREREGISTERED PROTOCOL` (`selection.rule`).

### REQ-STAT-18 — Costs/report label
**Given** any EST-B/policy summary artifact, **when** it is produced, **then** it MUST carry the label "frictionless label, not net economic validation" and state `trading_cost_price=0.0`, spread/commission/slippage unmodeled — never presented as net strategy performance.
- **Provenance**: `PREREGISTERED PROTOCOL` (`selection.costs`).

### REQ-STAT-19 — Manifest/provenance (HARDENED)
**Given** any real run, **when** it is initiated, **then** a manifest MUST be persisted before computation, containing (at minimum) `experiment_id`, `protocol_artifact_path`+SHA-256, `direction_policy_implementation_commit`, the 3 evaluation-seam commits (spec/impl/closeout), `policy_ids`, `dataset_identity`+file hashes, `population_definition_ref`, the join rule expressed as BOTH `CandidateIdentity`'s shape (`instrument, timeframe, signal_id, retest_index`) AND the `TradeJoinKey` reduction (`instrument, signal_id`) — named distinctly, never merged into one field — `outcome_field`, `est_b_definition`, `mei_r=0.20`, `cluster_definition_ref`, the full bootstrap config, `nomination_rule_ref`, and `cost_assumptions`. Reproducibility fingerprints (protocol SHA-256, all relevant commits, manifest SHA-256, dataset hashes, numpy version) MUST be logged with any result. No outcome-derived fields belong in the manifest.
- **Provenance**: `ENGINEERING DECISION`, with the `CandidateIdentity`/`TradeJoinKey` field-separation constrained by Section A.

### REQ-STAT-20 — Data-quality fail-closed (HARDENED)
**Given** any condition in Section N's table — including a `TradeJoinKey` resolving to more than one `CandidateIdentity`, or a `DirectionEvaluation` row unreconcilable against `Stage6Population` — **when** it is detected, **then** the run MUST abort with a typed error before any statistic is computed. A joined `Candidate` with zero matching `Trade` records (→ `NEVER_FILLED`) is explicitly EXCLUDED from this table — it is a valid outcome state (Section B/C), never an error.
- **Provenance**: `PREREGISTERED PROTOCOL` (`data_quality_fail_closed`) + `ENGINEERING DECISION` (the `NEVER_FILLED`-is-not-a-failure clarification, this hardening pass).

### REQ-STAT-21 — No policy/evaluation recomputation
**Given** frozen `DirectionEvaluation` rows, **when** the statistical layer consumes them, **then** it MUST use them as-is — it MUST NOT recompute `DirectionPolicy` decisions, alter `ALIGNED`/`OPPOSED`/`UNRESOLVED`, drop `UNRESOLVED`, or change Candidate identity/K−1 cutoff.
- **Provenance**: `PREREGISTERED PROTOCOL` + evaluation seam freeze (closeout commit `7775a25`).

### REQ-STAT-22 — Outcome access boundary / Layer-1 purity
**Given** the statistics core (Layer 1), **when** it is implemented, **then** it MUST accept only in-memory `DirectionPolicyObservation` records and MUST NOT import any filesystem/CSV/dataset-loading code; real-data access MUST be isolated to the Layer-2 adapter's entrypoint path only.
- **Provenance**: `ENGINEERING DECISION` (Section G) + `REPO CONVENTION` (existing `.importlinter` firewall contracts, Section G).

---

## G. Architecture / import boundaries

New top-level package (name TBD at implementation time — not frozen by this spec), never placed under `research/`. Three layers:

```text
Layer 1 — pure statistical core (zero filesystem/data-loading imports):
    stratify, compute_est_b, bootstrap_est_b, compute_instrument_deltas, nominate
    operates ONLY on DirectionPolicyObservation records (Section C)

Layer 2 — thin experiment adapter:
    load frozen inputs, execute the join (Section D), reconstruct htf_context (Section E),
    build DirectionPolicyObservation rows, validate manifest/provenance (REQ-STAT-19)

Layer 3 — entrypoint/runner (future, not part of this spec's scope)
```

This placement is forced, not chosen for taste: `detector/.importlinter` already enforces `evaluation-outcome-firewall` (forbidding `evaluation` from importing `backtest.simulate`/`backtest.metrics`/`backtest.levels`/`research`) and `no-policy-in-research` (forbidding `research` from importing `policy`/`evaluation`). A package needing to read BOTH `evaluation` and `backtest.simulate`/`metrics` cannot live under `research/` without violating the second contract. `.importlinter` gains a new root package plus a `forbidden` contract (neither `evaluation` nor `backtest` may import the new package) at implementation time — not part of this spec pass.

## H. Result artifact schema (design, non-normative reference)

```text
Manifest            — Section REQ-STAT-19, persisted before computation
Policy summary       — per policy: universe N, CLOSED/OPEN/NEVER_FILLED N,
                        ALIGNED/OPPOSED/UNRESOLVED N+share, MeanR/WR per relation,
                        EST-B point + CI + computability, instrument EST-B deltas,
                        eligibility status. PF = N/A always (never calculated).
Bootstrap summary    — replicate count, seed, percentile bounds, computability status.
                        NOT all 10,000 raw replicate values by default.
Nomination decision  — eligible policies, ineligibility reasons, ranking values,
                        tie status, nominee or NO POLICY NOMINATED.
```
The joined `DirectionPolicyObservation` table is NOT persisted long-term by default — deterministically regenerable from the frozen manifest inputs.

## I. Deferred (explicitly out of scope)

Runner implementation · statistics core code · adapter code · CLI entrypoint · `.importlinter` update · package naming · real dataset access · real EP-C execution · real EST-B/prevalence/nomination · DOLPolicy · KeyLevelPolicy · orchestration · strategy-level trade permission.

## J. Sign-off

**SPEC ONLY. NOT IMPLEMENTED. NO OUTCOMES INSPECTED.** This hardening pass corrects one structural defect from the prior spec draft (conflating `CandidateIdentity` with the operational `TradeJoinKey`) and makes this document independently sufficient to implement the runner without consulting any chat transcript. All prior statistical decisions (U-1, U-2, EST-B, CI, SEL-A, cluster semantics, SR-A architecture) remain approved and unchanged by this pass.

**22 normative requirements: REQ-STAT-01 through REQ-STAT-22, all present in full above.**
