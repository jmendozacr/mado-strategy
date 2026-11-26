# Protocol — Raza H4 FVG Setup + Mado Model-1 M15 Entry, 9AM Session

**Dated and fixed before any real-data outcome is computed.** Restates the brief's own five-step
sequence as exact, reproducible rules, resolving every ambiguity the brief left as a stated
research convention.

## Research question

After a 9AM NY H4 candle sweeps one side of the preceding (05:00-09:00 NY) H4 range into a known
fair-value gap and closes back inside, does a fresh M15 Model-1 setup (searched only from 13:00
onward) offer an executable entry toward the opposite side? Compare against the original D3/C2
population on the same instruments and dates.

## Step 1 — Daily bias (before 09:00 NY)

Reconstruct daily candles anchored to **17:00 NY close** (a NEW candle, built from the M15 series
the same way the existing H4 candles are -- `complete_feeder_candle_ny`'s own bucket/completeness
logic, generalized to a 24-hour span, 96 M15 bars, opening at 17:00 NY) -- **not** the existing
`daily` OHLCSeries loaded from the D1 CSV, which is UTC-midnight-anchored (verified: its own
timestamps are `00:00:00`), not NY-17:00-anchored, and would silently misalign with this protocol's
own stated convention if reused as-is.

Classify the latest COMPLETED daily candle (`C_today`, closed by 09:00 NY when the 9AM session
starts) against the PRECEDING daily candle's own range (`C_yesterday`):

- `sweep_side` (wick-based, same convention as every sweep check in this lab): `HIGH_ONLY` /
  `LOW_ONLY` / `BOTH` / `NEITHER`.
- `close_position` (C_today's own close vs. C_yesterday's range): `INSIDE` (strict, `1e-9`
  tolerance, same convention as `raza-crt-candle2-9am`) / `OUTSIDE` / `EXACT_BOUNDARY`.

**Daily bias**: `LOW_ONLY` sweep + `INSIDE` close -> `bullish`. `HIGH_ONLY` sweep + `INSIDE` close
-> `bearish`. Anything else (`BOTH`, `NEITHER`, `OUTSIDE`, `EXACT_BOUNDARY`, or a missing/incomplete
daily candle on either side) -> **no trade that day** (`NO_DAILY_BIAS`).

## Step 2 — Reference candle and the FVG key level (at 09:00 NY)

Reference = the completed 05:00-09:00 NY H4 candle (`causal_intrabar.complete_feeder_candle_ny`,
reused unmodified -- identical to `raza-crt-candle2-9am`'s own reference candle). "Known at 09:00"
FVG: any H4 fair-value gap from `primitives.fvg.detect_fvgs(h4_series, config.fvg)` (reused
unmodified, the EXISTING gap definition -- no new fill/expiry rule invented) whose own
`end_index`'s candle closes strictly before 09:00 NY. A gap's `fill_status` is NOT checked
(the existing production `fvg_to_key_levels` never sets an expiry for FVG-derived `KeyLevel`s
either -- this protocol follows that same convention, not a new one).

**Gap-sweep requirement**: for a bullish daily bias, the current (09:00-13:00 NY) candle's own LOW
must land strictly inside at least one `bullish`-direction known gap (`gap.bottom <= current_low <=
gap.top`). For bearish, the current candle's own HIGH must land inside a `bearish`-direction gap
(`gap.bottom <= current_high <= gap.top`). If no such gap exists, this is **not** a qualifying
setup (`NO_MATCHING_GAP`) -- it is never counted as a qualifying H4 setup.

## Step 3 — The H4 decision (at 13:00 NY)

Classify the current (09:00-13:00 NY) candle against the reference, reusing the SAME arithmetic as
`raza-crt-candle2-9am`'s own `classify_one` (sweep_side/close_position, `1e-9` tolerance):

- **Qualifies** only if: `sweep_side` is single-sided (`HIGH_ONLY` or `LOW_ONLY`, never `BOTH`),
  `close_position == "INSIDE"` (strict, never `EXACT_BOUNDARY`), the swept side AGREES with the
  daily bias (`LOW_ONLY` only under a `bullish` bias, `HIGH_ONLY` only under a `bearish` bias), and
  Step 2's gap-sweep requirement holds.
- **Unlike `raza-crt-candle2-9am`'s two units, double sweeps are EXCLUDED here** (the brief's own
  explicit "sweep on exactly one side" -- a scope difference from the earlier, purely observational
  experiment, stated so the two are never confused).
- Record: `swept_extreme` (the current candle's own low for a bullish setup, high for bearish) and
  `target_edge` (the reference candle's OPPOSITE edge -- high for bullish, low for bearish).

A setup failing any of these conditions is **not** a qualifying H4 setup and is excluded from the
population this protocol measures (it is a different, unstudied population -- never silently
folded into a "discard" outcome, which is reserved for setups that DO qualify here but fail later).

## Step 4 — The M15 entry search (from 13:00 NY)

**Window**: `[idx(13:00 NY bar), idx(last M15 bar strictly before 15:00 NY)]` -- 8 bars (2 hours),
the same window-truncation discipline `causal_anchor_v2.confirm_in_ltf_window_v2` already uses
(`truncated = candles[:end_idx+1]`) ensures no bar at or after 15:00 is ever read for anchor/
confirmation search.

**Entry mechanism**: `causal_anchor_v2.confirm_in_ltf_window_v2` (reused UNMODIFIED -- the EXACT
same anchor-search + `entries.model1._track_anchor` engulf/retest/retry sequence this whole lab has
verified since Phase 9), called with this window and direction FIXED to the daily bias (never both
directions, unlike the original D3/C2 trigger population, which searches both per H4 candle).
"Both the anchor and confirmation must come from bars opening at or after 13:00" is satisfied
exactly by this function's own `search_start_idx` -- an anchor or confirmation that would only be
findable using an EARLIER bar is structurally unreachable, not specially excluded.

**Pre-entry invalidation scan** (independent of, and compared against, the above): over the SAME
window, the first M15 bar index at which EITHER (a) price re-breaches `swept_extreme` further
(bullish: `candle.low <= swept_extreme`; bearish: `candle.high >= swept_extreme`) OR (b) price
already reaches `target_edge` (bullish: `candle.high >= target_edge`; bearish: `candle.low <=
target_edge`) -- wick-based, same convention as every sweep check in this lab, available only once
that bar's own close is known (causal, no lookahead).

**Resolution** (comparing bar indices directly -- whichever happens first, by construction never
simultaneous with Model-1's own confirmation on the exact bar index since (a)/(b) and confirmation
are checked on the same candle stream):

- If Model-1 CONFIRMS within the window AND (no invalidation occurs, OR it occurs strictly AFTER
  the confirmation index) -> proceed to Step 5 (fill search).
- If invalidation occurs AT OR BEFORE Model-1 would confirm (including when Model-1 never confirms
  at all) -> **DISCARD**, reason `SWEPT_EXTREME_BREACH` or `TARGET_BEFORE_ENTRY` (whichever
  triggered; if both trigger on the same bar, `TARGET_BEFORE_ENTRY` takes precedence, since
  reaching the target is the more specific, intended-outcome-adjacent event).
- If Model-1 never confirms (returns `PENDING` or `None`) and no invalidation ever occurs within
  the window -> **EXPIRED**.

## Step 5 — Entry, stop, target, RR floor, and the fill/cutoff rule

- Entry price/type: `Model1Signal.entry_price`/`entry_type` from the CONFIRMED signal itself
  (Mado's own existing selection, `entries.model1._select_entry` via `_track_anchor` -- reused
  unmodified, never recomputed).
- Stop: `backtest.levels.stop_loss` (reused unmodified; `swings`/`indices` from `detect_swings` on
  the full M15 series, same as the original pipeline).
- **Target (the new rule)**: `backtest.levels.take_profit` (reused UNMODIFIED -- no new formula),
  fed a lightweight context object whose `.high`/`.low` are the REFERENCE candle's own high/low
  (not the original HTF CRT range) -- this is exactly "the opposite reference edge" by
  construction, since `take_profit` already returns `htf_context.high` for bullish / `.low` for
  bearish.
- RR floor: `backtest.levels.risk_reward(entry, stop, target, direction) >= 2.0` (reused unmodified
  formula, SAME 2.0 threshold as the baseline D3/C2 config) -- checked BEFORE an order is ever
  considered placed. A confirmed, non-invalidated signal that fails this floor is recorded as its
  own outcome, `RR_FLOOR_REJECTED`, distinct from `UNFILLED_ORDER` (whose order WAS valid and
  submitted but never touched).
- Fill search: starts at `order_placed_ts` (`available_at` of the confirmation bar, identical
  convention to the original pipeline), using the SAME `core.sweep.two_heap_sweep`/
  `backtest.simulate._fill_sides()` touch primitive, truncated to end strictly before 15:00 NY (an
  order that never fills by then is `UNFILLED_ORDER`, never left open past the session).
- Exit resolution: `backtest.simulate._resolve_exits` (reused unmodified, over the FULL M15 series,
  no 15:00 cutoff -- the brief's own cutoff applies only to entry search and fill, never to how
  long an already-filled trade is allowed to run).
- Costs: `config.backtest.trading_cost_price` (same baseline config per instrument).
- **One filled trade per instrument per session**, satisfied by construction: the fixed daily-bias
  direction and the window-bounded, single anchor-chain search can produce at most one terminal
  CONFIRMED signal per session.

## Outcome taxonomy (pre-registered, mutually exclusive, applied in this order)

`NO_DAILY_BIAS` / `NO_MATCHING_GAP` / H4-disqualified (not a qualifying setup, excluded from the
measured population) -- then, for every QUALIFYING H4 setup: `ENTERED` (filled; reports its own
realized R, net of cost) / `DISCARD_SWEPT_EXTREME_BREACH` / `DISCARD_TARGET_BEFORE_ENTRY` /
`EXPIRED` (window closes, Model-1 never confirms, no invalidation) / `RR_FLOOR_REJECTED` (confirms,
survives the invalidation race, but the planned RR never reaches 2.0) / `UNFILLED_ORDER` (confirms,
passes RR, order placed, never touched before 15:00).

## What to measure

Every qualifying H4 setup, by outcome category, by instrument and pooled. Net R per qualifying H4
setup after costs (0 for every non-`ENTERED` outcome -- never an invented value). Comparison
against the ORIGINAL D3/C2 9AM population on the same instruments/dates: sessions where BOTH this
variant and D3/C2 produce an executed trade, sessions where only one does, sessions where neither
does -- by `(instrument, NY calendar date)`, since this variant's own "session" and D3/C2's own
9AM trigger are both anchored to the same NY day.

## Pre-declared stop condition

If the qualifying-H4-setup count, pooled across all three pairs, turns out too small for the
`ENTERED` subgroup's own R statistics to be meaningful (judged plainly, the same discipline as
every prior unit), the report states that directly rather than asserting a conclusion.

## Synthetic validation cases (fixed before real data is run)

The brief's own three worked examples (Enter / Wait / Discard) are implemented as synthetic unit
tests BEFORE any real-data run, proving the mechanism reproduces each one exactly:
1. **Enter**: bullish daily bias, H4 sweeps the reference low into the marked gap and closes
   inside, a fresh M15 anchor at 13:15, Model-1 confirms, target still ahead, fills before 15:00.
2. **Wait**: identical H4 setup, but the only available M15 confirmation uses a bar before 13:00 --
   the search (correctly scoped to start at 13:00) finds nothing there and continues; this unit
   test asserts the pre-13:00 confirmation is never used, not a separate code path.
3. **Discard**: after a valid H4 close, price reaches the reference high (the target) before any
   M15 entry completes -- `DISCARD_TARGET_BEFORE_ENTRY`.

Additional synthetic cases added for completeness: `EXPIRED` (window closes with no confirmation
and no invalidation), `RR_FLOOR_REJECTED` (confirms, but planned RR < 2.0), `UNFILLED_ORDER`
(confirms, passes RR, order never touched), `NO_DAILY_BIAS` (daily double sweep), `NO_MATCHING_GAP`
(valid H4 close-back-inside but no known gap of the matching direction).
