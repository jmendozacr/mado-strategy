# Independent backtest audit -- EURUSD / USDCAD / AUDUSD (1AM+9AM recipe)

Generated 2026-11-17 from this repository's own, unmodified code, for the
live "1AM+9AM diversified strategy" that `scanner/main.py` polls MT5 for
and alerts/auto-executes on three pairs: EURUSD, USDCAD, AUDUSD.

**Nothing in `detector/` or `scanner/` was changed, recalibrated, or
re-optimized to produce this export.** `export_audit.py` in this same
directory only imports and calls the existing
`detector/experimental/htf_trigger_1am_9am_backtest.py` (`SYMBOL_CONFIG`,
`backtest_1am_9am`, `trade_stats`) and `detector/backtest/simulate.py`
(`simulate`) against the existing `data/<SYMBOL>_{D1,H4,M15}_*.csv`
files, then serializes their real, in-memory output. Re-run it yourself
with `detector/.venv/Scripts/python.exe export_audit.py` to reproduce
every number in this directory from scratch.

## Files

### `trades.csv`
One row per simulated trade (`backtest.simulate.Trade`), for all three
pairs combined (`pair` column distinguishes them).

| column | meaning | units |
| --- | --- | --- |
| `pair` | EURUSD / USDCAD / AUDUSD | - |
| `signal_id` | the Model-1 LTF signal's own id | - |
| `model` | `1am` or `9am` -- which feeder-candle model triggered this signal (`detector/causal/htf_trigger.py:56-67`) | - |
| `direction` | `bullish` / `bearish` | - |
| `entry_index` | bar index into that pair's own M15 series (NOT comparable across pairs -- each pair has its own series) | integer |
| `entry_timestamp_broker` | resolved from `entry_index` against the M15 series' own timestamp column | ISO 8601, **broker/server time, see Timezones below** |
| `entry_price`, `stop_loss`, `take_profit` | the three levels the signal was built with | price units (e.g. 1.12345 for EURUSD) |
| `partial_exit_index/_timestamp_broker/_price` | leg 1's equilibrium-level partial close, if it fired; blank if the trade never reached the partial level | - / ISO 8601 / price units |
| `partial_r_multiple` | leg 1's own R, net of its share of trading cost | R (multiples of the original risk distance) |
| `partial_gap_filled` | true if the partial-close candle opened already past the partial level (gap fill, not a limit fill at the exact level) | boolean |
| `exit_index/_timestamp_broker/_price` | final close (leg 2, or the whole position if no partial fired); blank if the trade is still open at the end of the available data | - / ISO 8601 / price units |
| `outcome` | `win` / `loss` / `open` -- `win` means the BLENDED r_multiple is net-positive after cost, not merely "take-profit resolved first" | - |
| `r_multiple` | the trade's final, blended net result (both legs, cost deducted exactly once) -- blank only when `outcome=open` | R |
| `ambiguous_bar` | true if SL and TP were touched on the same candle (intrabar order unknowable; code resolves SL-wins-ties pessimistically) | boolean |
| `gap_filled` | true if the final-exit candle opened already past the chosen level | boolean |
| `breakeven_after_partial_config` | this pair's own config flag value, repeated on every row for convenience (True for all 3 pairs in this recipe) | boolean |

### `execution_events.csv`
Long format: one row per discrete lifecycle event, so a single trade in
`trades.csv` becomes 2-4 rows here (`entry_fill`, optionally
`partial_close` + `sl_update_to_breakeven`, then `exit` or
`still_open_at_data_end`).

**Important limitation, stated per the task's instructions:** the
simulator (`detector/backtest/simulate.py`) does **not** persist a
separate "stop-loss was moved to breakeven" field. The `sl_update_to_breakeven`
rows in this file (`derived=True`) are reconstructed, not read off a
stored field: whenever a trade's `partial_exit_index` is set AND that
pair's `breakeven_after_partial` config is `True` (true for all three
pairs here), the code's own, read documented behavior
(`_resolve_trade`'s `breakeven_after_partial` branch, same source file)
guarantees leg 2's stop became `entry_price` at that same bar. This is a
code-verified inference, not an invented number, but it is not a literal
persisted record either -- treat `derived=True` rows accordingly.

Columns: `pair`, `signal_id`, `model`, `event_type`, `bar_index`,
`timestamp_broker`, `price`, `position_fraction_closed` (blank unless the
event closes part/all of the position), `r_multiple_leg` (that leg's own
R, blank for `entry_fill`), `derived` (boolean, see above), `note`.

### `backtest_config.json`
The real `BacktestConfig` dataclass values (`detector/core/config.py`)
for EURUSD/USDCAD/AUDUSD, read directly off `SYMBOL_CONFIG` in
`detector/experimental/htf_trigger_1am_9am_backtest.py` -- confirmed
byte-identical, for these three pairs, to `scanner/main.py`'s own
hand-mirrored `BACKTEST_CONFIG` as of the commit this was generated from
(`_provenance.generated_from_commit`). Also records the account-level
constants (`risk_pct_per_trade`, `initial_balance_usd`,
`max_fill_wait_candles`) and the exact source CSV paths used.

`min_stop_distance_price`, `sl_buffer_atr_multiple`, `trading_cost_price`
are all in **price units** (e.g. `0.0006` = 6 pips for a 4th-decimal
pair like EURUSD/USDCAD/AUDUSD), not pips, to match the codebase's own
convention.

### `optimization_history.csv`
Every parameter-selection event found anywhere in this repository's
tracked history for EURUSD/USDCAD/AUDUSD's `min_stop_distance_price`, plus
the one genuine walk-forward validation found for `min_risk_reward`. **Two
of the four rows (USDCAD, AUDUSD) have no persisted sweep table -- only
the qualitative result survives in the commit message itself; this is
stated explicitly in each row's `notes` and `source` columns, per the
task's instruction to flag missing optimization history rather than
invent it.** No sweep or calibration was found anywhere in this repo for
EURUSD's own `trading_cost_price`, `min_risk_reward`, or
`breakeven_after_partial` as applied to this specific 3-pair recipe --
`trading_cost_price` values trace to FTMO-cost research cited in
`odd/tasks/realistic-cost-prop-firm-validation.md`, not a numeric sweep.

### `data_split.json`
States plainly that **no train/validation/out-of-sample split exists**
for the backtest results in `trades.csv`, or for the SL-floor calibration
events in `optimization_history.csv` -- both ran over the full available
historical window with nothing held out. It also documents the one real
exception found (a 3-fold walk-forward for the `min_risk_reward`
parameter, on an older, related-but-different population) and confirms
that a separate, more rigorous "Statistical Runner" preregistration
pipeline exists in this repo (`detector/runner/`, `detector/selection/`,
`detector/adapter/`) but is for a different instrument set (EURUSDm /
GBPUSDm / DXYm) and has zero code or data connection to this recipe.

## Reconciliation

There is **no pre-existing, persisted canonical result file** anywhere in
this repository for this exact recipe/pair combination to diff against
(confirmed by search across `pairs/`, `.sdd/evidence/`, and the whole
tree -- the only prior numbers live in commit messages, code comments,
and `odd/tasks/` prose, never a file). `export_audit.py` therefore
reconciles the only way that is actually possible here: it independently
re-sums `r_multiple` and the closed-trade count straight from the rows it
is about to write to `trades.csv`, and asserts that sum equals the
backtest harness's own `trade_stats()` aggregate, computed from the exact
same in-memory `Trade` objects, before accepting the run as valid. The
assertion is in `export_audit.py`'s `main()`; its outcome for this run is
recorded in `_reconciliation_check.json` (included for transparency, not
one of the five requested deliverables) and echoed in the script's stdout.

This is an **internal consistency check** (the export matches the
harness's own math), not a match against some independent, external
ground truth -- because no such ground truth is persisted anywhere in
this codebase. If you need to validate against a truly independent
source, the only options found during this audit are: (a) re-run
`research/diversified_1am_9am_rolling.py` yourself and compare, or (b)
compare against a live MT5 account's actual trade history -- `scanner/state.json`
is gitignored and only tracks alert-dedup/pending-partial state, not a
historical trade ledger, and the new `mt5/`/`tradingview/` directories in
this working tree are EURUSD-only strategy-tester source ports (MQL5/Pine
Script), not real account exports.

## Portfolio overlap across pairs

The backtest treats EURUSD, USDCAD, and AUDUSD as **three independent
per-instrument simulations** -- each pair gets its own M15/H4/D1 series
and its own `simulate()` call; trades are only merged afterward for
reporting. **No simultaneous cross-pair exposure check exists**: neither
the backtest harness nor the live scanner (`scanner/main.py`, which polls
each symbol in its own loop) checks whether EURUSD, USDCAD, and AUDUSD
have overlapping open positions, or caps combined risk when they do. A
separate research script (`research/diversified_1am_9am_rolling.py`,
not run for this audit) does merge all three pairs into one notional
account for an account-wide daily-loss stop and a rolling-window equity
simulation, explicitly on the basis of real calendar timestamps -- but it
too does not check open-position overlap, and it explicitly documents
that its own within-pair 2R-open concurrency gate cannot be meaningfully
applied across pairs with different M15 series.

## Timezones

The source CSVs (`data/<SYMBOL>_{D1,H4,M15}_*.csv`) carry naive
timestamps (no UTC offset in the file) on the broker's own export grid.
This codebase's own documented assumption (`detector/causal/htf_trigger.py`'s
module docstring) is that the H4 series is a fixed-UTC grid
(00/04/08/12/16/20 UTC) -- **this is the codebase's stated assumption,
not independently re-verified by this audit against the broker's actual
server-time offset.** "1AM"/"9AM" in the recipe's own name refer to
**America/New_York (NY) local time**: `MODEL_1AM` triggers on the H4
candle whose UTC hour is 4 (= NY 00:00 in winter / 00:00 DST-adjusted;
confirmation window NY 02:00-04:00), `MODEL_9AM` triggers on the UTC-12:00
candle (confirmation window NY 09:00-10:30) --
`detector/causal/htf_trigger.py:40-41,56-67`. All `*_timestamp_broker`
columns in `trades.csv`/`execution_events.csv` are the raw, naive broker
timestamps read straight off the M15 series -- convert them yourself if
you need a specific real-world zone; this audit does not re-derive that
conversion beyond what the recipe's own trigger-window logic already
assumes.

## Known limitations / explicit gaps (not invented, not filled in)

1. **No real executed-trade ledger exists.** Everything in `trades.csv`/
   `execution_events.csv` is from the backtest SIMULATION, not a live MT5
   account statement. `scanner/state.py` (the live scanner's own
   persistence) only tracks alert dedup and pending-partial state, never
   a historical closed-trade log -- confirmed by reading it.
2. **`optimization_history.csv` rows OPT-2/OPT-3 (USDCAD/AUDUSD SL floor)
   have no persisted sweep table**, only the qualitative result and
   headline numbers quoted verbatim from the two commit messages that
   made the change (`b1de44d`, `078655e`). No sweep script or log file
   for that specific run exists anywhere in this repository.
3. **No data split exists for the SL-floor calibrations** -- see
   `data_split.json`. The one genuine walk-forward split found
   (`min_risk_reward`) was run on a different, predecessor population and
   was never re-applied to the final 3-pair recipe.
4. **EURUSD's trading cost (`0.00013`) is cited to FTMO-cost web research**
   in `odd/tasks/realistic-cost-prop-firm-validation.md`, independently
   verified against FTMO's platform per that document's own L3 log entry;
   USDCAD's (`0.000167`) is an FX-rate-adjusted derivation of the same
   research (per `odd/tasks/scanner-1am-9am-diversified.md:S2`); this
   audit did not re-derive or re-verify either conversion.
5. **Pre-2026-11-16 data**: USDCAD and AUDUSD traded (in this backtest)
   with `min_stop_distance_price=0.0` (no floor) before commit `b1de44d`.
   `trades.csv` reflects only the CURRENT, calibrated config (post-`078655e`)
   applied uniformly over the full historical window -- it does NOT
   reproduce what the live scanner would actually have alerted on before
   that calibration landed, since the floor is applied retroactively to
   the whole backtest, not just to trades after 2026-11-16.
6. **Calibration-window vs. backtest-window mismatch.** USDCAD/AUDUSD's
   `min_stop_distance_price` floor was calibrated on a 2022-2026 window
   only -- stated in a code comment
   (`detector/experimental/htf_trigger_1am_9am_backtest.py:80-82`), not
   in either commit message. This audit's `trades.csv` instead runs the
   FULL 2003-2026 history under `data/`, because that is the harness's
   own unmodified default and it exposes no date-range flag to restrict
   it. See `data_split.json`'s `scope_mismatch_flagged` field.
7. This export covers EURUSD/USDCAD/AUDUSD only, per the task's scope.
   GBPUSD and USDJPY are configured in the same `SYMBOL_CONFIG`/
   `BACKTEST_CONFIG` dicts and were calibrated in some of the same
   commits, but are intentionally excluded from every file in this
   directory.
