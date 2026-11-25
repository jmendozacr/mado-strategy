# Deliverable E — Independent Verdicts (Phase 3.1)

Continuation and recovery are different questions and are **not** combined into one verdict.

## A. Continuación frente al mercado normal: `SENSITIVE_TO_CONTROL_DESIGN`

Phase 3's apparently significant ~-4.4pp continuation gap (4h/1d/3d, CI excluding zero at 90%) shrinks
to ~-2.6pp and loses significance once the control's own price-causality defect is fixed
(`docs/19-...`). A 5-seed sensitivity check at the 1d horizon (`docs/20-...`) shows the sign stays
negative throughout, but the magnitude ranges from -0.16pp to -2.61pp (>16x spread) and **none** of
the five seeds reach 90%-CI significance. Per the brief's own rule, a sign-stable but
magnitude-fragile, never-significant result is classified as sensitive to control design, not as
persisting exploratory evidence and not as having cleanly disappeared to ~zero either. **No claim of
a continuation effect survives this phase.**

## B. Recuperación hacia la entrada original: `NO_DIFFERENTIAL_RECOVERY_EVIDENCE`

The primary, pre-registered endpoint (P(recovery within 24 calendar hours), 95% CI) moves from
+1.66pp [-1.67,+5.06] (Phase 3) to **+1.11pp [-2.34,+4.53]** (Phase 3.1) -- still crossing zero, still
below the pre-declared 5pp relevance bar. **The fix confirms, rather than overturns, Phase 3's
verdict.** The short-horizon secondary diffs (1h/4h) keep their sign and significance but shrink in
magnitude (`docs/19-...`); per the brief's explicit instruction, this is not promoted to the primary
endpoint or used to change this verdict.

## What neither verdict means

Neither classification demonstrates profitability, an executable trading rule, or genuine
out-of-sample validation. The full 2015-2026 history remains previously-examined data for every
prior research line in this repository (D3/C2's own backtest, its robustness audit, this lab's own
Phases 1-3). No re-entry rule, parameter optimization, or model training was performed this phase,
per the explicit stop instruction.

---

# Deliverable F — Checkpoint

## Files changed this phase

- `control/sampling.py` -- `control_to_event_record` now uses the reference bar's OPEN, not its
  CLOSE, for the synthetic `entry_price`/`stop_loss`/`exit_price`.
- `behavior/recovery_analysis.py` -- same fix in `recovery_control_to_event_record`.
- `stats/seed_sensitivity.py` (new) -- the 5-seed continuation robustness check.
- `tests/test_control_price_causality.py` (new) -- 6 tests: the RED reproduction of the defect, the
  GREEN fix for both constructor functions, an exact-bisect regression, a post-event-movement
  non-contamination check, and an exact-boundary-inclusion check.
- `docs/18` (causal diagnosis + temporal contract), `docs/19` (3-way comparison), `docs/20` (control
  robustness + seed sensitivity), `docs/21` (this document) -- new. `docs/09-17` (Phases 1-3)
  **unchanged**, kept as historical reference.
- `odd/tasks/loss-pattern-discovery.md` -- Phase 3.1 specs/tasks appended.

## Tests

Full suite: `uv run --project detector python -m pytest research/loss-pattern-discovery/tests` --
**83 passed** (77 from Phase 1-3 + 6 new this phase). `uv run lint-imports`: 11/11 contracts kept.

## Commands to reproduce

```bash
cd detector
uv run python -m pytest ../research/loss-pattern-discovery/tests
uv run python ../research/loss-pattern-discovery/stats/eligibility_report.py
uv run python ../research/loss-pattern-discovery/stats/atlas.py
uv run python ../research/loss-pattern-discovery/stats/seed_sensitivity.py
uv run python ../research/loss-pattern-discovery/stats/visualize.py
```

## SHA

- Base (Phase 3): `f040a47aa65e0fe69730b2efe03fa69c3973a998`.
- This phase's commit: `370d434` (fix + re-verification), this doc's own SHA recorded in the same
  follow-up commit pattern used in Phase 3.

## Limitations carried forward

- `docs/06`'s L1 (no "valid signal, never executed" group for Line A), L9/L10 (seeded, non-exhaustive
  control pool; one-way stratification only) remain open, unaffected by this phase.
- The 1am-vs-9am recovery/MAE gap (Phase 2, reinforced in Phase 3 and unaffected by this fix) remains
  unexplained and unexamined this phase.
- The seed-sensitivity check in this phase was deliberately limited to 5 seeds and the continuation
  metric at one horizon (1d), per the brief's own "no investigación extensa" instruction -- it is
  evidence of fragility, not an exhaustive robustness study.
- No change this phase touched `detector/`, the original D3/C2 experiments, or
  `audit/trader-algorithm-fidelity/` (confirmed: only `control/sampling.py`,
  `behavior/recovery_analysis.py`, and new test/doc/script files were modified).
