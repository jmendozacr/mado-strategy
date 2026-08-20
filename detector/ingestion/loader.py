import pandas as pd

from core.candle import Candle, OHLCSeries
from core.pairing_table import TIMEFRAME_DURATIONS

REQUIRED_COLUMNS = ("<DATE>", "<TIME>", "<OPEN>", "<HIGH>", "<LOW>", "<CLOSE>")

_TIMEFRAME_REFERENCE_DELTAS = tuple(
    (delta, timeframe) for timeframe, delta in TIMEFRAME_DURATIONS.items()
)


class LoadError(Exception):
    pass


def load_mt5_csv(path: str, symbol: str) -> OHLCSeries:
    df = pd.read_csv(path, sep="\t", dtype=str)

    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise LoadError(f"missing required column(s): {', '.join(missing)}")

    timestamps = pd.to_datetime(
        df["<DATE>"] + " " + df["<TIME>"], format="%Y.%m.%d %H:%M:%S"
    )

    candles = tuple(
        Candle(
            timestamp=timestamps.iloc[i].to_pydatetime(),
            open=float(df["<OPEN>"].iloc[i]),
            high=float(df["<HIGH>"].iloc[i]),
            low=float(df["<LOW>"].iloc[i]),
            close=float(df["<CLOSE>"].iloc[i]),
        )
        for i in range(len(df))
    )

    _validate_timestamp_order(candles)

    return OHLCSeries(
        candles=candles, instrument=symbol, timeframe=_infer_timeframe(candles)
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
