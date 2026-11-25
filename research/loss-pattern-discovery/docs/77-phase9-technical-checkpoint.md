# Deliverable J — Phase 9 Technical Checkpoint

## Files created

- `extract/event_identity_reconciliation.py` + `tests/test_event_identity_reconciliation.py` (8)
- `extract/model1_rejection_diagnostics.py` + `tests/test_model1_rejection_diagnostics.py` (7)
- `extract/stage6_attrition_diagnostics.py` + `tests/test_stage6_attrition_diagnostics.py` (5)
- `stats/event_identity_reconciliation_report.py`
- `tests/test_phase9_requirements.py` (4 + coverage-map docstring)
- `docs/67` through `docs/77` (this file)

## Files extended (reused functions unmodified, only new counters/call sites added)

- `extract/funnel_reconstruction.py`: now calls `run_d_c2_instrumented` and
  `build_stage6_population_instrumented` instead of the plain functions; adds
  `rejection_taxonomy_by_model`, `anchor_probe_by_model`, `stage6_removed_by_model`,
  `population_cuts_check`, `triggers_by_model_period`, `confirmed_by_model_period`,
  `reconstructed_identities` to its own result dict. `PERIOD_BUCKETS` exported.

## Original production code reused, byte-for-byte, never modified

| File | SHA-256 (first 16 hex chars) |
|---|---|
| `audit/2026-11-17-causal-lookahead-audit/causal_intrabar.py` | `3886554bfa41e8cb` |
| `audit/2026-11-17-causal-lookahead-audit/causal_anchor_v2.py` | `fd31db1b1b51e6c3` |
| `audit/2026-11-17-causal-lookahead-audit/run_d1_d2_d3.py` | `a184925f3b5379a5` |
| `audit/2026-11-17-causal-lookahead-audit/run_c1_c2.py` | `f8ad3e3738c26c10` |
| `audit/2026-11-17-causal-lookahead-audit/funnel_2015plus_run2.csv` | `9e8d2e9df3e8261b` |
| `audit/2026-11-17-causal-lookahead-audit/trades_d3_c2_2015plus_run2.csv` | `72bbfbf48e982483` |
| `detector/entries/model1.py` | `ce2635c0c08411de` |
| `detector/backtest/population.py` | `a2cb65f03e37f8ef` |

Hash identity before/after the full pipeline run is a pytest assertion
(`tests/test_phase9_requirements.py::test_source_files_untouched_by_phase9_pipeline`), not just a
one-time manual check.

## Reconciliation results (exact match to the user's Phase 9 baseline)

| | 1AM | 9AM |
|---|---|---|
| Triggers with Key Level | 11206 | 8712 |
| Model-1 confirmed | 1805 | 3311 |
| Candidates built | 718 | 1806 |
| Filled | 620 | 1427 |
| Evaluable (closed) | 619 | 1424 |

Event-level identity (`stable_id`): 2047/2047 matched, zero mismatches (Deliverable A).

## Rejection reasons, counts by model (sum of all 3 pairs)

| Reason | 1AM | 9AM |
|---|---|---|
| `no_model1_anchor_found` | 4634 | 1932 |
| `model1_pending_or_invalidated` (always PENDING) | 3464 | 3469 |
| `window_empty_before_search` | 1303 | 0 |

Stage-6 attrition: 100% `_rr_floor_cut` for both models (1087/1087 for 1AM, 1505/1505 for 9AM) --
zero `_dedup`, zero `_kill_zone_cut` (Deliverable C).

## Tests run

223 tests in `research/loss-pattern-discovery/tests/` -- all passed (full suite, including the
198 from Phases 2-8 plus this phase's 24 new tests: 7 + 5 + 8 + 4). `lint-imports`: 11/11 contracts
passed, no new violations.

## Reproduction commands

```bash
cd detector && uv sync --extra dev
uv run python -m pytest ../research/loss-pattern-discovery/tests   # 223 tests
uv run python ../research/loss-pattern-discovery/extract/funnel_reconstruction.py  # per-symbol if memory-constrained
uv run python ../research/loss-pattern-discovery/stats/event_identity_reconciliation_report.py
uv run python ../research/loss-pattern-discovery/stats/funnel_reconciliation_report.py
uv run lint-imports   # from detector/
```

## Limitations (stated, not hidden)

- The anchor probe (Deliverable B) checks only the FIRST `find_first_valid_anchor` call, not every
  intermediate anchor the retry chain cycles through after each internal invalidation.
- The Integrity verdict is `PARTIAL_IDENTITY_RECONCILIATION`, not `EVENT_LEVEL_RECONCILED`, because
  3 harmless cross-instrument `signal_id` collisions exist in the real ledger -- investigated and
  explained, but present.
- The structural comparison (Deliverable E) reports associations between window architecture and
  rejection-category rates, never a demonstrated cause; no counterfactual re-simulation was run.
- Running all 3 symbols in one process hits an OS-level OOM kill on this machine (~16.7GB RAM,
  ~3.48GB free observed); the reproducible workaround is one process per symbol, merged afterward.

## Commits

Main commit: see `git log` on `research/loss-pattern-discovery` for this phase's commit, recorded
by a tiny follow-up commit immediately after, per this lab's standing convention (every prior
phase from 5 onward follows the same two-commit pattern).

## Final recommendation

Phase 10, if authorized: test whether confirmation-stage rejection-taxonomy variation (Layer 1/2,
Deliverable F) associates with the eventual E1 outcome (Layer 4) among executed trades, under the
same non-causal, pre-registered discipline this lab has used since Phase 3 (Deliverable I, full
detail). This phase stops here -- no Phase 10 work without explicit new authorization.
