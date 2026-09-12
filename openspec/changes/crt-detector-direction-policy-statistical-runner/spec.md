# Formal Spec — DirectionPolicy Statistical Runner V1 (Line B / Policy Layer)

**Change**: `crt-detector-direction-policy-statistical-runner` · **Version**: V3 (amends V2, commit `6b48374ec9fa513897d050b7114a9f313f3d1b65`; V2 amends V1, commit `dc8af7daa6f8ff9f51abf2b94e7604f28ec53658`) · **Status**: SPEC ONLY — NOT IMPLEMENTED — NO OUTCOMES INSPECTED
**Nature**: freezes HOW the already-preregistered DirectionPolicy Discovery experiment will be measured, joined, clustered, bootstrapped, and nominated. No outcome, backtest, prevalence, EST-B value, WR, PF, or performance claim appears anywhere in this document, by construction. This document is sufficient by itself to implement the runner — it does not depend on any chat transcript or Engram summary for normative text.

**V2 amendment scope**: V1 left WR's outcome source unspecified relative to `realized_r`. Auditing this repo's own `backtest/metrics.py::compute_metrics` convention (win rate always derives from the categorical `Trade.outcome`, never from `r_multiple`'s sign) surfaced this as a pre-implementation, pre-outcome gap during Layer-1 engineering — no real outcome was inspected to find it. V2 freezes `closed_outcome` (Section C/C2) as an independent categorical field, amends REQ-STAT-01/04/06/19 in place, and corrects a dangling cross-reference in REQ-STAT-20. Nothing else changes: EST-B, MEI, U-1/U-2, bootstrap, RNG, CI, and SEL-A are UNCHANGED and NOT reopened by V2.

**V3 amendment scope (this pass)**: freezes the Layer-2 adapter contract (Stage6Population + DirectionEvaluation + Trade + HTF alignment + manifest → `DirectionPolicyObservation[]`), following a design-only audit of the real upstream code. Adds REQ-STAT-23 through REQ-STAT-33 (Section F), five new sections K–O (below), and corrects one finding from that same design pass that turned out to be wrong on closer inspection (Section K) — Layer-2 does NOT need new provenance-preserving machinery; `tag_alignment()`'s `signal_id → htf_context` mapping is proven a function by construction (that earlier claim is SUPERSEDED BY CODE AUDIT). V3 also transcribes, verbatim, the full `data_quality_fail_closed` list from the canonical Amendment JSON — only 3 of its 12 preregistered conditions had made it into V1/V2's normative text (Section M) — and resolves REQ-STAT-29's candidate-cutoff timestamp semantics (Candidate event = `retest_index` = K, strict `<` boundary, naive-UTC comparison per this repo's own established timestamp convention), leaving zero `HUMAN DECISION REQUIRED` items in the finished V3 pass. Nothing in Layer-1 (EST-B, WR, MEI, U-1/U-2, bootstrap, RNG, CI, SEL-A, `detector/selection/`) is reopened by this pass.

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

`Trade.outcome`'s `win`/`loss` value for a CLOSED row is preserved verbatim into the statistical observation as `closed_outcome` (Section C2) — a categorical field, independent of `realized_r`'s sign, never derived from it (V2 amendment).

## C. The statistical observation record

```python
class ClosedTradeOutcome(StrEnum):
    WIN = "win"
    LOSS = "loss"


@dataclass(frozen=True)
class DirectionPolicyObservation:
    candidate_id: CandidateIdentity     # full 4-tuple — see Section A. NEVER the reduced TradeJoinKey.
    context_cluster_id: tuple[str, int, int, int]   # (instrument, htf_context.start_index, htf_context.end_index, htf_context.resolved_at_index)
    policy_id: str                      # one of the 4 frozen DirectionPolicy IDs
    relation: Literal["ALIGNED", "OPPOSED", "UNRESOLVED"]
    outcome_state: OutcomeState
    closed_outcome: ClosedTradeOutcome | None   # V2: categorical WIN/LOSS, CLOSED-only — Section C2
    realized_r: float | None
```

Invariant enforced at construction, fail-closed:
`outcome_state == CLOSED  ⟺  realized_r is not None AND finite AND closed_outcome ∈ {WIN, LOSS}`.
Equivalently, `outcome_state != CLOSED  ⟺  realized_r is None AND closed_outcome is None` — OPEN and NEVER_FILLED never carry either field.

### Join integrity: NEVER_FILLED vs. a real failure

Both of these produce `NEVER_FILLED` (valid, expected, no error):
- The Candidate's `TradeJoinKey` maps to zero Trades because the entry order never filled (`backtest.simulate._fill_pass`'s `excluded_never_filled` population).

Both of these produce a `DATA QUALITY FAILURE` (invalid, MUST raise, never silently resolved):
- A `DirectionEvaluation` row references a `signal_id`/`CandidateIdentity` that cannot be reconciled against `Stage6Population.candidates` for the same run (upstream integrity break between the evaluation seam and the population it was built from).
- A single `TradeJoinKey` maps to more than one distinct `CandidateIdentity` within the run (ambiguous join — see Section D).
- A single `TradeJoinKey` maps to more than one `Trade` (duplicate join).

The absence of a Trade is never, by itself, evidence of a data-quality problem — it is the defining condition of `NEVER_FILLED`. This table is REQ-STAT-20's normative reference — there is no separate "Section N."

### C2. WR outcome contract (V2 amendment)

`closed_outcome` is the ONLY source of a CLOSED observation's WIN/LOSS classification. It is NEVER derived from `sign(realized_r)`, `realized_r > 0`, or any equivalent inference — WR semantics are categorical, independent of the realized-R statistic, exactly mirroring this repo's own existing convention (`backtest/metrics.py::compute_metrics` derives `win_rate` from `Trade.outcome`, never from `r_multiple`'s sign). The exact WR formula and its empty-stratum behavior are frozen in Section E.

Layer-2 mapping (documented here for the future adapter — NOT implemented by Layer-1, which only ever sees the two enum members as already-resolved input):
```text
Trade.outcome == "win"   -> closed_outcome = ClosedTradeOutcome.WIN,  outcome_state = CLOSED
Trade.outcome == "loss"  -> closed_outcome = ClosedTradeOutcome.LOSS, outcome_state = CLOSED
Trade.outcome == "open"  -> closed_outcome = None,                    outcome_state = OPEN
```

- **Provenance**: `Trade.outcome`'s `win`/`loss` value → `PREREGISTERED PROTOCOL` (the pre-existing `Trade` contract, `backtest/simulate.py`). Carrying it into `DirectionPolicyObservation` as an independent categorical field, rather than deriving WR from `realized_r`'s sign → `HUMAN DECISION` (this V2 amendment, made explicitly to prevent collapsing WR semantics into MeanR semantics).

**Note**: as with the V1 hardening pass (Section A), this amendment does not add a 23rd requirement — it hardens the wording of REQ-STAT-01, 04, 06, 19, and 20 (Section F).

## D. Deterministic join contract

1. `CandidateIdentity` is read directly off `Stage6Population.candidates` (via `Candidate.signal_id`/`retest_index`) and the owning `OHLCSeries.instrument`/`.timeframe`, exactly as validated today by `evaluation.direction._validate_candidates`.
2. For each `CandidateIdentity`, derive `TradeJoinKey = (instrument, signal_id)` (Section A).
3. **Before** using any join result, the adapter MUST prove, for the whole run: `TradeJoinKey → CandidateIdentity` is a function (at most one `CandidateIdentity` per `TradeJoinKey`). If violated → `DATA QUALITY FAILURE`, no arbitrary selection.
4. Look up `Trade` by `TradeJoinKey`. Zero matches → `NEVER_FILLED`. Exactly one match → `OPEN` or `CLOSED` per `Trade.outcome`, and for a `CLOSED` result `Trade.outcome`'s `win`/`loss` value is carried forward as `closed_outcome` (Section C2) — never re-derived from `r_multiple`. More than one match → `DATA QUALITY FAILURE` (duplicate Candidate→Trade join).
5. Every joined `Trade` MUST map back to exactly the `CandidateIdentity` expected from step 1 — the adapter re-derives `TradeJoinKey` from the `CandidateIdentity` it started with and asserts the `Trade` it retrieves reports the same `signal_id`; a mismatch is a `DATA QUALITY FAILURE`, not a silent correction.

---

## E. Canonical statistical contract (unchanged from the design pass — reference only)

### EST-B
```text
EST-B(P) = mean(realized_r | policy=P, outcome_state=CLOSED, relation=ALIGNED)
         - mean(realized_r | policy=P, outcome_state=CLOSED, relation=OPPOSED)
```
Unweighted arithmetic mean, no trimming/winsorizing/weighting. `UNRESOLVED` excluded from numerator/denominator, reported separately (N/share/MeanR/WR). If `closed_ALIGNED == 0` or `closed_OPPOSED == 0` on the observed sample → `EST-B = NOT ESTIMABLE` (explicit typed state, never `0R`/silently-propagated `NaN`/`±inf`).

### WR (categorical win rate, V2 amendment)
```text
WR(stratum) = count(realized_r | policy=P, outcome_state=CLOSED, relation=<stratum>, closed_outcome=WIN)
            / count(realized_r | policy=P, outcome_state=CLOSED, relation=<stratum>)
```
Computed independently for each of the three CLOSED relation strata (ALIGNED, OPPOSED, UNRESOLVED). Every CLOSED observation carries exactly one of `{WIN, LOSS}` (Section C invariant), so the denominator is simply that stratum's CLOSED count — no separate WIN+LOSS reconciliation is needed. If a stratum's CLOSED count is 0 → `WR = NOT ESTIMABLE` (the same explicit typed state EST-B uses on an empty stratum — never `0%`, `NaN`, or `±inf`). OPEN and NEVER_FILLED never enter this denominator, exactly as they never enter EST-B's. WR reads `closed_outcome` only; it is never derived from `realized_r`'s sign (Section C2).

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
  5. data-quality checks (Section C's join-integrity table, REQ-STAT-20) pass

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

### REQ-STAT-01 — Observation/outcome states (HARDENED, V2)
**Given** a Stage6 `CandidateIdentity` and its join result against `Trade` (Section D), **when** building a `DirectionPolicyObservation`, **then** `outcome_state` MUST be exactly one of `CLOSED|OPEN|NEVER_FILLED` per Section B, `candidate_id` MUST be the full `CandidateIdentity` (never the reduced `TradeJoinKey`), and `outcome_state == CLOSED ⟺ realized_r is not None AND finite AND closed_outcome ∈ {WIN, LOSS}` (V2: `closed_outcome` added, Section C/C2) — `closed_outcome` MUST be `None` whenever `outcome_state != CLOSED`.
- **Provenance**: `ENGINEERING DECISION` (record shape), constrained by `PREREGISTERED PROTOCOL` (`population.key` defines `candidate_id`'s shape; `Trade.outcome`'s win/loss values define `closed_outcome`'s domain, V2).

### REQ-STAT-02 — Deterministic join (HARDENED)
**Given** a `DirectionEvaluation` row (identity = `CandidateIdentity`) and the `Trade` population for the same run, **when** joining them, **then** the adapter MUST (a) derive `TradeJoinKey = (instrument, signal_id)` from `CandidateIdentity`, (b) prove `TradeJoinKey → CandidateIdentity` is a function for the whole run before using any join result, (c) look up `Trade` by `TradeJoinKey`, and (d) classify zero matches as `NEVER_FILLED` (valid), never as a failure. A `TradeJoinKey` mapping to more than one `CandidateIdentity`, or to more than one `Trade`, MUST raise `DATA QUALITY FAILURE` — never silently resolved.
- **Provenance**: `CandidateIdentity` → `PREREGISTERED PROTOCOL` (`population.key`). `TradeJoinKey` derivation + its fail-closed uniqueness proof + the `NEVER_FILLED`-is-not-a-failure clarification → `ENGINEERING DECISION`.

### REQ-STAT-03 — Same economic outcome across policies (HARDENED)
**Given** one Candidate C (one `CandidateIdentity`) with 4 `DirectionEvaluation` rows (one per policy), **when** joined to its outcome, **then** all 4 `DirectionPolicyObservation` rows for C MUST carry the identical `candidate_id`, `outcome_state`, and `realized_r`; only `relation` may differ across the 4 rows.
- **Provenance**: `PREREGISTERED PROTOCOL` (4N invariant, evaluation seam) + `ENGINEERING DECISION` (this follows mechanically once `candidate_id` is the full `CandidateIdentity`, since one `CandidateIdentity` yields exactly one join result).

### REQ-STAT-04 — CLOSED eligibility (V2)
**Given** a joined `Trade`, **when** `outcome ∈ {win, loss}`, **then** it is `CLOSED`, its `r_multiple` enters EST-B computation, and its categorical `outcome` value is carried forward as `closed_outcome` for WR (Section C2/E) — independently, never derived from `r_multiple`'s sign; **when** `outcome == "open"` or no `Trade` exists for the `TradeJoinKey`, **then** it is excluded from both EST-B and WR and reported separately as `OPEN`/`NEVER_FILLED` respectively.
- **Provenance**: `PREREGISTERED PROTOCOL` (`selection.primary_estimand`, "closed MeanR"; `Trade.outcome`'s existing win/loss contract) + engineering audit of `backtest/metrics.py::compute_metrics` (V2: confirms WR's categorical precedent).

### REQ-STAT-05 — EST-B arithmetic
**Given** CLOSED observations for policy P, **when** computing `EST-B(P)`, **then** it MUST equal the unweighted arithmetic mean of `realized_r` where `relation=ALIGNED` minus the same where `relation=OPPOSED`, with no trimming/winsorizing/weighting.
- **Provenance**: `PREREGISTERED PROTOCOL` (`selection.primary_estimand`).

### REQ-STAT-06 — UNRESOLVED exclusion/reporting (V2)
**Given** observations with `relation=UNRESOLVED`, **when** computing EST-B, **then** they MUST be excluded from numerator/denominator; **when** reporting, **then** they MUST appear as their own stratum with N/share/MeanR/WR (WR per Section E, computed over that stratum's CLOSED∩UNRESOLVED observations only), never imputed as 0R/loss/skip/0%.
- **Provenance**: `PREREGISTERED PROTOCOL` (`selection.reporting`); WR formula → V2 amendment (Section C2/E).

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
**Given** any real run, **when** it is initiated, **then** a manifest MUST be persisted before computation, containing (at minimum) `experiment_id`, `protocol_artifact_path`+SHA-256, `direction_policy_implementation_commit`, the 3 evaluation-seam commits (spec/impl/closeout), `policy_ids`, `dataset_identity`+file hashes, `population_definition_ref`, the join rule expressed as BOTH `CandidateIdentity`'s shape (`instrument, timeframe, signal_id, retest_index`) AND the `TradeJoinKey` reduction (`instrument, signal_id`) — named distinctly, never merged into one field — `outcome_field` (covering both `realized_r` and, from V2, `closed_outcome`), `est_b_definition`, `mei_r=0.20`, `cluster_definition_ref`, the full bootstrap config, `nomination_rule_ref`, and `cost_assumptions`. Reproducibility fingerprints (protocol SHA-256, all relevant commits, manifest SHA-256, dataset hashes, numpy version) MUST be logged with any result. No outcome-derived fields belong in the manifest.
- **Provenance**: `ENGINEERING DECISION`, with the `CandidateIdentity`/`TradeJoinKey` field-separation constrained by Section A, and `outcome_field`'s dual coverage constrained by Section C2 (V2).

### REQ-STAT-20 — Data-quality fail-closed (HARDENED, V2: reference corrected)
**Given** any condition in Section C's join-integrity table — a `DirectionEvaluation` row unreconcilable against `Stage6Population`, a `TradeJoinKey` resolving to more than one `CandidateIdentity`, or a `TradeJoinKey` resolving to more than one `Trade` — **when** it is detected, **then** the run MUST abort with a typed error before any statistic is computed. A joined `Candidate` with zero matching `Trade` records (→ `NEVER_FILLED`) is explicitly EXCLUDED from this table — it is a valid outcome state (Section B/C), never an error.
- **Provenance**: `PREREGISTERED PROTOCOL` (`data_quality_fail_closed`) + `ENGINEERING DECISION` (the `NEVER_FILLED`-is-not-a-failure clarification, V1 hardening pass; V2 corrects a dangling "Section N" cross-reference to point at Section C's actual table — no semantic change).

### REQ-STAT-21 — No policy/evaluation recomputation
**Given** frozen `DirectionEvaluation` rows, **when** the statistical layer consumes them, **then** it MUST use them as-is — it MUST NOT recompute `DirectionPolicy` decisions, alter `ALIGNED`/`OPPOSED`/`UNRESOLVED`, drop `UNRESOLVED`, or change Candidate identity/K−1 cutoff.
- **Provenance**: `PREREGISTERED PROTOCOL` + evaluation seam freeze (closeout commit `7775a25`).

### REQ-STAT-22 — Outcome access boundary / Layer-1 purity
**Given** the statistics core (Layer 1), **when** it is implemented, **then** it MUST accept only in-memory `DirectionPolicyObservation` records and MUST NOT import any filesystem/CSV/dataset-loading code; real-data access MUST be isolated to the Layer-2 adapter's entrypoint path only.
- **Provenance**: `ENGINEERING DECISION` (Section G) + `REPO CONVENTION` (existing `.importlinter` firewall contracts, Section G).

### REQ-STAT-23 — Layer-2 instrument-scoped input contract (V3)
**Given** `backtest.simulate.Trade` carries no `instrument` field (verified: `backtest/simulate.py`'s `Trade` dataclass), **when** Layer-2 accepts Trades for a run, **then** it MUST NOT accept an undifferentiated `Sequence[Trade]` — it MUST require Trades scoped per instrument (e.g. one `Stage6Population` + `DirectionEvaluation[]` + `Trade[]` + `ReconciliationReport` bundle per instrument), with `instrument` supplied by the bundle/`Stage6Population.series.instrument`, never inferred from a `Trade`.
- **Provenance**: `ENGINEERING DECISION`, forced by `Trade`'s actual shape — not a preregistered choice.

### REQ-STAT-24 — TradeJoinKey functional-dependency proof (V3)
**Given** a `TradeJoinKey`, **when** Layer-2 uses it to look up a `Trade` or `CandidateIdentity`, **then** it MUST first prove, within one instrument's run: (a) `TradeJoinKey → CandidateIdentity` is a function, (b) `TradeJoinKey → Trade` is a function (at most one `Trade` per key). Either violated → typed `TradeJoinIntegrityError`, no arbitrary selection.
- **Provenance**: `PREREGISTERED PROTOCOL` (`data_quality_fail_closed`: "duplicate Candidate→Trade join") + `ENGINEERING DECISION` (the exact two-function-proof mechanism, hardens REQ-STAT-02).

### REQ-STAT-25 — Aggregate completeness proof before NEVER_FILLED (V3)
**Given** a `Stage6Population` and its paired `ReconciliationReport` for the same instrument run, **when** Layer-2 interprets a Candidate's absence from the supplied `Trade[]` as `NEVER_FILLED`, **then** it MUST first verify `len(Stage6Population.candidates) == len(trades) + ReconciliationReport.excluded_never_filled` (proven identity: `backtest/simulate.py::_fill_pass`/`_resolve_exits`). If this fails, the supplied Trade collection is incomplete/untrustworthy — abort with a typed error; absence in an unverified collection is NEVER sufficient for `NEVER_FILLED`. `ReconciliationReport` is therefore a REQUIRED Layer-2 input, used for aggregate completeness only — never for identity-level joins (it carries no signal-level detail).
- **Provenance**: `ENGINEERING DECISION` (the exact accounting identity, derived from reading `backtest/simulate.py`) constrained by `PREREGISTERED PROTOCOL` ("open and never-filled explicit").

### REQ-STAT-26 — Independent Candidate↔DirectionEvaluation reconciliation (V3)
**Given** a `CandidateIdentity` and its `DirectionEvaluation` rows, **when** Layer-2 builds observations, **then** it MUST independently verify — never merely trust the upstream evaluation seam's own frozen invariant — that the group has exactly 4 rows, exactly one per `FROZEN_POLICY_IDS` member, and identical `(instrument, timeframe, signal_id, retest_index)` across all 4. Missing policy, duplicate policy, unexpected policy ID, or cross-row identity mismatch → typed `CandidateReconciliationError`.
- **Provenance**: `ENGINEERING DECISION` — defense-in-depth over an already-frozen seam invariant (evaluation closeout commit `7775a25`), not a new rule.

### REQ-STAT-27 — Relation mapping (V3)
**Given** `evaluation.direction.PolicyRelation` (ALIGNED/OPPOSED/UNRESOLVED) and `selection.model.Relation` (same three values, separate enum by Layer-1-purity design), **when** Layer-2 maps one to the other, **then** it MUST use an explicit, exhaustive mapping (ALIGNED→ALIGNED, OPPOSED→OPPOSED, UNRESOLVED→UNRESOLVED) — no permissive string cast. Any other value → typed error, fail closed.
- **Provenance**: `ENGINEERING DECISION` (repo convention: separate enums per layer boundary, per `.importlinter`'s `selection-layer1-purity` contract).

### REQ-STAT-28 — Cluster reconstruction is a proven function, full-series-only (V3, hardens REQ-STAT-07)
**Given** `context_cluster_id` reconstruction via `tag_alignment()` re-run, **when** joining by `signal_id`, **then** the mapping `signal_id → htf_context` MUST be treated as non-ambiguous by construction: `Model1Signal.signal_id` embeds `anchor_index` verbatim (`entries/model1.py`), and `tag_alignment()`'s `htf_context` assignment is a pure function of `anchor_index` alone (`alignment/htf_ltf.py`) — so identical `signal_id` implies identical `anchor_index` implies identical `htf_context`, always. No provenance-preserving sidecar or alternate join key is required or permitted to replace this mechanism. Layer-2 MUST NOT call `tag_alignment()` incrementally or on a truncated series — only on the complete, frozen series identical to the one that built the `Stage6Population` under evaluation (guards against the unrelated, pre-existing `test_alignment_detection_has_no_lookahead` failure, which concerns truncated-vs-full replay consistency, not this join).
- **Provenance**: `PREREGISTERED PROTOCOL` (`selection.cluster_key`) + `ENGINEERING DECISION` (the non-ambiguity proof and the full-series-only guardrail — both derived from reading `entries/model1.py`, `primitives/crt_range.py`, `alignment/htf_ltf.py`, and `cli.py::_detect_all`, not assumed).

### REQ-STAT-29 — Candidate and outcome-followup cutoffs (V3, RESOLVED)
**Given** the canonical Amendment's `dataset.candidate_cutoff_end_utc` and `dataset.outcome_followup_end_utc`, **when** Layer-2 validates a run, **then**:

(a) the Candidate's governing event timestamp is `ltf_series.candles[candidate.retest_index].timestamp` — the candle at the Candidate's retest event `K` (`population.cutoff.evaluation_event_index`: `"Candidate.retest_index = K"`, canonical Amendment) — NEVER the anchor, origin, confirmation, or fill candle. A Candidate is eligible for the discovery population **iff** that timestamp is strictly before `candidate_cutoff_end_utc` (`timestamp < candidate_cutoff_end_utc`); a timestamp equal to or after the cutoff is NOT eligible. Layer-2 MUST NOT silently filter a boundary-violating Candidate it receives — a Candidate presented to it that already violates this boundary is a frozen-population integrity failure (abort with a typed error), since Layer-2 validates the frozen boundary, it does not repair `Stage6Population` or alter Candidate generation;

(b) before any timestamp access, `0 <= candidate.retest_index < len(ltf_series.candles)` MUST hold — violation is a `DATA QUALITY FAILURE`, never Python's negative-index wraparound behavior;

(c) no Trade resolution may consume a candle timestamped after `outcome_followup_end_utc` — a Trade still unresolved at that boundary remains `OPEN`; Layer-2 MUST NOT fetch later candles to resolve it;

(d) `candidate_cutoff_end_utc` (population admission: can this Candidate exist?) and `outcome_followup_end_utc` (resolution horizon: how long may an already-eligible Candidate's Trade keep resolving?) answer two SEPARATE questions and MUST NOT be conflated — a Candidate admitted before the candidate cutoff may legitimately have its Trade resolve up to the later outcome-followup cutoff.

Both comparisons occur entirely in the LTF-series index/timestamp domain (`retest_index` is an LTF index, never compared against an HTF index). `Candle.timestamp` is a **naive** `datetime` throughout this repo — confirmed: `ingestion/loader.py::load_mt5_csv` parses via `pd.to_datetime(df["<DATE>"] + " " + df["<TIME>"], format="%Y.%m.%d %H:%M:%S")`, with no `utc=True`/`%z`, producing a naive `Timestamp`→`datetime` — representing UTC by an existing, already-established repo convention (`alignment/htf_ltf.py::_daily_close`'s own docstring: "Daily bars are UTC-daily per the confirmed broker-is-UTC+0 finding"). The frozen cutoff strings (`"...Z"`, explicit UTC) MUST be parsed to naive datetimes for comparison (drop the redundant `Z`/tzinfo marker, never attach one to either side) — comparing naive against timezone-aware, or converting to local time, is prohibited.
- **Provenance**: `PREREGISTERED PROTOCOL` (the two cutoff values; and Candidate event = `retest_index` = K, `population.cutoff.evaluation_event_index`, canonical Amendment) + `HUMAN DECISION` (the strict `<` boundary comparator — resolved pre-outcome, this V3 pass; NOT mentorship-derived) + `REPO CONVENTION` (naive `datetime` = UTC, evidenced in `alignment/htf_ltf.py`, applied here to the cutoff comparison).

### REQ-STAT-30 — Complete dataset data-quality fail-closed inventory (V3)
**Given** the canonical Amendment's `data_quality_fail_closed` array (12 conditions, verbatim), **when** any condition is detected, **then** the run MUST abort with a typed error before any statistic is computed — see Section M for the complete condition-by-condition table (canonical text, responsible layer, validation point, typed failure, synthetic-testability). Only 3 of the 12 conditions were previously transcribed into this spec (Section C's join-integrity table, REQ-STAT-02/20); V3 transcribes the remaining 9 verbatim.
- **Provenance**: `PREREGISTERED PROTOCOL` (`data_quality_fail_closed`, verbatim, Section M).

### REQ-STAT-31 — Execution baseline (V3)
**Given** the eventual first real discovery execution, **when** it is authorized, **then** it MUST be tied to one `measurement_execution_baseline_commit` — a single Git commit recorded AFTER Layer-2 and Layer-3 implementation + closeout + full measurement-instrument verification — representing the exact executable measurement system authorized for that discovery. At execution time, the enumerated protected paths (Section N) MUST match that baseline commit exactly, with no uncommitted modification to any protected path (unrelated working-tree changes outside protected paths need not abort). Historical per-component commit hashes (DirectionPolicy, evaluation seam, statistical spec V1/V2/V3, Layer-1, Layer-2, Layer-3) remain in the manifest for provenance only — they are NOT individually diffed against HEAD; the single execution-baseline commit is the authoritative final source-tree snapshot. (Corrects an earlier design-pass recommendation to diff each historical component commit's whole directory against HEAD — rejected: legitimate later commits routinely touch those same paths for unrelated reasons, as this repo's own history already demonstrates.)
- **Provenance**: `ENGINEERING DECISION` (no repo precedent existed; proposed and confirmed this session).

### REQ-STAT-32 — Manifest V3 schema (V3, extends REQ-STAT-19)
**Given** REQ-STAT-19's manifest, **when** extended for V3, **then** it MUST additionally contain: `statistical_spec_v3_commit`, `layer1_implementation_commit` (`75d9c37ac08a314a6518484b7e62ee3c7eb798c1`), `layer2_implementation_commit` and `layer3_implementation_commit` (once they exist), `measurement_execution_baseline_commit`, and `protected_paths` (definition + version, Section N). Still no outcome-derived field.
- **Provenance**: `ENGINEERING DECISION`, extending REQ-STAT-19's existing shape.

### REQ-STAT-33 — Layer-2 architecture / import boundary (V3, extends Section G)
**Given** Layer-2's need to import `evaluation`, `backtest`, `alignment`, and `selection.model`, **when** it is implemented, **then** it MUST live in a NEW top-level package — never under `selection/` (forbidden by the `selection-layer1-purity` import-linter contract, which blocks exactly those imports from anywhere under `selection.*`). A new `forbidden` import-linter contract MUST prevent the reverse direction: `evaluation`, `backtest`, `alignment`, `policy`, and `selection` MUST NOT import the new package.
- **Provenance**: `ENGINEERING DECISION` (Section O) + `REPO CONVENTION` (mirrors the existing `no-selection-in-outcome-layers` pattern).

---

## G. Architecture / import boundaries

Layer 1 lives in `detector/selection/` (frozen, committed `75d9c37ac08a314a6518484b7e62ee3c7eb798c1`). Layer 2 needs its own NEW top-level package (candidate name `adapter`, matching this section's own "thin experiment adapter" phrasing — not frozen by this spec, final spelling deferred to a repo-convention audit at implementation time, same process `selection` went through). It **cannot** live under `selection/`: the `selection-layer1-purity` import-linter contract forbids anything under `selection.*` from importing `research`/`backtest`/`evaluation`/`ingestion`, all of which Layer-2 needs. Three layers:

```text
Layer 1 — pure statistical core (zero filesystem/data-loading imports):
    stratify, compute_est_b, bootstrap_est_b, compute_instrument_deltas, nominate
    operates ONLY on DirectionPolicyObservation records (Section C)
    package: detector/selection/  [FROZEN, COMMITTED]

Layer 2 — thin experiment adapter (REQ-STAT-23..30, 33):
    instrument-scoped reconciliation (Section L), dataset/data-quality validation (Section M),
    cluster reconstruction (REQ-STAT-28), manifest/provenance validation (REQ-STAT-19/32)
    package: NEW top-level, name TBD — never under selection/

Layer 3 — entrypoint/runner + execution baseline (REQ-STAT-31, future, not part of this spec's scope)
```

This placement is forced, not chosen for taste: `detector/.importlinter` already enforces `evaluation-outcome-firewall` (forbidding `evaluation` from importing `backtest.simulate`/`backtest.metrics`/`backtest.levels`/`research`), `no-policy-in-research` (forbidding `research` from importing `policy`/`evaluation`), and (since Layer-1's freeze) `selection-layer1-purity`/`no-selection-in-outcome-layers`. `.importlinter` gains a new root package for Layer-2 plus a `forbidden` contract (REQ-STAT-33: `evaluation`/`backtest`/`alignment`/`policy`/`selection` must not import the new package) at implementation time — not part of this spec pass.

## H. Result artifact schema (design, non-normative reference)

```text
Manifest            — Section REQ-STAT-19, persisted before computation
Policy summary       — per policy: universe N, CLOSED/OPEN/NEVER_FILLED N,
                        ALIGNED/OPPOSED/UNRESOLVED N+share, MeanR/WR per relation
                        (WR formula: Section E/C2, V2), EST-B point + CI +
                        computability, instrument EST-B deltas, eligibility
                        status. PF = N/A always (never calculated).
Bootstrap summary    — replicate count, seed, percentile bounds, computability status.
                        NOT all 10,000 raw replicate values by default.
Nomination decision  — eligible policies, ineligibility reasons, ranking values,
                        tie status, nominee or NO POLICY NOMINATED.
```
The joined `DirectionPolicyObservation` table is NOT persisted long-term by default — deterministically regenerable from the frozen manifest inputs.

## I. Deferred (explicitly out of scope)

Runner implementation (Layer 3) · Layer-2 adapter code · CLI entrypoint · `.importlinter` update for the Layer-2 package · Layer-2 package naming · real dataset access · real EP-C execution · real EST-B/prevalence/nomination · DOLPolicy · KeyLevelPolicy · orchestration · strategy-level trade permission. (Layer-1 statistics core code is no longer deferred — `detector/selection/`, frozen, committed `75d9c37ac08a314a6518484b7e62ee3c7eb798c1`.)

## K. Correction: cluster reconstruction is NOT ambiguous (V3)

**Status of the predecessor finding: `SUPERSEDED BY CODE AUDIT`.** This corrects a finding from the predecessor Layer-2 design pass — read before Sections L–O. That pass concluded `signal_id → htf_context` was not provably a function, reasoning from `Model1Signal.signal_id`'s omission of `purge_target` plus a comment in `tests/property/test_no_lookahead.py` about overlapping CRT range candidates. Re-auditing the actual code that produces both sides of that mapping disproves it — CP-A/CP-B/CP-C, a provenance sidecar, and any Stage6-provenance mutation are all unnecessary; none is adopted:

1. `primitives/crt_range.py::detect_crt_ranges` iterates `for i in range(len(candles)-1)` and appends at most one `CRTRange` per `i`, so `CRTRange.start_index` is unique across the returned list — no two distinct CRT ranges share a `start_index`.
2. `entries/model1.py::_track_anchor` sets `Model1Signal.origin_index` to that same `start_index` (`purge_engulf`) or to `FVG.start_index` (`fvg_fill`); `signal_id = f"{origin_index}-{anchor_index}-{direction}-{confirmation_type}-{entry_type}"` embeds `origin_index` and `anchor_index` verbatim.
3. `alignment/htf_ltf.py::tag_alignment` computes `htf_context` as a pure function of `anchor_index` ALONE (via `ltf_series.candles[signal.anchor_index].timestamp` → `_enclosing_htf_index` → a fixed `purge_index_to_range` lookup) — it never reads `origin_index`, `confirmation_type`, `entry_type`, or `purge_target`.

Since `anchor_index` is a literal component of `signal_id`, two signals sharing `signal_id` necessarily share `anchor_index`, and therefore necessarily produce the identical `htf_context`. **`signal_id → htf_context` is a function by construction, always** — there is no ambiguous case to guard against, no sidecar provenance structure to build, and REQ-STAT-07's original method (re-run `tag_alignment()`, join by `signal_id`) is sound as originally written. The `purge_target` disambiguation the lookahead test's own `_key()` helper needs is a property of THAT test's internal comparison (which deliberately excludes `origin_index` for its own truncated-vs-full purposes) — it is not evidence about `signal_id`'s uniqueness.

What DOES survive from that design pass, unchanged: Layer-2 must still never call `tag_alignment()` incrementally/truncated (REQ-STAT-28) — that restriction guards against a real, different, pre-existing issue (the known lookahead-test failure), unrelated to this correction.

- **Provenance**: `ENGINEERING DECISION` — a corrected finding, backed by re-reading `primitives/crt_range.py`, `entries/model1.py`, and `alignment/htf_ltf.py` directly rather than inferring from a test comment.

## L. Layer-2 reconciliation contract (V3)

**Dedup source-survivor semantics** (audited, `backtest/population.py::_dedup`, unchanged EP-C behavior — documented here for completeness, not because it threatens cluster provenance per Section K): candidates are grouped by `(anchor_index, direction, entry_price, entry_type)`; within a group, the survivor is `min(group, key=lambda c: c.origin_index)` — lowest `origin_index` wins. An exact `origin_index` tie (only possible if `origin_index` numerically coincides across unrelated CRT-range/FVG origins — not observed to be structurally forced) falls back to Python's stable `min()`, i.e. first-encountered in `tag_alignment()`'s own emission order. This is existing, frozen EP-C membership logic — V3 does not change it, and (per Section K) it does not create a cluster-provenance risk: whichever candidate survives, its own `signal_id` still resolves its own correct `htf_context` unambiguously.

**Instrument-scoped input** (REQ-STAT-23): Layer-2 accepts one `Stage6Population` + `DirectionEvaluation[]` + `Trade[]` + `ReconciliationReport` bundle per instrument, with `instrument` read from `Stage6Population.series.instrument` — never inferred from a bare `Trade` (which carries none).

**TradeJoinKey proof** (REQ-STAT-24): before any lookup, prove `TradeJoinKey → CandidateIdentity` and `TradeJoinKey → Trade` are both functions within that instrument's run. Violation → `TradeJoinIntegrityError`.

**Aggregate completeness / NEVER_FILLED** (REQ-STAT-25): require `len(Stage6Population.candidates) == len(trades) + ReconciliationReport.excluded_never_filled` BEFORE trusting Trade-absence as `NEVER_FILLED`.

**Candidate↔DirectionEvaluation reconciliation** (REQ-STAT-26): independently verify exactly 4 rows, one per frozen policy ID, identical `CandidateIdentity` across all 4 — never trust the upstream seam's own invariant blindly.

**Relation mapping** (REQ-STAT-27): explicit exhaustive `evaluation.direction.PolicyRelation → selection.model.Relation` map; unexpected value fails closed.

## M. Complete dataset data-quality fail-closed inventory (V3)

The canonical Amendment's `data_quality_fail_closed` array (verbatim, 12 conditions) — only the first 3 below were previously transcribed into this spec (Section C / REQ-STAT-02/20):

| # | Canonical condition (verbatim) | Layer | Validation point | Typed failure | Synthetic-testable? |
|---|---|---|---|---|---|
| 1 | "duplicate Candidate→Trade join" | Layer-2 | TradeJoinKey proof (REQ-STAT-24) | `TradeJoinIntegrityError` | Yes |
| 2 | "open and never-filled explicit" | Layer-1 (already enforced, frozen construction invariant) + Layer-2 (must construct, never infer/hide) | `DirectionPolicyObservation.__post_init__`; Layer-2's outcome mapping (REQ-STAT-04) | `ClosedOutcomeMismatchError` (Layer-1) / mapping logic (Layer-2) | Yes |
| 3 | "non-finite R" | Layer-1 (already enforced, `OutcomeRealizedRMismatchError`) + Layer-2 (defensive check at the Trade→observation boundary, since `Trade.r_multiple` is not type-guaranteed finite) | Trade mapping (REQ-STAT-04/28-adjacent) | `TradeOutcomeContractError` (Layer-2) / `OutcomeRealizedRMismatchError` (Layer-1) | Yes |
| 4 | "duplicate candles/timestamps/keys" | Layer-2 (dataset validation) | Manifest/dataset validation, before population construction | `DatasetIntegrityError` | Yes |
| 5 | "missing files/candles" | Layer-2 (dataset validation against manifest file list) | Manifest/dataset validation | `DatasetIntegrityError` | Yes |
| 6 | "boundary gaps affecting prefix/setup/outcome" | Layer-2 (dataset validation, ties to cutoff checks) | Manifest/dataset validation + REQ-STAT-29 | `DatasetIntegrityError` | Yes |
| 7 | "impossible zero-risk R" | Layer-2 (Trade-level check) — **IMPLEMENTATION/EXECUTION CHECK**: whether `backtest.levels` already structurally prevents `entry_price == stop_loss` was not traced this session | Trade mapping | `TradeOutcomeContractError` | Yes (once the upstream guarantee, if any, is confirmed) |
| 8 | "hash drift" | Layer-2 (dataset hash validation against manifest) | Manifest/dataset validation | `DatasetIntegrityError` | Yes |
| 9 | "no post-hoc dedup" | Layer-2 (negative constraint: the transactional adapter pipeline, Section O, has no dedup-observations step anywhere after construction) | Structural (absence of a step) + property test | N/A (code-review + property test: output count always 4N) | Yes |
| 10 | "no winsorization" | Layer-1 (already enforced — `estimators.py`/`stratify.py` use plain arithmetic mean only) | N/A — already frozen, committed | N/A | Already covered (81 Layer-1 tests) |
| 11 | "no trimming" | Layer-1 (already enforced, same as #10) | N/A — already frozen, committed | N/A | Already covered |
| 12 | "no incomplete-session dropping" | Layer-2 (ties to boundary-gap/cutoff validation, #6/REQ-STAT-29) | Manifest/dataset validation | `DatasetIntegrityError` / `FrozenArtifactMismatchError` | Yes |

No canonical condition may exist only in the JSON after V3 — this table is now the durable repo record (REQ-STAT-30).

## N. Execution baseline & protected paths (V3)

Before first real discovery execution: record one `measurement_execution_baseline_commit` (REQ-STAT-31), created AFTER Layer-2 + Layer-3 implementation, closeout, and full measurement-instrument verification. Protected paths (enumerated exactly at that time, NOT the whole repo): `detector/policy/`, `detector/evaluation/`, `detector/selection/`, the Layer-2 adapter package, the Layer-3 runner package, `detector/backtest/candidate.py`, `detector/backtest/population.py`, `detector/backtest/simulate.py`, `detector/backtest/levels.py`, the `alignment/` components used for provenance reconstruction, and the manifest/protocol artifact itself. At execution time: current state of every protected path MUST equal the baseline commit exactly (no uncommitted modification) — unrelated working-tree changes outside protected paths need not abort. This REPLACES the predecessor design pass's "diff each historical component commit against HEAD" idea, which this session's own audit disproved: `backtest/population.py`/`candidate.py` legitimately changed (commits `53a6514`, `26d94be`) after the Amendment's own recorded `commits.candidate_generation` (`3d3531e`) for unrelated reasons — a single execution-baseline commit, not a scattered set of historical references, is the only reliable final source-tree snapshot.

## O. Layer-2 architecture (V3)

Import direction (REQ-STAT-33): Layer-2 MAY import `evaluation`, `backtest`, `alignment`, `selection.model`. It MUST NOT live under `selection/`. `evaluation`, `backtest`, `alignment`, `policy`, and `selection` MUST NOT import Layer-2 (new `forbidden` import-linter contract, mirroring `no-selection-in-outcome-layers`). Recommended internal shape: staged pure functions (mirroring `detector/selection/`'s own module style — one function per pipeline stage from Section L/M) behind one transactional facade that exposes `DirectionPolicyObservation[]` only after every validation in Sections L–N succeeds; no partial/lazy output. Final package name deferred to a repo-convention audit at implementation time (candidate: `adapter`).

## P. Sign-off

**SPEC ONLY. NOT IMPLEMENTED. NO OUTCOMES INSPECTED.** This hardening pass corrects one structural defect from the prior spec draft (conflating `CandidateIdentity` with the operational `TradeJoinKey`) and makes this document independently sufficient to implement the runner without consulting any chat transcript. All prior statistical decisions (U-1, U-2, EST-B, CI, SEL-A, cluster semantics, SR-A architecture) remain approved and unchanged by this pass.

**V2 amendment**: adds `closed_outcome` (Section C/C2) as WR's categorical source — sourced from the pre-existing `Trade.outcome` contract, never derived from `realized_r`'s sign — and amends REQ-STAT-01, 04, 06, and 19 in place; REQ-STAT-20 gets a dangling cross-reference correction only, no semantic change. No other statistical decision (EST-B, MEI, U-1, U-2, bootstrap, RNG, CI, SEL-A, cost assumptions) is reopened by V2. This gap surfaced entirely from auditing this repo's own pre-existing `Trade`/`compute_metrics` convention — no real outcome was inspected to discover or resolve it.

**V3 amendment (this pass)**: freezes the Layer-2 adapter contract — REQ-STAT-23 through REQ-STAT-33, Sections K–O. Corrects one finding from the predecessor design-only pass (Section K: `signal_id → htf_context` IS a function by construction; no provenance-preserving sidecar is needed or permitted — the earlier ambiguity claim is SUPERSEDED BY CODE AUDIT). Transcribes, verbatim, all 12 conditions of the canonical Amendment's `data_quality_fail_closed` array (Section M) — 9 of which had never reached this spec's normative text before. Replaces an earlier, rejected fingerprint-verification idea (per-historical-commit whole-directory diffing) with a single `measurement_execution_baseline_commit` + enumerated protected paths (Section N), evidenced by this repo's own history (`backtest/population.py`/`candidate.py` legitimately changed after the Amendment's recorded `candidate_generation` commit). REQ-STAT-29's candidate-cutoff timestamp semantics are now RESOLVED (Candidate event = `retest_index` = K, strict `<` boundary, naive-UTC comparison per this repo's existing timestamp convention) — **zero `HUMAN DECISION REQUIRED` items remain in V3**; every requirement is implementation-ready. Layer-1 (`detector/selection/`, frozen, committed `75d9c37ac08a314a6518484b7e62ee3c7eb798c1`) is NOT reopened by this pass. No real outcome was inspected — this entire pass is design/code-reading only.

**33 normative requirements: REQ-STAT-01 through REQ-STAT-33, all present in full above.**
