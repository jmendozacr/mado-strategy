# Loss Pattern Discovery Lab

Objective: investigate whether losing trades / SL invalidations of existing CRT/D3-C2 strategies
contain exploitable predictive information, without modifying the original strategies.
Branch: `research/loss-pattern-discovery` (worktree: `mado-strategy-research-loss-pattern-discovery`,
sibling of the main worktree). Base: `detector-msnr-key-levels` @ `95eb1a7668dc6b0d8ea29e18c7874df4e40ca034`.
Test runner: `pytest` (stdlib + pandas/numpy only, no heavy deps without justification).
Delivery strategy: `ask-on-risk` (default).

## Specs

- S1 (research question, verbatim): "¿Podemos analizar sistemáticamente las operaciones perdedoras
  de una estrategia, descubrir patrones recurrentes en el comportamiento del precio y utilizar esa
  evidencia para desarrollar una estrategia de trading completamente nueva?" Explicitly NOT an
  optimization of the existing system; NOT a rule change to CRT/D3-C2.
- S2 (idealized expectancy baseline, verbatim formula): win rate 20%, RR 1:2 →
  `0.20 × 2R − 0.80 × 1R = −0.40R`. Losing trades may still reveal recurring market behavior worth
  studying even though the raw strategy is a loser.
- S3 (three research lines): A — pre-entry failure prediction (independent filter). B — **priority**:
  post-SL behavior (direction, MFE/MAE, time-to-move, reversal vs continuation, volatility regime,
  session/pair/regime dependence, cost-aware exploitability). C — alternative strategy discovery,
  only if A/B produce sufficiently robust evidence; explicitly: "tampoco debemos asumir que una
  estrategia perdedora se convierte automáticamente en rentable al invertir sus señales."
- S4 (causal constraint on any hypothetical new entry, verbatim): "La nueva operación hipotética
  nunca podrá ejecutarse antes de que su condición de entrada sea observable." A post-SL continuation
  entry may only use information known at or after the original SL + any required confirmation.
- S5 (data provenance discipline): before using any historical trade as evidence, verify where it
  came from, what rules generated it, and whether its execution is causally valid. Known prior
  issues in this repo: look-ahead bias, retrospective anchor selection, H4 broker-vs-NY-feeder
  timezone mismatch, impossible/premature fills. D3/C2 may be used as an initial event generator but
  the research is not restricted to its rules.
- S6 (dataset must include comparison groups): not only losers — keep winners and, where possible,
  valid signals that never executed, to avoid selection bias.
- S7 (minimum per-event fields, verbatim groups): Identificación (stable ID, source+experiment
  version, instrument, timestamp, original direction, session, config id); Operación original
  (entry, SL, TP, risk in price and R, activation time, exit time, exit reason, result, execution
  integrity/validity status); Contexto observable (pre-entry known info, structural features,
  volatility, temporal condition, price context, info available at each decision instant); Trayectoria
  posterior (MFE, MAE, time-to-SL/TP, invalidation price/time, post-SL movement, defined future
  horizons, censoring at data/horizon exhaustion, execution/trajectory ambiguities).
- S8 (hard separation, verbatim): "Separa explícitamente: `features_pre_entry`, `features_at_stop`,
  `post_stop_outcomes`. Esta separación es fundamental. No utilices los resultados futuros como
  variables predictoras."
- S9 (methodological guardrails): protect against look-ahead, data leakage, survivorship/selection
  bias, overfitting, multiple testing, trade dependence/overlap, unstable regimes, unrealistic fills,
  results explained only by spread/costs. Use chronological discovery/validation/final-test splits
  with purge/embargo for overlapping events, never random shuffling of time-adjacent observations.
  Historical years already used in prior research are not virgin OOS merely by reserving a sub-range.
  Register hypotheses before evaluating them on reserved data.
- S10 (methodology order): descriptive stats, distributions, conditional probabilities, uncertainty
  intervals, baseline comparisons, period/pair stability checks FIRST. ML (trees, GBM, clustering,
  etc.) only later, only if justified. Discovery must be interpretable before becoming a strategy.
- S11 (protected artifact, verbatim rules): `audit/trader-algorithm-fidelity/` (paused 30-case human
  pilot, not yet started) must stay untouched — no modifying its files, opening/altering its journal,
  altering its 30-case manifest, revealing hidden selection categories, showing specific case
  results, or using those sessions as discovered-pattern examples. If those events must be excluded
  from analysis, do it through an internal mechanism that does not expose categories or results.
- S12 (read-only boundary, verbatim list): `docs/`, `detector/`, `scanner/`,
  `audit/trader-algorithm-fidelity/`, original D3/C2 experiments, original historical files, prior
  backtest results — all read-only. New work stays inside `research/loss-pattern-discovery/`, plus
  minimal justified isolated-environment config files.
- S13 (lab structure, minimum): objectives/hypotheses doc, source/provenance inventory, event schema,
  extraction tools, integrity/causality validators, descriptive statistics, future-experiments notes,
  reproducible results, limitations/decisions log. Reuse `detector/` as a read-only dependency instead
  of duplicating code, only if it introduces no side effects. Derived datasets must be regenerable via
  documented commands. No committing large historical files or unnecessary generated artifacts.
- S14 (phase-1 scope, verbatim list, items 1-10 of section 10): create branch+isolated env; inspect
  historical sources and experiments; evaluate which trade sources are reliable enough; design the
  event dataset schema; implement a first reproducible extractor if sources allow it; create
  chronology/provenance/integrity validators; produce an initial descriptive summary of coverage,
  quality and available results; identify what's needed to analyze post-SL trajectories; document
  risks/assumptions/limitations; **stop before mass pattern search, strategy optimization, or model
  training.**
- S15 (stop condition, verbatim): "Si encuentras defectos en los datos o en la fidelidad de
  ejecución, prioriza documentarlos y resolver la elegibilidad de los registros dentro del
  laboratorio antes de continuar. No corrijas silenciosamente los experimentos originales. No
  presentes todavía ninguna estrategia como rentable."
- S16 (final report must answer, verbatim sections): A. Infraestructura (branch/worktree/SHA/sources
  reachable). B. Calidad de los datos (counts: total/usable/execution-or-chronology-problems/missing
  info). C. Viabilidad (can we causally reconstruct SLs? measure post-SL movement? what resolution is
  needed? what limits confident conclusions?). D. Implementación (files, tests, repro commands,
  commit SHAs). E. Recomendación for the next research unit toward a "Post-Stop-Loss Behavior Atlas".

## Tasks

| ID | Linked S# | Route | Status | Commit |
|----|-----------|-------|--------|--------|
| T1 | S1,S12 | inline (git) | done | worktree+branch created, no commit needed |
| T2 | S5,S9 | delegated explorer | done | — (read-only, no commit) |
| T3 | S13 | inline | done | pending commit (this round) |
| T4 | S7,S8 | inline | done | pending commit (this round) |
| T5 | S5,S14 | inline (depends on T2) | done | decision D1 in `06-limitations-and-decisions-log.md` |
| T6 | S9,S14 | inline (depends on T2,T5) | done | pending commit (this round) |
| T7 | S10,S14 | inline (depends on T6) | done | `artifacts/phase1_summary.{md,json}` (gitignored, regenerable) |
| T8 | S14,S16 | inline | done (minimal) | mechanism documented in `05-excluded-protected-artifacts.md`; no actual overlap found to exclude yet |
| T9 | S15 | inline | done | this report |

### Phase 2 specs (S17+)

- S17 (premise, verbatim): "no hemos demostrado que las 1.265 pérdidas equivalgan a 1.265 Stop Loss
  ejecutados. Ese es nuestro primer problema de investigación." Phase 2 is exclusively descriptive
  and comparative -- no strategy design, entry optimization, or model training this round either.
- S18 (eligibility taxonomy, verbatim categories): A Confirmed Stop Event; B Stop After Partial Exit
  (preserve per-stage info); C Other Negative Exit; D Ambiguous Stop Event (unresolved intrabar
  ambiguity, gap, insufficient data, or source limitation); E Open/Censored. Adapt the taxonomy if
  real fields require it, documenting why; never classify as confirmed something only plausible.
  Entregable A: eligibility table with counts/pct/reasons/confidence. If too few stops verify,
  stop before the Atlas and report what's missing -- never relax criteria for a bigger sample.
- S19 (trajectory reconstruction requirements): per eligible event, establish stop_event_time/price,
  original/opposite direction, original risk in price units, time convention, execution confidence,
  and the first instant a new hypothetical operation could have acted. Causality precaution
  (verbatim intent): if the SL triggered inside an M15 bar, never retrospectively use that same bar's
  full high/low to attribute a post-SL opportunity when intrabar order is unknown -- use a
  conservative observation point excluding information before the event was knowable; alternate
  conventions may be computed but must stay clearly separated. Never interpret a favorable excursion
  as realizable profit. Horizons: 1h, 4h, 1d, 3d; declare and consistently apply calendar vs.
  market-effective time; distinguish weekends/closures/missing data/incomplete horizons.
- S20 (variables per horizon, verbatim groups): Movimiento (raw max/min, directional return at
  horizon close, MFE, MAE, MFE/MAE in R, MFE/MAE normalized by observable volatility at the event);
  Continuación (movement favoring the SL-triggering direction, max continuation magnitude, time to
  predefined thresholds); Reversión (movement against the stop-out direction, recovery frequency to
  original entry, time to that recovery); Trayectoria (observable order of favorable/adverse moves,
  same-bar ambiguities, censorship state, distance traveled before a reversal). Never compute R with
  zero/unknown/invalid risk. Never fill a censored observation artificially.
- S21 (control group, mandatory, verbatim intent): must test whether post-SL behavior differs from
  normal market behavior, not merely observe a tendency. Match/stratify using ONLY pre-reference-
  instant information: instrument, NY hour/session, historical period, prior volatility, reference
  direction, other data-justified features. Never select controls on future trajectories. Document
  how a control's direction and start instant are defined. Avoid one market episode over-contributing
  to both groups. If matching is weak, report it and also keep an unmatched baseline. Compare, per
  horizon: continuation/reversal probability, excursion magnitude, time-to-move, return distribution,
  dispersion/uncertainty, and the absolute SL-vs-control difference. A 65%-vs-63% gap may be
  uninteresting; 65%-vs-45% merits further study but still proves no profitability. Never present
  hypothetical examples as real results.
- S22 (stratification, verbatim minimum cuts): instrument (EURUSD/USDCAD/AUDUSD); origin model
  (1AM/9AM); eligibility outcome (confirmed; stop-after-partial; ambiguous kept separate for
  sensitivity); historical period (predeclare intervals before comparing, never chosen to maximize
  differences); direction (buy/sell original). Never exclude EURUSD just because the original
  backtest was weak there -- a losing pair's invalidations can still be informative. Avoid excessive
  fragmentation: report sample sizes/uncertainty for small combinations rather than presenting
  percentages as solid evidence; no combinatorial subgroup search.
- S23 (statistics/QC, verbatim list): sample sizes, medians/quantiles, distributions, uncertainty
  intervals, SL-vs-control comparisons, sensitivity to ambiguous events/partial exits/gaps, temporal
  variation. Account for dependence between near-in-time events -- never treat same-day/same-episode
  overlapping trades as fully independent. If bootstrapping, justify the temporal grouping unit.
  Record how many events are excluded from each comparison and why. Never test hundreds of thresholds
  looking for the best result -- this phase's thresholds/hypotheses are defined before inspecting
  final distributions.
- S24 (outputs, verbatim sections): A Stop Event Eligibility Report; B Post-Stop-Loss Behavior Atlas;
  C Matched Control Comparison; D Data Quality & Limitations; E Research Findings (separate confirmed
  observations, descriptive regularities, new hypotheses for another phase, inconclusive results, and
  evidence AGAINST the hypothesis). Never declare an exploitable edge from the Atlas alone.
  Visualizations if feasible without new dependencies: MFE/MAE distribution, continuation vs.
  reversal, control-group differences, by-pair behavior, historical stability.
- S25 (protection, verbatim additions over Phase 1's S11/S12): never open/modify
  `audit/trader-algorithm-fidelity/runtime/events.jsonl`; never show individual trades identifiable by
  date+pair that could reveal future human-pilot session results; limit the user-facing report to
  aggregates, keeping detailed data inside the lab with controlled access for reproducibility.
- S26 (mandatory 13 tests, execution order Pasos 1-8, and stop condition): see
  `research/loss-pattern-discovery/tests/test_phase2_requirements.py`'s docstring for the 1-13
  requirement-to-test map. Run Phase 1's 18 tests too; never silence a failing test. If Paso 1 shows
  SL cannot be reliably identified, stop with a blocking report and a plan for what's needed instead
  of forcing the rest of the investigation.

### Phase 2 tasks

| ID | Linked S# | Route | Status | Commit |
|----|-----------|-------|--------|--------|
| T10 | S18 | inline | done | eligibility classifier + report; 1262/1265 confirmed (99.4%), 0 stop-after-partial (explained, not a defect), 3 ambiguous, 0 other |
| T11 | S19,S20 | inline | done | `behavior/post_stop_metrics.py` + tests |
| T12 | S21 | inline | done | `control/sampling.py` + tests |
| T13 | S22,S23 | inline (depends on T10-T12) | done | `stats/bootstrap.py`, `stats/atlas.py` |
| T14 | S24 | inline (depends on T13) | done | `docs/09-atlas-results.md`, `docs/10-control-comparison.md`, `docs/11-research-findings.md`, `docs/12-next-research-unit-recommendation.md`, `artifacts/figures/*.png` (gitignored) |
| T15 | S25 | inline | done | no new boundary files touched; `events.jsonl` never referenced |
| T16 | S26 | inline | done | full suite green (final count/commit recorded in the Log); real-scale Atlas run completed: n_eligible=1262, n_ambiguous=3, n_controls=1262 |

### Phase-2 real-data headline (full numbers in `docs/09-11`)

- Eligibility: 1262/1265 losses (99.4%) Confirmed, 0 Stop-After-Partial (explained by
  breakeven_after_partial reward structure), 3 Ambiguous, 4 Open-censored.
- Atlas: P(continuation) ~55-56% vs. P(reversal) ~43-44% at every horizon (1h/4h/1d/3d); recovery to
  original entry price grows from 25.4% (1h) to 85.4% (3d).
- Control comparison: continuation/reversal split is statistically indistinguishable from a matched
  "ordinary market moment" control at every horizon (diffs -0.4 to +1.1pp, all CIs cross zero). One
  borderline MAE difference at 1d (-0.234R, CI excludes zero) is flagged inconclusive given 8
  comparisons ran with no multiple-testing correction.
- One real stratified difference found: 1am session shows larger MAE (3.18R vs 2.05R) and higher
  recovery (88.0% vs 70.0%) than 9am at 1d — flagged as a hypothesis for a future unit, not explained
  here.

T1 = branch/worktree. T2 = map D3/C2 experiments, causal-lookahead-audit findings, detector reusable
modules, data/ schema, existing `research/` conventions, trader-algorithm-fidelity boundary
(path-only). T3 = lab skeleton + objectives/hypotheses/provenance docs (this file's twin under
`research/loss-pattern-discovery/docs/`). T4 = event schema (dataclasses) with the
features_pre_entry/features_at_stop/post_stop_outcomes separation. T5 = source reliability
assessment per S5/S9 (which experiments are usable evidence, which are tainted and why). T6 =
extractor + integrity/causality/chronology validators. T7 = descriptive summary (counts, coverage,
quality, no pattern mining). T8 = exclusion mechanism for S11 (opaque hold-out set, no category/result
leakage). T9 = final limitations/risks doc + the A-E report to the user.

## Log

- L1: User's original request (2026-11-24, this session) — full multi-section brief creating this
  research line; condensed into S1-S16 above verbatim where decision-relevant. Key non-negotiable:
  rigor and causality over positive results; three research lines A/B/C with B as initial priority;
  hard read-only boundary on `docs/`, `detector/`, `scanner/`, `audit/trader-algorithm-fidelity/`,
  original D3/C2 experiments/results; stop after phase-1 (no pattern mining, no optimization, no
  model training, no profitability claims yet).
- L2: Prior-session memory recalled before starting (mado-strategy Engram, read before writing):
  (a) `audit/2026-11-17-causal-lookahead-audit/results-d3-c2-robustness-2015plus.md` already found
  the D3/C2 "+78.603R" headline has NO genuine OOS, is cost-fragile (EURUSD already ≤0 expectancy at
  zero extra cost; combined flips negative around +0.025-0.04R/trade extra cost), is concentrated in
  2021-2026 (2015-2020 was net -16.7R combined), and EURUSD's sign flips removing 8/12 years
  (coin-flip signature) — USDCAD/AUDUSD are more robust to single-year removal but still untested
  out-of-sample. This means D3/C2 trade rows are NOT a uniformly trustworthy evidence pool; EURUSD
  rows in particular should not be treated the same as USDCAD/AUDUSD rows without flagging this.
  (b) The separate `audit/trader-algorithm-fidelity/` app rebuilds NY-feeder H4 from closed M15 bars
  (incomplete buckets marked non-evaluable) to handle the broker-H4-vs-NY-feeder timezone mismatch —
  this is a candidate reusable pattern for causal H4 reconstruction in this lab, without touching that
  app's own files.
  (c) `data/` is gitignored and absent from the new worktree; it only exists at the main worktree's
  absolute path. Lab code must reference it by configurable absolute path, not copy it.
