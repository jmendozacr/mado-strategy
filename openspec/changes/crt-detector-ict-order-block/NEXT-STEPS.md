# Next Steps — Architecture Pivot to Daily-Tier Key Levels

**Status at pause (2026-09-01)**: `crt-detector-ict-order-block` is PAUSED after two full redesigns within this same change (V1 → V2 documented in `spec.md`/`design.md`). A THIRD pivot is now confirmed and required before this change can proceed — do not resume apply work until spec V3 + design V3 exist.

## The pivot, user-confirmed

1. **Timeframe**: Order Block (as a Key Level for confluence) must be detected on **Daily (1D)** candles, not H4. Confirmed against the user's own separate, previously-working tool `crt-scanner_old` (`D:\Josué\Documents\proyectos\crt-scanner_old\core\htf_confluence.py`), which crosses H4 CRT signals against Daily-timeframe Key Levels (FVG/OB/Swing) — a genuine 3-tier hierarchy: **Daily (Key Level) → H4 (CRT signal/purge) → M15 (execution)**. V1 and V2 of this change both computed Order Block on H4 (2-tier: H4 Key Level ↔ H4 purge) — confirmed wrong scope, not just a wrong detection rule.
2. **Invalidation**: stays **first-touch mitigates** (V2's REQ-62, already implemented and tested) — user reconfirmed this explicitly even after seeing conflicting evidence (see below). Do NOT revert to `crt-scanner_old`'s `entry_model.py` close-invalidation rule for this Daily-tier Key Level — that rule belongs to a DIFFERENT concept (see next section).

## Important disentanglement — two different OB concepts in the user's own history, do not conflate them

`crt-scanner_old` contains TWO separate Order-Block-shaped mechanisms that look similar (same 2-candle engulfing detection) but serve different roles:

- **`core/entry_model.py` ("Clutifx")**: an M15 **execution/entry** model. OB found within a CRT setup's own H4-sweep-triggered time window on M15. `check_ob_touch` (price re-enters the zone) is the ENTRY TRIGGER (a good thing — "go"). `check_ob_invalidation` (a candle CLOSES beyond the zone) is what kills it (a bad thing — "the level failed"). This is NOT the Key Level / confluence concept — it's a specific entry-timing mechanism, out of scope for `crt-detector-key-level-confluence`.
- **`core/htf_confluence.py`**: the **confluence gate** concept — Daily Key Levels (FVG/OB/Swing, ALL of them, no freshness/invalidation filtering at all) checked with a **10% tolerance** (`tolerance_ratio * (crt_high - crt_low)`, not exact overlap) against the H4 CRT signal's own swept boundary (`crt_low` for bullish, `crt_high` for bearish — the CRT RANGE's boundary, not necessarily "the purge candle's wick extreme" the way this codebase currently computes it). Picks the MOST RECENT matching level (`max(..., key=lambda kl: kl.time)`) — our current `_key_level_credit_map` picks the OLDEST (`min(..., key=lambda level: level.origin_index)`). This is the closer analog to what we're building, but with two unresolved deltas from our current design (tolerance; recency tie-break) — see Open Questions below.

The user's invalidation answer (first-touch mitigates) applies to the confluence concept, NOT `entry_model.py`'s close-invalidation — these are different mechanisms for different roles, confirmed not to be in conflict once disentangled.

## What this touches

- **`crt-detector-ict-order-block`** (this change): needs spec V3 + design V3. Detection rule (2-candle engulfing, unchanged from V2) now runs on the Daily series instead of H4. `detect_ict_order_blocks` itself likely doesn't change (same pure function over a candle series) — what changes is WHICH series feeds it, and how confluence is checked (H4 CRT range boundary vs Daily zone, not H4 purge wick vs H4 zone).
- **`crt-detector-key-level-confluence-core`** (sub-change #1, FVG, currently PAUSED): built FVG detection on H4 (2-tier), same as this change's V1/V2. Will very likely need the same Daily-tier pivot — its own S-000 code (branch `wip/crt-detector-key-level-confluence-core-s000`) predates this discovery and was never re-examined against it. Do not resume #1 without addressing this.
- **`detector/cli.py`**: needs a THIRD data input (Daily series) — today only `--csv` (LTF/M15) and `--htf-csv` (HTF/H4) exist. New flags needed (`--daily-csv`/`--daily-symbol`, naming TBD), and `pairs/D1/*.csv` (already present in the repo, unused so far) becomes live input.
- **The confluence mechanism itself** (`alignment/htf_ltf.py::_key_level_credit_map`) may need rework: checking a Daily Key Level against an H4 CRT range's boundary is a genuinely different cross-timeframe comparison than the current same-series wick-vs-zone check.

## Open questions for spec V3 (unresolved, do not guess)

1. **Tolerance**: does the 10%-of-CRT-range tolerance from `htf_confluence.py` apply to our confluence check, or does the current codebase's exact-overlap requirement (no tolerance, a deliberate ADR in #1's design) stand? Not asked yet — ask explicitly, don't assume either way.
2. **Which price gets checked**: the CRT range's own `high`/`low` boundary (matching `htf_confluence.py`'s `signal.crt_low`/`crt_high`), or the actual purge candle's wick extreme (current codebase's refinement)? These can differ.
3. **Tie-break among multiple qualifying Key Levels**: most recent (`htf_confluence.py`'s choice) vs oldest (current codebase's choice, inherited from FVG's #1 design). Not yet reconciled.
4. **Does this pivot also apply to FVG** (sub-change #1), and if so, is it addressed as part of resuming #1, or does #2 (this change) need to land first as the reference implementation of the 3-tier pattern before #1 gets touched?
5. **CLI flag naming and whether Daily-loading is mandatory or optional** (pair mode today is already optional via `--htf-csv`/`--htf-symbol`; a third tier likely follows the same optional-pair-mode precedent, but confirm).

## Evidence trail (read before resuming, don't re-derive)

- `sdd/crt-detector-ict-order-block/explore` (obs #463) — original MSS-anchored rule (V1)
- `sdd/crt-detector-ict-order-block/restrictiveness-investigation` (obs #471) — V1's 82-84% exclusion explained (OB dies permanently, rarely reforms)
- `sdd/crt-detector-ict-order-block/recency-window-sweep` (obs #472) — recency-window idea tested, doesn't help (68-86% range)
- Spec V2 / Design V2 (`spec.md`, `design.md` in this folder) — immediate-engulfing detection + first-touch invalidation, ported from `crt-scanner/scanner/detectors/ob_detector.py`
- V2 real-data run (`evidence/real-data-h4-m15.md`) — 98.0-98.4% exclusion, even MORE restrictive than V1 (touch-invalidation kills OBs faster than close-invalidation)
- This document's own evidence: `crt-scanner/scanner/main.py` (OB never actually wired into the live alert pipeline — that pipeline uses TBS+Model1 instead), `crt-scanner/docs/SCANNER_PLAN.md` (original plan: OB/FVG on M15 within a 4h post-TS window, ALTERNATIVE to Model1, not a combined gate — a third mental model, confirmed NOT the one in play here since the user affirmed OB=KeyLevel/Model1=entry-confirmation as the correct relationship), `crt-scanner_old/core/htf_confluence.py` and `crt-scanner_old/core/entry_model.py` (this document's main findings, detailed above)

## Recommended entry point next session

Re-run `sdd-spec` (unfreeze V2 → V3) for `crt-detector-ict-order-block`, addressing Open Questions 1-3 above first (ask the user, don't infer), THEN `sdd-design` V3 for the 3-tier architecture, THEN decide (Open Question 4) whether to apply V3 to this change first or coordinate with #1's resumption.
