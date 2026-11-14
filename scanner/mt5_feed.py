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
from datetime import datetime, timedelta, timezone

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


def account_balance() -> float:
    info = mt5.account_info()
    if info is None:
        raise MT5ConnectionError(f"account_info() failed: {mt5.last_error()}")
    return float(info.balance)


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
    expiration = datetime.now(timezone.utc) + timedelta(minutes=max_fill_wait_candles * candle_minutes)
    request = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": volume,
        "type": _ORDER_TYPE[order_type],
        "price": entry_price,
        "sl": stop_loss,
        "tp": take_profit,
        "type_time": mt5.ORDER_TIME_SPECIFIED,
        "expiration": int(expiration.timestamp()),
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }
    result = mt5.order_send(request)
    if result is None:
        raise MT5ConnectionError(f"order_send({symbol}) returned None: {mt5.last_error()}")
    return result


def order_succeeded(result) -> bool:
    return result.retcode == mt5.TRADE_RETCODE_DONE
