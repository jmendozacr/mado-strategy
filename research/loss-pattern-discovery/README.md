# Loss Pattern Discovery Lab

Independent research line investigating whether losing trades and Stop Loss invalidations of
existing CRT / D3-C2 strategies contain exploitable predictive information — without modifying the
original strategies, charters, or detector rules.

This lab does **not** optimize the existing system and does **not** assume a losing strategy becomes
profitable by inverting its signals. It treats SL events as a source of hypotheses to test, not as
conclusions.

## Status

Phase 8 (Signal Funnel Integrity & Execution Selection Audit) — see
`../../odd/tasks/loss-pattern-discovery.md` for the live task list,
`docs/06-limitations-and-decisions-log.md` for the running decision log, and
`docs/63-research-verdict-phase8.md` for the current checkpoint. Verdicts:
`FUNNEL_RECONSTRUCTED_AND_RECONCILED` (every stage reconciles exactly against the ledger, zero
unexplained discrepancy) and `MATERIAL_EXECUTION_SELECTION_DIFFERENCE` (9AM confirms ~2.3-2.5x as
many credited triggers into Model-1 signals as 1AM, consistently across all three pairs — the
largest, cleanest 1AM/9AM difference found in this lab so far, though not yet tested as an
explanation for the E1 gap). Still associations, not causal or tradable claims.

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
  schema/      event dataclasses (features_pre_entry / features_at_stop / post_stop_outcomes)
  extract/     reproducible extractors from source experiments into the event schema;
               `funnel_reconstruction.py` (read-only diagnostic adapter reconstructing the
               per-model candidate/fill funnel split, Phase 8)
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
               distribution + E1 timing association; Phase-8 funnel reconciliation report
  tests/       pytest suite for every module above
  artifacts/   regenerable derived datasets + figures (gitignored — never commit generated files here)
  config.py    read-only pointer to the main worktree's gitignored `data/` directory
```

## Reproducing

```bash
cd detector && uv sync --extra dev   # once, per worktree
uv run python -m pytest ../research/loss-pattern-discovery/tests   # 198 tests
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
uv run python ../research/loss-pattern-discovery/extract/funnel_reconstruction.py        # Phase 8 Deliverables A/B (heavy, ~20-30min)
uv run python ../research/loss-pattern-discovery/stats/funnel_reconciliation_report.py    # Phase 8 Deliverables B/C/D
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
