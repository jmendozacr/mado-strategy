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
- L3: User independently re-reviewed commit `4aadf26` and found 3 concrete defects before authorizing
  Phase 3: (1) `control/sampling.py`'s candidate pool never actually filtered by NY hour despite the
  docs claiming it did; (2) `behavior/post_stop_metrics.py` had 3 timing defects (raw_max/min seeded
  from an out-of-window bar; candle-open used where candle-close/availability was required; `censored`
  conflated true data exhaustion with ordinary weekend closures); (3) the eligibility report's "99.4%"
  mixed denominators (1265 losses vs. 1269 losses+open) without saying so. Explicit instruction: fix
  these BEFORE evaluating the recovery-to-entry phenomenon, preserve Phase 2's original numbers as
  historical reference (never overwritten), and compare old vs. corrected explicitly.

## Phase 3 specs (S27+)

- S27 (premise, verbatim): "no hemos demostrado que las 1.265 pérdidas equivalgan a 1.265 Stop Loss
  ejecutados" carried forward; now specifically: before treating the 75.4%/85.4% recovery-to-entry
  figures as a candidate phenomenon, fix the 3 confirmed defects above, recompute, and compare against
  the original. Recovery percentages are retrospective observations, not profitability evidence.
- S28 (control-group fix, verbatim requirements): distinguish `origin_model` (1AM/9AM) from
  `actual_stop_time_ny` (when the stop itself executed) and `control_reference_time_ny`; match by a
  simple, pre-declared NY-hour convention (never invent a stop hour from the model label); keep
  instrument/period/volatility/exclusion criteria; generate match-quality diagnostics (NY hour,
  volatility, risk distance, instrument, period, direction); report how many controls could not be
  matched; distinguish matched / matched-with-replacement / unmatched, never silently relaxed;
  preserve seed/reproducibility. RED-then-GREEN test required for the naive-pool defect specifically.
- S29 (post-stop metric fix, verbatim defects A/B/C): A -- no OHLC beyond a horizon's own boundary may
  affect that horizon's metrics, regardless of which bar is chronologically first after exit. B --
  distinguish candle open vs. close/availability vs. SL instant vs. first observable recovery instant
  vs. exact horizon close; never use a still-open candle's OHLC prematurely; document and apply one
  consistent convention. C -- distinguish fully observed / partially observed by data exhaustion /
  unexpected gap / normal market closure / absence-of-movement-from-closed-market; never convert a
  non-evaluable observation into "no recovery"; never call a legitimate weekly closure censored if
  calendar time still has a valid interpretation; define calendar vs. market-effective time treatment
  (at least as a sensitivity). 10 specific required tests enumerated in section 2 of the user's brief
  (mapped 1:1 in `tests/test_post_stop_metrics.py`'s new tests, see `docs/13-...`).
- S30 (re-run and compare, verbatim): re-run the Atlas with the SAME original hypotheses/thresholds
  (never recalibrate 0.25R or horizons to recover a statistical difference); produce an explicit
  diff table (n, hour distribution, continuation, reversal, MFE/MAE, recovery, uncertainty intervals,
  pct censored, control quality) between `4aadf26` (original) and the corrected run; never silently
  overwrite the original results, keep them as historical reference; if the new control materially
  changes the ~55% continuation conclusion, document that plainly, without seeking a favorable spin.
  Fix the denominator inconsistency (1262/1265=99.76% vs 1262/1269=99.45%) and verify the real test
  count (commit message vs docs had drifted).
- S31 (H1/H0, verbatim): H1 -- post-SL recovery to the original entry differs in frequency from
  comparable controlled market moments (controlling hour, volatility, distance to target). H0 -- no
  relevant difference. Primary endpoint: P(recovery within 24 calendar hours | confirmed SL) vs. the
  same for a matched control, with a synthetic target placed at the control's OWN target_distance
  (never assumed to be exactly 1R -- gap fills can make it differ from risk_price). Secondary,
  descriptive-only metrics (never a search for the best horizon): recovery at 1h/4h/3d, time to first
  contact, distance-to-level in ATR, cumulative incidence, non-recovering cases, weekend/gap effect,
  by-pair/model differences. 95% CI for the primary endpoint specifically (this lab's other endpoints
  stay at 90%), block bootstrap, absolute magnitude reported alongside significance. Explicitly: this
  is replication/exploratory evidence within a previously-examined 2015-2026 dataset, never described
  with out-of-sample-validation language, since the 75.4%/85.4% figures were already observed before
  this hypothesis was written down.
- S32 (executable-entry distinction, verbatim A-D): A Historical contact (a candle touched the level);
  B Causal confirmation (the information needed to assert recovery is already available); C First
  opportunity to act (the market could potentially accept an order after that confirmation); D
  Subsequent outcome (what happens after that instant, never reusing the prior recovery move as the
  new trade's own gain). This phase only builds A/B/C correctly. Never assume an exact fill at the
  recovered level if the signal only confirms later. Required fields (names adapted to the existing
  schema): `recovery_touch_bar_open`, `recovery_confirmed_at`, `recovery_first_actionable_at`,
  intrabar-ambiguity state, gap condition, recovered reference price.
- S33 (continue/stop criteria, verbatim): Phase 3 must be able to produce a negative result. If
  recovery is statistically similar to the control: report H0 as not rejected (never "equivalence
  proven"), document magnitude/precision, never turn 85.4% into a strategy, never hunt new subgroups
  looking for a positive result. If a relevant difference appears: check stability across
  periods/instruments, sensitivity to the control design, sensitivity to target distance/volatility,
  verify it doesn't depend on gaps/ambiguity/calendar effects, and propose one concrete causal
  hypothesis for a later phase -- never optimize parameters, test multiple re-entry rules, or backtest
  a new strategy's profitability this round.
- S34 (protection, unchanged from Phase 2's S11/S25): same read-only boundary; human-fidelity pilot and
  `audit/trader-algorithm-fidelity/runtime/events.jsonl` untouched and unopened this phase too.
- S35 (deliverables, verbatim): A Informe de correcciones; B Atlas corregido (explicit vs-original
  comparison); C Auditoría del grupo de control; D Recovery-to-Entry Analysis; E Veredicto (one of
  `NO_DIFFERENTIAL_RECOVERY_EVIDENCE` / `EXPLORATORY_DIFFERENTIAL_RECOVERY` / `INCONCLUSIVE` /
  `METHODOLOGY_BLOCKED`); F Checkpoint (files, tests, repro commands, SHA, limitations). Stop at the
  end of this phase -- no re-entry strategy, no bot, no parameter optimization, no model training.

## Phase 3 tasks

| ID | Linked S# | Route | Status | Commit |
|----|-----------|-------|--------|--------|
| T17 | S28 | inline | done | `control/sampling.py` rewrite + `common/ny_time.py`; 13 tests (RED defect-proof + GREEN fix) |
| T18 | S29 | inline | done | `behavior/post_stop_metrics.py` defects A/B/C fixed; 19 tests (10 user-specified mapped) |
| T19 | S30 | inline (depends on T17,T18) | done | real-data re-run: `artifacts/phase3_atlas_corrected.json`; `docs/14-atlas-corrected-vs-original.md` |
| T20 | S31,S32 | inline (depends on T18) | done | `behavior/recovery_analysis.py` + 5 tests; `docs/15-recovery-to-entry-analysis.md` |
| T21 | S30 (denominator fix) | inline | done | `stats/eligibility_report.py` now reports both denominators explicitly |
| T22 | S35 | inline | done | `docs/13-16`, this checkpoint |

## Phase 3.1 specs (S36+)

- S36 (premise, verbatim): independent review of published Phase-3 code found an additional causal
  defect in the synthetic controls: `control_to_event_record`/`recovery_control_to_event_record` used
  `bisect_left` to find the reference bar then took its `.close`, while attributing that price to an
  event timestamped at `control.control_ts` (the bar's OWN OPEN) -- the close is only available 15
  minutes later. Must confirm against both the D3/C2 ledger's own exit semantics and the M15 candle
  convention before changing anything, define an explicit temporal contract (reference_bar_open,
  reference_bar_close, reference_price_available_at, event_effective_at, first_actionable_at,
  post_event_observation_start), choose Option A (close-referenced) or Option B (open-referenced)
  on consistency grounds alone -- never by which produces better statistics -- and re-verify whether
  Phase 3's findings survive.
- S37 (fix verification, verbatim cautions): fixing the control's timestamp/price must not
  accidentally exclude the first bar that truly begins after the reference price was available, nor
  include the bar whose own data defined that price as if it were subsequent movement. Re-check NY
  matching/ATR/exclusion/target-distance-vs-risk-distance still hold under the new contract; never
  recalibrate tolerances to chase a more favorable result.
- S38 (tests, verbatim 11 checks + 2 explicit boundary cases): RED reproduction with the exact
  O/H/L/C=1.1000/1.1050/1.0990/1.1040 M15 10:00-10:15 bar showing the old code would use 1.1040 "at"
  10:00; then GREEN checks for reference-price availability, no future closes, no reuse of the
  reference bar as subsequent movement, no bisect off-by-one, correct 1h/4h/1d/3d boundaries
  (including an exact-close boundary and a horizon ending mid-bar), correct NY/EST-EDT matching,
  ATR using only available information, unchanged gap/weekly-closure treatment, determinism under a
  fixed seed, and no contamination of original sources.
- S39 (re-run, verbatim constraints): same 1262 eligible events (unless documented otherwise), same
  0.25R threshold, same horizons, same statistical criteria, same seeds, same primary 24h recovery
  endpoint, same 5pp relevance bar -- never tuned after seeing results. Mandatory 3-way comparison
  table (Phase 2 `4aadf26` / Phase 3 `f040a47` / Phase 3.1) specifically for: continuation-vs-control
  (Phase 3's ~-4.4pp from 4h onward -- does it persist?), recovery-to-entry 24h (Phase 3's +1.66pp,
  95% CI [-1.67,+5.06] -- still inconclusive after the fix?), and the 1h/4h recovery descriptive diffs
  (~+5.5pp -- do they change?) -- without promoting a secondary horizon to the new primary endpoint.
- S40 (limited robustness, verbatim): explicitly exploratory seed-sensitivity check for the
  continuation metric only, across multiple equally-valid control-sampling seeds, never presenting
  only the best seed; report the range and sign stability with the rest of the design held fixed;
  never interpret 4h/1d/3d as three independent confirmations when they share `first_move_direction`;
  no subgroup search, no threshold optimization.
- S41 (two independent verdicts, verbatim categories): A -- continuation vs. normal market:
  `DIFFERENCE_PERSISTS_EXPLORATORY` / `DIFFERENCE_DISAPPEARS` / `SENSITIVE_TO_CONTROL_DESIGN` /
  `INCONCLUSIVE`. B -- recovery to original entry: `NO_DIFFERENTIAL_RECOVERY_EVIDENCE` /
  `EXPLORATORY_DIFFERENTIAL_RECOVERY` / `INCONCLUSIVE`. Never combined; neither alone proves
  profitability; 2015-2026 remains previously-examined data, not genuine OOS.
- S42 (protection/deliverables, unchanged from Phase 3's S34/S35): same read-only boundary and human-
  pilot protection; Deliverables A-F as listed in section 10 of this phase's brief; commit on
  `research/loss-pattern-discovery` and push to origin only if everything is correct; stop at the end.

## Phase 3.1 tasks

| ID | Linked S# | Route | Status | Commit |
|----|-----------|-------|--------|--------|
| T23 | S36 | inline | done | confirmed via `detector/backtest/simulate.py:170` (`_resolve_level_exit`) that real events never had this defect; `docs/18-phase3.1-causal-contract-and-fix.md` |
| T24 | S36,S37 | inline | done | `control/sampling.py` + `behavior/recovery_analysis.py`: `.close` -> `.open` at the reference bar |
| T25 | S38 | inline | done | `tests/test_control_price_causality.py`, 6 tests (RED + 5 GREEN); full suite 83 passed, lint-imports 11/11 |
| T26 | S39 (depends on T24) | inline | done | real-data re-run; `docs/19-phase3.1-results-comparison.md` |
| T27 | S40 (depends on T26) | inline | done | `stats/seed_sensitivity.py`, 5 seeds; `docs/20-control-robustness-and-seed-sensitivity.md` |
| T28 | S41,S42 | inline | done | `docs/21-verdict-and-checkpoint-phase3.1.md`: continuation `SENSITIVE_TO_CONTROL_DESIGN`, recovery `NO_DIFFERENTIAL_RECOVERY_EVIDENCE` |

### Phase-3.1 headline

Fixing the control's price-causality defect (close -> open at the reference bar) shrank Phase 3's
continuation-vs-control gap from -4.4pp (CI excluding zero) to -2.6pp (CI crossing zero) at 4h/1d/3d,
and a 5-seed sensitivity check showed the sign stays negative but the magnitude ranges -0.16pp to
-2.61pp with zero of five seeds reaching significance -- verdict `SENSITIVE_TO_CONTROL_DESIGN`. The
recovery-to-entry primary endpoint moved from +1.66pp to +1.11pp, still crossing zero -- verdict
`NO_DIFFERENTIAL_RECOVERY_EVIDENCE` confirmed, not reversed.

## Phase 4 specs (S43+)

- S43 (new question, verbatim): distinct from continuation/recovery -- do different FAILURE
  MECHANISMS exist within losing trades, and what observable information characterizes them? Two
  temporally-separated questions: A pre-entry (known before the trade began) vs. B during-the-trade
  (the path from entry to SL) -- never use B to retroactively claim A was predictable. Descriptive
  only this phase, no trading signals yet.
- S44 (data audit first, verbatim): reuse `schema/events.py`, `extract/from_causal_lookahead_audit.py`,
  `eligibility/stop_eligibility.py`, `behavior/post_stop_metrics.py`, `common/ny_time.py`; never
  assume ledger timestamps equal an M15 bar's close (the exact mistake fixed for synthetic controls
  in Phase 3.1 must not be reintroduced here); determine what is reconstructible at each of 6 stages
  (signal activation, order placement, entry execution, open, SL confirmed, post-SL) and the last
  available M15 datum at each.
- S45 (pre-entry dataset, verbatim): both wins and losses, same extraction methodology on both (the
  comparison is the point -- loss-only features tell nothing about specificity). Small, interpretable
  variable set across identification/volatility/geometry/temporal/directional groups (never a huge
  indicator catalog); each feature documented with name/formula/source/availability
  instant/unit/missing-value treatment/causality test; continuous values preserved, never prematurely
  bucketed; any CRT/Key-Level/anchor-dependent feature's provenance registered before use (none were
  used this phase).
- S46 (pre-SL trajectory reconstruction, verbatim): for every confirmed SL, reconstruct entry-to-SL
  using the same causal conventions as prior phases. Fundamental caution: never reconstruct an
  intrabar order M15 cannot observe; never attribute the entry or exit bar's own extremes to "before
  the event" without flagging ambiguity; never confuse the planned SL price with the actual executed
  (possibly gapped) price; never fabricate a zero MFE pre-SL when information is insufficient --
  exclude or flag explicitly, keep alternate scenarios separate.
- S47 (multidimensional taxonomy, verbatim): duration / favorable-excursion-before-SL / path-
  integrity as INDEPENDENT dimensions, never 5 mutually-exclusive labels; threshold justification
  required before computing anything, numeric cuts only with a defensible economic/technical
  criterion (continuous distributions otherwise); never choose thresholds using future returns or
  searching for the most profitable split.
- S48 (win-vs-loss comparison, verbatim): two separate datasets, `pre_entry_features` and
  `failure_path_features`; never use post-SL-only-known characteristics to retrospectively judge
  which trades "could have been avoided"; comparison limited to EXECUTED trades (L1 selection-bias
  limitation still open, not blocking, not presented as a claim about every CRT opportunity).
- S49 (Atlas + stats, verbatim): answer the 10 questions in section 8 of the brief; reuse the 4
  predeclared period buckets; visible sample sizes; one-way stratification only, no combinatorial
  subgroup search; descriptive stats primarily (distributions/medians/quantiles/rates/uncertainty/
  predeclared comparisons), no clustering/ML, no mass correlation search against future returns, no
  win-rate-maximizing combination search.
- S50 (Layer A/B/C separation, verbatim): Layer A (pre-entry) and Layer B (at-stop/failure-path) must
  stay isolated from Layer C (post-stop) while designing/computing the taxonomy -- no post-SL MFE,
  recovery, continuation, or future return may select a failure-mode group.
- S51 (protection, unchanged): same read-only boundary and human-pilot protection as Phases 1-3.1.
- S52 (15 required tests + full suite, verbatim): see `tests/test_phase4_requirements.py`'s coverage-
  map docstring for the 1-15 requirement-to-test mapping.
- S53 (deliverables, verbatim): A Pre-Entry Feature Audit; B Pre-Stop Trajectory Reconstruction; C
  Failure Mode Taxonomy; D Failure Mode Atlas; E Research Findings (5 categories); F Phase-5
  recommendation (one priority hypothesis, or an explicit statement that none is justified); G
  Checkpoint. Commit and push to origin if correct; stop at the end -- no ML, no RR optimization, no
  bots, no CRT modification.

## Phase 4 tasks

| ID | Linked S# | Route | Status | Commit |
|----|-----------|-------|--------|--------|
| T29 | S44 | inline | done | `docs/22-phase4-design-and-pre-registration.md` |
| T30 | S45 | inline | done | `features/pre_entry_features.py`; 6 tests; 100% coverage on 2047 trades |
| T31 | S46 | inline | done | `behavior/pre_stop_trajectory.py`; 9 tests; 79.95%/12.76%/7.29% reconstructible/ambiguous/insufficient |
| T32 | S47 | inline (depends on T31) | done | `failure_modes/taxonomy.py`; 5 tests |
| T33 | S48,S49 (depends on T30-T32) | inline | done | `stats/failure_mode_atlas.py`; `docs/23-26` |
| T34 | S52 | inline | done | `tests/test_phase4_requirements.py` (3 new); full suite 106 passed, lint-imports 11/11 |
| T35 | S50,S53 | inline | done | `docs/27-28` |

### Phase-4 headline

71.7% of reconstructible confirmed stops (1009/1262) show at least partial (>=0.25R) favorable
excursion before failing -- a straight slide to the stop is the minority pattern. 20.05% of confirmed
stops cannot have a pre-SL path reconstructed at all (same/adjacent-bar entry-to-exit). No pre-entry
feature shows a stark win/loss median separation. 1AM shows a markedly different failure-path
integrity profile than 9AM (31.2% vs. 15.3% ambiguous/insufficient) -- a THIRD independent signal
(after Phase 2/3's MAE and recovery findings) pointing at an unexplained 1AM/9AM mechanism, proposed
as the priority Phase-5 hypothesis (not evaluated this phase).

## Phase 5 specs (S54+)

- S54 (checkpoint + two populations, verbatim): start from checkpoint `5e332c7`. Never start directly
  from the 1262-loss population; use the full executed-trade population (778 win, 1265 loss, 4
  open/censored) as primary, to avoid the selection bias of starting from losses alone. Two
  populations, never mixed: primary = all evaluable executed trades; secondary = the 1262
  confirmed-stop losses (used only to explain Phase 4's own Deliverable D figures).
- S55 (H1/H2/H3 pre-registration, verbatim): register before running new analyses. H1 -- the
  probability of a confirmed stop within the entry bar or the next M15 bar differs between 1AM/9AM;
  verify actual bar indices and the fills engine's timestamp semantics, never assume
  `duration <= 15min`; evaluate unadjusted, then adjusted for pre-entry conditions. H2 -- the gap
  shrinks substantially when controlling for `risk_atr` (= `risk_price / pre_entry_ATR`), instrument,
  period, prior volatility, direction -- candidate explanatory variables, never chosen by which gives
  the best result. H3 (secondary, limited) -- Phase 2/3's MAE-post-SL/recovery gaps might be
  partially explained by risk geometry; investigate only as secondary, not a reopened strategy
  search.
- S56 (standardization method, verbatim): check common support between 1AM/9AM `risk_atr`
  distributions before matching/standardizing; never force extreme matching, never extrapolate
  beyond common support; if insufficient overlap, conclude the dataset cannot separate model-effect
  from stop-geometry. Simple, transparent method only (standardization or matching with balance
  diagnostics) -- explicitly not complex ML. Document specification/calipers before inspecting the
  adjusted result; never optimize matching to produce significance.
- S57 (time-to-SL taxonomy, verbatim): distinguish SL-confirmed vs. TP/win vs. partial exit vs.
  ambiguous vs. open/censored -- never treat wins or opens as independent censoring of SL without
  justification. Use a defensible descriptive estimator; avoid survival models assuming
  non-informative censoring when that assumption does not hold.
- S58 (mechanism check, verbatim): investigate whether Phase 4's path-integrity gap (31.2% vs. 15.3%)
  is a mechanical artifact of `duration_bars` rather than independent information; reconstruct the
  funnel executed_trade -> exit_type -> duration_bars -> confirmed_stop -> path_integrity explicitly.
- S59 (causal constraint, verbatim, section 11 of the brief): `origin_model` is not randomly
  assigned. A difference surviving adjustment does not prove the model causes it. Separate total vs.
  conditioned differences; document confounders vs. potential mediators; never use strong causal
  language; never claim a residual difference demonstrates a model-specific mechanism; never force
  NY-hour matching if models naturally operate in non-overlapping hours.
- S60 (statistical rigor, verbatim): sample sizes, absolute differences, CIs, balance diagnostics,
  common-support size, temporal dependence, one-way sensitivity by instrument/period only (never a
  combined grid), competing-event counts, missing-data analysis. One primary endpoint with 95% CI,
  everything else secondary/explanatory. No dozens of tests chasing significance. The 2015-2026
  history remains previously-examined, not genuine out-of-sample, regardless of this phase's CIs.
- S61 (15 required tests + full suite, verbatim): see `tests/test_phase5_requirements.py`'s
  coverage-map docstring for the 1-15 requirement-to-test mapping; re-run the existing 106 prior
  tests; never hide or change a test just to get green.
- S62 (deliverables, verbatim): A Model Population Audit (full table, explicit denominators); B
  Pre-Entry Comparability Report (distributions by model); C Early Stop-Loss Analysis (H1
  unadjusted/adjusted); D Failure Mechanism Explanation (how much of the integrity gap is explained
  by duration, how much remains unexplained); E Secondary Behavioral Analysis (H3, only if
  defensible); F Research Verdict & Checkpoint -- classify into exactly one of
  `MOSTLY_EXPLAINED_BY_RISK_GEOMETRY`, `RESIDUAL_MODEL_ASSOCIATION`, `NO_ROBUST_DIFFERENCE`,
  `INSUFFICIENT_COMMON_SUPPORT`, `INCONCLUSIVE`, with files/tests/commands/results/sample-size-
  changes/limitations/commits/SHAs and a recommended next hypothesis if any.
- S63 (protection, unchanged): same read-only boundary and human-pilot protection as Phases 1-4; no
  GUI, no AI models, no new strategies, no RR/SL/TP/entry-parameter optimization; stop at the end of
  Phase 5, no Phase 6 without explicit authorization.

## Phase 5 tasks

| ID | Linked S# | Route | Status | Commit |
|----|-----------|-------|--------|--------|
| T36 | S54,S55,S56 | inline | done | `common/trade_timing.py`; `docs/29-phase5-design-and-pre-registration.md` |
| T37 | S54,S62(A,B) | inline | done | `stats/model_population_audit.py`; `docs/30-31` |
| T38 | S55,S56,S58 | inline | done | `stats/early_stop_hypothesis.py`; `docs/32-33` |
| T39 | S55(H3) | inline | done | `stats/secondary_behavioral_adjustment.py`; `docs/34` |
| T40 | S61 | inline | done | `tests/test_trade_timing.py` (6), `tests/test_early_stop_hypothesis.py` (8), `tests/test_phase5_requirements.py` (1); full suite 121 passed, lint-imports 11/11 |
| T41 | S59,S62(F) | inline | done | `docs/35-research-verdict-and-checkpoint-phase5.md` |

### Phase-5 headline

Using the full executed-trade population (not loss-only), the 1AM model shows a 9.35pp higher
same-or-next-bar confirmed-stop rate than 9AM (18.90% vs. 9.55%, 95% CI [5.85, 12.77]). This gap does
NOT shrink after standardizing for `risk_atr` (+9.93pp standardized, CI [6.30, 13.44]) -- H2 (risk
geometry explains it) is not supported. Phase 4's path-integrity gap is confirmed to be a mechanical
restatement of this same duration fact (0/1262 mismatches), not independent evidence. The secondary
H3 check (MAE/recovery) also fails to be explained by `risk_atr`. Verdict: `RESIDUAL_MODEL_ASSOCIATION`
-- a real, adjustment-robust association between model and early-stop rate, reported as association
only (origin_model is not randomly assigned; no causal mechanism claimed). `cost_to_risk_ratio` and
`atr_m15_at_entry` (both markedly different between models) are untested candidate explanations for a
future unit, not evaluated this phase.

## Phase 6 specs (S64+)

- S64 (checkpoint + engine audit, verbatim): start from checkpoint `8031cb2`. Read-only inspection
  of `detector/backtest/simulate.py`'s fill/SL/TP resolution before implementing anything; document
  what is observable vs. a simulator convention. Never assume same-bar SL is always impossible or
  always executable -- base classification only on what the engine and data can actually
  demonstrate.
- S65 (correction to the brief's own premise, discovered during the audit): the brief names
  `detector/backtest/simulate.py` as "the" engine, but this lab's actual source ledger was produced
  by `audit/2026-11-17-causal-lookahead-audit/causal_intrabar.py`'s `fill_pass_c` (entry fill
  eligibility REPLACED, floored at `first_fillable_index` strictly after Model-1's own confirmation
  bar) + `_resolve_exits` imported UNMODIFIED from `simulate.py` (SL/TP/partial resolution
  unchanged). Verified by reading both files directly, not assumed from the brief's own framing.
- S66 (E0-E4 decomposition, verbatim): split Phase 5's `confirmed_stop AND duration_bars<=1`
  endpoint into same-bar/next-bar/later-SL/other-exits/open-censored, same denominator as Phase 5,
  same eligibility criteria, never recoding ambiguous events as confirmed. Identity
  `Gap_early == Gap_E0 + Gap_E1` verified by test, not assumed.
- S67 (intrabar uncertainty taxonomy, verbatim): independent dimensions, not one exclusive label --
  sequence-verifiable, engine-conservative-same-bar, same-bar-multi-level-ambiguity, gap-affected,
  insufficient-evidence. One OHLC-based partial-identification criterion derived and used (fill
  candle's own open vs. entry price, by price-path continuity) -- never an invented intrabar order
  beyond that one geometric fact.
- S68 (sensitivity scenarios S0-S3, verbatim): S0 baseline (motor original, unmodified); S1
  next-bar alone (never framed as a conditional "survived bar 0" probability); S2 same-bar
  indeterminate events as partial-identification bounds (never recoded as wins or non-entries); S3
  verifiable subset only, with exclusion count/reason/selection-bias check reported explicitly.
- S69 (model construction audit, verbatim, read-only): inspect `causal/htf_trigger.py`'s
  `MODEL_1AM`/`MODEL_9AM` for verified structural differences (never invent mechanisms); evaluate
  alternative explanations (trading cost, risk_atr, instrument) without re-optimizing anything.
- S70 (statistical rigor, unchanged): same primary population/denominators/horizons/blocks/95% CI/
  eligibility criteria/periods/seeds as Phase 5; one-way sensitivity only; no combinatorial grid; no
  significance-chasing; 2015-2026 remains previously-examined, not genuine OOS.
- S71 (18 required tests + full suite, verbatim): see `tests/test_phase6_requirements.py`'s
  coverage-map docstring for the 1-18 requirement-to-test mapping; re-run the existing 121 tests;
  never hide or change a test just to get green.
- S72 (deliverables, verbatim): A Execution Semantics Audit; B Early-Stop Decomposition; C Intrabar
  Uncertainty Report; D Sensitivity Analysis; E Model Construction Audit; F Research Verdict --
  classify into exactly one of `MOSTLY_SAME_BAR_ENGINE_DEPENDENT`, `NEXT_BAR_DIFFERENCE_PERSISTS`,
  `MIXED_ENGINE_AND_MARKET_ASSOCIATION`, `INSUFFICIENT_INTRABAR_INFORMATION`,
  `NO_ROBUST_EARLY_STOP_DIFFERENCE`, with numeric justification; G Recommendation for Phase 7 (one
  hypothesis, not evaluated); H Technical Checkpoint. Commit and push to origin if correct; stop at
  the end of Phase 6 -- no Phase 7 without explicit authorization, no RR/SL/TP/entry-parameter
  optimization, no ML, no new strategies.

## Phase 6 tasks

| ID | Linked S# | Route | Status | Commit |
|----|-----------|-------|--------|--------|
| T42 | S64,S65 | inline | done | `docs/37-phase6-design-and-pre-registration.md` |
| T43 | S66 | inline | done | `eligibility/stop_timing_decomposition.py`; `stats/stop_timing_decomposition.py`; `docs/38` |
| T44 | S67 | inline | done | `eligibility/intrabar_ambiguity.py`; `stats/intrabar_uncertainty_report.py`; `docs/39` |
| T45 | S68 (depends on T43,T44) | inline | done | `stats/sensitivity_scenarios.py`; `docs/40` |
| T46 | S69 | inline | done | `docs/41` |
| T47 | S71 | inline | done | `tests/test_stop_timing_decomposition.py` (10), `tests/test_intrabar_ambiguity.py` (11), `tests/test_sensitivity_scenarios.py` (7), `tests/test_phase6_requirements.py` (1); full suite 150 passed, lint-imports 11/11 |
| T48 | S72(F,G) | inline | done | `docs/42-43` |

### Phase-6 headline

The brief's own premise needed one correction first: this lab's actual ledger comes from the causal
audit's `fill_pass_c` + `simulate.py`'s UNMODIFIED `_resolve_exits`, not a raw `simulate()` call --
verified before anything else. Decomposing Phase 5's +9.35pp early-stop gap: same-bar (`Gap_E0`,
+3.97pp) falls just BELOW the 5pp relevance bar on its own, while next-bar (`Gap_E1`, +5.38pp) --
which has ZERO same-bar intrabar ambiguity by construction -- independently clears both the
statistical and relevance bars. Within same-bar events, 84-92% have their entry-before-stop
sequence verifiable from OHLC alone (price-path continuity from the fill candle's own open), not
genuinely ambiguous; sensitivity bounds on the small remaining ambiguous subset (11 of 2043 events)
are under 1pp wide. Verdict: `NEXT_BAR_DIFFERENCE_PERSISTS` -- the 1AM/9AM association is not an
artifact of the engine's same-bar SL-wins-ties convention. The one verified structural difference
between models (confirmation window timing, 2h vs. 1h30m) remains an untested candidate mechanism,
proposed as the priority Phase-7 hypothesis (not evaluated this phase).

## Phase 7 specs (S73+)

- S73 (checkpoint + mandatory correction, verbatim): start from checkpoint `986f3be`. Before any
  Phase 7 analysis: reproduce with a red test, then fix, Phase 6's S2 partial-identification bug
  (pairing the same scenario on both models instead of the correct cross-model extrema
  `Gap_min=rate_1am_min-rate_9am_max`, `Gap_max=rate_1am_max-rate_9am_min`); add tests for uncertain
  events in BOTH models; verify the four extreme combinations are contained; separate point
  identification bounds from a statistical CI on the identified set; never treat two single-
  scenario CIs as automatically valid for the whole set; preserve `docs/40` unchanged as historical
  reference; document the correction's impact on the Phase 6 verdict.
- S74 (window reconstruction, verbatim): reconstruct `window_start_at`/`window_end_at`/
  `confirmation_bar_open`/`confirmation_available_at`/`order_placed_at`/`entry_filled_at` from
  `detector/causal/htf_trigger.py` + the ACTUAL causal pipeline that produced the ledger -- never
  confuse `confirmation_bar_open` with `confirmation_available_at`, nor `order_placed_at` with
  `entry_filled_at`; respect `fill_pass_c`'s existing causal corrections.
- S75 (discovery during S74, not pre-specified in the brief): tracing the real generating script
  (`run_d1_d2_d3.py`'s "D3" config) revealed the 9AM window Phase 6 documented (90min,
  09:00-10:30 NY, from the static `MODEL_9AM` config) is NOT what generated this ledger -- the real
  window is 240min (09:00-13:00 NY, `causal_anchor_v2.py::new_9am_window_fns`). 1AM is unaffected.
  Corrected via a banner on `docs/41`, never a silent rewrite; verified against all 2043 real
  events (0 violations after the fix, vs. 1080 before it).
- S76 (temporal feature dataset, verbatim): `event_id`/`origin_model`/`instrument`/`direction`/
  `period_bucket`; window fields; `confirmation_elapsed_minutes`/`remaining`/`relative_position`/
  `bar_position`; `order_to_fill_minutes` (descriptive only, never a pre-entry predictor -- it
  resolves at fill, after the window-position fact this phase studies); reused `risk_atr`/
  `atr_m15_at_entry`/`risk_price`/`planned_rr` from Phase 4, unmodified. Every field's source/
  formula/availability/unit/missing-treatment/causality-test documented before use.
- S77 (distribution audit, verbatim): continuous distributions only, one FIXED pre-declared
  30-minute bin width (never tuned on E1), by model/instrument/period, before any adjustment.
- S78 (E1 endpoint, verbatim): same primary population/denominators as Phase 6; E1 =
  `confirmed_stop AND duration_bars==1`, unconditional incidence among executed trades, never
  framed as "P(SL at bar 1 | survived bar 0)" (a different estimand this phase does not compute).
  Reproduce Phase 6's +5.38pp exactly before adjusting.
- S79 (association models, verbatim): Model 0 baseline; Model 1 risk_atr-standardized (reusing
  Phase 5's method); Model 2 timing-standardized, run TWICE (absolute minutes AND relative
  position -- NOT equivalent, since window durations differ); Model 3 one-way by instrument/period
  (never a joint grid), reusing the SAME global quintile cutpoints as Model 2 for every subgroup
  (never re-derived per subgroup -- this is both a robustness fix for empty subgroups and a
  methodological one, consistent with Phase 5's cutpoints-fixed-once discipline).
- S80 (common support, verbatim): absolute-minutes and relative-position common support are
  checked and reported SEPARATELY, never conflated; if either fails the pre-existing 30%-
  unsupported threshold, that specific adjustment is not used as evidence either way.
- S81 (window duration vs. market hour, verbatim): never present excluding late-window
  confirmations from this descriptive/associative analysis as a contrafactual "what if the window
  were shorter" backtest -- that would require a different, explicitly causal design this phase
  does not attempt.
- S82 (selection/candidate audit, read-only, verbatim): audit whether the source pipeline retains
  candidate/non-executed-signal counts; `funnel_2015plus_run2.csv` does (model-specific
  `windows_considered`/`triggers_with_key_level`/`model1_confirmed`/`never_filled` columns; a
  caveat flagged, not resolved, on `candidates_built`/`filled` appearing pair- not model-level);
  never re-generate it, never declare a global window-width effect proven from executed trades
  alone.
- S83 (statistics, verbatim): 95% CI on the primary endpoint; block bootstrap; explicit sample
  sizes/denominators/missing-data treatment; one-way sensitivity only (instrument, period, absolute
  vs. relative position, common-support exclusion), never a combinatorial search for the most
  favorable subgroup; 2015-2026 remains previously-examined, not genuine OOS.
- S84 (20 required tests + full suite, verbatim): see `tests/test_phase7_requirements.py`'s
  coverage-map docstring for the 1-20 requirement-to-test mapping; re-run the existing 150 tests;
  never hide or change a test just to get green.
- S85 (deliverables, verbatim): A Phase 6 Sensitivity Correction; B Confirmation Window
  Reconstruction; C Temporal Feature Dataset; D Confirmation Timing Distribution; E E1 Association
  Analysis; F Support and Selection Audit; G Research Verdict -- classify into exactly one of
  `TIMING_ASSOCIATION_EXPLAINS_MUCH_OF_GAP`, `TIMING_ASSOCIATION_PARTIALLY_REDUCES_GAP`,
  `E1_DIFFERENCE_PERSISTS_AFTER_TIMING_ADJUSTMENT`, `INSUFFICIENT_TEMPORAL_OVERLAP`,
  `INCONCLUSIVE`, with numeric justification, never converting a statistical reduction into a
  causal demonstration; H Phase 8 Recommendation (one hypothesis, not evaluated); I Checkpoint.
  Commit and push to origin if correct; stop at the end of Phase 7 -- no Phase 8 without explicit
  authorization, no contrafactual window re-simulation, no RR/SL/TP/entry-parameter optimization,
  no ML, no new strategies.

## Phase 7 tasks

| ID | Linked S# | Route | Status | Commit |
|----|-----------|-------|--------|--------|
| T49 | S73 | inline | done | `stats/sensitivity_scenarios.py` (S2 fix); `tests/test_sensitivity_scenarios.py` (net +4); `docs/46` |
| T50 | S74,S75 | inline | done | `features/confirmation_window_features.py`; `tests/test_confirmation_window_features.py` (12); `docs/47`; correction banner on `docs/41` |
| T51 | S76 | inline | done | `stats/temporal_feature_dataset.py`; `tests/test_temporal_feature_dataset.py` (4); `docs/48` |
| T52 | S77 | inline | done | `stats/confirmation_timing_distribution.py`; `tests/test_confirmation_timing_distribution.py` (4); `docs/49` |
| T53 | S78,S79,S80 (depends on T50,T51) | inline | done | `stats/e1_timing_association.py`; `tests/test_e1_timing_association.py` (6); `docs/50` |
| T54 | S82 | inline | done | `docs/51` (read-only, no new module) |
| T55 | S84 | inline | done | `tests/test_phase7_requirements.py` (1); full suite 180 passed, lint-imports 11/11 |
| T56 | S81,S85(G,H) | inline | done | `docs/52-53` |

### Phase-7 headline

A mandatory pre-analysis correction (S73) fixed a real bug in Phase 6's S2 bounds (cross-model
pairing error) -- corrected identified interval [+8.22pp, +9.63pp], verdict unaffected. The main
investigation's own Unit A then found that Phase 6's own Model Construction Audit was wrong about
the 9AM window: the ledger-generating pipeline (`run_d1_d2_d3.py`'s "D3" config) actually uses a
240-minute 9AM window (09:00-13:00 NY), not the 90-minute static config Phase 6 cited -- reversing
the "1AM has the longer window" premise entirely (1AM's 120min is now the SHORTER one). Testing
confirmation-window POSITION as an explanation for Phase 6's +5.38pp E1 gap: standardizing on
absolute elapsed minutes FAILS common support (50.3% of 9AM has no 1AM counterpart, since 1AM's
window structurally cannot reach past 120 minutes) -- confirming the brief's own section-9 concern
empirically. Standardizing on RELATIVE position within each model's own window (full common
support; both models share an identical median relative position of 0.625) leaves the gap
unchanged: +5.42pp vs. +5.38pp unadjusted. Verdict: `E1_DIFFERENCE_PERSISTS_AFTER_TIMING_ADJUSTMENT`
-- confirmation timing does not explain the gap either, joining `risk_atr` (Phases 5/6) as a
tested-and-ruled-out candidate. `atr_m15_at_entry` and `cost_to_risk_ratio` remain the only
untested candidates from Phase 5's original list, recommended for Phase 8 (not evaluated this
phase).

## Phase 8 specs (S86+)

- S86 (checkpoint + provenance verification, verbatim): start from checkpoint `cefc88e`. Verify, by
  reading `run_d1_d2_d3.py`/`run_c1_c2.py` directly, exactly why `candidates_built`/`filled`/
  `never_filled`/`skipped_no_placement` appear duplicated across the `1am`/`9am` rows of the same
  (pair, arm) in `funnel_2015plus_run2.csv` -- never assume a column's granularity from the
  presence of a `model` column alone. Never correct the original CSV; any fix must be a derived,
  reproducible reconciliation inside this lab.
- S87 (observation units, verbatim): formally define each funnel stage's TRUE observation unit
  (window, trigger-direction, signal, candidate, trade) before computing anything; never divide
  counts across incompatible units; distinguish windows that produce 0/1/2 triggers explicitly;
  report an impediment rather than inventing an unidentifiable rate.
- S88 (diagnostic adapter, verbatim): reuse `run_d_c2`/`build_stage6_population`/`fill_pass_c`
  UNMODIFIED to recover the per-model split of stages the pooled `pop_stats` cannot provide;
  respect D3/C2 exactly (`anchor_source="new"`, `windows_9am="new"`); never modify rules, never
  reoptimize, never use post-entry information for a never-filled candidate; never write to
  `audit/2026-11-17-causal-lookahead-audit/`; cross-check the reconstruction's own per-model sums
  against the unmodified function's pooled return value before trusting it.
- S89 (reconciliation, verbatim): sum by instrument must equal sum by model must equal the ledger
  baseline (1AM 620/619/1, 9AM 1427/1424/3, total 2047/2043/4); E1 must still reproduce 72/619 and
  89/1424 exactly; detect duplicate identifiers; report unresolvable identifiers explicitly; never
  accept an unexplained discrepancy silently.
- S90 (conversion rates, verbatim): only compute a rate when numerator/denominator share an
  observation unit linked by a verified relationship; `P(E1 | executed trade)` is never equated
  with `P(executed E1 | trigger)` nor with any notion of "probability of losing an opportunity that
  never existed"; one-way comparisons only (instrument, period), never a combinatorial subgroup
  search.
- S91 (selection characterization, verbatim): compare confirmed/placed/never-filled/executed
  populations using only features knowable at the instant in question; `atr_at_order_placement`/
  `planned_risk_atr_at_order_placement` (new, computed at `order_placed_ts` with bars closed
  strictly before it) kept explicitly distinct from Phase 4/5's `atr_m15_at_entry`/`risk_atr`
  (computed at `entry_ts`, unavailable for never-filled candidates) -- never assumed numerically
  identical. No predictor, classifier, or threshold search of any kind.
- S92 (E1 interpretation, verbatim): do not alter Phases 5-7's historical E1 results; describe how
  the funnel findings should inform (not revise) their interpretation; no new adjustment variable
  introduced merely because its distribution looks like it might explain the gap.
- S93 (statistics, verbatim): exact counts; rates with an explicit, unit-checked denominator;
  checksums of every provenance source; duplicate/missing-identifier detection; one-way sensitivity
  by instrument/period only; no CI invented where temporal dependence has not been modeled; no
  causal language for any funnel-stage association; 2015-2026 remains previously-examined, no
  genuine OOS.
- S94 (25 required tests + full suite, verbatim): see `tests/test_phase8_requirements.py`'s
  coverage-map docstring for the 1-25 requirement-to-test mapping; re-run the existing 180 tests;
  never hide or change a test just to get green.
- S95 (deliverables, verbatim): A Funnel Provenance Audit; B Model-Specific Funnel Reconstruction;
  C Identity & Cardinality Audit; D Funnel Conversion Report; E Execution Selection Analysis; F E1
  Interpretation Review; G Research Verdict -- two labels (integrity + selection) from
  `FUNNEL_RECONSTRUCTED_AND_RECONCILED`/`MATERIAL_EXECUTION_SELECTION_DIFFERENCE`/
  `NO_MAJOR_SELECTION_DIFFERENCE_DETECTED`/`PARTIAL_FUNNEL_RECONSTRUCTION`/
  `INSUFFICIENT_EVENT_LEVEL_PROVENANCE`, criteria fixed before inspecting results; H Phase 9
  Recommendation (one hypothesis, not evaluated); I Checkpoint. Commit and push to origin if
  correct; stop at the end of Phase 8 -- no Phase 9 without explicit authorization, no predictors,
  no ML, no new strategies, no contrafactual window re-simulation.

## Phase 8 tasks

| ID | Linked S# | Route | Status | Commit |
|----|-----------|-------|--------|--------|
| T57 | S86 | inline | done | `docs/56-funnel-provenance-audit.md` |
| T58 | S87 | inline | done | `docs/57-phase8-design-and-pre-registration.md` |
| T59 | S88 (depends on T58) | inline | done | `extract/funnel_reconstruction.py`; `tests/test_funnel_reconstruction.py` (11) |
| T60 | S89 (depends on T59) | inline | done | `stats/funnel_reconciliation_report.py`; `tests/test_funnel_reconciliation_report.py` (5); `docs/58-59` |
| T61 | S90 | inline | done | `docs/60` |
| T62 | S91 (depends on T59) | inline | done | `docs/61` (covariates added to `extract/funnel_reconstruction.py`) |
| T63 | S92 | inline | done | `docs/62` |
| T64 | S94 | inline | done | `tests/test_phase8_requirements.py` (2 + coverage map); full suite 198 passed, lint-imports 11/11 |
| T65 | S95(G,H,I) | inline | done | `docs/63-65` |

### Phase-8 headline

Traced `candidates_built`/`filled`/`never_filled`/`skipped_no_placement`'s duplication across
model rows exactly to `run_c1_c2.process_arm`'s pooled `pop_stats` dict, merged verbatim into both
rows -- confirmed in the real CSV (EURUSD/USDCAD/AUDUSD all show byte-identical values on their
1am/9am rows). A read-only diagnostic adapter, reusing the original D3/C2 pipeline functions
unmodified, reconstructed the true per-model split and cross-checked its own sums against the
unmodified pipeline's pooled output (`matches: true`, all 3 pairs) -- then reconciled EXACTLY
against the ledger baseline (2047/2043/4, E1 72/619 and 89/1424, zero unexplained discrepancy).
The funnel is trustworthy (`FUNNEL_RECONSTRUCTED_AND_RECONCILED`) AND the two models select
materially different populations before a single trade executes
(`MATERIAL_EXECUTION_SELECTION_DIFFERENCE`): 9AM confirms ~2.3-2.5x as many credited triggers into
Model-1 signals as 1AM, consistently across all three pairs -- by far the largest, cleanest
1AM/9AM difference found in this lab so far, plausibly linked to 9AM's longer confirmation window
(Phase 7) but not tested causally. Fill rate given a built candidate, by contrast, is broadly
similar between models. Phases 5-7's E1 results are unchanged; this phase adds that they compare
two differently-selected populations, not that the comparison is invalid. Recommended for Phase 9
(not evaluated this phase): a structural comparison of what Model-1's confirmation criterion
filters on, using the never-confirmed population's own characteristics.

## Phase 9 specs (S96+)

- S96 (checkpoint, verbatim): start from checkpoint `cb97415`. Reconcile against the user's exact
  baseline table (Triggers 1AM=11206/9AM=8712; Confirmations 1AM=1805/9AM=3311; Candidates
  1AM=718/9AM=1806; Executed 1AM=620/9AM=1427; Evaluable 1AM=619/9AM=1424) matching Phase 8's own
  reconstruction totals.
- S97 (event-level identity, verbatim): extend identity verification to prove
  signal_id/stable_id/entry_index/entry_price/model/instrument/direction equality between this
  phase's reconstruction and the ledger; investigate any discrepancy before accepting it, never
  silently.
- S98 (Model-1 rejection mechanism, verbatim): audit `entries/model1.py`/`causal_anchor_v2.py`'s
  real rejection mechanism, distinguishing no-anchor-found/pending/invalidated/window-exhausted;
  verify whether `"model1_pending_or_invalidated"` conflates two distinct situations.
- S99 (rejection taxonomy, verbatim): build a reproducible, multidimensional (never forced
  mutually-exclusive) rejection taxonomy.
- S100 (Stage-6 exclusion rules, verbatim): audit `detector/backtest/population.py`'s Stage-6
  exclusion rules, distinguishing "rule available" vs. "active" vs. "applied" vs. "responsible for
  a specific rejection"; never attribute a rejection to a rule that never evaluated.
- S101 (instrumentation, verbatim): build isolated diagnostic instrumentation ONLY if needed,
  reusing original functions/order/config exactly, with a MANDATORY equivalence test proving the
  instrumented candidate set is identical (not just same length) to the original.
- S102 (reconstruction, verbatim): reconstruct the full rejection funnel by model/instrument/period
  (periods: 2015-2017/2018-2020/2021-2023/2024-2026), reconciling exactly against the stated
  baseline numbers with no unexplained discrepancy.
- S103 (structural comparison, verbatim): compare 1AM vs. 9AM structurally without attributing the
  confirmation-rate gap causally to window duration (no contrafactual re-simulation).
- S104 (causal-availability dictionary, verbatim): build a causal-availability dictionary (Layer 1
  At Trigger / Layer 2 During Confirmation / Layer 3 At Order Placement / Layer 4 After Fill); a
  variable observed after a rejection can never be used as a predictor of that rejection.
- S105 (E1 interpretation, verbatim): review what this means for E1 interpretation WITHOUT
  changing Phases 5-8's historical numbers.
- S106 (25 required tests + full suite, verbatim): see `tests/test_phase9_requirements.py`'s
  coverage-map docstring for the 1-25 requirement-to-test mapping; re-run the existing 198 tests;
  never hide or change a test just to get green; synthetic cases required: successful
  confirmation, no anchor, pending, invalidation, expiration, two directions in one window,
  deduplication, geometry rejection, simultaneous rejections, accepted confirmation producing no
  candidate, candidate never filled.
- S107 (deliverables, verbatim): A Event-Level Identity Reconciliation; B Model-1 Rejection
  Taxonomy; C Stage-6 Candidate Attrition Audit; D Reconstructed Rejection Funnel; E Structural
  Comparison 1AM vs. 9AM; F Causal Availability Dictionary; G E1 Interpretation Update; H Research
  Verdict -- two independent dimensions: Integrity
  (`EVENT_LEVEL_RECONCILED`/`PARTIAL_IDENTITY_RECONCILIATION`/`UNRESOLVED_IDENTITY_MISMATCH`) and
  Selection (`CONFIRMATION_REJECTIONS_DOMINATE`/`STAGE6_ATTRITION_MATERIAL`/
  `MULTIPLE_SELECTION_MECHANISMS`/`INSUFFICIENT_REJECTION_PROVENANCE`/`NO_MAJOR_NEW_DIFFERENCE`),
  criteria defined BEFORE inspecting results; I Phase 10 Recommendation (one hypothesis, not
  evaluated); J Technical Checkpoint. Run full suite + lint-imports; review with the usual
  harness; commit and push to origin if correct; stop at the end of Phase 9 -- no Phase 10 without
  explicit authorization, no predictors, no ML, no new strategies, no contrafactual window
  re-simulation.

## Phase 9 tasks

| ID | Linked S# | Route | Status | Commit |
|----|-----------|-------|--------|--------|
| T66 | S96,S98 | inline | done | `docs/67-phase9-design-and-pre-registration.md` |
| T67 | S97 | inline | done | `extract/event_identity_reconciliation.py`; `tests/test_event_identity_reconciliation.py` (8); `stats/event_identity_reconciliation_report.py`; `docs/68` |
| T68 | S98,S99 (depends on T66) | inline | done | `extract/model1_rejection_diagnostics.py`; `tests/test_model1_rejection_diagnostics.py` (7); `docs/69` |
| T69 | S100,S101 (depends on T66) | inline | done | `extract/stage6_attrition_diagnostics.py`; `tests/test_stage6_attrition_diagnostics.py` (5); `docs/70` |
| T70 | S102 (depends on T68,T69) | inline | done | `extract/funnel_reconstruction.py` (extended); `docs/71` |
| T71 | S103 | inline | done | `docs/72` |
| T72 | S104 | inline | done | `docs/73` |
| T73 | S105 (depends on T70) | inline | done | `docs/74` |
| T74 | S106 | inline | done | `tests/test_phase9_requirements.py` (4 + coverage map); full suite 223 passed, lint-imports 11/11 |
| T75 | S107(H,I,J) | inline | done | `docs/75-77` |

### Phase-9 headline

Proved, both analytically (code trace) and empirically (a deterministic regression test on the
real unmodified functions), that `confirm_in_ltf_window_v2`'s retry loop can never return
INVALIDATED as a terminal status -- `"model1_pending_or_invalidated"` is a misnomer for D3: it is
ALWAYS PENDING. Proved all five `_population_cuts` exclusion categories are structurally
impossible for D3/C2, and that `_kill_zone_cut` is available-but-inactive
(`kill_zone_gated=False`): **100% of Stage-6 candidate attrition, for both models, across all
three pairs, is `_rr_floor_cut` alone** -- zero dedup, zero kill-zone. Full event-level identity
reconciliation via `stable_id` matched exactly (2047/2047, zero mismatches); a separate,
investigated finding showed 3 `signal_id` values collide harmlessly across instruments
(`entries/model1.py`'s ID formula carries no instrument/date component) -- explained, with zero
impact on any prior phase. The full rejection funnel reconciled exactly to the user's stated
baseline, and the 1AM/9AM confirmation-rate gap (~16% vs. ~38%) is stable across all four periods
and all three instruments -- not a single-era or single-pair artifact. Verdicts (two independent
dimensions): Integrity = `PARTIAL_IDENTITY_RECONCILIATION` (the strict zero-duplicate-signal_id
bar is not met, though the true primary key reconciles perfectly and the collision is fully
explained); Selection = `MULTIPLE_SELECTION_MECHANISMS` (confirmation-stage rejection dominates in
absolute count for both models, AND Stage-6's RR floor independently removes a material share --
60.2% of 1AM's confirmed signals, 45.5% of 9AM's). Phases 5-8's historical numbers are unchanged;
this phase adds that the two models' EXECUTED populations were already selected at a ~2.4x
differential rate before any trade-level dynamics begin, so the E1 gap can no longer be
interpreted as comparing two comparably-selected samples. Recommended for Phase 10 (not evaluated
this phase): test whether confirmation-stage rejection-taxonomy variation (Layer 1/2) associates
with the eventual E1 outcome (Layer 4) among executed trades, under the same non-causal,
pre-registered discipline.

## Phase 10 specs (S108+)

- S108 (checkpoint, verbatim): start from checkpoint `4b3e9c1`. Audit the real internal
  confirmation-attempt path (anchor restarts, internal invalidations) for Model-1 signals that
  CONFIRM -- Phase 9 found `confirm_in_ltf_window_v2` never returns terminal INVALIDATED, but
  never reconstructed the full internal retry trajectory for confirmed signals.
- S109 (hypotheses, verbatim): H1 confirmation-path complexity is associated with E1 incidence;
  H2 this association may differ between 1AM and 9AM; H3 the 1AM/9AM E1 gap may change when
  descriptively standardized against the path-complexity contrast. No directional prediction
  registered. Observational only, never causal, never profitability.
- S110 (state-machine audit, verbatim): reconstruct from source exactly when an attempt begins,
  what constitutes a new anchor (never a fresh search -- the invalidating candle's own index,
  reused), what constitutes an internal invalidation, when a retry is allowed, when the search
  limit is reached, how the final anchor is selected, when engulf/retest confirm, what information
  is available at each M15 close, and when the order is finally placed. Never interpret an
  internal invalidation as a Stop Loss exit.
- S111 (instrumentation, verbatim): isolated diagnostic within `research/loss-pattern-discovery/`
  only; never modifies the original state machine; distinguishes OBSERVED attempts from
  hypothetical ones; never reads candles after `confirmation_available_at`; equivalence verified
  by comparing sets/identities (stable_id, signal_id within instrument, confirmation_index,
  candidates, fills), never counts alone.
- S112 (identity, verbatim): `stable_id`/`event_id` remains the primary key; no global join on
  `signal_id` alone; cross-instrument collisions never mix histories; the 4 censored trades keep
  their identity; unreconstructable events reported explicitly.
- S113 (descriptive audit before E1, verbatim): describe attempt/invalidation/restart counts,
  confirmation duration, % confirming without vs. with prior invalidations, coverage, by
  instrument and period, BEFORE inspecting any E1 rate. Primary contrast
  `internal_invalidation_count == 0` vs. `>= 1`, pre-declared; if degenerate or unidentifiable,
  stop and document why rather than substituting a result-maximizing threshold. Never promote every
  correlated counter into an independent hypothesis.
- S114 (E1 endpoint, verbatim): E1 = `CONFIRMED_STOP AND duration_bars == 1`, reproduced exactly
  (72/619 = 11.63% for 1AM, 89/1424 = 6.25% for 9AM, gap +5.38pp) before any new feature is added.
  Never assign E1 to a signal that never executed; preserve winners in the denominator; never
  silently drop unreconstructable cases from the reported population.
- S115 (primary analysis, verbatim): `P(E1 | ..., internal_invalidation_count == 0)` vs.
  `P(E1 | ..., >= 1)`, WITHIN each model; composition comparison between models (no causal
  attribution to window duration); descriptive standardization of the model gap by the same
  contrast, compared to +5.38pp, never reported as a causal decomposition.
- S116 (robustness, verbatim): reuse only pre-order-available controls; never post-fill
  information (atr_m15_at_entry if post-order, fill timing, MFE/MAE, exit result, rejected-
  confirmation futures); small-N discipline (72/89 E1 events) -- simple comparison, predeclared
  limited controls, report insufficient evidence rather than an unstable model; block bootstrap per
  the lab's own established methodology; separate-by-instrument consistency check, never hiding
  AUDUSD heterogeneity if present.
- S117 (interpretation, verbatim): distinguish Asociación consistente / Asociación heterogénea /
  Sin asociación robusta / Evidencia insuficiente. Never claim invalidations cause E1, that direct
  confirmation is better, that a feature improves profitability, that a result-based filter is
  operable, or that out-of-sample validation occurred.
- S118 (Phase 11 RR proposal, verbatim): register, but do NOT execute, a proposal to investigate
  the Stage-6 RR floor (`min_risk_reward=2.0`, 100% of Stage-6 attrition per Phase 9, 2,592
  confirmed signals discarded). The 2,592 signals are not 2,592 lost trades -- no invented
  executions, no profitability figure for them without an authorized, reproducible counterfactual
  simulation. No change to `min_risk_reward` anywhere; no new RR backtest run.
- S119 (24 required tests + full suite, verbatim): see `tests/test_phase10_requirements.py`'s
  coverage-map docstring for the 1-24 requirement-to-test mapping; re-run the existing 223 tests;
  synthetic cases required: zero/one/multiple restarts, direct confirmation, window exhaustion
  (engulfed-then-pending, never-engulfed), no-anchor-at-all; never weaken an existing test.
- S120 (deliverables, verbatim): A Confirmation State Machine Audit; B Confirmation Path
  Diagnostic; C Event Identity & Causal Availability Audit; D Confirmation Path Distribution; E
  E1 Association Analysis; F Robustness & Selection Limitations; G Research Verdict --
  `CONFIRMATION_PATH_ASSOCIATION_FOUND`/`MODEL_SPECIFIC_ASSOCIATION`/
  `NO_ROBUST_CONFIRMATION_PATH_ASSOCIATION`/`INSUFFICIENT_PATH_RECONSTRUCTION`/
  `INSUFFICIENT_STATISTICAL_EVIDENCE`/`INCONCLUSIVE`, criteria fixed before inspecting E1; H Phase
  11 RR Filter Research Proposal (registered, not run); I Recommendation (prioritize one single
  next unit); J Checkpoint. Run full suite + lint-imports; review with the usual harness; commit
  and push to origin if correct; stop at the end of Phase 10 -- no automatic advance to Phase 11.

## Phase 10 tasks

| ID | Linked S# | Route | Status | Commit |
|----|-----------|-------|--------|--------|
| T76 | S108,S110 | inline | done | `docs/79-phase10-design-and-pre-registration.md`, `docs/80` |
| T77 | S111 (depends on T76) | inline | done | `extract/confirmation_path_diagnostics.py`; `tests/test_confirmation_path_diagnostics.py` (10); `docs/81` |
| T78 | S111 (orchestration, depends on T77) | inline | done | `extract/confirmation_path_reconstruction.py`; `tests/test_confirmation_path_reconstruction.py` (2) |
| T79 | S112 | inline | done | `extract/confirmation_path_identity_audit.py`; `tests/test_confirmation_path_identity_audit.py` (5); `docs/82` |
| T80 | S113 (depends on T78) | inline | done | `stats/confirmation_path_distribution.py`; `tests/test_confirmation_path_distribution.py` (3); `docs/83` |
| T81 | S114,S115 (depends on T79,T80) | inline | done | `stats/confirmation_path_e1_association.py`; `tests/test_confirmation_path_e1_association.py` (4); `docs/84` |
| T82 | S116,S117 | inline | done | `docs/85-86` |
| T83 | S118 | inline | done | `docs/87` (proposal only, no code) |
| T84 | S119 | inline | done | `tests/test_phase10_requirements.py` (4 + coverage map); full suite 251 passed, lint-imports 11/11 |
| T85 | S120(I,J) | inline | done | `docs/88-89` |

### Phase-10 headline

Reconstructed the full internal confirmation-attempt trajectory (anchor restarts, internal
invalidations) for every one of the 5,116 confirmed Model-1 signals across all 3 pairs, with
100% coverage and zero unreconstructable events -- proven equivalent to the real, unmodified
`confirm_in_ltf_window_v2`/`_track_anchor` by two dedicated tests comparing full identity, not
just counts. 9AM's confirmed population needs at least one internal invalidation nearly twice as
often as 1AM's (43.9% vs. 27.0%), stable across all instruments and periods. The pre-registered
primary contrast (`internal_invalidation_count == 0` vs. `>= 1`, within each model) found that
signals confirming directly show a HIGHER E1 rate than signals needing a restart -- statistically
distinguishable from zero only in 9AM (+3.39pp, 95% CI [+0.83pp, +5.97pp]), not in 1AM (+1.11pp,
CI includes zero), though both point the same direction and every per-instrument check (AUDUSD
included) agrees in sign. Verdict: `MODEL_SPECIFIC_ASSOCIATION`. Standardizing the persistent
1AM/9AM E1 gap by this same variable leaves it essentially unchanged (+5.11pp vs. +5.38pp
unadjusted) -- confirmation-path complexity does not explain that gap, joining `risk_atr` and
confirmation-window timing as tested-and-ruled-out candidates. Neither model's own point
difference clears this lab's 5pp relevance bar, so this finding is reported as real but small.
Registered, NOT executed: a Phase 11 proposal to investigate whether the Stage-6 RR floor
(100% of Stage-6 attrition, 2,592 confirmed signals discarded, Phase 9) discards economic value --
recommended as the single highest-priority next unit, ahead of further validating this phase's
own (smaller-magnitude) association.
