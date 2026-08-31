import csv

from core.candle import OHLCSeries

MT5_HEADER = "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>"


def _row(date: str, time: str, o: float, h: float, l: float, c: float) -> str:
    return f"{date}\t{time}\t{o}\t{h}\t{l}\t{c}\t100\t0\t2"


def _read_csv_rows(path):
    with open(path, newline="") as f:
        return list(csv.reader(f))


def write_series_csv(series: OHLCSeries, path) -> None:
    """Design §8.9: renders any `OHLCSeries` as an MT5-format CSV, reading
    each candle's own timestamp — unlike the per-fixture writers in
    test_cli_backtest_e2e.py, which hard-code a single date."""
    rows = [MT5_HEADER]
    for candle in series.candles:
        rows.append(
            _row(
                candle.timestamp.strftime("%Y.%m.%d"), candle.timestamp.strftime("%H:%M:%S"),
                candle.open, candle.high, candle.low, candle.close,
            )
        )
    path.write_text("\n".join(rows))
