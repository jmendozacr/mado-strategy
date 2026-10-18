"""Pulls fresh candles from the user's locally-running MT5 terminal and
converts them to the exact same core.candle.OHLCSeries type the detector
already consumes -- never a separate parallel candle representation.
"""
from datetime import datetime, timezone

import MetaTrader5 as mt5

from core.candle import Candle, OHLCSeries

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
