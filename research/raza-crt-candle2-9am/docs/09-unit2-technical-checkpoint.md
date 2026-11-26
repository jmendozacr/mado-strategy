# Unit 2 Technical Checkpoint — 13:00-Exact-Confirmation Experiment

## Files created

- `docs/05-correction-2026-11-26.md`, `docs/06-session-trace.md`, `docs/07-thirteen-oclock-protocol.md`,
  `docs/08-thirteen-oclock-results.md`, this file.
- `raza_extract/thirteen_oclock_experiment.py` -- `build_experiment_for_symbol`,
  `reconcile_baseline_against_ledger`; reuses `build_stage6_population`/`fill_pass_c`/
  `_resolve_exits` unmodified, restricted to the 13:00-exact confirmation population, run once for
  baseline (unrestricted-by-close) and once for variant (`close_position == "INSIDE"` only).
- `raza_extract/build_and_save_thirteen_oclock.py` -- per-symbol orchestration (one process per
  symbol, same OOM workaround as Unit 1 and the sibling lab).
- `raza_stats/thirteen_oclock_report.py` -- funnel/decomposition/primary-metric/bootstrap report.
- `tests/test_thirteen_oclock_experiment.py` (3), `tests/test_thirteen_oclock_report.py` (4).

## Verified review findings (Section 1 correction, `docs/05`)

- Entry-bar timestamp vs. order-placement timestamp: 1,104/116/207 (before/at/after 13:00) by
  entry bar, vs. 1,308/119/0 by order placement -- both re-verified exactly against the real
  ledger and the classification artifacts.
- `INSIDE` population: 957 double sweeps, 2,580 single-sided -- re-verified exactly.

## Population and counts (Section 3/4)

232 confirmed 9AM signals pooled (EURUSD 72, USDCAD 81, AUDUSD 79) whose own `model1_available_ts`
equals the current H4 candle's own close-availability instant exactly -- feasibility-checked before
`docs/07` was committed, reconfirmed identically by the full run. Baseline funnel: 232 confirmed ->
140 candidates -> 119 filled -> 118 closed, 1 open. Variant funnel: 232 confirmed -> 38 candidates
-> 28 filled -> 28 closed, 0 open. Baseline's 119 executed trades reconcile 100% against the real
ledger (`reconcile_baseline_against_ledger`, zero mismatches, zero missing).

## Primary result

Paired mean-R difference (variant - baseline, n=231, 1 AUDUSD signal censored): **+0.0179**, 95%
block-bootstrap CI **[-0.154, +0.171]** (218 NY-date blocks pooled across instruments) -- crosses
zero; by-instrument signs disagree (EURUSD +0.107, USDCAD -0.032, AUDUSD -0.013). Per the
pre-declared stop condition in `docs/07`, reported as too small for a useful conclusion at the
primary-metric level. Decomposition: 64 losses avoided (-71.93R total) against 26 gains forgone
(+67.78R total), net +4.15R total-R advantage for the variant arm.

## Tests

16 tests total for this experiment directory: 9 from Unit 1 (7 in
`test_reference_candle_classification.py` + 2 in `test_funnel_and_outcome_report.py`) plus 7 new
from Unit 2 (`test_thirteen_oclock_experiment.py` [3] + `test_thirteen_oclock_report.py` [4]).
All 16 pass. `lint-imports`: 11/11 contracts kept, 0 broken.

## Reproduction commands

See `README.md`'s own Unit 2 section.

## Limitations (stated, not hidden)

- The primary (per-confirmation) metric is explicitly reported as inconclusive -- the CI crosses
  zero and the range dwarfs the point estimate. The per-closed-trade and total-R numbers are
  context for interpreting that inconclusiveness, never a substitute conclusion.
- 66 of 119 executed trades in this population fill at the exact same M15 timestamp as their own
  order placement and the H4 close -- an irreducible ordering ambiguity at 15-minute resolution,
  flagged throughout, never resolved by assumption.
- The variant arm is, by construction, always a subset of what baseline would also execute (every
  `UNAFFECTED` case matches exactly) -- this unit never claims the gate could produce a NEW trade
  baseline would not have taken.
- 2015-2026 remains previously examined; this is an exploratory historical comparison, not an
  out-of-sample validation.
- No change to `min_risk_reward`, Stop Loss, Take Profit, cost model, trading hours, or any
  detector/scanner code. No adoption recommendation.

## Commits

See the commit record appended to `docs/04-commit-record.md` (or a dedicated follow-up) after this
unit's own commits land.

## Final recommendation

This report is the stopping point requested. No further unit begins without explicit new
authorization.
