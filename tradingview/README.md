# CRT indicators and strategies for TradingView

Paste [`mado_crt_scanner.pine`](mado_crt_scanner.pine) into the TradingView Pine Editor and add it to a 15-minute EURUSD chart. The script draws a position-style risk/reward graphic from the **first M15 candle that touches the entry**, starting at the Model-1 retest and within the backtest's 20-candle fill window. The green zone runs from entry to target, the red zone from entry to stop, and the gray line marks entry. Adjust the width and the number of recent positions in the indicator settings. Create an alert with the condition **Any alert() function call** to receive direction, anchor and fill times in New York, entry, stop, and target. The separate long and short conditions provide static messages.

The indicator implements the scanner's M15 CRT purge/engulf/retest path, H4 CRT alignment, H4 FVG Key Level gate, 07:00–11:00 New York anchor window, structural stop with a 0.3 ATR buffer, H4 opposite-extreme target, and minimum 2:1 reward/risk. It waits for closed M15 and H4 candles. It discards a pending setup if price touched its stop or target between the retest and the alert bar. The graphic is built from Pine boxes and a line; it is not TradingView's editable Long Position or Short Position drawing tool. If H4 context resolves after the fill, the graphic appears retrospectively on the fill candle; the alert occurs only at the later confirmation. The inferred fill is based on OHLC touch, not an actual broker execution. The indicator does not claim to reproduce the Python backtest's returns.

## Differences from the Python scanner

- Daily ICT Order Block Key Levels are not implemented. On the local EURUSDm sample through 2026-09-04, 1,023 of 1,028 scanner alerts used an H4 FVG; five used a Daily Order Block.
- Only `CONFIRMED` Model-1 signals can alert. The Python scanner's historical filter also admits some `INVALIDATED` and `PENDING` signals after a retest. In the same sample, 759 alerts were `CONFIRMED`, 241 `INVALIDATED`, and 28 `PENDING`.
- TradingView's data feed and H4 candle boundaries can differ from the MT5 EURUSDm feed. The MT5 sample uses H4 opens at 00:00, 04:00, 08:00, 12:00, 16:00, and 20:00 UTC. Compare those boundaries before comparing individual signals.
- A later resolving H4 CRT range can replace an earlier context for the same purge candle. The script alerts when an eligible context first becomes available and cannot retract an alert already sent.
- The Python scanner's news calendar only annotates messages; the indicator does not fetch or annotate news.

The Pine script has not been compiled in TradingView from this environment. Validate it in the Pine Editor and compare a sample of chart signals against the Python scanner before using its alerts operationally.

## 1AM+9AM backtest strategy

Paste [`mado_1am9am_backtest.pine`](mado_1am9am_backtest.pine) into the Pine Editor and add it to a 15-minute EURUSD chart, then open the **Strategy Tester** tab for the equity curve, win rate, drawdown, and trade list — this is a `strategy()`, not an `indicator()`, so TradingView computes those natively instead of the hand-drawn graphic the scanner script uses.

It ports the "1AM+9AM diversified" recipe currently live in `scanner/main.py` for EURUSD only (the recipe the funded-account backtests and the live scanner both run): hand-built 2-candle H4 Turtle Soup at the 04:00 UTC and 12:00 UTC candles, gated by a live H4 FVG key level (`>= 0.1x ATR14` H4, at the gap's confirming candle); the LTF Model-1 anchor/engulf/retest/entry sequence on M15, confined to NY 02:00–04:00 (1AM) / 09:00–10:30 (9AM) — confirmation, retest, and entry must all complete inside that same window, or the setup is abandoned; structural stop (deepest opposite swing between anchor and retest, else the anchor's own wick) plus a 0.3x ATR14(M15, snapshotted at anchor) buffer, floored at 0.0006 (6 pips); H4 opposite-extreme target; a 2:1 minimum R:R filter; a 50% partial exit at the entry-to-target midpoint with the remainder moved to true breakeven; and fixed 1% risk against a non-compounding $10,000 balance.

### Known approximations vs. the Python recipe

- **M15 anchor selection.** The Python recipe's LTF anchor comes from `detect_crt_ranges` treating every single M15 candle as its own 1-candle range, keeping only the ranges that later resolve (true break or Turtle-Soup false break) within 20 candles, then taking the earliest in-window wick breach among those. This script approximates that as "wick breaks the highest high / lowest low of the prior 20 M15 candles," dropping the own-resolution-within-20-candles pre-filter. In practice these coincide for the large majority of liquid FX breaches; they can diverge on an unresolved, directionless range.
- **Structural SL level.** The Python recipe takes the deepest *swing point* (a confirmed fractal) between the anchor and the retest. This script uses the raw running wick extreme over that same span instead of a fractal-filtered swing, which can occasionally place the stop a few pips wider than the exact port.
- **Trading cost.** `scanner/main.py`'s EURUSD config nets out a ~1.3 pip (`trading_cost_price=0.00013`) round-trip cost per trade in its R-multiple math. This script does not model it — add a commission/slippage setting in the Strategy Tester's properties if you want a cost-adjusted comparison.
- **One trade per model at a time.** The script will not open a second 1AM (or 9AM) trade while a previous one from that same model is still open. The Python backtest's own concurrency behavior across overlapping trades was not re-verified for this port.

Validate a sample of trades against the Python backtest/ledger before trusting this for anything beyond a sanity-check comparison.
