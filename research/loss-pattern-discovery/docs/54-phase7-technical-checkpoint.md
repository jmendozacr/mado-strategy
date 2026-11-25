# Deliverable I — Technical Checkpoint (Phase 7)

## Files created

- `docs/46-phase6-sensitivity-correction.md` -- Deliverable A (S2 bounds bug fix).
- `docs/47-confirmation-window-reconstruction.md` -- Deliverable B (Unit A), including the
  9AM-window-duration correction discovered during this phase.
- `features/confirmation_window_features.py` -- `ConfirmationWindowFeatures`,
  `compute_confirmation_window_features`, `compute_all_confirmation_window_features`.
- `docs/48-temporal-feature-dataset.md`, `stats/temporal_feature_dataset.py` -- Deliverable C.
- `docs/49-confirmation-timing-distribution.md`, `stats/confirmation_timing_distribution.py` --
  Deliverable D.
- `docs/50-e1-association-analysis.md`, `stats/e1_timing_association.py` -- Deliverable E.
- `docs/51-support-and-selection-audit.md` -- Deliverable F (read-only, no new module).
- `docs/52-research-verdict-phase7.md` -- Deliverable G.
- `docs/53-phase8-recommendation.md` -- Deliverable H.
- This file -- Deliverable I.
- A correction banner added to `docs/41-model-construction-audit.md` (not rewritten).
- `stats/sensitivity_scenarios.py` -- `scenario_s2` corrected (the cross-model pairing bug).
- `tests/test_sensitivity_scenarios.py` -- updated for the corrected S2 (net +4 tests).
- `tests/test_confirmation_window_features.py` (12 tests), `tests/test_temporal_feature_dataset.py`
  (4 tests), `tests/test_confirmation_timing_distribution.py` (4 tests),
  `tests/test_e1_timing_association.py` (6 tests), `tests/test_phase7_requirements.py` (1 test +
  coverage-map docstring for all 20 required proofs).

## Tests

180 tests passing (150 prior + 30 new), `lint-imports` 11/11 contracts kept. No existing test
modified except where the S2 bug fix required it (disclosed in `docs/46`); no test hidden or
weakened to reach green. `test_source_files_untouched_by_phase7_pipeline` hashes the source ledger,
`simulate.py`, `causal/htf_trigger.py`, `causal_intrabar.py`, `causal_anchor_v2.py`, and
`run_d1_d2_d3.py` before and after the full Phase 7 pipeline runs -- unchanged.

## Reproduce

```bash
cd detector
uv run python ../research/loss-pattern-discovery/stats/sensitivity_scenarios.py          # A (corrected)
uv run python ../research/loss-pattern-discovery/stats/temporal_feature_dataset.py       # C
uv run python ../research/loss-pattern-discovery/stats/confirmation_timing_distribution.py  # D
uv run python ../research/loss-pattern-discovery/stats/e1_timing_association.py          # E
uv run pytest ../research/loss-pattern-discovery/tests -q
uv run lint-imports
```

## Main results (summary; full detail in docs/46-53)

- **A**: Phase 6's S2 bug fixed -- corrected identified interval [+8.22pp, +9.63pp] (was
  [+8.50pp, +9.35pp]); Phase 6 verdict unaffected.
- **B**: the 9AM window that actually generated this ledger is 09:00-13:00 NY (240min), not
  09:00-10:30 NY (90min) as Phase 6 stated -- 1AM's 02:00-04:00 NY (120min) is unaffected and
  correct. This REVERSES the "1AM has the longer window" premise both Phase 6 and this phase's own
  brief stated.
- **C**: 0 of 2043 events have missing temporal features; `order_to_fill_minutes` deliberately
  excluded from the predictor set (resolves after entry).
- **D**: median RELATIVE position is identical (0.625) between models despite the 2x absolute
  duration difference.
- **E**: risk_atr-standardized E1 gap unchanged (+5.63pp vs. +5.38pp unadjusted). Absolute-minutes
  timing standardization FAILS common support (50.3% of 9AM unsupported) -- not usable. Relative-
  position timing standardization (full common support) also leaves the gap unchanged (+5.42pp).
- **F**: candidate/non-executed signal counts exist (`funnel_2015plus_run2.csv`) but the
  `candidates_built`/`filled` columns look pair-level, not model-level -- flagged, not resolved.
- **G**: `E1_DIFFERENCE_PERSISTS_AFTER_TIMING_ADJUSTMENT`.

## Sample-size changes vs. Phase 6

None in the primary population (2043 evaluable executed trades, 619 1AM / 1424 9AM). Model 2a/3's
standardization effectively uses fewer 9AM trades (the supported strata only, ~49.7% of 9AM) for
its (untrustworthy) point estimate -- reported explicitly as a consequence of insufficient support,
never substituted for the full population.

## Limitations (open)

- Phase 7's own verdict-category numeric mapping was written after seeing the Model 2/3 results,
  not in a dedicated pre-registration document beforehand (the underlying thresholds themselves
  were fixed since Phase 5 and not altered) -- disclosed in `docs/52`, not hidden.
- The `funnel_2015plus_run2.csv` audit (Deliverable F) flags but does not resolve the
  `candidates_built`/`filled` column ambiguity.
- No contrafactual re-simulation of an alternative window duration was attempted (out of scope,
  brief section 10).
- `atr_m15_at_entry` and `cost_to_risk_ratio` (Phase 5's other two candidate explanatory variables)
  remain untested against E1 specifically -- recommended for Phase 8.

## Commits

See `docs/55-phase7-commit-record.md` for the exact commit SHA once pushed.
