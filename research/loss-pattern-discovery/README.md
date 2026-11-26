# Loss Pattern Discovery Lab

Independent research line investigating whether losing trades and Stop Loss invalidations of
existing CRT / D3-C2 strategies contain exploitable predictive information — without modifying the
original strategies, charters, or detector rules.

This lab does **not** optimize the existing system and does **not** assume a losing strategy becomes
profitable by inverting its signals. It treats SL events as a source of hypotheses to test, not as
conclusions.

## Status

Phase 10 (Confirmation Path & Early-Stop Association) — see
`../../odd/tasks/loss-pattern-discovery.md` for the live task list,
`docs/06-limitations-and-decisions-log.md` for the running decision log, and
`docs/89-phase10-technical-checkpoint.md` for the current checkpoint. Verdict:
`MODEL_SPECIFIC_ASSOCIATION` — signals that confirm Model-1 directly (zero internal
invalidations) show a higher E1 rate than signals needing at least one internal restart, but this
is statistically distinguishable from zero only within 9AM (95% CI [+0.83pp, +5.97pp]), not within
1AM (CI includes zero), despite both pointing the same direction, and consistently so across all
three instruments. Neither model's point difference clears this lab's own 5pp relevance bar.
Standardizing the persistent 1AM/9AM E1 gap by this same variable leaves it essentially unchanged
(+5.11pp vs. +5.38pp unadjusted) — the gap is not explained by confirmation-path complexity.
Registered, but explicitly NOT executed: a Phase 11 proposal to investigate whether the Stage-6 RR
floor (100% of Stage-6 attrition, Phase 9) discards economic value or correctly filters
unfavorable setups (`docs/87`). Still associations, not causal or tradable claims.

## Layout

```
research/loss-pattern-discovery/
  README.md                        this file
  docs/
    01-objectives-and-hypotheses.md     research questions (not conclusions, not rules to implement)
    02-source-inventory.md              provenance of every historical trade/event source inspected
    03-event-schema.md                  the event schema and why pre/at-stop/post-stop are separated
    04-methodology-safeguards.md        anti-bias protocol (splits, purge/embargo, pre-registration)
    05-excluded-protected-artifacts.md  how the fidelity-audit pilot is excluded without leaking it
    06-limitations-and-decisions-log.md running log of defects found, decisions, open questions
    07-phase2-stop-eligibility-and-atlas.md  Phase 2 design: eligibility taxonomy, Atlas, controls
    08-data-quality-and-limitations-phase2.md  Deliverable D
    09-atlas-results.md                   Deliverable B (Post-Stop-Loss Behavior Atlas results)
    10-control-comparison.md              Deliverable C (matched control comparison results)
    11-research-findings.md               Deliverable E (confirmed/descriptive/hypotheses/inconclusive)
    12-next-research-unit-recommendation.md
    13-phase3-corrections-report.md       Deliverable A (Phase 3 defect root-causes, RED/GREEN proofs)
    14-atlas-corrected-vs-original.md     Deliverable B (explicit before/after comparison)
    15-control-group-audit.md             Deliverable C (match-quality evidence)
    16-recovery-to-entry-analysis.md       Deliverable D (H1/H0, primary + secondary endpoints)
    17-verdict-and-checkpoint.md          Deliverable E/F (verdict + checkpoint, Phase 3)
    18-phase3.1-causal-contract-and-fix.md   control price-causality diagnosis + temporal contract
    19-phase3.1-results-comparison.md        Phase 2 vs. 3 vs. 3.1 explicit comparison
    20-control-robustness-and-seed-sensitivity.md  match-quality + 5-seed continuation check
    21-verdict-and-checkpoint-phase3.1.md    current verdicts + checkpoint (Phase 3.1)
    22-phase4-design-and-pre-registration.md  data audit + feature/threshold pre-registration
    23-pre-entry-feature-audit.md             Deliverable A (Layer A features, win-vs-loss medians)
    24-pre-stop-trajectory-reconstruction.md  Deliverable B (entry-to-SL path, integrity breakdown)
    25-failure-mode-taxonomy.md               Deliverable C (3 independent dimensions)
    26-failure-mode-atlas.md                  Deliverable D (the 10 Atlas questions, answered)
    27-research-findings-phase4.md            Deliverable E
    28-phase5-recommendation-and-checkpoint.md  Deliverable F/G (Phase 4 checkpoint)
    29-phase5-design-and-pre-registration.md  H1/H2/H3, endpoint verification, standardization spec
    30-model-population-audit.md              Deliverable A (full-population audit table)
    31-pre-entry-comparability-report.md      Deliverable B (pre-entry distributions by model)
    32-early-stop-loss-analysis.md            Deliverable C (H1/H2 unadjusted + standardized)
    33-failure-mechanism-explanation.md       Deliverable D (is the integrity gap mechanical?)
    34-secondary-behavioral-analysis.md       Deliverable E (H3, limited)
    35-research-verdict-and-checkpoint-phase5.md  Deliverable F (Phase 5 verdict + checkpoint)
    36-phase5-commit-record.md                 Phase 5 commit SHA
    37-phase6-design-and-pre-registration.md   Deliverable A (execution semantics audit) + S0-S3/taxonomy pre-registration
    38-early-stop-decomposition.md             Deliverable B (E0/E1/E2/E3/E4 by model + instrument)
    39-intrabar-uncertainty-report.md          Deliverable C (sequence-verifiable vs. ambiguous within E0)
    40-sensitivity-analysis.md                 Deliverable D (S0-S3 scenario comparison)
    41-model-construction-audit.md             Deliverable E (1AM/9AM structural differences + ruled-out explanations)
    42-research-verdict-phase6.md              Deliverable F (Phase 6 verdict + checkpoint)
    43-phase7-recommendation.md                Phase 6 Deliverable G (next hypothesis, not evaluated)
    44-phase6-technical-checkpoint.md          Phase 6 Deliverable H + commit record
    45-phase6-commit-record.md                 Phase 6 commit SHA
    46-phase6-sensitivity-correction.md        Deliverable A (Phase 7): S2 cross-model-pairing bug fix
    47-confirmation-window-reconstruction.md   Deliverable B: window reconstruction + 9AM-duration correction
    48-temporal-feature-dataset.md             Deliverable C: field integrity for the temporal feature dataset
    49-confirmation-timing-distribution.md     Deliverable D: timing distributions by model/instrument/period
    50-e1-association-analysis.md              Deliverable E: Models 0-3 (risk + timing standardization)
    51-support-and-selection-audit.md          Deliverable F: funnel/candidate-count audit
    52-research-verdict-phase7.md              Deliverable G (Phase 7 verdict + checkpoint)
    53-phase8-recommendation.md                Deliverable H (next hypothesis, not evaluated)
    54-phase7-technical-checkpoint.md          Phase 7 Deliverable I (checkpoint)
    55-phase7-commit-record.md                 Phase 7 commit SHA
    56-funnel-provenance-audit.md              Deliverable A (Phase 8): candidates_built/filled pooling, traced to source
    57-phase8-design-and-pre-registration.md   Unit B: observation units + pre-registered verdict criteria
    58-model-specific-funnel-reconstruction.md Deliverable B: per-model/instrument funnel, reconciled
    59-identity-and-cardinality-audit.md       Deliverable C: identifier chain, duplicates, multi-signal windows
    60-funnel-conversion-report.md             Deliverable D: identifiable conversion rates only
    61-execution-selection-analysis.md         Deliverable E: filled vs. never-filled covariate comparison
    62-e1-interpretation-review.md             Deliverable F: E1 read in light of selection (no numbers changed)
    63-research-verdict-phase8.md              Deliverable G (Phase 8 verdicts: integrity + selection)
    64-phase9-recommendation.md                Deliverable H (next hypothesis, not evaluated)
    65-phase8-technical-checkpoint.md          Deliverable I (checkpoint)
    66-phase8-commit-record.md                 Phase 8 commit SHA
    67-phase9-design-and-pre-registration.md   structural facts from source + pre-registered verdict criteria (Phase 9)
    68-event-level-identity-reconciliation.md  Deliverable A: stable_id reconciliation + signal_id collision investigation
    69-model1-rejection-taxonomy.md            Deliverable B: Model-1 anchor/engulf/retest rules + full rejection taxonomy
    70-stage6-candidate-attrition-audit.md     Deliverable C: available/active/applied/responsible audit, 100% rr_floor
    71-reconstructed-rejection-funnel.md       Deliverable D: funnel by model/instrument/period, reconciled to baseline
    72-structural-comparison-1am-9am.md        Deliverable E: 1AM vs. 9AM structural differences (no causal claim)
    73-causal-availability-dictionary.md       Deliverable F: Layer 1-4 variable availability dictionary
    74-e1-interpretation-update.md             Deliverable G: E1 read in light of Phase 9 (no historical numbers changed)
    75-phase9-research-verdict.md              Deliverable H: both verdict dimensions, pre-registered criteria applied
    76-phase10-recommendation.md               Phase 9's own Deliverable I: next hypothesis, not evaluated
    77-phase9-technical-checkpoint.md          Phase 9 Deliverable J: checkpoint
    78-phase9-commit-record.md                 Phase 9 commit SHA
    79-phase10-design-and-pre-registration.md  state-machine facts from source + pre-registered H1/H2/H3 + verdict criteria (Phase 10)
    80-confirmation-state-machine-audit.md     Deliverable A: the 10-question answer set, restated as its own deliverable
    81-confirmation-path-diagnostic.md         Deliverable B: instrumentation design, equivalence proofs, synthetic cases
    82-event-identity-and-causal-availability-audit.md  Deliverable C: stable_id reconciliation + no-lookahead proof
    83-confirmation-path-distribution.md       Deliverable D: path-complexity distribution by model/instrument/period
    84-e1-association-analysis.md              Deliverable E: the pre-registered contrast's E1 results
    85-robustness-and-selection-limitations.md Deliverable F: support, heterogeneity, selection caveats
    86-phase10-research-verdict.md             Deliverable G: verdict, criteria applied mechanically
    87-phase11-rr-filter-counterfactual-proposal.md  Deliverable H: Phase 11 proposal, registered, NOT executed
    88-phase10-recommendation.md               Deliverable I: Phase 11 prioritized over further path-association validation
    89-phase10-technical-checkpoint.md         Deliverable J: checkpoint
  schema/      event dataclasses (features_pre_entry / features_at_stop / post_stop_outcomes)
  extract/     reproducible extractors from source experiments into the event schema;
               `funnel_reconstruction.py` (read-only diagnostic adapter reconstructing the
               per-model candidate/fill funnel split, Phase 8; extended in Phase 9 with
               rejection-taxonomy/Stage-6-attribution/period-bucketed counters);
               `model1_rejection_diagnostics.py` (Phase 9: anchor-probe + rejection-category
               diagnostics, `run_d_c2_instrumented`); `stage6_attrition_diagnostics.py` (Phase 9:
               per-rule Stage-6 removal attribution, `build_stage6_population_instrumented`);
               `event_identity_reconciliation.py` (Phase 9: ledger identity reader + comparator);
               `confirmation_path_diagnostics.py` (Phase 10: traced retry-loop mirror,
               `confirm_in_ltf_window_v2_traced`, `run_d_c2_with_confirmation_paths`);
               `confirmation_path_reconstruction.py` (Phase 10: per-symbol orchestration, one
               process per symbol); `confirmation_path_identity_audit.py` (Phase 10: merges
               per-symbol path artifacts, reconciles against the real ledger by `stable_id`)
  eligibility/ stop-event eligibility classification (Phase 2, Unit A); `stop_timing_decomposition.py`
               (E0-E4) + `intrabar_ambiguity.py` (sequence-verifiability taxonomy), Phase 6
  features/    pre-entry (Layer A) feature extraction (Phase 4); `confirmation_window_features.py`
               (Model-1 confirmation window reconstruction + temporal position), Phase 7
  behavior/    post-stop-loss (Layer C) + pre-stop (Layer B) behavior metrics, recovery_analysis.py
  failure_modes/  multidimensional failure-mode classification (Phase 4, Layer B)
  control/     matched control-group sampling, NY-hour matched (Phase 3 fix)
  common/      shared utilities (cached OHLCSeries timestamp index; `ny_time.py` NY wall-clock
               conversion; `trade_timing.py` bar-index-based duration/endpoint, Phase 5)
  validate/    integrity, chronology, causality and provenance validators
  stats/       descriptive statistics, bootstrap, Atlas orchestration scripts, visualizations,
               Phase-5 early-stop hypothesis + population audit + secondary behavioral adjustment;
               Phase-6 stop-timing decomposition + intrabar-uncertainty report + sensitivity scenarios
               (S2 corrected in Phase 7); Phase-7 temporal feature dataset + confirmation timing
               distribution + E1 timing association; Phase-8 funnel reconciliation report;
               Phase-9 event identity reconciliation report; Phase-10 confirmation path
               distribution + E1 association (`confirmation_path_distribution.py`,
               `confirmation_path_e1_association.py`)
  tests/       pytest suite for every module above
  artifacts/   regenerable derived datasets + figures (gitignored — never commit generated files here)
  config.py    read-only pointer to the main worktree's gitignored `data/` directory
```

## Reproducing

```bash
cd detector && uv sync --extra dev   # once, per worktree
uv run python -m pytest ../research/loss-pattern-discovery/tests   # 251 tests
uv run python ../research/loss-pattern-discovery/stats/eligibility_report.py   # Phase 2 Deliverable A
uv run python ../research/loss-pattern-discovery/stats/atlas.py               # Phase 2/3 Deliverables B/C + recovery analysis
uv run python ../research/loss-pattern-discovery/stats/seed_sensitivity.py    # Phase 3.1 Deliverable D (continuation seed check)
uv run python ../research/loss-pattern-discovery/stats/failure_mode_atlas.py  # Phase 4 Deliverables A-D
uv run python ../research/loss-pattern-discovery/stats/model_population_audit.py        # Phase 5 Deliverables A, B
uv run python ../research/loss-pattern-discovery/stats/early_stop_hypothesis.py         # Phase 5 Deliverables C, D
uv run python ../research/loss-pattern-discovery/stats/secondary_behavioral_adjustment.py  # Phase 5 Deliverable E
uv run python ../research/loss-pattern-discovery/stats/stop_timing_decomposition.py      # Phase 6 Deliverable B
uv run python ../research/loss-pattern-discovery/stats/intrabar_uncertainty_report.py    # Phase 6 Deliverable C
uv run python ../research/loss-pattern-discovery/stats/sensitivity_scenarios.py          # Phase 6 Deliverable D (S2 corrected in Phase 7)
uv run python ../research/loss-pattern-discovery/stats/temporal_feature_dataset.py       # Phase 7 Deliverable C
uv run python ../research/loss-pattern-discovery/stats/confirmation_timing_distribution.py  # Phase 7 Deliverable D
uv run python ../research/loss-pattern-discovery/stats/e1_timing_association.py          # Phase 7 Deliverable E
uv run python ../research/loss-pattern-discovery/extract/funnel_reconstruction.py        # Phase 8/9 (heavy, ~20-30min/symbol; run per-symbol if memory-constrained)
uv run python ../research/loss-pattern-discovery/stats/funnel_reconciliation_report.py    # Phase 8 Deliverables B/C/D
uv run python ../research/loss-pattern-discovery/stats/event_identity_reconciliation_report.py  # Phase 9 Deliverable A
uv run python ../research/loss-pattern-discovery/extract/confirmation_path_reconstruction.py <SYMBOL>  # Phase 10 Deliverable B (one process per symbol, same OOM workaround)
uv run python ../research/loss-pattern-discovery/stats/confirmation_path_distribution.py  # Phase 10 Deliverable D (run after all 3 symbols above)
uv run python ../research/loss-pattern-discovery/stats/confirmation_path_e1_association.py  # Phase 10 Deliverable E
uv run python ../research/loss-pattern-discovery/stats/visualize.py           # figures
```

## Read-only boundary

This lab must never write to, or depend on side effects from: `docs/`, `detector/`, `scanner/`,
`audit/trader-algorithm-fidelity/`, original D3/C2 experiment code/results, or original historical
data files. See `docs/05-excluded-protected-artifacts.md` for how the paused human-fidelity pilot is
kept out of this analysis.

## Reproducing derived datasets

Every file under `artifacts/` must be regenerable from a documented command. See each script's
`--help` and `docs/02-source-inventory.md` for the exact command used to produce each artifact.
