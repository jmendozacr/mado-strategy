from datetime import datetime
from unittest import mock

from fixtures.synthetic import (
    model1_pre_confirmation_breach_setup,
    model1_purge_engulf_charter2_setup,
)

import cli
from cli import main
from core.config import KillZoneConfig

MT5_HEADER = "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>"


def _row(date: str, time: str, o: float, h: float, l: float, c: float) -> str:
    return f"{date}\t{time}\t{o}\t{h}\t{l}\t{c}\t100\t0\t2"


def _series_to_mt5_csv_text(series) -> str:
    lines = [MT5_HEADER]
    for candle in series.candles:
        lines.append(
            _row(
                candle.timestamp.strftime("%Y.%m.%d"), candle.timestamp.strftime("%H:%M:%S"),
                candle.open, candle.high, candle.low, candle.close,
            )
        )
    return "\n".join(lines)


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


def test_main_returns_1_and_prints_error_for_missing_csv_file(tmp_path, capsys):
    """A nonexistent --csv path must fail via the CLI's normal clean
    `error: ...` stderr contract, not an uncaught FileNotFoundError
    traceback — main() only wrapped (LoadError, PairingError) around the
    load step, missing the OSError pandas.read_csv raises for a missing
    file.
    """
    missing_csv = tmp_path / "does-not-exist.csv"
    output_dir = tmp_path / "out"

    exit_code = main(
        ["--csv", str(missing_csv), "--symbol", "EURUSD", "--output-dir", str(output_dir)]
    )

    assert exit_code == 1
    assert "error:" in capsys.readouterr().err
    assert not (output_dir / "overlay.png").exists()


def test_main_returns_1_and_prints_error_when_output_dir_path_is_a_file(tmp_path, capsys):
    """--output-dir pointing through an existing FILE (not a directory)
    makes `output_dir.mkdir(...)` raise `NotADirectoryError`/`FileExistsError`
    (both `OSError` subclasses) — this ran unguarded, past the try/except
    that only wraps the CSV-loading step, escaping as a raw traceback
    instead of the CLI's `error: ...` + exit-1 contract.
    """
    csv_path = tmp_path / "eurusd.csv"
    _write_valid_csv(csv_path)
    blocking_file = tmp_path / "blocker"
    blocking_file.write_text("not a directory")
    output_dir = blocking_file / "out"

    exit_code = main(
        ["--csv", str(csv_path), "--symbol", "EURUSD", "--output-dir", str(output_dir)]
    )

    assert exit_code == 1
    assert "error:" in capsys.readouterr().err


def test_types_alignment_alone_includes_model1_and_alignment_rows(tmp_path):
    """REQ-23: `--types alignment` alone (no `model1` token) must still
    populate model1_signals/aligned_signals — `_filter_by_types` gated
    both purely on `"model1" in types`, so `--types alignment` alone
    produced zero rows/markers in both the chart and detections.csv.
    """
    ltf_path = tmp_path / "eurusd_1h.csv"
    htf_path = tmp_path / "eurusd_daily.csv"
    ltf_path.write_text(_series_to_mt5_csv_text(model1_purge_engulf_charter2_setup()))
    _write_daily_csv(htf_path)
    output_dir = tmp_path / "out"

    exit_code = main(
        [
            "--csv", str(ltf_path), "--symbol", "EURUSD",
            "--htf-csv", str(htf_path), "--htf-symbol", "EURUSD",
            "--output-dir", str(output_dir),
            "--types", "alignment",
        ]
    )

    assert exit_code == 0
    csv_rows = (output_dir / "detections.csv").read_text().splitlines()
    assert any(row.split(",")[1] == "model1" for row in csv_rows[1:])


def test_invalidated_model1_signal_excluded_from_chart_but_kept_in_csv(tmp_path):
    """An INVALIDATED Model-1 signal (REQ-18: emitted, not dropped, for a
    pre-confirmation breach) renders identically to a live PENDING/
    CONFIRMED signal if passed through unfiltered — misleading for a
    trader scanning the chart. It must be excluded from what's plotted,
    while `detections.csv` keeps it (its `status` column already
    distinguishes it).
    """
    ltf_path = tmp_path / "eurusd_1h.csv"
    ltf_path.write_text(_series_to_mt5_csv_text(model1_pre_confirmation_breach_setup()))
    output_dir = tmp_path / "out"

    with mock.patch("cli.render_chart", side_effect=cli.render_chart) as chart:
        exit_code = main(
            ["--csv", str(ltf_path), "--symbol", "EURUSD", "--output-dir", str(output_dir)]
        )

    assert exit_code == 0
    charted_model1_signals = chart.call_args.kwargs["model1_signals"]
    assert all(s.status.value != "invalidated" for s in charted_model1_signals)

    csv_rows = (output_dir / "detections.csv").read_text().splitlines()
    model1_rows = [row for row in csv_rows[1:] if row.split(",")[1] == "model1"]
    assert any(row.split(",")[5] == "invalidated" for row in model1_rows)


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


def test_ny_kill_zone_boundary_shifts_with_dst_not_fixed_utc_offset():
    """New REQ-29: 11:00 UTC is the NY Kill Zone open (07:00 local) during
    EDT (summer, UTC-4) but one hour before it (06:00 local) during EST
    (winter, UTC-5) — proves the predicate converts via real
    America/New_York tz rules, not a fixed UTC offset (this session's
    real-data finding: broker candle timestamps are UTC with no further
    broker offset).
    """
    config = KillZoneConfig()
    winter = datetime(2026, 1, 5, 11, 0, 0)  # EST: 11:00 UTC -> 06:00 NY local
    summer = datetime(2026, 7, 6, 11, 0, 0)  # EDT: 11:00 UTC -> 07:00 NY local

    assert cli._in_ny_kill_zone(winter, config) is False
    assert cli._in_ny_kill_zone(summer, config) is True


def test_ny_kill_zone_upper_bound_is_exclusive():
    config = KillZoneConfig()
    just_before_close = datetime(2026, 7, 6, 14, 59, 0)  # EDT: 10:59 NY local
    at_close = datetime(2026, 7, 6, 15, 0, 0)  # EDT: 11:00 NY local

    assert cli._in_ny_kill_zone(just_before_close, config) is True
    assert cli._in_ny_kill_zone(at_close, config) is False
