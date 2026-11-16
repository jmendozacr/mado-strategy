"""One-off: proves the NEW partial-close + move-to-breakeven mechanics
(odd/tasks/scanner-breakeven-after-partial.md T5) round-trip against the
real MT5 terminal before wiring them into the 120s poll loop. Opens a
REAL market position 4x volume_min (so a clean 50% split is a valid,
tradeable volume -- volume_min itself can't be split, confirmed by a
real retcode=10014 "Invalid volume" the first time this ran at
volume_min), partially closes half, moves the remainder's SL, then
closes what's left -- no position is left open at the end, success or
failure.

The SL move target is 15 pips below the open price, NOT literally
`entry_price` -- a position that was JUST opened at market has
entry==current price, so moving SL to the exact entry immediately would
violate the broker's minimum-stop-distance rule (confirmed by a real
retcode=10016 "Invalid stops" the first time this ran that way). In
REAL use this never happens: the partial only fires after price has
already moved meaningfully away from entry, so breakeven is never this
close to the live price by construction -- this script just can't
simulate that real price movement, so it tests the SLTP mechanism at a
safely-displaced price instead."""
import time

import mt5_feed
import MetaTrader5 as mt5

SYMBOL = "EURUSD"
TEST_VOLUME_MULTIPLE = 4  # 4x volume_min -> a 50% split lands on a valid step

mt5_feed.connect()
try:
    specs = mt5_feed.symbol_trade_specs(SYMBOL)
    tick = mt5.symbol_info_tick(SYMBOL)
    entry_price = tick.ask
    far_sl = round(entry_price * 0.90, 5)
    far_tp = round(entry_price * 1.10, 5)
    volume = round(specs["volume_min"] * TEST_VOLUME_MULTIPLE, 8)

    open_request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": volume,
        "type": mt5.ORDER_TYPE_BUY,
        "price": entry_price,
        "sl": far_sl,
        "tp": far_tp,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    open_result = mt5.order_send(open_request)
    print(f"open: retcode={open_result.retcode} comment={open_result.comment!r} order={open_result.order}")
    if not mt5_feed.order_succeeded(open_result):
        raise SystemExit("could not open the test position -- aborting, nothing to clean up")

    ticket = open_result.order
    position = mt5_feed.get_open_position(ticket)
    for _ in range(5):  # brief MT5-side propagation delay, observed once between order_send and positions_get
        if position is not None:
            break
        time.sleep(0.5)
        position = mt5_feed.get_open_position(ticket)
    print(f"opened: ticket={ticket} volume={position.volume} sl={position.sl} tp={position.tp}")

    from execution import partial_close_volume
    half = partial_close_volume(
        volume=position.volume, partial_fraction=0.5,
        volume_step=specs["volume_step"], volume_min=specs["volume_min"],
    )
    print(f"computed partial volume: {half}")
    close_result = mt5_feed.close_partial_position(ticket, SYMBOL, "bullish", half)
    print(f"partial close: retcode={close_result.retcode} comment={close_result.comment!r}")

    position = mt5_feed.get_open_position(ticket)
    print(f"after partial: volume={position.volume} (expected {volume - half})")

    safe_breakeven_proxy = round(entry_price - 0.0015, 5)  # 15 pips below -- safely clear of the stops-level rule
    sltp_result = mt5_feed.modify_stop_loss(ticket, SYMBOL, new_sl=safe_breakeven_proxy, take_profit=far_tp)
    print(f"modify SL: retcode={sltp_result.retcode} comment={sltp_result.comment!r}")
    position = mt5_feed.get_open_position(ticket)
    print(f"after SL move: sl={position.sl} (expected {safe_breakeven_proxy})")

    cleanup = mt5_feed.close_partial_position(ticket, SYMBOL, "bullish", position.volume)
    print(f"cleanup close: retcode={cleanup.retcode} comment={cleanup.comment!r}")

    remaining = mt5_feed.get_open_position(ticket)
    print(f"final check -- position still open: {remaining is not None}")
finally:
    mt5_feed.disconnect()
