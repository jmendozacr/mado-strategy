# Deliverable F — Research Verdict & Checkpoint (Phase 5)

## Verdict: `RESIDUAL_MODEL_ASSOCIATION`

Per the numeric criteria pre-declared in `docs/29-phase5-design-and-pre-registration.md` (section
4), decided BEFORE this table was filled in:

| Criterion | Pre-declared threshold | Observed | Met? |
|---|---|---|---|
| Unadjusted gap relevant | 95% CI excludes 0 AND \|gap\| >= 5pp | +9.35pp, CI [5.85, 12.77] | Yes |
| Common support holds | <=30% of either model's mass unsupported | 0% unsupported, both models | Yes |
| Standardized gap ALSO relevant | 95% CI excludes 0 AND \|gap\| >= 5pp | +9.93pp, CI [6.30, 13.44] | Yes |

All three hold simultaneously -> `RESIDUAL_MODEL_ASSOCIATION`, not `MOSTLY_EXPLAINED_BY_RISK_GEOMETRY`
(which would require the standardized CI to include 0 or shrink below 5pp -- it did neither; if
anything the gap grew slightly).

**What this verdict does and does not claim (brief section 11).** `origin_model` (1AM vs. 9AM) was
never randomly assigned -- it is a property of which HTF trigger condition held at signal time. This
verdict states that the association between model and early-stop rate **survives adjustment for the
one pre-registered candidate confounder (`risk_atr`)**. It does **not** claim that the model
*causes* the earlier stops, and it does **not** claim a model-specific causal mechanism has been
demonstrated. `cost_to_risk_ratio` and `atr_m15_at_entry` (Deliverable B) are correlated with model
but were never tested as adjustment variables -- they remain candidate confounders/mediators for a
future unit, not ruled in or out.

## Files created this phase

- `common/trade_timing.py` -- bar-index-based duration/endpoint helper (M15-timestamp-causal).
- `stats/model_population_audit.py` -- Deliverable A + B data.
- `stats/early_stop_hypothesis.py` -- Deliverables C + D (H1/H2, standardization, mechanism check).
- `stats/secondary_behavioral_adjustment.py` -- Deliverable E (H3).
- `tests/test_trade_timing.py` (6 tests), `tests/test_early_stop_hypothesis.py` (8 tests),
  `tests/test_phase5_requirements.py` (1 test + coverage-map docstring for all 15 required proofs).
- `docs/29` through `docs/35` (this file) -- design/pre-registration + Deliverables A-F.

## Tests

121 tests passed (106 pre-Phase-5 + 15 new), `lint-imports` 11/11 contracts kept. No existing test
was modified, skipped, or deleted to reach green.

## Reproduce

```bash
cd detector
uv run python ../research/loss-pattern-discovery/stats/model_population_audit.py      # A, B
uv run python ../research/loss-pattern-discovery/stats/early_stop_hypothesis.py        # C, D
uv run python ../research/loss-pattern-discovery/stats/secondary_behavioral_adjustment.py  # E
uv run pytest ../research/loss-pattern-discovery/tests -q
uv run lint-imports
```

## Main results (summary; full detail in docs/30-34)

- **A**: win rates close across models (62.3% vs. 60.6% loss rate) -- no major selection-bias
  concern between populations. Duration is the starkest difference: median 21 vs. 6 M15 bars.
- **B**: pre-entry distributions mostly comparable (planned_rr, day-of-week, activation lag,
  recent-range position); `atr_m15_at_entry` lower and `cost_to_risk_ratio` higher for 1AM.
- **C**: H1 unadjusted +9.35pp [5.85, 12.77]; H2 (risk_atr-standardized) +9.93pp [6.30, 13.44] --
  gap does not shrink, H2 not supported. Heterogeneous by instrument (absent in AUDUSD) and by
  period (not significant in 2018-20/2024-26), though always positive in sign.
- **D**: Phase 4's path-integrity gap is mechanically identical to `same_or_next_bar` (0/1262
  mismatches) -- a restatement, not independent information. The underlying duration difference
  itself is unexplained by risk_atr and holds across wins and losses, not just failures.
- **E**: H3 (MAE/recovery gap) also persists in every risk_atr quintile -- consistent with C/D.

## Sample-size changes vs. Phase 4

Phase 4 worked from the 1262-confirmed-stop population only. Phase 5's primary population is the
full 2043 evaluable executed trades (778 win, 1265 loss, 4 `OPEN_CENSORED` excluded) -- explicitly
required by the brief to avoid the selection bias of starting from losses alone. The confirmed-stop
secondary population (1262) is unchanged from Phase 4 and used only to explain Phase 4's own
Deliverable D figures.

## Limitations

- Risk_atr is the only adjustment variable tested; `cost_to_risk_ratio` and
  `atr_m15_at_entry`/feeder-candle construction remain untested.
- The H1 association is heterogeneous by instrument/period -- not a uniform effect.
- Standardization used direct standardization with fixed pooled weights (a documented
  simplification, not a matched/weighted regression); see `docs/29` section 4.
- The 2015-2026 history remains previously-examined, not genuine out-of-sample data, regardless of
  the confidence intervals reported here.
- `origin_model` is observational, not randomly assigned -- association, not causation (see above).

## Commits

See `docs/36-phase5-commit-record.md` for the exact commit SHAs once pushed.

## Recommended next hypothesis (Phase 6, not evaluated now)

Test whether `cost_to_risk_ratio` and/or `atr_m15_at_entry` (both markedly different between models,
Deliverable B) explain more of the early-stop gap than `risk_atr` did -- using the same transparent
standardization/common-support method, same verdict taxonomy, same one-way sensitivity discipline.
If both also fail to explain the gap, the next natural question is the model's own feeder-candle /
confirmation-window construction (not inspected in any phase so far), which is a structural/
mechanical question, not a statistical-adjustment one, and would need a different kind of audit.
