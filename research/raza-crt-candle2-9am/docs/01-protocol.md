# Protocol — Raza "Candle 2" Close-Back-Inside Rule Applied to the 9AM D3/C2 Reference Candle

**Dated and fixed 2026-11-26, before any outcome (trade result, R, win/loss) is inspected.** This
document defines the population, unit of observation, classification scheme, and comparison plan.
Any later deviation from this document must be logged explicitly, never silently substituted.

## Terminology: Raza's "candle 2" vs. this lab's "D3/C2"

**These are two unrelated, coincidentally similar names.** Raza's thread (`docs/raza-crt-thread.md`,
transcribed from the attached PDF) uses "C1/C2/C3" for a 3-candle (or N-candle) sequence on ANY
timeframe: C1 is the range, C2 sweeps one side and closes its BODY back inside, C3 delivers to the
other side. This experiment's own "D3/C2" is this lab's INTERNAL EXPERIMENT NAME from the prior
causal-lookahead audit (`anchor_source="new"`, arm `"c2"` = the NY-anchored feeder grid), unrelated
to Raza's candle numbering. Every mention of "C2" in this experiment's own code and reports means
the NY-anchored grid arm, NEVER Raza's second candle. Raza's candle-2 concept is referred to here
as "the close-back-inside rule" or "the reference-range re-entry rule" to avoid collision.

## Research question (restated)

Among the 9AM D3/C2 baseline activations (same historical run, instruments, and dates as the
verified Phase 8-10 baseline), how often does the 09:00-13:00 New York H4 candle ultimately close
back inside the 05:00-09:00 New York reference range after sweeping it? How do the ORIGINAL trade
outcomes (as actually executed, with the original entry/stop/target/cost/RR rules -- never a new
rule set) differ across the resulting groups?

## Source code reused, read-only, never modified

- `audit/2026-11-17-causal-lookahead-audit/causal_intrabar.py` -- `complete_feeder_candle_ny`
  (reused unmodified to reconstruct the reference candle's high/low); `REFERENCE_HOUR_NY["9am"]=5`,
  `CURRENT_HOUR_NY["9am"]=9`, `REFERENCE_IS_PREVIOUS_DAY["9am"]=False` confirm the reference candle
  is the SAME NY calendar day's 05:00-09:00 span and the current candle is that day's 09:00-13:00
  span -- exactly the ranges this experiment compares.
- `audit/2026-11-17-causal-lookahead-audit/run_d1_d2_d3.py::run_d_c2` -- reused unmodified for the
  authoritative 9AM trigger population (`stable_id`, direction, `activation_instant_ts`,
  confirmation/candidate/fill linkage), pinned to `anchor_source="new"`, `windows_9am="new"`,
  `arm_name="d3_c2"` -- the SAME pinning as Phases 8-10.
- `research/loss-pattern-discovery/extract/model1_rejection_diagnostics.py::_window_open_ts_from_stable_id`
  -- reused unmodified (read-only import from the sibling lab, never a copy) to recover each
  trigger's own `current_open_ts` (09:00 NY) from its `stable_id`.
- The real ledger (`audit/2026-11-17-causal-lookahead-audit/trades_d3_c2_2015plus_run2.csv`) for
  original trade outcomes -- read-only, unchanged.

**No candle-sweep or close-position decision in this experiment reimplements
`detect_sweep_and_key_level`'s own baseline logic.** That function (and everything upstream of it)
stays exactly as Phase 8-10 verified it; this experiment only adds ONE new, read-only
reconstruction of the CURRENT H4 candle's own COMPLETE (09:00-13:00) span -- which the baseline
itself never needed, since it only tracks a provisional running high/low during the (shorter)
activation window.

## Population

**All 9AM D3/C2 baseline activations** -- every credited trigger (`triggers_with_key_level`) for
the 9AM model, across EURUSD/USDCAD/AUDUSD, 2015-01-01+, identical to the Phase 8-10 baseline
(8,712 triggers). This includes triggers that never confirmed, never became a candidate, never
filled, and never executed -- the funnel stages are reported as denominators, not as population
filters.

## Unit of observation

**One credited trigger = one `stable_id`** (format `{symbol}|d3_c2|9am|{current_open_ts isoformat}|{direction}`).
A single current H4 candle can produce UP TO TWO triggers (one per direction) if it sweeps and gets
credited on both sides within the activation window -- this experiment reports BOTH the distinct
signal (`stable_id`) count and the distinct candle (`instrument`, `current_open_ts`) count at every
stage, never conflating them. `direction` and `stable_id` are read directly from the baseline
trigger record, never re-derived.

## Close-position classification (the primary grouping variable)

For each trigger, reconstruct its own current H4 candle's COMPLETE 09:00-13:00 span via
`complete_feeder_candle_ny` (gives `high`, `low`) plus the bucket's own last M15 candle's `close`
(the H4 candle's reconstructed close price, by OHLC-aggregation construction -- never a separate
computation). Classify against the ALREADY-RECONSTRUCTED reference candle's `[low, high]`:

- **`INSIDE`**: reference_low `<` final_close `<` reference_high, STRICTLY (our own operational
  choice, stated explicitly, per the brief: a close exactly ON a boundary is NOT counted as
  inside). Floating-point ties use a `1e-9` tolerance (the same convention Phase 9 used for
  `entry_price` comparisons), applied symmetrically to both bounds.
- **`EXACT_BOUNDARY`**: final_close equals reference_low or reference_high within that tolerance.
- **`OUTSIDE`**: final_close is beyond either bound by more than the tolerance (i.e., the candle's
  body closed through the range, not back inside it).
- **`MISSING_OR_INCOMPLETE`**: either the reference or the current H4 candle's own M15 bucket fails
  `validate_complete_feeder_bucket`'s completeness check (holiday/gap/DST edge) -- reported as its
  own category, EXCLUDED from the close-position comparison, never silently dropped from the
  population count.

## Sweep-side classification (a separate dimension, reported alongside, never collapsed into it)

Using the SAME complete current-candle high/low (not the activation-window's provisional running
high/low): `HIGH_ONLY` (final high `>` reference_high, final low `>=` reference_low), `LOW_ONLY`
(final low `<` reference_low, final high `<=` reference_high), `BOTH` (final high `>` reference_high
AND final low `<` reference_low -- a double sweep). By construction, the trigger's OWN credited
side must remain swept by the final close (the complete span is a superset of the activation
window's own running high/low) -- verified empirically, never assumed, reported as a coverage
check in the results (Deliverable A requirement 14 in the prior phases' convention: equivalence of
sets, not counts alone).

## Direction-ambiguity rule (Raza page 2)

Raza's own rule only defines direction for a SINGLE-side sweep ("C2 takes the high -> target the
low. Takes the low -> target the high."). It never addresses a candle that sweeps BOTH sides.
**For any trigger whose current candle is `BOTH` (double sweep), this experiment does NOT assign a
Raza-style direction to that candle -- it is labeled `DOUBLE_SWEEP_AMBIGUOUS` and reported as its
own category, kept separate from `HIGH_ONLY`/`LOW_ONLY`.** The trigger's OWN baseline direction
(already fixed by the real D3/C2 pipeline, independent of this label) is never changed or
reinterpreted by this ambiguity -- the two are reported side by side, never merged.

## Timeline fields retained per trigger

`activation_instant_ts` (baseline activation), `model1_available_ts`/`order_placed_ts` (M15
confirmation / order placement -- identical value per `causal_anchor_v2.build_causal_signal_v2`),
`entry_ts` (fill, from the real ledger, executed trades only), `exit_ts` (from the real ledger,
closed trades only), and `h4_close_available_ts` = `current_open_ts + 4h` (13:00 NY in UTC -- the
instant the complete current candle's own close becomes knowable). An event whose ordering versus
13:00 cannot be established at M15-bar resolution (an exact timestamp tie) is marked
`ORDERING_INDETERMINATE`, never arbitrarily broken in either direction.

**The 13:00 close is used ONLY as a retrospective label on the ORIGINAL trade record.** It is never
used to pick an earlier order, credit an earlier fill, or alter any already-executed trade's own
entry/stop/target/cost/RR -- those stay exactly as the real ledger recorded them.

## Primary contrast and comparisons (pre-declared)

1. **Funnel by close-position group**: trigger (activation) -> confirmed -> candidate -> filled ->
   closed trade, with the close-position group as the row label and the ORIGINAL, unmodified
   denominator shown at every stage. Open trades stay visible, excluded only from the outcome
   (R/win-rate) metrics.
2. **Outcome by close-position group, closed trades only**: net mean R, win rate, n -- pooled and
   by instrument. Uncertainty on the INSIDE-vs-OUTSIDE mean-R difference via block bootstrap,
   clustering by shared current-candle (`instrument`, `current_open_ts`) OR shared NY trading date
   when candles don't coincide -- the SAME block-bootstrap discipline
   (`research/loss-pattern-discovery/stats/bootstrap.py::block_key`, reused unmodified) this lab
   has used since Phase 3.
3. No RR tuning, no entry/stop/target change, no 1AM model, no daily bias, no FVG exception, no
   rejection-block exit -- all explicitly out of scope for this first comparison, per the brief.

## What would make this contrast degenerate (stop-and-document condition)

If `MISSING_OR_INCOMPLETE` or `DOUBLE_SWEEP_AMBIGUOUS` together account for a large majority of
the credited-trigger population (no fixed numeric threshold pre-declared here, since none of this
lab's prior phases needed one for an analogous check -- "large majority" is judged qualitatively
and reported transparently either way), or if one close-position group has zero closed trades,
this is reported as `INSUFFICIENT_SUPPORT` for that specific group/comparison, never papered over
or merged into a different, result-favorable grouping.

## Chart-example selection rule (stated before any outcome is inspected)

Select the FIRST 9AM trigger (chronologically, by `activation_instant_ts`) within each of
`INSIDE`, `OUTSIDE`, `EXACT_BOUNDARY`, and `DOUBLE_SWEEP_AMBIGUOUS` for EURUSD specifically (the
instrument with the longest, most complete history) -- a rule fixed by chronology and category
membership alone, independent of the trigger's own R-outcome or win/loss.
