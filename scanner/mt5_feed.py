"""Pulls fresh candles from the user's locally-running MT5 terminal and
converts them to the exact same core.candle.OHLCSeries type the detector
already consumes -- never a separate parallel candle representation.

odd/tasks/scanner-auto-execution.md T2: also the thin (deliberately
untested, like the rest of this module -- no live terminal to test
against outside a real MT5 session) live-calling wrappers for account
balance, symbol trade specs, and pending-order placement. All real
decision logic (lot sizing, order type) lives in execution.py's pure
functions instead -- this module only ever marshals MT5's own types.
"""
from datetime import datetime, timezone

import MetaTrader5 as mt5

from core.candle import Candle, OHLCSeries

_ORDER_TYPE = {
    "BUY_LIMIT": mt5.ORDER_TYPE_BUY_LIMIT,
    "BUY_STOP": mt5.ORDER_TYPE_BUY_STOP,
    "SELL_LIMIT": mt5.ORDER_TYPE_SELL_LIMIT,
    "SELL_STOP": mt5.ORDER_TYPE_SELL_STOP,
}

_MT5_TIMEFRAME_MAP = {
    "M15": mt5.TIMEFRAME_M15,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}
# core.pairing_table.TIMEFRAME_DURATIONS' own labels -- NOT the same
# strings as MT5's own timeframe names (caught by a real KeyError the
# first time this ran against live data: "H4" is not a label this
# codebase recognizes anywhere, it's "4H").
_OHLCSERIES_TIMEFRAME_LABEL = {"M15": "15M", "H4": "4H", "D1": "D"}


class MT5ConnectionError(Exception):
    pass


def connect() -> None:
    if not mt5.initialize():
        raise MT5ConnectionError(f"MetaTrader5.initialize() failed: {mt5.last_error()}")


def disconnect() -> None:
    mt5.shutdown()


def fetch_series(symbol: str, timeframe: str, count: int) -> OHLCSeries:
    """Pulls the `count` most recent CLOSED candles for `symbol`/`timeframe`.
    REQ (mirrors ingestion.loader.load_mt5_csv's own contract): candles are
    returned oldest-to-newest, matching what OHLCSeries/core.candle
    everywhere else in the detector expects."""
    mt5_timeframe = _MT5_TIMEFRAME_MAP[timeframe]
    rates = mt5.copy_rates_from_pos(symbol, mt5_timeframe, 1, count)
    if rates is None or len(rates) == 0:
        raise MT5ConnectionError(f"copy_rates_from_pos({symbol}, {timeframe}) returned no data: {mt5.last_error()}")
    candles = tuple(
        Candle(
            timestamp=datetime.fromtimestamp(int(row["time"]), tz=timezone.utc).replace(tzinfo=None),
            open=float(row["open"]), high=float(row["high"]), low=float(row["low"]), close=float(row["close"]),
        )
        for row in rates
    )
    return OHLCSeries(candles=candles, instrument=symbol, timeframe=_OHLCSERIES_TIMEFRAME_LABEL[timeframe])


def symbol_trade_specs(symbol: str) -> dict:
    """execution.calculate_lot_size's real-world inputs, straight from the
    broker -- never hand-derived (REQ, odd/tasks/scanner-auto-execution.md
    S3): this is the whole reason S3 rejects redoing the backtest's own
    manual FX-rate conversion for a USDCAD-style pair, MT5 already knows
    the real contract specs for every symbol."""
    info = mt5.symbol_info(symbol)
    if info is None:
        raise MT5ConnectionError(f"symbol_info({symbol}) failed: {mt5.last_error()}")
    return {
        "tick_value": float(info.trade_tick_value), "tick_size": float(info.trade_tick_size),
        "volume_min": float(info.volume_min), "volume_max": float(info.volume_max),
        "volume_step": float(info.volume_step),
    }


def current_price(symbol: str, direction: str) -> float:
    """The real fill-side price for comparing against a signal's own
    `entry_price` (execution.pending_order_type) -- ask for a bullish
    (buy-side) order, bid for a bearish (sell-side) one, matching which
    side of the spread that order would actually transact on."""
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise MT5ConnectionError(f"symbol_info_tick({symbol}) failed: {mt5.last_error()}")
    return float(tick.ask if direction == "bullish" else tick.bid)


def current_exit_price(symbol: str, direction: str) -> float:
    """The real EXIT-side price for a position already open in
    `direction` -- the OPPOSITE side from `current_price`'s own entry
    convention: a bullish (buy) position closes/is valued at the bid, a
    bearish (sell) one at the ask (odd/tasks/scanner-breakeven-after-
    partial.md T4, matches `close_partial_position`'s own side choice)."""
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise MT5ConnectionError(f"symbol_info_tick({symbol}) failed: {mt5.last_error()}")
    return float(tick.bid if direction == "bullish" else tick.ask)


def send_pending_order(
    symbol: str, order_type: str, volume: float, entry_price: float, stop_loss: float, take_profit: float,
    max_fill_wait_candles: int, candle_minutes: int = 15,
):
    """Places the PENDING order (odd/tasks/scanner-auto-execution.md S4/S5)
    and returns MT5's own result object -- the caller (main.py) checks
    `result.retcode`, this function never raises on a trade-side rejection
    (a rejected/requoted order is an expected outcome, not a connection
    failure -- only a dead connection raises, same MT5ConnectionError
    convention as every other function here)."""
    if order_type not in _ORDER_TYPE:
        raise ValueError(f"unknown order_type: {order_type!r}, expected one of {sorted(_ORDER_TYPE)}")
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise MT5ConnectionError(f"symbol_info_tick({symbol}) failed: {mt5.last_error()}")
    # Expiration must be computed off the BROKER's own server clock (tick.time),
    # never the local machine's UTC -- confirmed by a real retcode=10022
    # "Invalid expiration" when this used datetime.now(timezone.utc): this
    # server runs ~2h ahead, so a locally-computed "future" timestamp was
    # already in the past from the server's point of view.
    expiration_epoch = int(tick.time) + max_fill_wait_candles * candle_minutes * 60
    request = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": volume,
        "type": _ORDER_TYPE[order_type],
        "price": entry_price,
        "sl": stop_loss,
        "tp": take_profit,
        "type_time": mt5.ORDER_TIME_SPECIFIED,
        "expiration": expiration_epoch,
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }
    result = mt5.order_send(request)
    if result is None:
        raise MT5ConnectionError(f"order_send({symbol}) returned None: {mt5.last_error()}")
    return result


def order_succeeded(result) -> bool:
    return result.retcode == mt5.TRADE_RETCODE_DONE


def get_pending_order(ticket: int):
    """`None` once the order has either filled (became a position) or
    been cancelled/expired -- the caller tells those two apart by
    checking `get_open_position` too (filled: a position exists;
    expired/cancelled: neither exists)."""
    orders = mt5.orders_get(ticket=ticket)
    if not orders:
        return None
    return orders[0]


def get_open_position(ticket: int):
    """odd/tasks/scanner-breakeven-after-partial.md T3: `None` when the
    position isn't open yet (pending order not filled) or has already
    closed -- both read the same to the caller, "nothing to manage yet/
    anymore". MT5 fills a pending order's position under the SAME ticket
    number as the order that opened it."""
    positions = mt5.positions_get(ticket=ticket)
    if not positions:
        return None
    return positions[0]


def close_partial_position(ticket: int, symbol: str, direction: str, volume: float):
    """Closes `volume` lots of the position at `ticket` -- a BUY position
    (bullish) closes via a SELL deal at the bid, a SELL position via a BUY
    deal at the ask (the OPPOSITE side from the one that opened it, same
    convention `current_price` already encodes for entries, inverted
    here for an exit). Never raises on a trade-side rejection, same
    MT5ConnectionError-only-on-dead-connection convention as every other
    function here."""
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise MT5ConnectionError(f"symbol_info_tick({symbol}) failed: {mt5.last_error()}")
    if direction == "bullish":
        order_type, price = mt5.ORDER_TYPE_SELL, tick.bid
    else:
        order_type, price = mt5.ORDER_TYPE_BUY, tick.ask
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "position": ticket,
        "price": price,
        # TRADE_ACTION_DEAL (immediate market execution) needs FOK/IOC, not
        # RETURN -- confirmed by a real retcode=10030 "Unsupported filling
        # mode" (RETURN is only valid for TRADE_ACTION_PENDING's own
        # send_pending_order, which this is NOT).
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    if result is None:
        raise MT5ConnectionError(f"order_send(close partial {ticket}) returned None: {mt5.last_error()}")
    return result


def modify_stop_loss(ticket: int, symbol: str, new_sl: float, take_profit: float):
    """Moves the position's stop-loss to `new_sl` (breakeven, odd/tasks/
    scanner-breakeven-after-partial.md T4) -- `take_profit` must be
    resent alongside it or MT5 clears the existing take-profit instead of
    leaving it unchanged."""
    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": symbol,
        "position": ticket,
        "sl": new_sl,
        "tp": take_profit,
    }
    result = mt5.order_send(request)
    if result is None:
        raise MT5ConnectionError(f"order_send(modify SL {ticket}) returned None: {mt5.last_error()}")
    return result
