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

## From `docs/` video-capture work

None currently pending — charters 1-5's audit pass is complete.
