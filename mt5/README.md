# 1AM+9AM backtest EA for MT5

Same recipe as [`tradingview/mado_1am9am_backtest.pine`](../tradingview/mado_1am9am_backtest.pine) (EURUSD only — the "1AM+9AM diversified" recipe currently live in `scanner/main.py`), ported to MQL5 so it runs in MetaTrader 5's own Strategy Tester instead of TradingView. Unlike the Pine port, this one uses MT5's **native H4 candles directly** (no hand-built synthetic H4 bucket needed) and MT5's native `ATR` indicator and tick value/size — both more faithful to the Python recipe's own data than the TradingView version had to be.

## Running it

1. Open **MetaEditor** (F4 from the MT5 terminal, or the toolbar icon), `File → New → Expert Advisor (from template)`, name it anything, then replace the generated contents with [`Mado_1am9am_Backtest.mq5`](Mado_1am9am_Backtest.mq5).
2. Compile (`F7`). Fix any reported errors — this file was written but not compiled from this environment, so treat the compiler as the first real check.
3. In the MT5 terminal, open **Strategy Tester** (`Ctrl+R`). Select this EA, **Symbol: EURUSD**, **Period: M15**, pick your date range.
4. **Settings → the Forex Properties / General tab → Account type → Hedging.** This is required: the 1AM and 9AM models can each hold their own open EURUSD position at the same time, which a Netting-type account would instead merge into one — the EA's per-model tracking assumes Hedging.
5. Run. Check the **Results** tab for the trade list and the **Graph** tab for the equity curve, same way you'd read FTMO/backtest numbers already.

## Known approximations vs. the Python recipe

Same four as the Pine port (see [`tradingview/README.md`](../tradingview/README.md#known-approximations-vs-the-python-recipe) for the full explanation): M15 anchor selection (rolling 20-bar high/low break instead of the exact resolved-range algorithm), structural SL level (raw wick extreme instead of a fractal-confirmed swing), no modeled trading cost, and one trade per model at a time. Two more that are specific to running this as a real MT5 EA rather than a bar-by-bar Python simulation:

- **DST is computed by rule, not looked up.** `IsUSEasternDST()` hand-implements the US rule (2nd Sunday of March → 1st Sunday of November, both at local 2am) instead of using an IANA timezone database (MQL5 has none built in). Correct for any year under the current US rule; would need updating if that rule ever changes.
- **Partial-exit volume is lot-step rounded.** The Python simulator closes exactly `PartialFrac` (50%) of the position with no granularity limit. MT5 lets you close a position fraction, but the closed volume is rounded to the symbol's `SYMBOL_VOLUME_STEP`, so the real fraction executed can be slightly off 50% — negligible on the usual lot sizes this risk/stop combination produces, more noticeable on a very small account/position.
- **Broker server time vs. UTC.** The EA assumes the broker's quote timestamps are already UTC-aligned (matching the exported CSVs the rest of this repo already uses). If your broker's H4 bars don't open at 00/04/08/12/16/20 server time, set the `BrokerUTCOffsetHours` input accordingly before trusting the 1AM/9AM hour gating.

Validate a sample of trades against the Python backtest/ledger before trusting this for anything beyond a sanity-check comparison.
