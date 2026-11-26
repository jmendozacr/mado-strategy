# Deliverable A — Confirmation State Machine Audit

Full source citations and the 10-question answer set are pre-registered in
`docs/79-phase10-design-and-pre-registration.md` section 1 (written before any new code ran).
This document restates the operative summary as its own deliverable, per the Phase 10 brief.

## The real control flow

```
causal_anchor_v2.confirm_in_ltf_window_v2(candles, window, direction, config):
    (origin_index, anchor) = find_first_valid_anchor(candles, window, direction)   # called ONCE
    purge_target = candles[origin_index]'s own extreme
    loop:
        result = entries.model1._track_anchor(candles, anchor, direction, purge_target, config, origin_index)
        if result is None:               -> terminal NONE   (never engulfed before the window's own end)
        elif result.status != INVALIDATED -> terminal PENDING or CONFIRMED
        else:                             -> anchor = result.confirmation_index; retry (NOT a fresh anchor search)
```

## Key structural clarifications (the part easy to misread)

1. **"A new anchor" on retry is not a new search.** `find_first_valid_anchor` runs exactly once,
   at the top. Every retry reuses the INVALIDATING candle's own index as the next attempt's
   anchor point -- `origin_index`/`purge_target` (from the very first search) never change.
2. **An internal invalidation is never a Stop Loss exit.** It happens strictly before
   `order_placed_ts` -- there is no position open yet. This audit, and every downstream
   deliverable, treats it purely as a confirmation-process event.
3. **The search ceiling never exceeds the confirmation window's own end**, regardless of how many
   retries precede it: `window_end = min(anchor_index + max_retest_lookback, len(truncated) - 1)`,
   and `truncated` is already sliced at the window's own `end_idx + 1` by
   `confirm_in_ltf_window_v2` itself. `max_retest_lookback = 20` (D3's `Model1Config` default).
4. **Algebraic identity**: `confirmation_attempt_count = internal_invalidation_count + 1`, always
   -- every non-terminal attempt is, by construction, `INVALIDATED` (the only status that loops),
   and exactly one terminal attempt ends the loop. `anchor_restart_count` is the identical
   quantity to `internal_invalidation_count` -- there is no other restart mechanism.
5. **Causal availability**: every decision about candle `j` depends only on candles `<= j`, each
   knowable only at `causal_intrabar.available_at(candle, M15_DURATION)` -- its own close, never
   earlier. The order is placed at the close of the exact candle that completes the retest
   (`model1_available_ts == order_placed_ts`).

## What this audit rules out

No interpretation in this phase treats an internal invalidation as a loss, a rejected trade, or a
Stop Loss event of any kind. A confirmed signal's `internal_invalidation_count` describes how many
times its OWN confirmation process restarted before the position ever existed -- a pre-order
structural fact, available in full by `order_placed_ts`, never a post-order outcome.
