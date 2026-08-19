from datetime import datetime

import pytest

from ingestion.loader import LoadError, load_mt5_csv

MT5_HEADER = "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>"


def _row(date: str, time: str, o: float, h: float, l: float, c: float) -> str:
    return f"{date}\t{time}\t{o}\t{h}\t{l}\t{c}\t100\t0\t2"


def test_loads_valid_mt5_csv_with_ascending_timestamps_and_instrument(tmp_path):
    csv_path = tmp_path / "eurusd.csv"
    csv_path.write_text(
        "\n".join(
            [
                MT5_HEADER,
                _row("2026.01.01", "00:00:00", 1.1000, 1.1010, 1.0990, 1.1005),
                _row("2026.01.01", "01:00:00", 1.1005, 1.1020, 1.1000, 1.1015),
            ]
        )
    )

    series = load_mt5_csv(str(csv_path), symbol="EURUSD")

    assert series.instrument == "EURUSD"
    assert len(series.candles) == 2
    assert series.candles[0].timestamp < series.candles[1].timestamp
    assert series.candles[0].timestamp == datetime(2026, 1, 1, 0, 0, 0)
    assert series.candles[0].open == 1.1000
    assert series.candles[0].high == 1.1010
    assert series.candles[0].low == 1.0990
    assert series.candles[0].close == 1.1005


def test_rejects_duplicate_timestamps(tmp_path):
    csv_path = tmp_path / "eurusd.csv"
    csv_path.write_text(
        "\n".join(
            [
                MT5_HEADER,
                _row("2026.01.01", "00:00:00", 1.1000, 1.1010, 1.0990, 1.1005),
                _row("2026.01.01", "00:00:00", 1.1005, 1.1020, 1.1000, 1.1015),
            ]
        )
    )

    with pytest.raises(LoadError, match="2026-01-01T00:00:00"):
        load_mt5_csv(str(csv_path), symbol="EURUSD")


def test_rejects_non_monotonic_timestamps(tmp_path):
    csv_path = tmp_path / "eurusd.csv"
    csv_path.write_text(
        "\n".join(
            [
                MT5_HEADER,
                _row("2026.01.01", "01:00:00", 1.1000, 1.1010, 1.0990, 1.1005),
                _row("2026.01.01", "00:00:00", 1.1005, 1.1020, 1.1000, 1.1015),
            ]
        )
    )

    with pytest.raises(LoadError, match="non-monotonic"):
        load_mt5_csv(str(csv_path), symbol="EURUSD")


def test_rejects_csv_missing_high_column(tmp_path):
    csv_path = tmp_path / "eurusd.csv"
    csv_path.write_text(
        "\n".join(
            [
                "<DATE>\t<TIME>\t<OPEN>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>",
                "2026.01.01\t00:00:00\t1.1000\t1.0990\t1.1005\t100\t0\t2",
            ]
        )
    )

    with pytest.raises(LoadError, match="<HIGH>"):
        load_mt5_csv(str(csv_path), symbol="EURUSD")


def test_infers_timeframe_from_modal_candle_spacing(tmp_path):
    csv_path = tmp_path / "eurusd_daily.csv"
    csv_path.write_text(
        "\n".join(
            [
                MT5_HEADER,
                _row("2026.01.01", "00:00:00", 1.1000, 1.1010, 1.0990, 1.1005),
                _row("2026.01.02", "00:00:00", 1.1005, 1.1020, 1.1000, 1.1015),
                _row("2026.01.03", "00:00:00", 1.1015, 1.1030, 1.1010, 1.1025),
            ]
        )
    )

    series = load_mt5_csv(str(csv_path), symbol="EURUSD")

    assert series.timeframe == "D"
