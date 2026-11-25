# Loss Pattern Discovery Lab

Independent research line investigating whether losing trades and Stop Loss invalidations of
existing CRT / D3-C2 strategies contain exploitable predictive information — without modifying the
original strategies, charters, or detector rules.

This lab does **not** optimize the existing system and does **not** assume a losing strategy becomes
profitable by inverting its signals. It treats SL events as a source of hypotheses to test, not as
conclusions.

## Status

Phase 4 (Failure Mode Taxonomy & Pre-Entry Feature Audit) — see
`../../odd/tasks/loss-pattern-discovery.md` for the live task list,
`docs/06-limitations-and-decisions-log.md` for the running decision log, and
`docs/28-phase5-recommendation-and-checkpoint.md` for the current checkpoint and the Phase-5
recommendation (the 1AM-vs-9AM mechanism, now evidenced three independent ways).

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
    28-phase5-recommendation-and-checkpoint.md  Deliverable F/G (current checkpoint)
  schema/      event dataclasses (features_pre_entry / features_at_stop / post_stop_outcomes)
  extract/     reproducible extractors from source experiments into the event schema
  eligibility/ stop-event eligibility classification (Phase 2, Unit A)
  features/    pre-entry (Layer A) feature extraction (Phase 4)
  behavior/    post-stop-loss (Layer C) + pre-stop (Layer B) behavior metrics, recovery_analysis.py
  failure_modes/  multidimensional failure-mode classification (Phase 4, Layer B)
  control/     matched control-group sampling, NY-hour matched (Phase 3 fix)
  common/      shared utilities (cached OHLCSeries timestamp index; `ny_time.py` NY wall-clock conversion)
  validate/    integrity, chronology, causality and provenance validators
  stats/       descriptive statistics, bootstrap, Atlas orchestration scripts, visualizations
  tests/       pytest suite for every module above
  artifacts/   regenerable derived datasets + figures (gitignored — never commit generated files here)
  config.py    read-only pointer to the main worktree's gitignored `data/` directory
```

## Reproducing

```bash
cd detector && uv sync --extra dev   # once, per worktree
uv run python -m pytest ../research/loss-pattern-discovery/tests   # 106 tests
uv run python ../research/loss-pattern-discovery/stats/eligibility_report.py   # Phase 2 Deliverable A
uv run python ../research/loss-pattern-discovery/stats/atlas.py               # Phase 2/3 Deliverables B/C + recovery analysis
uv run python ../research/loss-pattern-discovery/stats/seed_sensitivity.py    # Phase 3.1 Deliverable D (continuation seed check)
uv run python ../research/loss-pattern-discovery/stats/failure_mode_atlas.py  # Phase 4 Deliverables A-D
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
