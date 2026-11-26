# Technical Checkpoint

## Files created (all new; nothing in `research/loss-pattern-discovery/`, `detector/`, `scanner/`,
## `docs/`, or any original ledger was modified)

- `docs/00-checkpoint-handoff.md`, `docs/01-protocol.md`, `docs/raza-crt-thread.md`,
  `docs/02-results-and-report.md`, `docs/03-technical-checkpoint.md` (this file).
- `raza_extract/reference_candle_classification.py` -- close-position/sweep-side/Raza-direction
  classification, reusing `causal_intrabar.complete_feeder_candle_ny` and the sibling lab's
  `run_d_c2_instrumented`/`_window_open_ts_from_stable_id` unmodified; `build_funnel_for_symbol`
  mirrors `funnel_reconstruction.reconstruct_for_symbol`'s own call sequence to also expose
  per-signal candidate/fill membership.
- `raza_extract/build_and_save.py` -- per-symbol orchestration (one process per symbol, the same
  OOM workaround Phases 9/10 documented).
- `raza_extract/render_chart_examples.py` -- the 4 pre-declared chart examples.
- `raza_stats/funnel_and_outcome_report.py` -- funnel/outcome/timeline aggregation, joining to the
  real ledger (`extract.from_causal_lookahead_audit.extract`, read-only import from the sibling
  lab) for original trade outcomes.
- `tests/conftest.py`, `tests/test_reference_candle_classification.py` (7 tests),
  `tests/test_funnel_and_outcome_report.py` (2 tests).
- `.gitignore` (excludes `artifacts/`/`figures/`, mirroring the sibling lab's own convention).

**Naming note**: this experiment's own `extract`/`stats` packages are named `raza_extract`/
`raza_stats` (not `extract`/`stats`) specifically to avoid a Python package-name collision with
`research/loss-pattern-discovery`'s own `extract`/`stats` packages, both of which are regular
packages (have `__init__.py`) and therefore cannot share a name across `sys.path` entries.

## Data used

The real, unmodified D3/C2 pipeline (`anchor_source="new"`, `windows_9am="new"`, `arm_name="d3_c2"`
-- identical pinning to Phases 8-10), re-run per symbol for the 9AM model only, 2015-01-01+. The
real executed-trade ledger (`trades_d3_c2_2015plus_run2.csv`), read-only.

## Counts (reconciled exactly against the Phase 8-10 baseline -- see `docs/00`)

Per-symbol: EURUSD 2,716 triggers / 1,039 confirmed / 610 candidates / 493 filled; USDCAD 3,036 /
1,202 / 623 / 489; AUDUSD 2,960 / 1,070 / 573 / 445. Pooled: 8,712 / 3,311 / 1,806 / 1,427 -- every
one of these numbers matches the artifact-verified Phase 8-10 baseline exactly.

## Tests

9 tests, all passing: 7 synthetic + real-data in `test_reference_candle_classification.py`
(close-position INSIDE/OUTSIDE/EXACT_BOUNDARY, double-sweep ambiguity, missing-reference/missing-
current handling, and a real-data smoke test proving stage-subset consistency AND that a trigger's
own credited side always stays swept by the complete candle); 2 in
`test_funnel_and_outcome_report.py` (funnel totals reconcile to baseline; order placement is never
after the H4 close).

`lint-imports` (run from `detector/`): 11/11 contracts kept, 0 broken -- no layering violation
introduced.

## Reproduction commands

```bash
cd detector && uv sync --extra dev
uv run python -m pytest ../research/raza-crt-candle2-9am/tests   # 9 tests
uv run python ../research/raza-crt-candle2-9am/raza_extract/build_and_save.py EURUSD
uv run python ../research/raza-crt-candle2-9am/raza_extract/build_and_save.py USDCAD
uv run python ../research/raza-crt-candle2-9am/raza_extract/build_and_save.py AUDUSD
uv run python ../research/raza-crt-candle2-9am/raza_stats/funnel_and_outcome_report.py
uv run python ../research/raza-crt-candle2-9am/raza_extract/render_chart_examples.py
uv run lint-imports   # from detector/
```

## Limitations (stated, not hidden)

- Only the "close back inside the range" rule from Raza's thread is tested -- HTF/LTF bias
  pairing, FVG/old-high/rejection-block key-level prioritization, with-trend/against-trend
  weighting, and SMT are all out of scope for this first comparison.
- The INSIDE-vs-OUTSIDE mean-R difference is a retrospective association within the EXECUTED
  population; Section E establishes it could not have informed any of these specific trades'
  own order placement (order is never placed after the H4 close becomes available).
- `EXACT_BOUNDARY` has only 2 closed trades pooled -- reported, never used for any inference.
- 2015-2026 remains previously examined by the sibling lab's own phases, not genuine
  out-of-sample data for any future prospective test.
- No prospective variant, redesigned window, or new entry/fill rule was built or evaluated --
  Section F names what would be required before attempting one.

## Commits

None. Per this experiment's own closing instruction ("Complete the analysis and stop at the report
for my review"), no commit or push was made -- all work exists only in this worktree, under
`research/raza-crt-candle2-9am/`, pending the user's review.

## Final recommendation

This report is the stopping point requested. No further phase or prospective-variant work should
begin without explicit new authorization, consistent with the sibling lab's own standing charter.
