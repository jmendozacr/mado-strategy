# Deliverable E — Verdict

## `NO_DIFFERENTIAL_RECOVERY_EVIDENCE`

The primary, pre-registered endpoint -- P(recovery to the original entry within 24 calendar hours),
confirmed SL vs. a matched control at the same NY hour/volatility/target distance -- shows a
difference of **+1.66 percentage points, 95% CI [-1.67pp, +5.06pp]**. The CI crosses zero, and the
point estimate is below the pre-declared 5-point relevance bar regardless. **H0 (no relevant
difference) is not rejected.** This is accepted as the answer, not forced toward a positive result:
recovery-to-entry, on its own, does not contain a statistically distinguishable signal from ordinary
comparable market behavior in this dataset, at this precision.

This does **not** mean "equivalence is proven" -- only that this analysis, at this sample size and
this endpoint, did not detect a relevant difference. The 85.4%/85.5% recovery-by-3d figures remain
true, interesting descriptive facts about this dataset; they are not promoted to a strategy, and no
new subgroup search was run looking for a horizon, pair, or period where a positive result might
appear.

## A separate, material correction this phase also produced (not part of the recovery verdict)

Fixing the control-matching defect (Deliverable B/C) reversed Phase 2's unrelated conclusion about
the **continuation/reversal split**: properly NY-hour-matched controls show SL events have
~4.4 percentage points LESS continuation than a comparable ordinary moment (CI excludes zero at
4h/1d/3d). This is reported in full in `docs/14-atlas-corrected-vs-original.md` and does not change
the recovery verdict above -- continuation and recovery are different questions -- but it is the
single most important correction from this phase and should not be read past.

## Entregable F — Checkpoint

### Files changed this phase

- `common/ny_time.py` (new) -- NY wall-clock conversion, `zoneinfo`-backed.
- `control/sampling.py` (rewritten) -- NY-hour matching, match tiers, `target_distance`, seeded
  per-bucket shuffle+cap, `audit_match_quality`.
- `behavior/post_stop_metrics.py` (rewritten) -- Defects A/B/C fixed, `classify_gap`, executable-entry
  fields (`recovery_touch_bar_open`, `recovery_confirmed_at`, `recovery_first_actionable_at`,
  `recovery_gap`, `recovery_reference_price`).
- `behavior/recovery_analysis.py` (new) -- Deliverable D's primary/secondary analysis.
- `stats/atlas.py` (updated) -- wired to the fixed control/behavior modules + recovery analysis;
  output renamed `phase3_atlas_corrected.json` (Phase 2's `phase2_atlas.json` filename/contents were
  never reused or overwritten).
- `stats/eligibility_report.py` (updated) -- both denominators (losses-only / losses+open) reported
  explicitly (Defect 3 fix).
- `stats/visualize.py` (updated) -- points at the new corrected-atlas filename.
- `tests/test_control_sampling.py` (rewritten), `tests/test_post_stop_metrics.py` (extended),
  `tests/test_series_index.py`, `tests/test_recovery_analysis.py` (new), `tests/test_bootstrap.py`
  (unchanged, still passing).
- `docs/13` through `docs/17` (this document) -- new. `docs/09`, `docs/10`, `docs/11`, `docs/12`
  (Phase 2) are **unchanged**, kept as historical reference.
- `odd/tasks/loss-pattern-discovery.md` -- Phase 3 specs S27-S35, tasks T17-T22.

### Tests

Full suite: `uv run --project detector python -m pytest research/loss-pattern-discovery/tests`
-- **77 passed** (Phase 1's 18 + Phase 2's 37 + Phase 3's new/modified tests across
`test_control_sampling.py`, `test_post_stop_metrics.py`, `test_series_index.py`,
`test_recovery_analysis.py`). `uv run lint-imports`: 11/11 contracts kept.

### Commands to reproduce

```bash
cd detector
uv run python -m pytest ../research/loss-pattern-discovery/tests
uv run python ../research/loss-pattern-discovery/stats/eligibility_report.py
uv run python ../research/loss-pattern-discovery/stats/atlas.py
uv run python ../research/loss-pattern-discovery/stats/visualize.py
```

### SHA

- Base (Phase 2): `4aadf261371ad1973ebbd397030930f46789f901`.
- This phase's commit: `2f89de9` (fixes + analysis), this doc's own placeholder corrected in the same
  follow-up commit that records it.

### Limitations carried forward (unresolved, not blocking this phase's verdict)

- `docs/06-limitations-and-decisions-log.md`'s L1 (no "valid signal, never executed" comparison group
  for Line A), L9 (control pool is a seeded 400-candidate sample, not exhaustive, though this run hit
  0 unmatched/0 replacement), L10 (one-way stratification only, by design).
- The 1am-vs-9am recovery/MAE gap (first flagged in Phase 2, reinforced here) remains unexplained.
- The continuation-vs-control correction (above) has not itself been stress-tested for stability
  across periods/instruments or sensitivity to the control design -- appropriate for a future unit,
  not performed this phase since the user's Section 6 stability checks are scoped to a relevant
  RECOVERY difference specifically, which did not occur.
- No re-entry rule, parameter optimization, or model training was performed, per the explicit stop
  instruction for this phase.
