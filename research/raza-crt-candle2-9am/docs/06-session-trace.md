# Section 2 — What Was Observable at 13:00: One Real Session Traced End-to-End

Example: `EURUSD|d3_c2|9am|2015-05-21T13:00:00|bullish`. Chosen because it actually executed
(so the full chain -- activation through fill and exit -- has real data at every step), it
confirms exactly at 13:00 NY (the population Section 3/4 studies), and its own fill is NOT at the
very first eligible bar (so this specific example is unambiguous; the general ambiguity rate
across the whole population is quantified separately below, using this example only to verify the
MECHANISM, never to claim this one case represents every case).

All times below are from the real M15 series (`_load_symbol_data("EURUSD")`), UTC as stored;
2015-05-21 falls under EDT (UTC-4), so 17:00 UTC = 13:00 NY. The reference candle's own span is
09:00-13:00 NY = 13:00-17:00 UTC (the SAME day, `REFERENCE_IS_PREVIOUS_DAY["9am"] is False`); the
current candle's span is 09:00-13:00 NY = 13:00-17:00 UTC -- wait, both are stated the same by
design (`REFERENCE_HOUR_NY=5`, `CURRENT_HOUR_NY=9`): reference is 05:00-09:00 NY = 09:00-13:00 UTC,
current is 09:00-13:00 NY = 13:00-17:00 UTC. Verified: `reference_low=1.11090`,
`reference_high=1.11813` (from the 09:00-13:00 UTC bucket); the current bucket's own complete span
runs candle index 301287 (13:00 UTC) through 301302 (16:45 UTC), closing at 17:00 UTC.

## The exact bar-by-bar trace

| Index | Timestamp (UTC) | NY local | Event |
|---|---|---|---|
| 301290 | 2015-05-21 13:45 | 09:45 EDT | **Anchor**: low 1.11055 breaks below the reference candle's own low (1.11090) |
| 301291 | 2015-05-21 14:00 | 10:00 EDT | **Engulf**: close 1.11293 closes beyond the anchor's own body high (1.11152) |
| 301292 | 2015-05-21 14:15 | 10:15 EDT | **Retest touch**: low 1.11131 wicks back into the anchor's body range; `retest_open = 1.11291` |
| 301293-301301 | 14:30-16:30 | 10:30-12:30 EDT | Neither closes beyond `retest_open` (1.11291) yet -- the retest sequence is still open |
| **301302** | **2015-05-21 16:45** | **12:45 EDT** | **Model-1 CONFIRMS**: close 1.11329 > 1.11291. This is the M15 bar the brief asks to trace "from its open through its close" -- it is simultaneously the LAST bar of the current H4 candle's own 09:00-13:00 NY span. |
| -- | 2015-05-21 17:00 | 13:00 EDT | `model1_available_ts` = `available_at(candle 301302, 15min)` = 17:00 UTC. **This is the SAME instant the current H4 candle's own close becomes final** (`h4_close_available_ts = current_open_ts + 4h = 13:00 UTC + 4h = 17:00 UTC`). Order placement decision and H4-close finality are the SAME M15-timestamp event here -- not sequential, not resolvable into "before/after" at this data resolution. |
| **301303** | **2015-05-21 17:00** | **13:00 EDT** | `first_fillable_index` (`bisect_left(m15_timestamps, 17:00 UTC)`): entry_price 1.11264 checked against this bar's own [low=1.11277, high=1.11336] -- **1.11264 < 1.11277, no touch**. Not filled here. |
| 301304 | 17:15 | 13:15 EDT | low=1.11302 -- still no touch |
| 301305 | 17:30 | 13:30 EDT | low=1.11280 -- still no touch |
| **301306** | **17:45** | **13:45 EDT** | low=1.11194 -- **1.11264 >= 1.11194, FILLS here**. Matches the real ledger's own `entry_timestamp_broker = 2015-05-21 17:45:00` exactly. |
| -- | 2015-05-22 09:30 | -- | Exit: `WIN`, `r_multiple = +1.557` (from the real ledger, unchanged) |

## General ordering verified against the implementation (not just this one example)

1. **The confirming bar is never itself fill-eligible.** `fill_pass_c`'s own assertion
   (`causal_intrabar.py`: `idx > confirmation_index_by_signal_id[sid]`) guarantees
   `first_fillable_index` is strictly after `confirmation_index` -- a fill during the 12:45-13:00
   NY confirmation bar is structurally impossible, not merely assumed. Verified directly in this
   trace: confirmation at 301302, first-fillable at 301303 (the very next bar), never 301302 itself.
2. **What the simulator assumes for the bar opening at 13:00**: `fill_pass_c` reuses
   `backtest.simulate._fill_sides()`'s own resolution rule -- for a bullish fill, `entry_price >=
   candle.low`; for bearish, `entry_price <= candle.high`. **This checks the bar's ENTIRE [low,
   high] range, not specifically its open** -- there is no special "gap at open" handling for
   fills (unlike exits, which DO check `_exit_gap_beyond` for an immediate-open-beyond-level
   case). A touch anywhere within the 13:00-13:15 NY bar resolves the fill; the exact intra-bar
   instant is never resolvable from OHLC data, by construction, for ANY bar, not only this one.
3. **EST/EDT**: this example falls under EDT; the general ordering (confirming bar = last bar of
   the current H4 span; first-fillable = next bar) is identical in structure for EST dates --
   verified by `complete_feeder_candle_ny`/`ny_anchored_open_utc`'s own DST-aware `zoneinfo`
   conversion, reused unmodified (Phase 7-10's own finding, not re-derived here).

## The event-ordering check the brief specifically asks for

**Of the 119 executed 9AM trades whose `order_placed_ts` lands exactly at 13:00 NY, 66 (55.5%)
ALSO fill at that exact same M15 timestamp** (entry bar == first-fillable bar == the 13:00-opening
bar itself) -- verified directly against the real ledger. **For these 66, the order-placement
decision, the H4 close becoming final, and the fill itself are all the SAME timestamped event; no
ordering among them is resolvable from 15-minute OHLC data.** The remaining 53 fill at a strictly
later bar (as this trace's own example does, filling 3 bars / 45 minutes after first-fillable) --
for those, the close/order-placement instant clearly precedes the fill by at least one full bar,
even though it is still simultaneous with the order-placement decision itself.

## Conclusion for Section 2's own gate

**The close does NOT become available strictly BEFORE the order-placement decision under the
existing model -- it becomes available at the SAME instant**, for every signal in this population
by construction (the confirming M15 bar is always the current H4 candle's own last bar). This is
not "the close cannot be available" (which would stop the analysis here, per the brief's own
fallback) -- it is "the close and the decision are the same event," a different and narrower
finding. Per the brief's own framing, this is treated as passing the timing check for the purpose
of Section 3/4's comparison, with the 66-of-119 same-instant-fill subset carried forward as an
explicitly flagged, reported-separately case, never treated as resolved ordering evidence.
