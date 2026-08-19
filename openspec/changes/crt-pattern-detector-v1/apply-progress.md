# Apply Progress: crt-pattern-detector-v1

**Scope this run**: `skeleton` (S-000 — Walking Skeleton)
**Mode**: Strict TDD
**Status**: S-000 complete — 8/8 tasks, 19/19 tests passing, import-linter contract KEPT

## Slices Built This Run

| Slice | Scope tag | Status | Tasks Done |
|---|---|---|---|
| S-000 | walking-skeleton | complete | 8/8 |

## Files Changed

| File | Action | What Was Done |
|---|---|---|
| `detector/pyproject.toml` | Created | Python 3.12 project root; hatchling; deps pandas/numpy/matplotlib; dev extras pytest/hypothesis/import-linter; `packages=["core","primitives","ingestion","viz"]`, `include=["cli.py"]` |
| `detector/core/candle.py` | Created | `Candle`, `OHLCSeries` (+ `.up_to(n)`, TDD'd) |
| `detector/core/results.py` | Created | `DetectionStatus` enum (per design §4.3, unused until S-004) |
| `detector/core/config.py` | Created | `SwingConfig` (empty), `DetectorConfig` (nests `swing`) |
| `detector/ingestion/loader.py` | Created | `load_mt5_csv(path, symbol)` — MT5 tab-delimited parse, required-column check, duplicate/non-monotonic timestamp rejection, modal-delta timeframe inference |
| `detector/primitives/swing.py` | Created | `SwingPoint`, `detect_swings()` — strict 3-candle fractal, both kinds |
| `detector/viz/chart.py` | Created | `render_chart()` — candle plot + Swing triangle markers (▽ high / △ low), legend always populated |
| `detector/cli.py` | Created | `main(argv)` — single-series mode only (`--csv`, `--symbol`, `--output-dir`); exit 0/1 |
| `detector/.importlinter` | Created | ADR-01 layers contract scoped to existing packages: `viz : ingestion` / `primitives` / `core` (siblings via `:`) |
| `detector/tests/fixtures/synthetic.py` | Created | `CandleSeriesBuilder` (fluent), `bearish_purge_setup()` (charter-2 [00:05:28] shape) |
| `detector/tests/conftest.py` | Created | `bearish_purge_series` pytest fixture wrapping the builder |
| `detector/tests/test_candle.py` | Created | 2 tests |
| `detector/tests/test_loader.py` | Created | 5 tests |
| `detector/tests/test_swing.py` | Created | 5 tests |
| `detector/tests/test_viz.py` | Created | 3 tests |
| `detector/tests/test_cli.py` | Created | 2 tests |
| `detector/tests/test_fitness_imports.py` | Created | 1 test — shells out to the real `lint-imports` binary, sanity-checked against an injected violation |
| `detector/tests/property/test_no_lookahead.py` | Created | 1 hypothesis property test (Swing, k=1), sanity-checked against an injected lookahead bug |
| `CLAUDE.md` (repo root) | Modified | Added `detector/` subproject section (stack, setup, test/lint/run commands) alongside the existing docs-KB description; corrected the now-inaccurate "no source code" claim with a one-clause exception rather than rewriting the section |
| `openspec/changes/crt-pattern-detector-v1/slices.md` | Modified | S-000 tasks marked `[x]` |

## TDD Cycle Evidence — S-000

| Task | Test (file::name) | Layer | RED evidence | GREEN | Triangulated | Refactored |
|---|---|---|---|---|---|---|
| candle | `test_candle.py::test_up_to_returns_candles_with_index_strictly_less_than_n` | unit | `NotImplementedError` | ✅ | 2 cases | none needed |
| loader | `test_loader.py::test_loads_valid_mt5_csv_with_ascending_timestamps_and_instrument` | unit | `NotImplementedError` | ✅ | n/a — happy path anchor | none needed |
| loader | `test_loader.py::test_rejects_duplicate_timestamps` | unit | `Failed: DID NOT RAISE LoadError` | ✅ | n/a — single case, spec-bounded | none needed |
| loader | `test_loader.py::test_rejects_non_monotonic_timestamps` | unit | `Failed: DID NOT RAISE LoadError` | ✅ | n/a — single case | none needed |
| loader | `test_loader.py::test_rejects_csv_missing_high_column` | unit | `KeyError: '<HIGH>'` (structural, from missing validation) | ✅ | n/a | none needed |
| loader | `test_loader.py::test_infers_timeframe_from_modal_candle_spacing` | unit | `AssertionError: assert '1H' == 'D'` | ✅ | forced generalisation from hardcoded `"1H"` | none needed |
| swing | `test_swing.py::test_detects_fractal_swing_high` | unit | `NotImplementedError` | ✅ | 2 cases (high, then low) | none needed |
| swing | `test_swing.py::test_detects_fractal_swing_low` | unit | `assert 0 == 1` | ✅ | forced the mirrored low branch | none needed |
| swing | `test_swing.py::test_tied_highs_are_not_swings` | unit | n/a — passed immediately (obvious implementation: strict `>` already excludes ties) | ✅ | n/a | none needed |
| swing | `test_swing.py::test_series_shorter_than_three_candles_returns_no_swings` | unit | n/a — passed immediately (`range(1, len-1)` already handles it) | ✅ | n/a | none needed |
| swing | `test_swing.py::test_pre_purge_high_flagged_before_purge_candle_appears` | unit (REQ-06.1 grounded) | n/a — passed immediately (local-window predicate is inherently causal) | ✅ | n/a | none needed |
| no-lookahead | `property/test_no_lookahead.py::test_swing_detection_has_no_lookahead` | property (fitness fn) | n/a — infrastructure/fitness test, not behaviour-driving; sanity-checked by injecting a lookahead bug (caught it — `IndexError` / assertion) | ✅ | 100 hypothesis examples | none needed |
| viz | `test_viz.py::test_render_chart_writes_a_nonempty_png_file` | unit | `NotImplementedError` | ✅ | n/a | none needed |
| viz | `test_viz.py::test_render_chart_always_shows_a_legend` | unit | written after an ad-hoc fix (see Deviations) — not a clean RED | ✅ | n/a | none needed |
| viz | `test_viz.py::test_render_chart_adds_one_marker_per_swing` | unit | written after an ad-hoc fix (see Deviations) — not a clean RED | ✅ | n/a | none needed |
| cli | `test_cli.py::test_main_produces_overlay_png_for_valid_single_series_csv` | unit (e2e-ish, in-process) | `NotImplementedError` | ✅ | n/a | none needed |
| cli | `test_cli.py::test_main_returns_1_and_prints_error_for_malformed_csv` | unit | n/a — passed immediately (error propagation already correct from GREEN) | ✅ | n/a | none needed |
| fitness | `test_fitness_imports.py::test_import_linter_layers_contract_holds` | architectural (fitness fn) | n/a — infrastructure test; sanity-checked by injecting `core → viz` import (caught it) | ✅ | n/a | none needed |

Real end-to-end acceptance also run manually (not a pytest test): `python -m detector.cli --csv <MT5-format sample> --symbol EURUSD --output-dir <dir>` from the repo root → exit 0, `overlay.png` produced (25.8 KB), visually inspected — candles + one Swing High and one Swing Low triangle marker rendered correctly.

## Deviations from Design

1. **Package layout resolved by experiment, not stated explicitly in design.md.** Design's file table shows `detector/core/candle.py` etc. and the CLI contract shows `python -m detector.cli`, which only reconcile if `detector/` acts as an implicit PEP 420 namespace package (for `-m` resolution from the repo root) while `core`/`primitives`/`ingestion`/`viz` are independently top-level-importable (matching ADR-01's bare layer names in the import-linter contract). Verified empirically: `cd detector && uv run pytest` (bare imports via editable install) and `uv run --project detector python -m detector.cli` from repo root (namespace-package resolution) both work correctly. This is the natural reading of the design, not a deviation in substance — flagged because it wasn't spelled out and required verification rather than assumption.
2. **`.importlinter` scoped to only the packages S-000 builds** (`core`, `ingestion`, `primitives`, `viz`) rather than pre-declaring `composite`/`entries`/`alignment`, which don't exist yet — import-linter errors on root_packages that aren't importable. Later slices (S-003 composite, S-004 entries, S-005 alignment) must extend `.importlinter`'s `root_packages` and `layers` when they introduce those packages. `cli.py` is excluded from `root_packages` (import-linter rejects bare-module root_packages, only accepts real packages) — acceptable since nothing imports `cli` back, so there's no upward-import risk the layers contract needs to catch for it.
3. **`viz/chart.py` legend fix + its two covering tests were written after implementing the fix**, not before — a genuine strict-TDD anti-cheating rule violation (rule 3: "no implementation written in advance of its driving test"). Context: the happy-path GREEN step incidentally surfaced a real UserWarning ("no artists with labels") that also violated the Global-facts requirement "legend always shown" — I fixed it inline and added tests retroactively to lock in the behaviour, rather than reverting and doing a clean RED first. Flagged here rather than hidden.
4. **REQ-24 (`detections.csv`) intentionally NOT built in S-000** despite design.md's general Output section mentioning it — slices.md explicitly assigns `viz/table.py` (REQ-24) to S-006, and S-000's covered REQ list (REQ-01/02/06/07/23) and acceptance criteria only require `overlay.png`. Building the CSV now would have required guessing an unspecified Swing-row column mapping (`direction`/`status` don't map cleanly onto `SwingPoint`) — correctly deferred rather than guessed.
5. **`cli.py` argparse scoped to single-series flags only** (`--csv`, `--symbol`, `--output-dir`) — did not pre-declare `--htf-csv`/`--htf-symbol`/`--from-date`/`--to-date`/`--types` even though slices.md's S-000.5 task line says "full arg parsing per design.md §4.6". Resolved this apparent tension in favour of the orchestrator's explicit instruction: "don't pre-build hooks for capabilities not yet specified." S-005/S-006 will extend the parser when pair mode and filters are actually implemented.
6. **Environment bootstrap**: the sandbox had neither `uv` nor Python 3.12 installed. Installed `uv` via `pip install --user uv`, then `uv python install 3.12` (uv-managed CPython 3.12.14). Not a design deviation, but worth recording — a fresh clone of this repo needs the same two bootstrap commands before `cd detector && uv sync --extra dev` works.

## Halt / Issues Found

None — no blocking halts. Deviations above are judgment calls made transparent rather than silent.

## Overall Progress

| Metric | Value |
|---|---|
| Slices in this scope | 1 |
| Slices complete | 1 |
| Slices in progress | 0 |
| Tasks complete | 8/8 |
| Tests passing | 19/19 (pytest) |
| Import-linter | 1/1 contracts kept |

## Next Step

Ready for `/build --scope=happy-path` (or per-slice: S-001, S-002, S-003 can run in parallel per the Build Order in slices.md — all only require S-000).
