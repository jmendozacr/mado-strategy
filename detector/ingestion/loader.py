import math

import pandas as pd

from core.candle import Candle, OHLCSeries
from core.pairing_table import TIMEFRAME_DURATIONS

REQUIRED_COLUMNS = ("<DATE>", "<OPEN>", "<HIGH>", "<LOW>", "<CLOSE>")

_TIMEFRAME_REFERENCE_DELTAS = tuple(
    (delta, timeframe) for timeframe, delta in TIMEFRAME_DURATIONS.items()
)


class LoadError(Exception):
    pass


_OHLC_COLUMNS = ("<OPEN>", "<HIGH>", "<LOW>", "<CLOSE>")


def load_mt5_csv(path: str, symbol: str) -> OHLCSeries:
    # na_filter=False: with dtype=str alone, pandas still applies its
    # default NA-sentinel detection ("", "N/A", "NaN", ...) and silently
    # turns a blank/sentinel OHLC cell into NaN — float(nan) then succeeds,
    # producing a `nan` field with no error. Disabling it keeps such cells
    # as literal strings, so they fail explicitly in the per-row float
    # conversion below instead of corrupting the candle.
    df = pd.read_csv(path, sep="\t", dtype=str, na_filter=False)

    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise LoadError(f"missing required column(s): {', '.join(missing)}")

    try:
        # V3/REQ-67: MT5's Daily (D1) export omits <TIME> entirely — no
        # intraday time on a daily bar. When absent, default to midnight;
        # when present (H4/M15/etc.), parse it same as before.
        if "<TIME>" in df.columns:
            timestamps = pd.to_datetime(
                df["<DATE>"] + " " + df["<TIME>"], format="%Y.%m.%d %H:%M:%S"
            )
        else:
            timestamps = pd.to_datetime(df["<DATE>"], format="%Y.%m.%d")
    except ValueError as e:
        raise LoadError(f"malformed date/time: {e}")

    candles = tuple(_row_to_candle(df, timestamps, i) for i in range(len(df)))

    _validate_timestamp_order(candles)

    return OHLCSeries(
        candles=candles, instrument=symbol, timeframe=_infer_timeframe(candles)
    )


def _row_to_candle(df: pd.DataFrame, timestamps: pd.Series, i: int) -> Candle:
    values = {}
    for column in _OHLC_COLUMNS:
        raw = df[column].iloc[i]
        try:
            parsed = float(raw)
        except ValueError:
            raise LoadError(f"malformed value at row {i}, column {column}: {raw!r}")
        # float() itself parses "nan"/"NaN"/"inf"/"Infinity" (case-
        # insensitive) into a valid non-finite float with no exception —
        # independent of pandas' own NA-sentinel handling above.
        if not math.isfinite(parsed):
            raise LoadError(f"non-finite value at row {i}, column {column}: {raw!r}")
        values[column] = parsed

    try:
        timestamp = timestamps.iloc[i].to_pydatetime()
    except (ValueError, OverflowError) as e:
        # A string like "0000.01.01" parses into a valid pandas Timestamp,
        # but stdlib `datetime` only supports years 1-9999 — to_pydatetime()
        # raises here, past the batch pd.to_datetime() try/except above.
        raise LoadError(f"malformed date/time at row {i}: {e}")

    return Candle(
        timestamp=timestamp,
        open=values["<OPEN>"],
        high=values["<HIGH>"],
        low=values["<LOW>"],
        close=values["<CLOSE>"],
    )


def _validate_timestamp_order(candles: tuple[Candle, ...]) -> None:
    for i in range(1, len(candles)):
        previous = candles[i - 1].timestamp
        current = candles[i].timestamp
        if current == previous:
            raise LoadError(f"duplicate timestamp: {current.isoformat()}")
        if current < previous:
            raise LoadError(
                f"non-monotonic timestamp at row {i}: {current.isoformat()} "
                f"follows {previous.isoformat()}"
            )


def _infer_timeframe(candles: tuple[Candle, ...]) -> str:
    if len(candles) < 2:
        return "1H"

    deltas = [
        candles[i].timestamp - candles[i - 1].timestamp
        for i in range(1, len(candles))
    ]
    modal_delta = max(set(deltas), key=deltas.count)

    closest = min(
        _TIMEFRAME_REFERENCE_DELTAS, key=lambda ref: abs(ref[0] - modal_delta)
    )
    return closest[1]
