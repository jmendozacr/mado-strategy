# Deliverable A — Phase 3.1 Causal Diagnosis and Temporal Contract

## The defect, confirmed against both sources (never assumed)

**D3/C2 ledger** (`audit/2026-11-17-causal-lookahead-audit/trades_d3_c2_2015plus_run2.csv`, via
`detector/backtest/simulate.py::_resolve_level_exit`, line 170):

```python
exit_price = exit_candle.open if gap_filled else level
```

A real SL event's `exit_price` is **either** the pre-known `level` (the `stop_loss`/`take_profit`
value, fixed when the order was placed, long before the exit bar exists) **or** that exit bar's own
**OPEN** under a gap. Neither branch ever uses `exit_candle.close`. So a real event's `(exit_ts,
exit_price)` pair is causally self-consistent: `exit_price` is knowable at `exit_ts` the instant that
bar opens, never 15 minutes later.

**Control construction** (`control/sampling.py::control_to_event_record`,
`behavior/recovery_analysis.py::recovery_control_to_event_record`, both before this fix):

```python
idx = bisect.bisect_left(timestamps, control.control_ts)
close_at_control = series.candles[idx].close   # <- the SAME bar's CLOSE
...
exit_ts = control.control_ts                     # <- that bar's OPEN
exit_price = close_at_control                    # <- not known until control_ts + 15min
```

`control.control_ts` is `series.candles[chosen_idx].timestamp` (confirmed in `sample_controls`) --
an M15 bar's OPEN, by the same MT5 convention as everywhere else in this lab. The control therefore
attributed a price not actually knowable until 15 minutes later to an event timestamped at the
earlier instant -- the user's 10:00/10:15 example exactly. **Confirmed impact**: every control's
synthetic `entry_price`/`stop_loss`/`exit_price` (and therefore every MFE/MAE/continuation/recovery
measurement built from it) used a price that could not have been known at the declared instant. Real
events never had this defect; only the synthetic controls did.

## Temporal contract (adopted, named to this lab's existing schema)

| Concept | Field | Value for a real SL event | Value for a control (after this fix) |
|---|---|---|---|
| Reference bar's open | `reference_bar_open` | `exit_ts` (= exit candle's own timestamp) | `control_ts` (= reference candle's own timestamp) |
| Reference bar's close | `reference_bar_close` | `exit_ts + M15_DURATION` (not used for price) | `control_ts + M15_DURATION` (not used for price) |
| Price available at | `reference_price_available_at` | `exit_ts` (level or that bar's own open) | `control_ts` (that bar's own open) -- **this fix** |
| Event effective instant | `event_effective_at` | `exit_ts` | `control_ts` |
| First actionable instant | `first_actionable_ts` (existing field, unchanged) | `exit_ts + M15_DURATION` | `control_ts + M15_DURATION` |
| Post-event observation start | `post_event_observation_start` | first bar with `timestamp > exit_ts` (existing `_bisect_after`) | same, unchanged |

## Decision: Option B (open-referenced), not Option A (close-referenced)

**Chosen because it matches how a real SL event's own `exit_price` is already defined** -- a
pre-known level or that bar's own open, never requiring the bar to close -- keeping both groups
causally symmetric with no special-casing. It was **not** chosen by comparing which option produced
a more favorable statistical result; Option A was never run end-to-end for comparison, exactly because
picking between them on that basis is what the brief explicitly prohibited.

**Why Option A would have been worse, structurally** (reasoned, not measured): shifting the control's
effective instant to `control_ts + M15_DURATION` while a real event's effective instant stays at its
own `exit_ts` (no such shift) would reintroduce the "mixed open-vs-close across groups" inconsistency
Section 4 warns against, and would require threading a second, parallel "effective_ts" concept through
`compute_post_stop_behavior`'s existing boundaries for one group only. Option B needs no such
parallel plumbing: `_bisect_after(series, exit_ts)` (unchanged) already starts post-event measurement
at the NEXT bar for both real and synthetic events identically, and the reference bar's own high/low
were never used for anything beyond providing the now-correct open price.

## What did NOT need to change

- `compute_post_stop_behavior`'s bar-inclusion boundary (`candle.timestamp + M15_DURATION <=
  horizon_ts`, Phase 3's Defect B fix) and its `_bisect_after` start boundary -- both already correct
  and already identical for real and synthetic events; this fix only corrects the PRICE a control
  attaches to its own already-correct timestamp.
- `compute_atr_at_event`'s pre-event lookback (Phase 3's fix already excludes the reference bar's own
  not-yet-closed candle from any ATR calculation, for both groups).
- NY-hour matching, exclusion buffer, period bucketing -- all timestamp-based, unaffected by which
  price a bar's timestamp resolves to.

## Verified: no accidental loss or contamination of a bar

`bisect_left(timestamps, control.control_ts)` finds the EXACT index of the reference bar (its
timestamp is drawn directly from that same array in `sample_controls`), not a neighbor --
`tests/test_control_price_causality.py::test_bisect_left_finds_the_exact_reference_bar_not_an_off_by_one`
constructs bars immediately before and after the reference bar with very different OHLC and confirms
the function still resolves to the reference bar's own values.
