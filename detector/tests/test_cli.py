from datetime import datetime
from unittest import mock

from fixtures.mt5_csv import MT5_HEADER, _row
from fixtures.synthetic import (
    model1_dual_purge_and_fvg_fill_charter2_setup,
    model1_pre_confirmation_breach_setup,
    model1_purge_engulf_charter2_setup,
)

import cli
from alignment.htf_ltf import AlignedSignal
from cli import main
from core.candle import Candle, OHLCSeries
from core.config import DetectorConfig, KillZoneConfig
from core.key_level import KeyLevel
from core.kill_zone import in_ny_kill_zone
from core.results import DetectionStatus
from entries.model1 import Model1Signal
from primitives.crt_range import CRTRange


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

    REQ-57.1 (this change) deliberately adds ONE new detect_fvgs call on
    the HTF series (Key Level sourcing, §8.6) — the invariant this test
    pins is "each series' FVGs computed exactly once", not "never on HTF".
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
    # cli.py computes LTF fvgs itself (reused by detect_model1_signals, so
    # entries.model1 never redundantly recomputes them — model1_fvgs stays
    # 0) plus one HTF call for Key Level sourcing (REQ-57.1) — both via
    # cli.py's own binding, two total, not two of each.
    assert cli_fvgs.call_count == 2
    assert model1_fvgs.call_count == 0


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


def test_main_rejects_daily_csv_without_daily_symbol(tmp_path, capsys):
    """REQ-67.3: --daily-csv and --daily-symbol must be provided together,
    mirroring --htf-csv/--htf-symbol's existing validation."""
    ltf_path = tmp_path / "eurusd_1h.csv"
    htf_path = tmp_path / "eurusd_daily.csv"
    daily_path = tmp_path / "eurusd_d.csv"
    _write_valid_csv(ltf_path)
    _write_daily_csv(htf_path)
    _write_daily_csv(daily_path)
    output_dir = tmp_path / "out"

    exit_code = main(
        [
            "--csv", str(ltf_path), "--symbol", "EURUSD",
            "--htf-csv", str(htf_path), "--htf-symbol", "EURUSD",
            "--daily-csv", str(daily_path),
            "--output-dir", str(output_dir),
        ]
    )

    assert exit_code == 1
    assert "--daily-symbol" in capsys.readouterr().err


def test_main_rejects_daily_csv_without_htf_csv(tmp_path, capsys):
    """Design executor note: --daily-csv without --htf-csv is rejected
    explicitly, mirroring --backtest's existing 'requires --htf-csv/
    --htf-symbol' pattern — Order Block confluence has no H4 purge to
    credit against without HTF present."""
    ltf_path = tmp_path / "eurusd_1h.csv"
    daily_path = tmp_path / "eurusd_d.csv"
    _write_valid_csv(ltf_path)
    _write_daily_csv(daily_path)
    output_dir = tmp_path / "out"

    exit_code = main(
        [
            "--csv", str(ltf_path), "--symbol", "EURUSD",
            "--daily-csv", str(daily_path), "--daily-symbol", "EURUSD",
            "--output-dir", str(output_dir),
        ]
    )

    assert exit_code == 1
    assert "--htf-csv" in capsys.readouterr().err


def test_main_returns_1_for_mismatched_daily_instrument(tmp_path, capsys):
    """ADR-F: --daily-symbol must match --symbol (mirrors load_pair's own
    instrument-match check), naming both in the error."""
    ltf_path = tmp_path / "eurusd_1h.csv"
    htf_path = tmp_path / "eurusd_daily.csv"
    daily_path = tmp_path / "gbpusd_d.csv"
    _write_valid_csv(ltf_path)
    _write_daily_csv(htf_path)
    _write_daily_csv(daily_path)
    output_dir = tmp_path / "out"

    exit_code = main(
        [
            "--csv", str(ltf_path), "--symbol", "EURUSD",
            "--htf-csv", str(htf_path), "--htf-symbol", "EURUSD",
            "--daily-csv", str(daily_path), "--daily-symbol", "GBPUSD",
            "--output-dir", str(output_dir),
        ]
    )

    stderr = capsys.readouterr().err
    assert exit_code == 1
    assert "EURUSD" in stderr
    assert "GBPUSD" in stderr


def test_main_produces_overlay_png_for_valid_daily_csv(tmp_path):
    """REQ-67.1: --daily-csv/--daily-symbol accepted alongside --htf-csv,
    run still succeeds end-to-end."""
    ltf_path = tmp_path / "eurusd_1h.csv"
    htf_path = tmp_path / "eurusd_daily.csv"
    daily_path = tmp_path / "eurusd_d.csv"
    _write_valid_csv(ltf_path)
    _write_daily_csv(htf_path)
    _write_daily_csv(daily_path)
    output_dir = tmp_path / "out"

    exit_code = main(
        [
            "--csv", str(ltf_path), "--symbol", "EURUSD",
            "--htf-csv", str(htf_path), "--htf-symbol", "EURUSD",
            "--daily-csv", str(daily_path), "--daily-symbol", "EURUSD",
            "--output-dir", str(output_dir),
        ]
    )

    assert exit_code == 0
    assert (output_dir / "overlay.png").exists()


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

    odd/tasks/model1-causal-retry-chain.md T3: swapped the fixture from
    the plain purge_engulf setup to the dual purge+fvg_fill one — the
    plain setup registers no Key Level against this test's bare 3-candle
    `_write_daily_csv` HTF (no FVG/Order Block forms on it), so its lone
    signal is correctly withheld by the REQ-56 confluence gate regardless
    of `--types` (the gate fix above now also withholds a causal
    `"unaligned"` tag, not just `"aligned"`, when neither a Key Level nor
    `fvg_fill` backs it) -- this test's own point is `--types alignment`
    inclusion, not confluence gating, so it needs a signal exempt from
    that gate on `fvg_fill` grounds alone, independent of any Key Level.
    """
    ltf_path = tmp_path / "eurusd_1h.csv"
    htf_path = tmp_path / "eurusd_daily.csv"
    ltf_path.write_text(_series_to_mt5_csv_text(model1_dual_purge_and_fvg_fill_charter2_setup()))
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


def test_detect_all_no_longer_takes_a_types_parameter_and_never_nulls_aligned_signals():
    """REQ-52.2: the dead `types` parameter is removed from `_detect_all`'s
    signature with no change to its observable output — display-only
    degradation now lives solely in `_filter_by_types` (C2/C2b)."""
    ltf_series = model1_purge_engulf_charter2_setup()
    htf_series = OHLCSeries(
        candles=(
            Candle(timestamp=datetime(2026, 1, 1, 0, 0, 0), open=1.1000, high=1.1030, low=1.0970, close=1.1010),
            Candle(timestamp=datetime(2026, 1, 2, 0, 0, 0), open=1.1010, high=1.1040, low=1.0980, close=1.1020),
        ),
        instrument="EURUSD", timeframe="D",
    )

    detections = cli._detect_all(ltf_series, htf_series, None, DetectorConfig())

    assert detections.aligned_signals is not None
    assert detections.model1_signals is not None


_HTF_CONTEXT = CRTRange(
    model="2-candle", high=1.1050, low=1.0950, start_index=0, end_index=1,
    resolution="true_break", resolved_at_index=1,
)
_KEY_LEVEL = KeyLevel(kind="fvg", top=1.1050, bottom=1.0950, origin_index=0, expiry_index=None)


def _model1_signal(confirmation_type="purge_engulf"):
    return Model1Signal(
        anchor_index=0, direction="bullish", purge_target=0.0,
        confirmation_type=confirmation_type, entry_type="body", entry_price=1.1000,
        retest_index=2, status=DetectionStatus.CONFIRMED, confirmation_index=2, origin_index=0,
    )


def _detections(model1_signals, aligned_signals):
    return cli._Detections(
        swings=[], fvgs=[], crt_ranges=[], mss_events=[],
        model1_signals=model1_signals, aligned_signals=aligned_signals, htf_crt_ranges=[],
    )


def test_filter_to_confluent_keeps_aligned_signal_with_key_level():
    """REQ-56.1: an aligned signal with a Key Level recorded survives the
    gate — row and marker both present."""
    signal = _model1_signal()
    tagged = AlignedSignal(ltf_signal=signal, htf_context=_HTF_CONTEXT, aligned="aligned", key_level=_KEY_LEVEL)
    detections = _detections(model1_signals=[signal], aligned_signals=[tagged])

    result = cli._filter_to_confluent(detections)

    assert result.aligned_signals == [tagged]
    assert result.model1_signals == [signal]


def test_filter_to_confluent_keeps_fvg_fill_confirmed_signal_without_key_level():
    """REQ-56.7: an fvg_fill-confirmed signal is never withheld by the
    gate, even with no Key Level ever recorded (no CRT range at all)."""
    signal = _model1_signal(confirmation_type="fvg_fill")
    tagged = AlignedSignal(ltf_signal=signal, htf_context=None, aligned="aligned", key_level=None)
    detections = _detections(model1_signals=[signal], aligned_signals=[tagged])

    result = cli._filter_to_confluent(detections)

    assert result.aligned_signals == [tagged]
    assert result.model1_signals == [signal]


def test_filter_to_confluent_withholds_aligned_non_fvg_fill_signal_with_no_key_level():
    """REQ-56.2 (the gate itself, S-000's minimal proof it bites at all —
    full e2e coverage is S-004's): an aligned, non-fvg_fill signal with no
    Key Level recorded is withheld from both aligned_signals and
    model1_signals."""
    signal = _model1_signal()
    tagged = AlignedSignal(ltf_signal=signal, htf_context=_HTF_CONTEXT, aligned="aligned", key_level=None)
    detections = _detections(model1_signals=[signal], aligned_signals=[tagged])

    result = cli._filter_to_confluent(detections)

    assert result.aligned_signals == []
    assert result.model1_signals == []


def test_filter_to_confluent_withholds_unaligned_non_fvg_fill_signal_with_no_key_level():
    """odd/tasks/model1-causal-retry-chain.md T3 fix: the causal pipeline's
    H-A rule (keyed by a signal's own `retest_index` timestamp, not legacy
    `tag_alignment`'s `anchor_index`-window match) can correctly tag a
    non-fvg_fill signal `aligned="unaligned"` for the same underlying reason
    legacy would have tagged it `aligned="aligned", key_level=None` — no
    HTF context backs this signal with a credited Key Level, just arrived
    at differently. The gate's original `keep()` only excluded the
    `aligned` case (`t.aligned != "aligned"` passed everything else
    through), so an `unaligned`, non-fvg_fill, no-key-level signal used to
    leak through uncredited -- it must be withheld identically to REQ-56.2's
    `aligned` case above."""
    signal = _model1_signal()
    tagged = AlignedSignal(ltf_signal=signal, htf_context=None, aligned="unaligned", key_level=None)
    detections = _detections(model1_signals=[signal], aligned_signals=[tagged])

    result = cli._filter_to_confluent(detections)

    assert result.aligned_signals == []
    assert result.model1_signals == []


def test_filter_to_confluent_keeps_insufficient_htf_data_signal():
    """REQ-56.4 (unaligned/insufficient rows unchanged): `insufficient_htf_data`
    means "not yet knowable", a genuinely different state from "evaluated,
    no key level" -- it must stay exempt from the gate, unlike plain
    `unaligned`/`aligned` with no key level."""
    signal = _model1_signal()
    tagged = AlignedSignal(ltf_signal=signal, htf_context=None, aligned="insufficient_htf_data", key_level=None)
    detections = _detections(model1_signals=[signal], aligned_signals=[tagged])

    result = cli._filter_to_confluent(detections)

    assert result.aligned_signals == [tagged]
    assert result.model1_signals == [signal]


_NO_FVG_HTF_DAILY = [
    ("2026.07.02", 1.1000, 1.1005, 1.0995, 1.1000),  # 0 — flat filler, no gap possible
    ("2026.07.03", 1.1000, 1.1005, 1.0995, 1.1000),  # 1 — flat filler
    ("2026.07.04", 1.1000, 1.1005, 1.0995, 1.1000),  # 2 — flat filler
    ("2026.07.05", 1.1020, 1.1028, 1.0900, 1.0910),  # 3 — CRT range: H=1.1028 L=1.0900
    ("2026.07.06", 1.0915, 1.1035, 1.0905, 1.0920),  # 4 — purge (LTF anchor's own calendar day)
    ("2026.07.07", 1.0920, 1.0930, 1.0910, 1.0925),  # 5 — trailing
]
_NO_FVG_LTF_CANDLES = [
    (1.1000, 1.1020, 1.0980, 1.1010),  # 0 — range: H=1.1020 L=1.0980
    (1.1010, 1.1035, 1.1000, 1.1015),  # 1 — anchor, purges High (10:00 NY-local -> 07:00)
    (1.1000, 1.1005, 1.0950, 1.0960),  # 2 — confirms
    (1.0960, 1.1012, 1.0955, 1.0965),  # 3 — retest + fills
    (1.0965, 1.1010, 1.0790, 1.0910),  # 4 — expansion -> CONFIRMED
]


def test_types_model1_gate_narrows_model1_signals_rows_too(tmp_path):
    """CRITICAL (plan-verify iteration 3): `--types model1` sets
    aligned_signals=None in `_filter_by_types`, so `write_detections_csv`
    falls back to the unfiltered `model1_signals` list unless
    `_filter_to_confluent` ALSO narrows `model1_signals` — otherwise the
    gate applies to `--types alignment` but not `--types model1`, violating
    the spec's "the gate applies uniformly regardless of flags" note. A
    fixture with no HTF FVG at all (no Key Level source registered)
    produces one aligned, non-fvg_fill Model-1 signal -> it must be
    withheld under BOTH --types tokens identically.
    """
    ltf_path = tmp_path / "eurusd_1h.csv"
    htf_path = tmp_path / "eurusd_daily.csv"
    ltf_path.write_text(
        "\n".join(
            [MT5_HEADER]
            + [
                _row("2026.07.06", f"{10 + i:02d}:00:00", o, h, l, c)
                for i, (o, h, l, c) in enumerate(_NO_FVG_LTF_CANDLES)
            ]
        )
    )
    htf_path.write_text(
        "\n".join(
            [MT5_HEADER] + [_row(date_str, "00:00:00", o, h, l, c) for date_str, o, h, l, c in _NO_FVG_HTF_DAILY]
        )
    )

    for types_token in ("model1", "alignment"):
        output_dir = tmp_path / f"out_{types_token}"
        exit_code = main(
            [
                "--csv", str(ltf_path), "--symbol", "EURUSD",
                "--htf-csv", str(htf_path), "--htf-symbol", "EURUSD",
                "--output-dir", str(output_dir), "--types", types_token,
            ]
        )
        assert exit_code == 0
        csv_rows = (output_dir / "detections.csv").read_text().splitlines()
        model1_rows = [row for row in csv_rows[1:] if row.split(",")[1] == "model1"]
        assert model1_rows == [], f"--types {types_token} leaked a non-confluent model1 row: {model1_rows}"


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

    assert in_ny_kill_zone(winter, config) is False
    assert in_ny_kill_zone(summer, config) is True


def test_ny_kill_zone_upper_bound_is_exclusive():
    config = KillZoneConfig()
    just_before_close = datetime(2026, 7, 6, 14, 59, 0)  # EDT: 10:59 NY local
    at_close = datetime(2026, 7, 6, 15, 0, 0)  # EDT: 11:00 NY local

    assert in_ny_kill_zone(just_before_close, config) is True
    assert in_ny_kill_zone(at_close, config) is False


def test_htf_key_levels_concatenate_fvg_and_ict_order_block_sources(tmp_path):
    """REQ-63: `_detect_all` must compose BOTH HTF Key Level sources (FVG
    and ICTOrderBlock) into the single `htf_key_levels` list handed to the
    alignment layer — neither silently shadows the other (the naming-
    collision risk the design flags for `to_key_levels`). Both adapters are
    mocked so the test proves the composition wiring, independent of
    whether this specific fixture happens to form a real FVG or Order
    Block organically.

    odd/tasks/model1-causal-retry-chain.md T3: this fixture's LTF series
    (`_write_valid_csv`, 2 flat candles) never produces any Model-1 signal
    at all, let alone an `fvg_fill` one — `cli.py`'s migrated `_detect_all`
    only calls `tag_alignment` when there's an `fvg_fill` signal to tag, so
    it's never invoked here and the old spy on it saw no call. Every
    `purge_engulf`-path signal (none, in this fixture, but the composed
    `htf_key_levels` still flow through unconditionally) now goes through
    `causal.generate.generate_causal_aligned_signals` instead — that's the
    function actually receiving the composed Key Levels for this fixture,
    so the spy moves there.
    """
    ltf_path = tmp_path / "eurusd_1h.csv"
    htf_path = tmp_path / "eurusd_daily.csv"
    _write_valid_csv(ltf_path)
    _write_daily_csv(htf_path)
    output_dir = tmp_path / "out"

    fake_fvg_key_level = KeyLevel(kind="fvg", top=1.2000, bottom=1.1990, origin_index=0)
    fake_ict_key_level = KeyLevel(kind="ict_order_block", top=1.2100, bottom=1.2090, origin_index=1)
    real_generate_causal_aligned_signals = cli.generate_causal_aligned_signals

    with (
        mock.patch("cli.to_key_levels", return_value=[fake_fvg_key_level]) as fake_fvg_adapter,
        mock.patch("cli.ict_order_block_to_key_levels", return_value=[fake_ict_key_level]) as fake_ict_adapter,
        mock.patch(
            "cli.generate_causal_aligned_signals", side_effect=real_generate_causal_aligned_signals
        ) as generate_causal_aligned_signals_spy,
    ):
        exit_code = main(
            [
                "--csv", str(ltf_path), "--symbol", "EURUSD",
                "--htf-csv", str(htf_path), "--htf-symbol", "EURUSD",
                "--output-dir", str(output_dir),
            ]
        )

    assert exit_code == 0
    assert fake_fvg_adapter.call_count == 1
    assert fake_ict_adapter.call_count == 1
    htf_key_levels = generate_causal_aligned_signals_spy.call_args.kwargs["htf_key_levels"]
    assert fake_fvg_key_level in htf_key_levels
    assert fake_ict_key_level in htf_key_levels


def test_cli_order_block_detection_uses_the_redefined_composite_detector():
    """odd/tasks/detector-order-block-redefinition.md S8: the archived
    `primitives.ict_order_block` detector (2-candle engulfment, body-only
    zone, ~26% real-break confirmation per T5) is swapped for
    `composite.ict_order_block` (MSS -> displacement -> backward-scan
    chain, ~75-82% confirmation) as the production source for HTF/Daily
    ICTOrderBlock Key Levels — the deferred, higher-risk step S8 itself
    named as separate from the walking skeleton."""
    import composite.ict_order_block as redefined

    assert cli.detect_ict_order_blocks is redefined.detect_order_blocks
    assert cli.ict_order_block_to_key_levels is redefined.to_key_levels
