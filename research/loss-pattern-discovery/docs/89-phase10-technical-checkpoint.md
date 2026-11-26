# Deliverable J — Phase 10 Technical Checkpoint

## Checkpoint

- Starting SHA: `4b3e9c1` (Phase 9's own SHA-record commit).
- Ending SHA: recorded in `docs/90-phase10-commit-record.md` after this phase's commits land.

## Files created

- `extract/confirmation_path_diagnostics.py` + `tests/test_confirmation_path_diagnostics.py` (10)
- `extract/confirmation_path_reconstruction.py` + `tests/test_confirmation_path_reconstruction.py` (2)
- `extract/confirmation_path_identity_audit.py` + `tests/test_confirmation_path_identity_audit.py` (5)
- `stats/confirmation_path_distribution.py` + `tests/test_confirmation_path_distribution.py` (3)
- `stats/confirmation_path_e1_association.py` + `tests/test_confirmation_path_e1_association.py` (4)
- `tests/test_phase10_requirements.py` (4 + coverage-map docstring)
- `docs/79` through `docs/89` (this file)

## Data used

- The real, unmodified D3/C2 pipeline, re-run per symbol (EURUSD, USDCAD, AUDUSD), 2015-01-01+,
  via `run_d1_d2_d3.run_d_c2` (reused byte-for-byte, never reimplemented).
- The real executed-trade ledger (`trades_d3_c2_2015plus_run2.csv`), read-only, unchanged.
- Per-symbol path artifacts: `artifacts/phase10_confirmation_paths_{EURUSD,USDCAD,AUDUSD}.json`
  (gitignored, regenerable by `extract/confirmation_path_reconstruction.py <SYMBOL>`, one process
  per symbol -- the same OOM workaround Phase 9 documented).

## Counts

| | EURUSD | USDCAD | AUDUSD | Total |
|---|---|---|---|---|
| Confirmed signals | 1719 | 1803 | 1594 | **5116** |
| Reconstructed | 1719 | 1803 | 1594 | **5116** |
| Unreconstructed | 0 | 0 | 0 | **0** |

5,116 matches Phase 9's pooled confirmed total exactly (1,805 for 1AM + 3,311 for 9AM).

Identity reconciliation against the real ledger: 2047/2047 executed trades matched, 0 missing,
0 cross-instrument mismatches, 0 duplicate `event_id`s, 4/4 open (censored) trades matched.
Primary-population path-reconstruction coverage: 100.0% (2043/2043).

## Comparisons (summary; full numbers in `docs/83-86`)

| | 1AM | 9AM |
|---|---|---|
| Confirmed, zero invalidation share | 73.0% | 56.1% |
| Primary population, zero-invalidation E1 rate | 12.09% | 8.15% |
| Primary population, >=1-invalidation E1 rate | 10.98% | 4.76% |
| Diff, 95% CI | +1.11pp, [-4.19, +6.36] | +3.39pp, [+0.83, +5.97] |
| Unadjusted model gap | +5.38pp [+2.52, +8.26] | -- |
| Model gap standardized by path complexity | +5.11pp [+2.23, +8.10] | -- |

Verdict: `MODEL_SPECIFIC_ASSOCIATION` (docs/86).

## Tests

251 tests in `research/loss-pattern-discovery/tests/` -- all passed (223 from Phases 2-9 plus
this phase's 28 new tests: 10 + 2 + 5 + 3 + 4 + 4 across the six new test files, reconciling to
251 total). `lint-imports`: 11/11 contracts kept, 0 broken.

## Reproduction commands

```bash
cd detector && uv sync --extra dev
uv run python -m pytest ../research/loss-pattern-discovery/tests   # 251 tests
uv run python ../research/loss-pattern-discovery/extract/confirmation_path_reconstruction.py EURUSD
uv run python ../research/loss-pattern-discovery/extract/confirmation_path_reconstruction.py USDCAD
uv run python ../research/loss-pattern-discovery/extract/confirmation_path_reconstruction.py AUDUSD
uv run python ../research/loss-pattern-discovery/stats/confirmation_path_distribution.py
uv run python ../research/loss-pattern-discovery/stats/confirmation_path_e1_association.py
uv run lint-imports   # from detector/
```

## Checksums of original sources reused, byte-for-byte, never modified

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
| `detector/backtest/levels.py` | `6d8a00695592ea8c` |

Every one of these matches Phase 9's own recorded checkpoint exactly (`docs/77`) -- confirmed
unchanged across this phase, not just assumed. Hash identity before/after the full pipeline run
is additionally a pytest assertion
(`tests/test_phase10_requirements.py::test_source_files_untouched_by_phase10_pipeline`).

## Limitations (stated, not hidden)

- Confirmation paths were reconstructed ONLY for confirmed signals -- rejected signals' own
  taxonomy was already fully characterized in Phase 9 and not re-derived here.
- `first_anchor_found_at`/`final_anchor_found_at` and the other secondary features (docs/79
  section 2) were characterized for causal validity but deliberately NOT tested against E1
  independently, per the brief's own anti-fishing instruction -- only the single pre-registered
  binary contrast was tested.
- Neither model's point difference clears this lab's own 5pp relevance bar (docs/86) -- the
  `MODEL_SPECIFIC_ASSOCIATION` verdict describes a real but small-magnitude effect.
- The composition shift between the confirmed and executed+evaluable populations (docs/84/85) is
  reported but not explained -- understanding why the RR floor interacts with path complexity
  this way is out of this phase's scope.
- 2015-2026 remains previously examined, not genuine out-of-sample data.
- Running all 3 symbols in one process still hits the same OS-level OOM kill Phase 9 found; the
  one-process-per-symbol workaround was reused unchanged.

## Commits

Main commit: see `git log` on `research/loss-pattern-discovery` for this phase's commit, recorded
by a tiny follow-up commit immediately after (`docs/90`), per this lab's standing convention.

## Final recommendation

Phase 11, if authorized: the RR 2.0 filter counterfactual investigation registered in `docs/87`
(NOT executed this phase) -- prioritized over further validating this phase's own association,
per `docs/88`'s explicit reasoning. This phase stops here -- no Phase 11 work without explicit new
authorization.
