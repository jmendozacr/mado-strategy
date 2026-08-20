# Simplify Gate — Apply Report

**Change**: crt-pattern-detector-v1
**Status**: ok — all 8 dedup'd findings from the 4-lens review (reuse, simplification, efficiency, altitude) applied. None skipped or reverted.

## Findings Applied

| # | Lens | Finding | File(s) | Outcome |
|---|---|---|---|---|
| 5 | simplification | Two parallel alignment dicts (`_ALIGNMENT_BORDER_COLORS`/`_ALIGNMENT_BORDER_LINESTYLES`) | `viz/chart.py` | Merged into `_ALIGNMENT_BORDER_STYLE: dict[str, tuple[color, linestyle]]`, single lookup at the call site. |
| 4 | simplification | Duplicated entry-line `LineCollection` block | `viz/chart.py` | Extracted `_add_entry_lines(ax, signals)`, called from `_plot_model1_signals` and `_plot_aligned_signals`. |
| 6 | simplification | Repeated filter-comprehension shape (x7) | `cli.py::_filter_by_date_range` | Extracted local `date_filter(items, series, index_of)` helper; each of the 7 fields now calls it with a lambda for the index attribute. |
| 8 | efficiency | `detect_mss_events` recomputes `detect_swings` even when caller already has them | `composite/mss.py`, `cli.py` | Added optional `swings: list[SwingPoint] \| None = None` param to `detect_mss_events`, matching the established `crt_ranges`/`fvgs`/`ltf_signals`/`htf_ranges` reuse pattern. `cli.py::_detect_all` computes swings once (`ltf_swings`) and passes them to both `_Detections.swings` and `detect_mss_events`. |
| 3 | reuse+altitude | Scatter-grouping pattern repeated 3x | `viz/chart.py` | Extracted `_scatter_grouped(ax, items, position_fn, groups, **scatter_kwargs)` — `groups` is a list of `(predicate, extra_kwargs)` pairs, so it covers both the 1-dimension case (`_plot_mss_events`, `_plot_model1_signals` — group by direction) and the 2-dimension case (`_plot_aligned_signals` — direction x alignment state) with the same helper. |
| 1 | reuse | Duplicate timeframe→duration table (`_TIMEFRAME_DURATIONS` in `alignment/htf_ltf.py` vs `_TIMEFRAME_REFERENCE_DELTAS` in `ingestion/loader.py`) | `core/pairing_table.py`, `alignment/htf_ltf.py`, `ingestion/loader.py` | Hoisted one canonical `TIMEFRAME_DURATIONS: dict[str, timedelta]` into `core/pairing_table.py` (alongside `PAIRING_TABLE`, which already owns the timeframe vocabulary). `htf_ltf.py` uses the dict directly (its native shape). `loader.py` derives its `(timedelta, str)` tuple shape locally via `tuple((delta, tf) for tf, delta in TIMEFRAME_DURATIONS.items())`. |
| 7 | altitude | Duplicate purge-index scan (`entries/model1.py::_first_purge` vs `alignment/htf_ltf.py::_find_purge_index`) | `primitives/crt_range.py`, `entries/model1.py`, `alignment/htf_ltf.py` | Extracted `first_breach_index(candles, start, end, high=None, low=None)` into `primitives/crt_range.py` (next to `CRTRange`). `model1.py` calls it once per side (`high=` xor `low=`, matching its own `side` param shape); `htf_ltf.py` calls it once with both `high=` and `low=` together (matching its single-loop-both-sides shape) — the optional-per-side params cleanly cover both call shapes without an awkward wrapper. Both private wrapper functions (`_first_purge`, `_find_purge_index`) removed — neither was tested directly. |
| 2 | reuse | Duplicate two-heap sweep algorithm (`composite/mss.py::_sweep_decisive_breaks` vs `primitives/fvg.py::_sweep_fill_status`) | `core/sweep.py` (new), `composite/mss.py`, `primitives/fvg.py` | Extracted generic `two_heap_sweep(candles, items, eligible_at, sides, default)` + `SweepSide(belongs, heap_key, resolves, result)` into `core/sweep.py`. Each side is described by a membership predicate, a heap-key function (already sign-adjusted for min/max-heap semantics), a resolve condition (per-side, since fvg.py compares against `candle.low`/`candle.high` while mss.py compares against `candle.close` for both sides), and a result-value function. Both `fvg.py::_sweep_fill_status` and `mss.py::_sweep_decisive_breaks` now build two `SweepSide`s and delegate to `two_heap_sweep` — push order, heap tuple shape `(key, idx)`, and the early-exit condition are unchanged. `test_performance.py` (differential regression against independent reference reimplementations of the original per-instance scans) re-run immediately after this change per the caution note — both tests passed. |

No findings were skipped or reverted — the caution notes on findings 2 and 7 turned out not to force an awkward abstraction in either case.

## Test Evidence

- Full suite after each finding: green throughout, ending at **105 passed** (same count as baseline before any findings).
- `uv run lint-imports` (via `.venv/Scripts/lint-imports.exe`, `uv` not on PATH): **1 kept, 0 broken** — `core` still depends on nothing outside itself; the new `core/sweep.py` only imports `core.candle`, and `core/pairing_table.py`'s new `TIMEFRAME_DURATIONS` only imports stdlib `datetime`. No layering edge changed.
- `tests/test_performance.py` (the differential regression pinning the sweep algorithms against independent reference reimplementations) re-run immediately after Finding 2 and again in the final full run: **2 passed** both times.
- `tests/property/test_no_lookahead.py` (hypothesis property suite): **6 passed** in the final run.

## Files Changed

| File | Action | What |
|---|---|---|
| `detector/viz/chart.py` | Modified | Findings 3, 4, 5 |
| `detector/cli.py` | Modified | Findings 6, 8 |
| `detector/composite/mss.py` | Modified | Findings 8, 2 |
| `detector/primitives/fvg.py` | Modified | Finding 2 |
| `detector/core/sweep.py` | Created | Finding 2 — `two_heap_sweep` + `SweepSide` |
| `detector/core/pairing_table.py` | Modified | Finding 1 — added `TIMEFRAME_DURATIONS` |
| `detector/alignment/htf_ltf.py` | Modified | Findings 1, 7 |
| `detector/ingestion/loader.py` | Modified | Finding 1 |
| `detector/primitives/crt_range.py` | Modified | Finding 7 — added `first_breach_index` |
| `detector/entries/model1.py` | Modified | Finding 7 |

## Next Recommended

Ready for `sdd-verify --mode=final`.
