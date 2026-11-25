# Deliverable I — Technical Checkpoint (Phase 8)

## Files created

- `docs/56-funnel-provenance-audit.md` -- Deliverable A.
- `docs/57-phase8-design-and-pre-registration.md` -- Unit B (observation units, pre-registered
  verdict criteria).
- `extract/funnel_reconstruction.py` -- the read-only diagnostic adapter: `ModelFunnelSplit`,
  `reconstruct_for_symbol`, `verify_against_pooled_counts`, `verify_sweep_and_trigger_invariants`,
  `_eligible_and_skipped`, `_covariates_for_group`.
- `docs/58-model-specific-funnel-reconstruction.md` -- Deliverable B results.
- `docs/59-identity-and-cardinality-audit.md` -- Deliverable C.
- `stats/funnel_reconciliation_report.py` -- `build_reconciliation_table`,
  `detect_duplicate_event_ids`, `e1_reconciliation`, `e0_e4_reconciliation`.
- `docs/60-funnel-conversion-report.md` -- Deliverable D.
- `docs/61-execution-selection-analysis.md` -- Deliverable E.
- `docs/62-e1-interpretation-review.md` -- Deliverable F.
- `docs/63-research-verdict-phase8.md` -- Deliverable G.
- `docs/64-phase9-recommendation.md` -- Deliverable H.
- This file -- Deliverable I.
- `tests/test_funnel_reconstruction.py` (11 tests), `tests/test_funnel_reconciliation_report.py`
  (5 tests), `tests/test_phase8_requirements.py` (2 tests + coverage-map docstring for all 25
  required proofs).

## Source of every counter (summary; full trace in docs/56)

| Counter | Source |
|---|---|
| `windows_considered`, `swept_*`, `triggers_with_key_level`, `model1_confirmed`, `zero_signal_reason_categories` | `run_c1_c2.FunnelCounters`, genuinely model-specific, already correct in the real funnel CSV |
| `candidates_built`, `filled`, `never_filled`, `skipped_no_placement` | `run_c1_c2.process_arm`'s pooled `pop_stats`, duplicated verbatim onto both model rows in the real funnel CSV -- reconstructed per-model by `extract/funnel_reconstruction.py` |
| Executed-trade counts, E0-E4 buckets | the real trades ledger (Phase 1's extractor, unchanged) -- always reliable, every row carries its own `model` |

## Tests

198 tests passing (180 prior + 18 new), `lint-imports` 11/11 contracts kept (see Reproduce for the
run). No existing test modified. `test_source_files_untouched_by_phase8_pipeline` hashes the source
ledger, `simulate.py`, `causal/htf_trigger.py`, `causal_intrabar.py`, `causal_anchor_v2.py`,
`run_d1_d2_d3.py`, `run_c1_c2.py`, and `funnel_2015plus_run2.csv` before and after this phase's
pipeline runs -- unchanged.

## Reproduce

```bash
cd detector
uv run python ../research/loss-pattern-discovery/extract/funnel_reconstruction.py       # A/B (heavy: ~20-30min, 3 symbols)
uv run python ../research/loss-pattern-discovery/stats/funnel_reconciliation_report.py   # B/C/D (reads the artifact above)
uv run pytest ../research/loss-pattern-discovery/tests -q
uv run lint-imports
```

## Reproduced counts (summary; full detail in docs/58-60)

- Baseline: 1AM 620/619/1, 9AM 1427/1424/3 -- exact match.
- E1: 72/619 (11.63%) vs. 89/1424 (6.25%), +5.38pp -- exact match to Phases 6/7.
- Confirmation rate: 1AM ~16%, 9AM ~37-40% of credited triggers (all 3 pairs).
- Filled candidates per window: 1AM 4.64-8.76%, 9AM 14.47-16.02% (all 3 pairs).

## Discrepancies

None unexplained. The one apparent discrepancy found during reconciliation (9AM/EURUSD: 492
evaluable vs. 493 reconstructed `filled`) was resolved exactly: one of the four OPEN-censored
trades belongs to 9AM/EURUSD (492 + 1 = 493) -- verified directly against the extracted ledger's
own open-trade list, not assumed.

## Limitations (open)

- `build_stage6_population`'s own internal exclusion-reason breakdown (duplicate/kill-zone/RR-floor)
  is not split per model (docs/57 section 3, an explicit scope boundary).
- The confirmation-rate difference is named as a plausible, untested mechanism for the funnel
  divergence -- not tested causally this phase (recommended for Phase 9).
- `candidates_built`'s 1AM/9AM ratio is heterogeneous across pairs (1.8x-3.5x) and not explained.
- No contrafactual window-width re-simulation was run (explicit boundary, reaffirmed from Phase 7).

## Commits

See `docs/66-phase8-commit-record.md` for the exact commit SHA once pushed.
