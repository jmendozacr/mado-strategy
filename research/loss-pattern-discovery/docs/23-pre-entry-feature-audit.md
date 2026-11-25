# Deliverable A — Pre-Entry Feature Audit

Implementation: `features/pre_entry_features.py`. Computed for all 2047 executed trades (778 wins,
1265 losses, 4 open) with the SAME methodology regardless of outcome. Coverage: **100%** have ATR
and recent-range computed (2047/2047) -- the dataset's 2003/2005-2026 history gives enough lookback
for every 2015+ entry; zero missing-reason flags fired.

| Feature | Formula | Source | Available at | Unit | Missing-value treatment | Causality test |
|---|---|---|---|---|---|---|
| `atr_m15_at_entry` | 14-bar M15 ATR, bars closed strictly before `entry_ts` | `behavior.post_stop_metrics.compute_atr_at_event` (reused, called at `entry_ts`) | `entry_ts` | price | `None` if <14 prior closed bars | `test_future_candle_does_not_affect_pre_entry_feature` |
| `recent_range_price`/`recent_range_atr` | max(high)-min(low) over the same 14-bar window, and that /ATR | same window | `entry_ts` | price / ATR-units | `None` if window incomplete | `test_entry_bar_itself_not_used_in_recent_range` |
| `risk_price` | `abs(entry_price - stop_loss)` | `schema.events.OriginalOperation` (existing) | order placement | price | n/a (always known) | inherited from Phase 1 |
| `reward_price` | `schema.events.FeaturesPreEntry.planned_reward_price` (existing) | same | order placement | price | n/a | inherited |
| `risk_atr` | `risk_price / atr_m15_at_entry` | derived | `entry_ts` | ATR-units | `None` if risk or ATR invalid | `test_zero_risk_does_not_divide_misleadingly` |
| `planned_rr` | `schema.events.FeaturesPreEntry.planned_rr` (existing) | same | order placement | ratio | `None` if entry==stop | inherited |
| `cost_to_risk_ratio` | per-symbol `trading_cost_price / risk_price` | `detector/experimental/htf_trigger_1am_9am_backtest.py::SYMBOL_CONFIG` (read-only reuse, same config the production scanner uses) | order placement | ratio | `None` if cost unknown or risk invalid | config value, not derived from any candle |
| `ny_hour_at_entry` | NY wall-clock hour-of-day at `entry_ts` | `common.ny_time.to_ny` (zoneinfo, DST-correct) | `entry_ts` | hour (0-24) | n/a | `test_ny_hour_and_weekday_cross_a_dst_boundary_correctly` |
| `day_of_week_ny` | NY-local weekday of `entry_ts` | same | `entry_ts` | 0=Mon..6=Sun | n/a | same |
| `time_activation_to_entry_s` | `entry_ts - activation_instant_ts` | existing fields | `entry_ts` | seconds | `None` if activation missing | structural |
| `prior_m15_return` | `(close-open)/open` of the last fully-closed bar before `entry_ts` | M15 series | `entry_ts` | fraction | `None` if no prior bar | same window test |
| `position_in_recent_range` | `(last_close - recent_low) / recent_range_price` | same window | `entry_ts` | 0..1 | `None` if range is 0 or window incomplete | same |
| `prior_move_direction` | sign of (last closed bar's close - first-of-window close) | same window | `entry_ts` | -1/0/+1 | n/a | same |
| `distance_to_recent_high_atr`/`..._low_atr` | `(recent_extreme - entry_price) / atr` | same window | `entry_ts` | ATR-units | `None` if ATR invalid | same |

Deliberately excluded (per the brief's "no catálogo enorme" instruction): any CRT Key-Level, anchor,
or kill-zone-derived feature -- all would require importing `detector`'s structural assumptions
(`primitives.crt_range`, `primitives.swing`, etc.) rather than being read directly from the ledger or
raw OHLC, and none were judged necessary for this phase's small, interpretable feature set.

## Win vs. loss, descriptive medians (quantiles in `artifacts/phase4_failure_mode_atlas.json`)

| Feature | Win (n=778) | Loss (n=1265) |
|---|---|---|
| `atr_m15_at_entry` | 0.00080 | 0.00080 |
| `risk_atr` | 1.40 | 1.36 |
| `planned_rr` | 2.73 | 3.00 |
| `ny_hour_at_entry` | 11.00 | 11.25 |
| `time_activation_to_entry_s` | 7200s (2.0h) | 8100s (2.25h) |
| `recent_range_atr` | 3.76 | 3.89 |
| `position_in_recent_range` | 0.519 | 0.492 |

**No pre-entry feature shows a stark median separation between winners and losers.** This is a
descriptive observation, not a formal hypothesis test (none was run, per this phase's own
instruction not to search for a predictive split) -- see `docs/27-research-findings-phase4.md` for
how this is classified.
