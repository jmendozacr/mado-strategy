# Scanner: breakeven-after-partial live position management

Branch: `detector-msnr-key-levels`. Test runner: `cd detector && uv run pytest` (scanner tests run from `scanner/`, own `.venv`).

## Specs

- **S1** (verbatim): "Adoptemos esto definitivamente, deberíamos intégrarlo al scanner de una mejor" — adopt `breakeven_after_partial` (validated: 100% FTMO rolling-window pass rate, 53.6 avg days vs 99.2 current, dominates total_r/win_rate/avg_r on all 5 pairs) in the live scanner, not just the backtest harness.
- **S2** (decision, this session): only NEW trades placed AFTER this deploy get partial+breakeven management. Currently-open positions (scanner has been live since Sunday 2026-11-15) are left untouched with their original SL/TP — zero retroactive risk.
- **S3** (decision, this session): manual verification against the real MT5 demo terminal BEFORE wiring into the production 120s poll loop — same precedent as `_test_send_order.py`'s pending-order round-trip test.

## Scope

The scanner today only places a pending order and never looks at it again (`send_pending_order`, fire-and-forget — MT5's own native SL/TP execution handles everything after that). Integrating breakeven-after-partial requires NEW infrastructure, not a config flag:
1. Track each filled position's `partial_price` (computed once, same formula as `backtest.levels.partial_price`) and whether its partial has already been taken.
2. Each poll, detect when a pending order has filled into an open position (match by order ticket == position ticket).
3. Each poll, for tracked-but-not-yet-partial positions, check if price has reached `partial_price`.
4. On reaching it: partially close 50% of the position's volume (new MT5 call, `TRADE_ACTION_DEAL` against the position) and move the remaining 50%'s stop-loss to breakeven (`TRADE_ACTION_SLTP`) — two new MT5 request shapes never used anywhere in this codebase before.

## Tasks

- **T1** DONE: `execution.py` — `partial_close_volume`, `partial_price_reached`. 6 new tests, 15/15 green.
- **T2** DONE: `state.py` — `pending_partial` dict schema (+ `load_state` backfill for the pre-existing production state.json), `record_pending_partial`/`clear_pending_partial`. 4 new tests, 8/8 green.
- **T3** DONE: `mt5_feed.py` — `get_pending_order`, `get_open_position`, `close_partial_position`, `modify_stop_loss`, `current_exit_price`. Deliberately untested (no live terminal in CI), verified manually instead (T5).
- **T4** DONE: `main.py` — `_execute_alert` now returns a tracking dict on success (`rules.py` extended to carry `partial_price` on the alert too); `run_once` records it via `state.record_pending_partial`. New `_check_pending_partials`, called each poll before the alert loop. 6 new tests (`tests/test_pending_partial.py` + extended assertions in `test_main_silent_seed.py`) -- caught a real gap where the existing `_FakeResult` test fixtures lacked `.order`, silently swallowed by the per-alert `except Exception` and masking that the new tracking wiring was never actually exercised until the fixture was fixed.
- **T5** DONE: `scanner/_test_partial_close.py` run against the real MT5 demo terminal. Found and fixed TWO real bugs before they could reach the poll loop:
  1. `close_partial_position` (`TRADE_ACTION_DEAL`) used `ORDER_FILLING_RETURN` -- this broker only supports FOK/IOC for market deals (RETURN is pending-order-only), confirmed by a real `retcode=10030 "Unsupported filling mode"`. Fixed to IOC.
  2. The first verification attempt tried moving SL to the exact entry price immediately after opening at market (no real price movement yet) -- violates the broker's minimum-stop-distance rule, confirmed by a real `retcode=10016 "Invalid stops"`. Not a production bug (the real partial only fires once price has moved meaningfully away from entry), but the test script needed a safely-displaced target to actually exercise the SLTP mechanism.
  3. Final run, 4x `volume_min` (0.04 lots) on EURUSD: open (10009) -> partial close 0.02/0.02 computed correctly (10009) -> SL move to target (10009) -> cleanup close (10009) -> confirmed no position left open. Full round-trip verified.
  4. One unrelated environmental blocker hit mid-verification: the broker's daily server-side rollover (~00:00 server time, observed `retcode=10018 "Market closed"` for ~10 minutes) -- waited it out, not a code issue.

Scanner suite: 52/52 passing (37 baseline + 15 new).

## Log

- **L1** (verbatim): "Adoptemos esto definitivamente, deberíamos intégrarlo al scanner de una mejor"
- **L2**: clarifying question asked + answered — only new trades going forward (not retroactive to currently-open positions); manual demo test before the production loop.
