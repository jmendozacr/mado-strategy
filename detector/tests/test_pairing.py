import pytest

from core.pairing_table import PairingError
from ingestion.pairing import load_pair

MT5_HEADER = "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>"


def _row(date: str, time: str, o: float, h: float, l: float, c: float) -> str:
    return f"{date}\t{time}\t{o}\t{h}\t{l}\t{c}\t100\t0\t2"


def _write_daily_csv(path):
    path.write_text(
        "\n".join(
            [
                MT5_HEADER,
                _row("2026.01.01", "00:00:00", 1.1000, 1.1010, 1.0990, 1.1005),
                _row("2026.01.02", "00:00:00", 1.1005, 1.1020, 1.1000, 1.1015),
                _row("2026.01.03", "00:00:00", 1.1015, 1.1030, 1.1010, 1.1025),
            ]
        )
    )


def _write_hourly_csv(path):
    path.write_text(
        "\n".join(
            [
                MT5_HEADER,
                _row("2026.01.01", "00:00:00", 1.1000, 1.1010, 1.0990, 1.1005),
                _row("2026.01.01", "01:00:00", 1.1005, 1.1020, 1.1000, 1.1015),
                _row("2026.01.01", "02:00:00", 1.1015, 1.1030, 1.1010, 1.1025),
            ]
        )
    )


def test_loads_valid_daily_htf_and_1h_ltf_pair(tmp_path):
    """REQ-03.1: same-instrument Daily HTF + 1H LTF loads to a pair of
    OHLCSeries.
    """
    htf_path = tmp_path / "eurusd_daily.csv"
    ltf_path = tmp_path / "eurusd_1h.csv"
    _write_daily_csv(htf_path)
    _write_hourly_csv(ltf_path)

    htf_series, ltf_series = load_pair(
        htf_csv=str(htf_path),
        htf_symbol="EURUSD",
        ltf_csv=str(ltf_path),
        ltf_symbol="EURUSD",
    )

    assert htf_series.instrument == "EURUSD"
    assert htf_series.timeframe == "D"
    assert ltf_series.instrument == "EURUSD"
    assert ltf_series.timeframe == "1H"


def test_rejects_mismatched_instrument_pairing_naming_both(tmp_path):
    """REQ-27.1: htf_symbol != ltf_symbol -> rejected, naming both
    instruments.
    """
    htf_path = tmp_path / "eurusd_daily.csv"
    ltf_path = tmp_path / "gbpusd_1h.csv"
    _write_daily_csv(htf_path)
    _write_hourly_csv(ltf_path)

    with pytest.raises(PairingError, match="EURUSD") as excinfo:
        load_pair(
            htf_csv=str(htf_path),
            htf_symbol="EURUSD",
            ltf_csv=str(ltf_path),
            ltf_symbol="GBPUSD",
        )
    assert "GBPUSD" in str(excinfo.value)


def test_rejects_unlisted_timeframe_pairing(tmp_path):
    """REQ-04.2: Daily HTF + Daily LTF is not a listed pairing (Daily
    expects 1H) -> rejected via core.pairing_table.
    """
    htf_path = tmp_path / "eurusd_daily.csv"
    ltf_path = tmp_path / "eurusd_daily2.csv"
    _write_daily_csv(htf_path)
    _write_daily_csv(ltf_path)

    with pytest.raises(PairingError, match="1H"):
        load_pair(
            htf_csv=str(htf_path),
            htf_symbol="EURUSD",
            ltf_csv=str(ltf_path),
            ltf_symbol="EURUSD",
        )
