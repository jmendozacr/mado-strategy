# Pending Changes

Follow-ups registered during planning that are correctly out of scope for their originating change, tracked here so they don't silently vanish. None of these are triaged or planned yet — they're a backlog, not commitments.

## From `crt-pattern-detector-v1`

- **`crt-detector-order-block-breaker`** (M) — standalone ICT-conventional Order Block detector + Breaker Block detector. Deferred because charter-2's own "Order Block" is actually the Model-1 anchor candle (delivered as REQ-17), not this concept; cost/value analysis ranked this pairing as the most expensive, least v1-standalone-valuable work in the original 7-detector graph.
- **`crt-detector-smt-divergence`** — SMT Divergence (charter-3, correlated-pair analysis, e.g. EUR/USD vs DXY).
- **`crt-detector-rejection-block`** — Rejection Block (charter-1 Key Level type).
- **CRT range "currently forming / live" state** — the one in-progress range at the tail of a series (useful for "run against data ending now" live-style use) is invisible under v1's resolved-only rule (REQ-14). Reopening this needs careful design to avoid undoing REQ-14's noise-flood fix — not a named change yet, just a flagged need.

## From `crt-pattern-detector-v1` — verify-report followups

Non-gating audit findings from final verification:
- **Ingestion validation gaps** (F-1) — `high<low`, OHLC outside `[low,high]`, missing/NaN values are silently accepted instead of error-rejected per design.md §4.6
- **Missing determinism fitness function** (F-2) — design.md §4.7 promises hypothesis property test; never implemented
- **CLI filtering asymmetry** (F-3) — `--types` excludes LTF `crt_ranges` but not HTF `htf_crt_ranges` in pair mode
- **Untracked data directory** (F-4) — `pairs/` (61MB real MT5 exports) not in `.gitignore`, at risk of accidental commit
- **Uncommitted work** (F-5) — S-005 onward + all post-acceptance passes not committed; blocks PR until staged
- **Undocumented entry-price logic** (F-6) — `entries/model1.py::_track_anchor` pre-confirmation-breach behavior undocumented/untested

Non-gating usability findings from steward reckoning:
- **CLI status/alignment filters** — today only `--types` available; need `--status` / `--aligned` to narrow results
- **Multi-week chart legibility** — detection density (3.48/candle) makes 9+ day windows unreadable; need zoom guidance or rendering threshold warning
- **Duplicate row disambiguation** — 764 duplicate row-groups with no signal-ID column; need unique identifier or deduplication
- **Legend occlusion** — white legend box hides ~12% of LTF candles at day zoom
- **Slice housekeeping** — `slices.md` S-006 manual-acceptance checkbox still unticked despite 3 passes with documented evidence

## From `crt-detector-backtest-engine`

13 followups surfaced across judgment-day (2 rounds, 4 blind judge passes) and the pre-archive steward reckoning — deliberately not fixed in that change's own fix-now batch (evidenced but not blocking the change's stated outcome, requiring a signed-spec reopen, or explicitly ratified as low-priority by the human at reckoning). Grouped by priority. Also feeds the already-registered `crt-detector-backtest-partial-exits` follow-on change.

**High value** (touch the change's "honest reporting" promise — recommend addressing before `crt-detector-backtest-partial-exits`):
1. **[priority bumped at reckoning with real-data evidence]** `excluded_never_confirmed` bucket / "never confirmed" disclosure label is factually wrong for signals that DID reach a confirming engulf close but never retested (PENDING+`retest_index=None`). Measured ~9% mislabeled at 400-candle scale; at real scale (141,784 signals) the bucket is 64,344 (45% of population), so ~5,800 signals carry a factually wrong disclosure label. The admission logic (`retest_index is None`) is correct — only the label is misleading. Fix requires reopening the signed spec (REQ-40's literal wording) to rename to something like "never retested", then the code. `detector/backtest/simulate.py:155-156`, `detector/viz/trades_table.py:93`.
2. Intra-fill-candle stop-outs (a trade whose own fill candle's range already reaches its stop) are silently excluded from same-candle resolution (spec-conformant, REQ-37 mandates the sweep start at `fill_index+1`) but `metrics_summary.txt` never discloses this optimistic-direction exclusion, asymmetric with REQ-33's deliberate pessimism for same-candle SL+TP ties. Cheap fix: one more disclosure line. `detector/backtest/simulate.py:261/264`, `detector/viz/trades_table.py`.

**Medium** (robustness / spec-text nits, corroborated by 4 independent judge passes across 2 rounds):
3. `risk == 0` → `ZeroDivisionError` reachable at the `simulate()`/`BacktestConfig` library boundary (bypassing the CLI's `sl_buffer > 0` check) via `BacktestConfig(sl_buffer_price=0.0)` + a doji anchor. Fix: validate in `BacktestConfig.__post_init__`. `detector/backtest/levels.py:85,96`, `detector/core/config.py`.
4. `_fixed_decimal` renders any value below ~5e-11 as `"0.0"`, misreporting a configured `--trading-cost`/`--sl-buffer` at that scale. `detector/viz/trades_table.py:112-118`.
5. REQ-34.1's signed spec scenario (bearish gap example) is arithmetically impossible as literally written — code and its test use the correct opposite reading. Needs a spec-text correction, not a code fix. `detector/backtest/simulate.py:133-139`.
6. REQ-52.2's premise ("the `types` parameter was already unused before removal") is factually false against the real baseline — it drove a real branch that got relocated, not removed as dead code. The refactor IS behavior-preserving (verified byte-for-byte), but the REQ's acceptance criterion as written can't be checked, and its tests are presence-only. Needs REQ-52.2 reworded as a relocation-equivalence requirement + a real before/after comparison test. `detector/cli.py:160-195`, `tests/test_cli.py:312-329`, `tests/test_cli_e2e.py:352-369`.
7. Backtest population is read from a pre-`_filter_by_types` snapshot in `cli.py`, not from the post-filter data REQ-40 names — currently correct but structurally fragile: a future change to `_filter_by_types` could desync `detections.csv` from the backtest population silently. `detector/cli.py:119-121`.

**Low** (style/coverage nits — fix opportunistically):
8. `_directional_sides`' `invert_bullish` boolean flag is correct but hard to read; two named helpers would be clearer. `detector/backtest/simulate.py:92-130`.
9. 5 CLI error-path tests assert only exit_code==1, never the message REQ-51.3/32.2 mandate be named (tracked as verify-final finding F-03, not a new item).
10. `include_signal_id` boolean threaded through 7 `_row` call sites in `viz/table.py` — could be decided once at the writer instead.
11. Import grouping inconsistent between `cli.py`/`backtest/metrics.py`/`viz/trades_table.py` vs. the rest of the codebase.
12. Minor test-coverage gaps: order-independence test compares only signal_ids not full Trade tuples; REQ-40.1's sum-invariant test only exercises 3/8 bucket terms (verified not a defect, just under-covered); REQ-45.1's own literal scenario has no dedicated test (verified manually holds); `_KILL_ZONE_BASE` fixture timestamp shift is global rather than confined to the tests that need it.
13. **[from reckoning, human-ratified as low priority — "leave as-is"]** The default `metrics_summary.txt` reads a frictionless average R that is optimistic relative to real trading costs (a cost sweep against real spread data shows the edge crosses breakeven around ~1.25 pips round-trip). The `(frictionless)` label is present and honest, `--trading-cost` works correctly; the gap is that a reader has to run the sweep themselves. Not a code change — a small sensitivity ladder printed alongside the frictionless default, if ever revisited. `detector/viz/trades_table.py`.

## From `docs/` video-capture work

None currently pending — charters 1-5's audit pass is complete.
