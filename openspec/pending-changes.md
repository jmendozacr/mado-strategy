# Pending Changes

Follow-ups registered during planning that are correctly out of scope for their originating change, tracked here so they don't silently vanish. None of these are triaged or planned yet — they're a backlog, not commitments.

## From `crt-pattern-detector-v1`

- **`crt-detector-order-block-breaker`** (M) — standalone ICT-conventional Order Block detector + Breaker Block detector. Deferred because charter-2's own "Order Block" is actually the Model-1 anchor candle (delivered as REQ-17), not this concept; cost/value analysis ranked this pairing as the most expensive, least v1-standalone-valuable work in the original 7-detector graph.
- **`crt-detector-smt-divergence`** — SMT Divergence (charter-3, correlated-pair analysis, e.g. EUR/USD vs DXY).
- **`crt-detector-rejection-block`** — Rejection Block (charter-1 Key Level type).
- **CRT range "currently forming / live" state** — the one in-progress range at the tail of a series (useful for "run against data ending now" live-style use) is invisible under v1's resolved-only rule (REQ-14). Reopening this needs careful design to avoid undoing REQ-14's noise-flood fix — not a named change yet, just a flagged need.

## From `docs/` video-capture work

None currently pending — charters 1-5's audit pass is complete.
