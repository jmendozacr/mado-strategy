from cli import main

MT5_HEADER = "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>"


def _row(date: str, time: str, o: float, h: float, l: float, c: float) -> str:
    return f"{date}\t{time}\t{o}\t{h}\t{l}\t{c}\t100\t0\t2"


def _write_valid_csv(path):
    path.write_text(
        "\n".join(
            [
                MT5_HEADER,
                _row("2026.01.01", "00:00:00", 1.1000, 1.1005, 1.0995, 1.1000),
                _row("2026.01.01", "01:00:00", 1.1000, 1.1020, 1.0995, 1.1005),
                _row("2026.01.01", "02:00:00", 1.1005, 1.1010, 1.0995, 1.1000),
            ]
        )
    )


def test_main_produces_overlay_png_for_valid_single_series_csv(tmp_path, capsys):
    csv_path = tmp_path / "eurusd.csv"
    _write_valid_csv(csv_path)
    output_dir = tmp_path / "out"

    exit_code = main(
        ["--csv", str(csv_path), "--symbol", "EURUSD", "--output-dir", str(output_dir)]
    )

    assert exit_code == 0
    assert (output_dir / "overlay.png").exists()
    assert (output_dir / "overlay.png").stat().st_size > 0


def test_main_returns_1_and_prints_error_for_malformed_csv(tmp_path, capsys):
    csv_path = tmp_path / "malformed.csv"
    csv_path.write_text(
        "\n".join(
            [
                "<DATE>\t<TIME>\t<OPEN>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>",
                "2026.01.01\t00:00:00\t1.1000\t1.0990\t1.1005\t100\t0\t2",
            ]
        )
    )
    output_dir = tmp_path / "out"

    exit_code = main(
        ["--csv", str(csv_path), "--symbol", "EURUSD", "--output-dir", str(output_dir)]
    )

    assert exit_code == 1
    assert "<HIGH>" in capsys.readouterr().err
    assert not (output_dir / "overlay.png").exists()
