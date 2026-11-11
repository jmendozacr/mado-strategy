"""Full-pipeline e2e (REQ-23, REQ-24, REQ-28): CLI wired end to end —
detection -> overlay.png + detections.csv -> date/type filters apply to
RESULTS, never the input series.
"""

from unittest import mock

from fixtures.mt5_csv import MT5_HEADER, _read_csv_rows, _row

from cli import main


# Charter-2 [00:07:27]-[00:07:56] dual purge+FVG-fill shape (matches
# fixtures.synthetic.model1_dual_purge_and_fvg_fill_charter2_setup): one
# hour per candle, exercises FVG, CRT range, and Model-1 together in a
# single small series.
_DUAL_CANDLES = [
    (1.1000, 1.1010, 1.0990, 1.1005),
    (1.1010, 1.1030, 1.1005, 1.1020),
    (1.1025, 1.1045, 1.1020, 1.1040),
    (1.1040, 1.1055, 1.1012, 1.1045),
    (1.1030, 1.1035, 1.1005, 1.1020),
    (1.1020, 1.1042, 1.1015, 1.1040),
    (1.1040, 1.1042, 1.1025, 1.1038),
    (1.1038, 1.1060, 1.1035, 1.1055),
]


def _write_dual_csv(path):
    rows = [MT5_HEADER]
    for i, (o, h, l, c) in enumerate(_DUAL_CANDLES):
        rows.append(_row("2026.01.01", f"{i:02d}:00:00", o, h, l, c))
    path.write_text("\n".join(rows))


def _write_flat_csv(path, n=2):
    rows = [MT5_HEADER]
    for i in range(n):
        rows.append(_row("2026.01.01", f"{i:02d}:00:00", 1.1000, 1.1005, 1.0995, 1.1000))
    path.write_text("\n".join(rows))


def test_full_pipeline_produces_populated_overlay_and_detections_csv(tmp_path):
    csv_path = tmp_path / "eurusd.csv"
    _write_dual_csv(csv_path)
    output_dir = tmp_path / "out"

    exit_code = main(
        ["--csv", str(csv_path), "--symbol", "EURUSD", "--output-dir", str(output_dir)]
    )

    assert exit_code == 0
    assert (output_dir / "overlay.png").stat().st_size > 0

    rows = _read_csv_rows(output_dir / "detections.csv")
    header, data_rows = rows[0], rows[1:]
    assert header == ["timestamp", "type", "direction", "price_high", "price_low", "status", "aligned", "key_level_source", "key_level_reaction"]
    types_present = {row[1] for row in data_rows}
    assert "fvg" in types_present
    assert "crt_range" in types_present
    assert "model1" in types_present
    assert len(data_rows) > 0


def test_zero_detections_still_emits_valid_empty_outputs(tmp_path):
    csv_path = tmp_path / "flat.csv"
    _write_flat_csv(csv_path)
    output_dir = tmp_path / "out"

    exit_code = main(
        ["--csv", str(csv_path), "--symbol", "EURUSD", "--output-dir", str(output_dir)]
    )

    assert exit_code == 0
    assert (output_dir / "overlay.png").stat().st_size > 0
    rows = _read_csv_rows(output_dir / "detections.csv")
    assert rows == [["timestamp", "type", "direction", "price_high", "price_low", "status", "aligned", "key_level_source", "key_level_reaction"]]


def test_types_filter_narrows_detections_csv_to_selected_types(tmp_path):
    """REQ-28.1: --types fvg,model1 -> only those rows appear."""
    csv_path = tmp_path / "eurusd.csv"
    _write_dual_csv(csv_path)
    output_dir = tmp_path / "out"

    exit_code = main(
        [
            "--csv", str(csv_path), "--symbol", "EURUSD",
            "--output-dir", str(output_dir),
            "--types", "fvg,model1",
        ]
    )

    assert exit_code == 0
    rows = _read_csv_rows(output_dir / "detections.csv")
    types_present = {row[1] for row in rows[1:]}
    assert types_present <= {"fvg", "model1"}
    assert "crt_range" not in types_present


def test_unknown_types_token_is_rejected(tmp_path, capsys):
    csv_path = tmp_path / "eurusd.csv"
    _write_dual_csv(csv_path)
    output_dir = tmp_path / "out"

    exit_code = main(
        [
            "--csv", str(csv_path), "--symbol", "EURUSD",
            "--output-dir", str(output_dir),
            "--types", "bogus",
        ]
    )

    assert exit_code == 1
    assert "bogus" in capsys.readouterr().err


def test_date_filter_excludes_all_results_outside_range(tmp_path):
    """REQ-28: filters apply to RESULTS, never the input series."""
    csv_path = tmp_path / "eurusd.csv"
    _write_dual_csv(csv_path)
    output_dir = tmp_path / "out"

    exit_code = main(
        [
            "--csv", str(csv_path), "--symbol", "EURUSD",
            "--output-dir", str(output_dir),
            "--from-date", "2027-01-01", "--to-date", "2027-01-02",
        ]
    )

    assert exit_code == 0
    rows = _read_csv_rows(output_dir / "detections.csv")
    assert rows == [["timestamp", "type", "direction", "price_high", "price_low", "status", "aligned", "key_level_source", "key_level_reaction"]]


def _write_dual_csv_at(path, date_str, start_hour):
    """Same `_DUAL_CANDLES` shape as `_write_dual_csv`, but starting at an
    arbitrary UTC hour instead of 00:00 — lets session-filter tests place
    the whole detection cluster inside/outside/straddling the NY Kill Zone.
    """
    rows = [MT5_HEADER]
    for i, (o, h, l, c) in enumerate(_DUAL_CANDLES):
        rows.append(_row(date_str, f"{(start_hour + i) % 24:02d}:00:00", o, h, l, c))
    path.write_text("\n".join(rows))


def _write_daily_csv(path):
    rows = [MT5_HEADER]
    for i, (o, h, l, c) in enumerate(
        [
            (1.1000, 1.1010, 1.0990, 1.1005),
            (1.1005, 1.1020, 1.1000, 1.1015),
            (1.1015, 1.1030, 1.1010, 1.1025),
        ]
    ):
        rows.append(_row(f"2026.01.0{i + 1}", "00:00:00", o, h, l, c))
    path.write_text("\n".join(rows))


def test_date_filter_does_not_change_detection_values_only_narrows_them(tmp_path):
    """Bug 3 (c): --from-date/--to-date must window what gets PLOTTED and
    what appears in detections.csv, never re-run detection against a
    truncated series (no-lookahead correctness depends on detecting against
    the full series always). Every row surviving the filtered run must be
    byte-identical to its counterpart in the unfiltered run — never a value
    recomputed from a shorter series.
    """
    csv_path = tmp_path / "eurusd.csv"
    _write_dual_csv(csv_path)
    full_dir = tmp_path / "full"
    filtered_dir = tmp_path / "filtered"

    main(["--csv", str(csv_path), "--symbol", "EURUSD", "--output-dir", str(full_dir)])
    main(
        [
            "--csv", str(csv_path), "--symbol", "EURUSD", "--output-dir", str(filtered_dir),
            "--from-date", "2026-01-01", "--to-date", "2026-01-01",
        ]
    )

    full_rows = {tuple(row) for row in _read_csv_rows(full_dir / "detections.csv")[1:]}
    filtered_rows = {tuple(row) for row in _read_csv_rows(filtered_dir / "detections.csv")[1:]}

    assert filtered_rows
    assert filtered_rows.issubset(full_rows)
    # all _DUAL_CANDLES fall on 2026-01-01, so this filter keeps everything
    assert filtered_rows == full_rows


def test_date_filter_windows_the_plotted_candles(tmp_path):
    """Bug 3 (b) at CLI level: a date filter must be threaded through to
    render_chart as a computed display-only index range covering exactly
    the candles inside the window — the wiring proof for the windowing
    behavior verified precisely (via wick-line counts) at the render_chart
    level in test_viz.py.
    """
    csv_path = tmp_path / "eurusd.csv"
    _write_dual_csv(csv_path)
    output_dir = tmp_path / "out"

    with mock.patch("cli.render_chart") as render_chart_spy:
        render_chart_spy.return_value = None
        exit_code = main(
            [
                "--csv", str(csv_path), "--symbol", "EURUSD", "--output-dir", str(output_dir),
                "--from-date", "2026-01-01", "--to-date", "2026-01-01",
            ]
        )

    assert exit_code == 0
    _, kwargs = render_chart_spy.call_args
    # all 8 _DUAL_CANDLES fall on 2026-01-01 -> the whole series is the window
    assert kwargs["ltf_index_range"] == (0, len(_DUAL_CANDLES) - 1)


def test_no_date_filter_passes_none_as_the_index_range(tmp_path):
    """Bug 3 (a): with no --from-date/--to-date, render_chart receives
    ltf_index_range=None — unchanged behavior (plot everything)."""
    csv_path = tmp_path / "eurusd.csv"
    _write_dual_csv(csv_path)
    output_dir = tmp_path / "out"

    with mock.patch("cli.render_chart") as render_chart_spy:
        render_chart_spy.return_value = None
        main(["--csv", str(csv_path), "--symbol", "EURUSD", "--output-dir", str(output_dir)])

    _, kwargs = render_chart_spy.call_args
    assert kwargs["ltf_index_range"] is None
    assert kwargs["htf_index_range"] is None


def test_session_filter_excludes_results_outside_ny_kill_zone(tmp_path):
    """New REQ-29: --session ny-killzone narrows RESULTS to detections
    anchored inside 07:00-11:00 NY-local time. Winter date, candles at UTC
    16:00-23:00 -> NY local 11:00-18:00 (EST) -> entirely after the kill
    zone closes.
    """
    csv_path = tmp_path / "eurusd.csv"
    _write_dual_csv_at(csv_path, "2026.01.05", start_hour=16)
    output_dir = tmp_path / "out"

    exit_code = main(
        [
            "--csv", str(csv_path), "--symbol", "EURUSD",
            "--output-dir", str(output_dir),
            "--session", "ny-killzone",
        ]
    )

    assert exit_code == 0
    rows = _read_csv_rows(output_dir / "detections.csv")
    assert rows == [["timestamp", "type", "direction", "price_high", "price_low", "status", "aligned", "key_level_source", "key_level_reaction"]]


def test_unknown_session_token_is_rejected(tmp_path, capsys):
    csv_path = tmp_path / "eurusd.csv"
    _write_dual_csv(csv_path)
    output_dir = tmp_path / "out"

    exit_code = main(
        [
            "--csv", str(csv_path), "--symbol", "EURUSD",
            "--output-dir", str(output_dir),
            "--session", "bogus",
        ]
    )

    assert exit_code == 1
    assert "bogus" in capsys.readouterr().err


def test_session_filter_does_not_change_detection_values_only_narrows_them(tmp_path):
    """Mirrors the date-filter invariant (Bug 3 (c)): a session filter must
    window RESULTS only, never re-run detection against a truncated series.
    Summer date, candles at UTC 11:00-18:00 -> NY local 07:00-14:00 (EDT):
    the first 4 candles (11:00-14:00 UTC) fall inside the 11:00-15:00 UTC
    kill zone window, the last 4 fall outside -> a genuine, non-vacuous
    narrowing where every surviving row must still be byte-identical.
    """
    csv_path = tmp_path / "eurusd.csv"
    _write_dual_csv_at(csv_path, "2026.07.06", start_hour=11)
    full_dir = tmp_path / "full"
    filtered_dir = tmp_path / "filtered"

    main(["--csv", str(csv_path), "--symbol", "EURUSD", "--output-dir", str(full_dir)])
    main(
        [
            "--csv", str(csv_path), "--symbol", "EURUSD", "--output-dir", str(filtered_dir),
            "--session", "ny-killzone",
        ]
    )

    full_rows = {tuple(row) for row in _read_csv_rows(full_dir / "detections.csv")[1:]}
    filtered_rows = {tuple(row) for row in _read_csv_rows(filtered_dir / "detections.csv")[1:]}

    assert filtered_rows
    assert filtered_rows.issubset(full_rows)
    assert filtered_rows != full_rows


def test_pair_mode_populates_aligned_column_on_model1_rows(tmp_path):
    ltf_path = tmp_path / "eurusd_1h.csv"
    htf_path = tmp_path / "eurusd_daily.csv"
    _write_dual_csv(ltf_path)
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
    rows = _read_csv_rows(output_dir / "detections.csv")
    model1_rows = [row for row in rows[1:] if row[1] == "model1"]
    assert len(model1_rows) > 0
    for row in model1_rows:
        assert row[6] in {"aligned", "unaligned", "insufficient_htf_data"}


def test_pair_mode_confluence_gate_withholds_every_uncredited_purge_engulf_row(tmp_path):
    """odd/tasks/model1-causal-retry-chain.md T3 regression: cli.py's
    pair-mode `model1_signals`/`aligned_signals` now come from the causal
    pipeline for `purge_engulf` signals (unchanged for `fvg_fill`, which has
    no causal equivalent yet). This fixture's HTF (`_write_daily_csv`, 3
    flat candles) registers no Key Level at all, so every `purge_engulf`
    signal — aligned or not — is correctly withheld by the REQ-56
    confluence gate (T3's `_filter_to_confluent` fix: an `"unaligned"` tag
    with no key_level is withheld exactly like `"aligned"` with no
    key_level). Only the `fvg_fill`-confirmed signal (exempt from the gate
    regardless of key_level) survives into detections.csv.
    """
    ltf_path = tmp_path / "eurusd_1h.csv"
    htf_path = tmp_path / "eurusd_daily.csv"
    _write_dual_csv(ltf_path)
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
    rows = _read_csv_rows(output_dir / "detections.csv")
    model1_rows = [row for row in rows[1:] if row[1] == "model1"]

    # Only the fvg_fill-confirmed signal survives (anchor_index=4, bullish,
    # entry 1.1035, CONFIRMED) — every purge_engulf row is gated out.
    assert len(model1_rows) == 1
    assert model1_rows[0][0] == "2026-01-01T04:00:00"
    assert model1_rows[0][2] == "bullish"
    assert model1_rows[0][5] == "confirmed"


def test_causal_purge_engulf_status_reflects_only_data_known_by_its_own_retest():
    """Direct unit-level pin for the causal correctness fact T3's migration
    relies on (not observable through detections.csv once the REQ-56
    confluence gate withholds the uncredited signal — see the e2e test
    above): on `fixtures.synthetic`-shaped series (here, this file's own
    `_DUAL_CANDLES`), the bearish anchor_index=2 signal (entry 1.1025,
    retest_index=5) reports `status=INVALIDATED` under LEGACY
    `entries.model1.detect_model1_signals` — but that value is only
    reachable by reading candle 7 (AFTER its own retest at candle 5) to see
    a LATER close breach its protected extreme. As of its own retest
    event, this signal had NOT yet invalidated; `causal.signals.
    causal_purge_engulf_signals` freezes status at the causal event
    boundary and correctly reports `PENDING` instead — the exact class of
    lookahead legacy `tag_alignment`/`detect_model1_signals` has
    (REQ-CAUSAL-21).
    """
    from datetime import datetime, timedelta

    from core.candle import Candle, OHLCSeries
    from core.config import CRTRangeConfig, Model1Config
    from core.results import DetectionStatus
    from entries.model1 import detect_model1_signals
    from causal.ranges import causal_crt_ranges
    from causal.signals import causal_purge_engulf_signals

    candles = tuple(
        Candle(timestamp=datetime(2026, 1, 1) + timedelta(hours=i), open=o, high=h, low=l, close=c)
        for i, (o, h, l, c) in enumerate(_DUAL_CANDLES)
    )
    series = OHLCSeries(candles=candles, instrument="EURUSD", timeframe="1H")

    legacy = next(
        s for s in detect_model1_signals(series)
        if s.anchor_index == 2 and s.direction == "bearish" and s.confirmation_type == "purge_engulf"
    )
    assert legacy.status == DetectionStatus.INVALIDATED
    assert legacy.retest_index == 5

    ranges = causal_crt_ranges(series, CRTRangeConfig())
    causal = next(
        s for s in causal_purge_engulf_signals(series, ranges, Model1Config())
        if s.anchor_index == 2 and s.direction == "bearish"
    )
    assert causal.status == DetectionStatus.PENDING
    assert causal.retest_index == 5


def test_pair_mode_types_excluding_alignment_keeps_model1_rows_but_blanks_aligned(tmp_path):
    """`alignment` is its own --types token (design 4.6/REQ-23's 6th
    encoding) distinct from `model1` — excluding it drops the HTF-tagged
    border-color styling and the CSV's aligned column, but model1 rows
    themselves still appear.
    """
    ltf_path = tmp_path / "eurusd_1h.csv"
    htf_path = tmp_path / "eurusd_daily.csv"
    _write_dual_csv(ltf_path)
    _write_daily_csv(htf_path)
    output_dir = tmp_path / "out"

    exit_code = main(
        [
            "--csv", str(ltf_path), "--symbol", "EURUSD",
            "--htf-csv", str(htf_path), "--htf-symbol", "EURUSD",
            "--output-dir", str(output_dir),
            "--types", "model1",
        ]
    )

    assert exit_code == 0
    rows = _read_csv_rows(output_dir / "detections.csv")
    model1_rows = [row for row in rows[1:] if row[1] == "model1"]
    assert len(model1_rows) > 0
    for row in model1_rows:
        assert row[6] == ""

    # REQ-52.2 regression: the C2 relocation (deleting `_detect_all`'s
    # display-degradation branch and re-expressing it as a single
    # `_filter_by_types` expression) must not change any model1 row's
    # non-aligned columns — only the `aligned` column (blanked above)
    # differs from the full-types run.
    aligned_output_dir = tmp_path / "out_aligned"
    main(
        [
            "--csv", str(ltf_path), "--symbol", "EURUSD",
            "--htf-csv", str(htf_path), "--htf-symbol", "EURUSD",
            "--output-dir", str(aligned_output_dir),
            "--types", "model1,alignment",
        ]
    )
    aligned_rows = _read_csv_rows(aligned_output_dir / "detections.csv")
    aligned_model1_rows = [row for row in aligned_rows[1:] if row[1] == "model1"]
    assert [row[:6] for row in model1_rows] == [row[:6] for row in aligned_model1_rows]
