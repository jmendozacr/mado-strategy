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
