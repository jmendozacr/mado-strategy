from unittest import mock

import cli
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


def test_main_produces_overlay_png_for_valid_htf_ltf_pair(tmp_path):
    """REQ-03: --htf-csv/--htf-symbol activate pair mode alongside the
    base --csv/--symbol (LTF) flags.
    """
    ltf_path = tmp_path / "eurusd_1h.csv"
    htf_path = tmp_path / "eurusd_daily.csv"
    _write_valid_csv(ltf_path)
    _write_daily_csv(htf_path)
    output_dir = tmp_path / "out"

    exit_code = main(
        [
            "--csv", str(ltf_path), "--symbol", "EURUSD",
            "--htf-csv", str(htf_path), "--htf-symbol", "EURUSD",
            "--output-dir", str(output_dir),
        ]
    )

    assert exit_code == 0
    assert (output_dir / "overlay.png").exists()


def test_pair_mode_computes_crt_ranges_and_fvgs_exactly_once_each(tmp_path):
    """Perf fix regression: `_detect_all` previously called
    detect_crt_ranges twice for LTF, twice for HTF, and detect_fvgs twice
    for LTF, per pair-mode run — `detect_model1_signals`/`tag_alignment`
    independently recomputed what cli.py had already computed, each
    triggering ITS OWN module-level detect_crt_ranges/detect_fvgs import
    binding. Every import site (cli, entries.model1, alignment.htf_ltf) is
    spied so a regression can't hide behind an internal fallback call.
    """
    ltf_path = tmp_path / "eurusd_1h.csv"
    htf_path = tmp_path / "eurusd_daily.csv"
    _write_valid_csv(ltf_path)
    _write_daily_csv(htf_path)
    output_dir = tmp_path / "out"

    real_detect_crt_ranges = cli.detect_crt_ranges
    real_detect_fvgs = cli.detect_fvgs

    with (
        mock.patch("cli.detect_crt_ranges", side_effect=real_detect_crt_ranges) as cli_crt_ranges,
        mock.patch("entries.model1.detect_crt_ranges", side_effect=real_detect_crt_ranges) as model1_crt_ranges,
        mock.patch("alignment.htf_ltf.detect_crt_ranges", side_effect=real_detect_crt_ranges) as align_crt_ranges,
        mock.patch("cli.detect_fvgs", side_effect=real_detect_fvgs) as cli_fvgs,
        mock.patch("entries.model1.detect_fvgs", side_effect=real_detect_fvgs) as model1_fvgs,
    ):
        exit_code = main(
            [
                "--csv", str(ltf_path), "--symbol", "EURUSD",
                "--htf-csv", str(htf_path), "--htf-symbol", "EURUSD",
                "--output-dir", str(output_dir),
            ]
        )

    assert exit_code == 0
    total_crt_ranges_calls = (
        cli_crt_ranges.call_count + model1_crt_ranges.call_count + align_crt_ranges.call_count
    )
    # One LTF call + one HTF call — not two of each — regardless of which
    # module ends up making them.
    assert total_crt_ranges_calls == 2
    # LTF only — FVGs aren't detected on the HTF series.
    assert cli_fvgs.call_count + model1_fvgs.call_count == 1


def test_main_rejects_htf_csv_without_htf_symbol(tmp_path, capsys):
    """--htf-csv and --htf-symbol must be provided together."""
    ltf_path = tmp_path / "eurusd_1h.csv"
    htf_path = tmp_path / "eurusd_daily.csv"
    _write_valid_csv(ltf_path)
    _write_daily_csv(htf_path)
    output_dir = tmp_path / "out"

    exit_code = main(
        [
            "--csv", str(ltf_path), "--symbol", "EURUSD",
            "--htf-csv", str(htf_path),
            "--output-dir", str(output_dir),
        ]
    )

    assert exit_code == 1
    assert "--htf-symbol" in capsys.readouterr().err


def test_main_returns_1_for_mismatched_instrument_pair(tmp_path, capsys):
    """REQ-27.1: mismatched htf/ltf symbols are rejected, naming both."""
    ltf_path = tmp_path / "eurusd_1h.csv"
    htf_path = tmp_path / "gbpusd_daily.csv"
    _write_valid_csv(ltf_path)
    _write_daily_csv(htf_path)
    output_dir = tmp_path / "out"

    exit_code = main(
        [
            "--csv", str(ltf_path), "--symbol", "EURUSD",
            "--htf-csv", str(htf_path), "--htf-symbol", "GBPUSD",
            "--output-dir", str(output_dir),
        ]
    )

    stderr = capsys.readouterr().err
    assert exit_code == 1
    assert "EURUSD" in stderr
    assert "GBPUSD" in stderr


def test_main_returns_1_for_unlisted_timeframe_pairing(tmp_path, capsys):
    """REQ-04.2: Daily HTF + 1H LTF where the LTF file is ALSO daily
    (mismatched pairing) is rejected, citing the expected 1H.
    """
    ltf_path = tmp_path / "eurusd_daily_ltf.csv"
    htf_path = tmp_path / "eurusd_daily_htf.csv"
    _write_daily_csv(ltf_path)
    _write_daily_csv(htf_path)
    output_dir = tmp_path / "out"

    exit_code = main(
        [
            "--csv", str(ltf_path), "--symbol", "EURUSD",
            "--htf-csv", str(htf_path), "--htf-symbol", "EURUSD",
            "--output-dir", str(output_dir),
        ]
    )

    assert exit_code == 1
    assert "1H" in capsys.readouterr().err
