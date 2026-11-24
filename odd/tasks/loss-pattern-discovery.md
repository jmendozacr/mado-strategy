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
