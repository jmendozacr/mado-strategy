"""S-000 walking skeleton: --backtest end to end (REQ-32.2, 45.1, 45.2).
One CONFIRMED signal fills within max_fill_wait and produces exactly one
trades.csv row; a cohort narrowed to zero by --types produces an empty,
fully-disclosed backtest run; detections.csv/overlay.png are unaffected.
"""

from fixtures.mt5_csv import MT5_HEADER, _read_csv_rows, _row

from cli import main


# Charter-2 example 1 (matches fixtures.synthetic.model1_purge_engulf_charter2_setup):
# candle1 purges the CRT High (bearish anchor), candle2 confirms (wick
# entry), candle3 retests AND fills within the same candle (bearish fill:
# high>=entry_price), candle4 expands. Timed at UTC 10:00-14:00 on
# 2026-07-06 (EDT) so the anchor (candle1, UTC 11:00) lands at NY 07:00 —
# inside the default kill zone.
_LTF_CANDLES = [
    (1.1000, 1.1020, 1.0980, 1.1010),  # 0 — range: H=1.1020 L=1.0980
    (1.1010, 1.1035, 1.1000, 1.1015),  # 1 — anchor, purges High (10:00 NY-local -> 07:00)
    (1.1000, 1.1005, 1.0950, 1.0960),  # 2 — confirms (wick entry @1.1035)
    (1.0960, 1.1012, 1.0955, 1.0965),  # 3 — retest (overlaps anchor body) + fills (high>=1.1010)
    (1.0965, 1.1010, 1.0790, 1.0910),  # 4 — expansion -> CONFIRMED; low also reaches take_profit (1.0800)
]

# Daily HTF pair: day0 forms a wide range (H=1.1010, L=1.0800), day1
# (2026-07-06, the LTF anchor's own calendar day) purges it -> the LTF
# anchor's enclosing HTF index (day1) resolves to day0's range as
# htf_context, giving a bearish take_profit of 1.0800 (well below entry,
# clearing the R:R floor). day2 exists so day1 is never the "last HTF
# candle" (avoids the insufficient_htf_data special case).
_HTF_DAILY = [
    ("2026.07.05", 1.1000, 1.1010, 1.0800, 1.1005),
    ("2026.07.06", 1.1005, 1.1025, 1.1000, 1.1020),
    ("2026.07.07", 1.1020, 1.1030, 1.1010, 1.1025),
]


def _write_ltf_csv(path):
    rows = [MT5_HEADER]
    for i, (o, h, l, c) in enumerate(_LTF_CANDLES):
        rows.append(_row("2026.07.06", f"{10 + i:02d}:00:00", o, h, l, c))
    path.write_text("\n".join(rows))


def _write_htf_csv(path):
    rows = [MT5_HEADER]
    for date_str, o, h, l, c in _HTF_DAILY:
        rows.append(_row(date_str, "00:00:00", o, h, l, c))
    path.write_text("\n".join(rows))


def _run_backtest(tmp_path, extra_args=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    ltf_path = tmp_path / "eurusd_1h.csv"
    htf_path = tmp_path / "eurusd_daily.csv"
    _write_ltf_csv(ltf_path)
    _write_htf_csv(htf_path)
    output_dir = tmp_path / "out"

    args = [
        "--csv", str(ltf_path), "--symbol", "EURUSD",
        "--htf-csv", str(htf_path), "--htf-symbol", "EURUSD",
        "--output-dir", str(output_dir),
        "--backtest",
    ]
    exit_code = main(args + (extra_args or []))
    return exit_code, output_dir


def test_confirmed_signal_within_max_fill_wait_produces_one_trade_row(tmp_path):
    exit_code, output_dir = _run_backtest(tmp_path, extra_args=["--types", "model1"])

    assert exit_code == 0
    rows = _read_csv_rows(output_dir / "trades.csv")
    assert rows[0] == [
        "signal_id", "anchor_timestamp", "entry_timestamp", "direction", "entry_price",
        "stop_loss", "take_profit", "exit_timestamp", "exit_price", "outcome",
        "r_multiple", "ambiguous_bar", "gap_filled",
    ]
    assert len(rows) - 1 == 1
    trade = rows[1]
    assert trade[3] == "bearish"
    assert float(trade[10]) > 0  # net r_multiple, positive on this fixture's win


def test_trades_csv_signal_id_joins_exactly_one_detections_csv_row(tmp_path):
    """REQ-42.1/41.3: on a --backtest run, detections.csv gains the
    trailing signal_id column (8 cols) and every trades.csv row's
    signal_id joins exactly one detections.csv row."""
    exit_code, output_dir = _run_backtest(tmp_path, extra_args=["--types", "model1"])

    assert exit_code == 0
    detections_rows = _read_csv_rows(output_dir / "detections.csv")
    assert detections_rows[0][-1] == "signal_id"
    assert len(detections_rows[0]) == 8

    trades_rows = _read_csv_rows(output_dir / "trades.csv")
    detection_signal_ids = [row[-1] for row in detections_rows[1:] if row[-1] != ""]
    for trade_row in trades_rows[1:]:
        trade_signal_id = trade_row[0]
        assert detection_signal_ids.count(trade_signal_id) == 1


def test_metrics_summary_discloses_wick_entry_price_divergence_note(tmp_path):
    """REQ-42.2: metrics_summary.txt discloses that trades.csv and
    detections.csv entry prices are independently computed and may differ
    for wick-type signals, so a reader does not mistake the divergence for
    a bug."""
    exit_code, output_dir = _run_backtest(tmp_path, extra_args=["--types", "model1"])

    assert exit_code == 0
    summary = (output_dir / "metrics_summary.txt").read_text()
    assert (
        "trades.csv entry_price and detections.csv entry_price are independently computed "
        "and may differ for wick-type signals" in summary
    )


def test_types_excluding_model1_produces_empty_zero_disclosure_run(tmp_path):
    """--types fvg --backtest: signals_considered=0, all-n/a, exit 0 — REQ-
    30's population is bound before display filtering (C2/C2b/C3), so
    excluding model1 from display also empties the backtest population.
    The run stays FULLY DISCLOSED (this module's own docstring): a note
    names --types as the cause, so a zero-signal report isn't mistaken for
    "the strategy never sets up"."""
    exit_code, output_dir = _run_backtest(tmp_path, extra_args=["--types", "fvg"])

    assert exit_code == 0
    trade_rows = _read_csv_rows(output_dir / "trades.csv")
    assert len(trade_rows) == 1  # header only

    summary = (output_dir / "metrics_summary.txt").read_text()
    assert "signals considered: 0" in summary
    assert "trades opened: 0" in summary
    assert "win rate: n/a" in summary
    assert "average R: n/a" in summary
    assert (
        "note: --types excluded model1/alignment signals from this run's population "
        "- the zero counts above reflect that filter, not an empty result set"
    ) in summary
    assert "total R: n/a" in summary
    assert "open trades: 0" in summary
    assert "no crt range: 0" in summary
    assert "unaligned: 0" in summary
    assert "never confirmed: 0" in summary
    assert "duplicate: 0" in summary
    assert "kill zone: 0" in summary
    assert "rr floor: 0" in summary
    assert "never filled: 0" in summary


def test_types_including_model1_discloses_no_types_exclusion_note(tmp_path):
    """Companion to the above: when --types includes model1 (the normal
    case, every other e2e test here), the --types-exclusion note is absent
    — it only fires when --types itself is what emptied the population."""
    exit_code, output_dir = _run_backtest(tmp_path, extra_args=["--types", "model1"])

    assert exit_code == 0
    summary = (output_dir / "metrics_summary.txt").read_text()
    assert "note: --types excluded model1/alignment" not in summary


def test_backtest_without_htf_flags_exits_1_naming_both(tmp_path):
    """REQ-32.2."""
    ltf_path = tmp_path / "eurusd.csv"
    ltf_path.write_text("\n".join([
        MT5_HEADER,
        _row("2026.01.01", "00:00:00", 1.1000, 1.1005, 1.0995, 1.1000),
        _row("2026.01.01", "01:00:00", 1.1000, 1.1020, 1.0995, 1.1005),
    ]))
    output_dir = tmp_path / "out"

    exit_code = main(
        ["--csv", str(ltf_path), "--symbol", "EURUSD", "--output-dir", str(output_dir), "--backtest"]
    )

    assert exit_code == 1
    assert not (output_dir / "trades.csv").exists()


def test_backtest_does_not_change_overlay_but_detections_gains_signal_id_column(tmp_path):
    """REQ-45.1 (overlay.png byte-identical) / REQ-41.3 + REQ-45.3 (V9: the
    signal_id column is CONDITIONAL on --backtest, so detections.csv is
    NOT expected to stay byte-identical between the two runs -- it legitimately
    gains a trailing 8th column on the --backtest run, while the
    non-backtest run stays at exactly 7 columns, byte-for-byte unchanged)."""
    ltf_path = tmp_path / "eurusd_1h.csv"
    htf_path = tmp_path / "eurusd_daily.csv"
    _write_ltf_csv(ltf_path)
    _write_htf_csv(htf_path)
    plain_dir = tmp_path / "plain"
    backtest_dir = tmp_path / "backtest"

    main(
        ["--csv", str(ltf_path), "--symbol", "EURUSD",
         "--htf-csv", str(htf_path), "--htf-symbol", "EURUSD",
         "--output-dir", str(plain_dir)]
    )
    main(
        ["--csv", str(ltf_path), "--symbol", "EURUSD",
         "--htf-csv", str(htf_path), "--htf-symbol", "EURUSD",
         "--output-dir", str(backtest_dir), "--backtest"]
    )

    assert (plain_dir / "overlay.png").read_bytes() == (backtest_dir / "overlay.png").read_bytes()
    plain_header = _read_csv_rows(plain_dir / "detections.csv")[0]
    backtest_header = _read_csv_rows(backtest_dir / "detections.csv")[0]
    assert plain_header == [
        "timestamp", "type", "direction", "price_high", "price_low", "status", "aligned",
    ]
    assert backtest_header == plain_header + ["signal_id"]
    assert not (plain_dir / "trades.csv").exists()
    assert (backtest_dir / "trades.csv").exists()


# --- S-006: configurable behavior + full disclosure (REQ-33.2, 36.2, 36.4,
# 36.5, 40.2, 48.3, 49.3, 49.4, 51.1-51.3) --------------------------------


def test_default_run_discloses_kill_zone_gate_enabled_and_frictionless_cost(tmp_path):
    """REQ-36.4 (default rendering) / REQ-48.3 (default rendering) / REQ-49.3
    (closed-trade disclosure wording): no override flags -> the gate reads
    "enabled" and cost reads "frictionless"; the fixture's one trade closes
    as a win, so the average/total R lines report "over 1 closed trades"
    plus the unlimited-capital note."""
    exit_code, output_dir = _run_backtest(tmp_path, extra_args=["--types", "model1"])

    assert exit_code == 0
    summary = (output_dir / "metrics_summary.txt").read_text()
    assert "kill-zone gate: enabled (evaluating anchor_index against the NY kill zone)" in summary
    assert "trading cost: 0.0 (frictionless)" in summary
    assert "average R: 7.778 over 1 closed trades" in summary
    assert "total R: 7.778 over 1 closed trades" in summary
    assert "note: average R and total R assume unlimited capital, no cap on concurrently open positions" in summary
    assert "same-candle SL+TP resolutions: 0" in summary


def test_session_filter_auto_disables_kill_zone_gate(tmp_path):
    """REQ-36.2/36.4: --session ny-killzone forces the internal gate off for
    the run (excluded_kill_zone=0 by construction) and states so explicitly,
    distinct from the reconciliation bucket count."""
    exit_code, output_dir = _run_backtest(tmp_path, extra_args=["--types", "model1", "--session", "ny-killzone"])

    assert exit_code == 0
    summary = (output_dir / "metrics_summary.txt").read_text()
    assert "kill-zone gate: auto-disabled (--session already applied)" in summary
    assert "  kill zone: 0" in summary


def test_kill_zone_gated_false_without_session_discloses_third_rendering(tmp_path):
    """REQ-36.5: --kill-zone-gated false WITHOUT --session renders the THIRD
    literal state, distinct from both "enabled" and "auto-disabled"."""
    exit_code, output_dir = _run_backtest(tmp_path, extra_args=["--types", "model1", "--kill-zone-gated", "false"])

    assert exit_code == 0
    summary = (output_dir / "metrics_summary.txt").read_text()
    assert "kill-zone gate: disabled (--kill-zone-gated false)" in summary


def test_trading_cost_override_discloses_per_trade_line(tmp_path):
    """REQ-48.3 (nonzero rendering): --trading-cost overrides the default and
    the summary states the configured cost, not the frictionless line."""
    exit_code, output_dir = _run_backtest(tmp_path, extra_args=["--types", "model1", "--trading-cost", "0.0005"])

    assert exit_code == 0
    summary = (output_dir / "metrics_summary.txt").read_text()
    assert "trading cost: 0.0005 per trade" in summary
    assert "trading cost: 0.0 (frictionless)" not in summary


def test_min_rr_override_changes_rr_floor_exclusion(tmp_path):
    """REQ-51.1: the fixture's one candidate has R:R ~7.78, which clears the
    2.0 default (1 trade opens) but not an --min-rr 8.0 override (excluded
    under rr_floor instead) -- trade counts measurably differ between the
    default run and the override run on the same input."""
    default_exit, default_dir = _run_backtest(tmp_path / "default", extra_args=["--types", "model1"])
    override_exit, override_dir = _run_backtest(tmp_path / "override", extra_args=["--types", "model1", "--min-rr", "8.0"])

    assert default_exit == 0 and override_exit == 0
    default_summary = (default_dir / "metrics_summary.txt").read_text()
    override_summary = (override_dir / "metrics_summary.txt").read_text()
    assert "trades opened: 1" in default_summary
    assert "  rr floor: 0" in default_summary
    assert "trades opened: 0" in override_summary
    assert "  rr floor: 1" in override_summary


def test_no_override_flags_matches_explicit_defaults_byte_for_byte(tmp_path):
    """REQ-51.2: omitting all 5 override flags produces output byte-identical
    to setting every field explicitly to its BacktestConfig default."""
    implicit_exit, implicit_dir = _run_backtest(tmp_path / "implicit", extra_args=["--types", "model1"])
    explicit_exit, explicit_dir = _run_backtest(
        tmp_path / "explicit",
        extra_args=[
            "--types", "model1",
            "--sl-buffer", "0.0002", "--min-rr", "2.0", "--trading-cost", "0.0",
            "--kill-zone-gated", "--max-fill-wait", "20",
        ],
    )

    assert implicit_exit == 0 and explicit_exit == 0
    assert (implicit_dir / "trades.csv").read_bytes() == (explicit_dir / "trades.csv").read_bytes()
    assert (implicit_dir / "metrics_summary.txt").read_bytes() == (explicit_dir / "metrics_summary.txt").read_bytes()


def test_invalid_max_fill_wait_exits_1_naming_flag_and_constraint(tmp_path):
    """REQ-51.3: a non-positive --max-fill-wait is rejected, exit 1, naming
    the flag, value and constraint -- not argparse's own exit 2."""
    exit_code, output_dir = _run_backtest(tmp_path, extra_args=["--max-fill-wait", "0"])

    assert exit_code == 1
    assert not (output_dir / "trades.csv").exists()


def test_invalid_sl_buffer_exits_1_naming_flag_and_constraint(tmp_path):
    """REQ-51.3: a negative --sl-buffer is rejected the same way."""
    exit_code, output_dir = _run_backtest(tmp_path, extra_args=["--sl-buffer", "-0.0002"])

    assert exit_code == 1
    assert not (output_dir / "trades.csv").exists()


def test_invalid_min_rr_exits_1_naming_flag_and_constraint(tmp_path):
    """REQ-51.3: a negative --min-rr is rejected the same way."""
    exit_code, output_dir = _run_backtest(tmp_path, extra_args=["--min-rr", "-1.0"])

    assert exit_code == 1
    assert not (output_dir / "trades.csv").exists()


def test_invalid_trading_cost_exits_1_naming_flag_and_constraint(tmp_path):
    """REQ-51.3: a negative --trading-cost is rejected the same way."""
    exit_code, output_dir = _run_backtest(tmp_path, extra_args=["--trading-cost", "-0.0001"])

    assert exit_code == 1
    assert not (output_dir / "trades.csv").exists()


_AMBIGUOUS_LTF_CANDLES = [
    (1.1000, 1.1020, 1.0980, 1.1010),  # 0 — range: H=1.1020 L=1.0980
    (1.1010, 1.1035, 1.1000, 1.1015),  # 1 — anchor, purges High (NY 07:00)
    (1.1000, 1.1005, 1.0950, 1.0960),  # 2 — confirms (wick entry @1.1035)
    (1.0960, 1.1012, 1.0955, 1.0965),  # 3 — retest (overlaps anchor body) + fills
    (1.0965, 1.1040, 1.0790, 1.0910),  # 4 — high now also reaches SL(1.1037) same candle as TP(1.0800) -> tie-break
]


def _run_backtest_with_candles(tmp_path, ltf_candles, extra_args=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    ltf_path = tmp_path / "eurusd_1h.csv"
    htf_path = tmp_path / "eurusd_daily.csv"
    rows = [MT5_HEADER]
    for i, (o, h, l, c) in enumerate(ltf_candles):
        rows.append(_row("2026.07.06", f"{10 + i:02d}:00:00", o, h, l, c))
    ltf_path.write_text("\n".join(rows))
    _write_htf_csv(htf_path)
    output_dir = tmp_path / "out"

    args = [
        "--csv", str(ltf_path), "--symbol", "EURUSD",
        "--htf-csv", str(htf_path), "--htf-symbol", "EURUSD",
        "--output-dir", str(output_dir),
        "--backtest",
    ]
    exit_code = main(args + (extra_args or []))
    return exit_code, output_dir


def test_same_candle_sl_and_tp_discloses_ambiguous_bar_count(tmp_path):
    """REQ-33.2: a trade resolving via the same-candle SL+TP tie-break is
    counted and disclosed as a distinct "same-candle SL+TP resolutions"
    line, separate from ordinary win/loss counts."""
    exit_code, output_dir = _run_backtest_with_candles(tmp_path, _AMBIGUOUS_LTF_CANDLES, extra_args=["--types", "model1"])

    assert exit_code == 0
    summary = (output_dir / "metrics_summary.txt").read_text()
    assert "same-candle SL+TP resolutions: 1" in summary
    trades = _read_csv_rows(output_dir / "trades.csv")
    assert trades[1][11] == "True"  # ambiguous_bar column


_OPEN_TRADE_LTF_CANDLES = [
    (1.1000, 1.1020, 1.0980, 1.1010),  # 0 — range: H=1.1020 L=1.0980
    (1.1010, 1.1035, 1.1000, 1.1015),  # 1 — anchor, purges High (NY 07:00)
    (1.1000, 1.1005, 1.0950, 1.0960),  # 2 — confirms (wick entry @1.1035)
    (1.0960, 1.1012, 1.0955, 1.0965),  # 3 — retest (overlaps anchor body) + fills; series ends here -> nothing left to sweep
]


def test_open_trade_at_series_end_discloses_open_trades_count(tmp_path):
    """REQ-49.4: a trade still open at series end is disclosed on its own
    "open trades" line, distinct from and in addition to the closed-trade
    average/total (which read "n/a" -- REQ-39.1/49.2 -- since nothing has
    closed)."""
    exit_code, output_dir = _run_backtest_with_candles(tmp_path, _OPEN_TRADE_LTF_CANDLES, extra_args=["--types", "model1"])

    assert exit_code == 0
    summary = (output_dir / "metrics_summary.txt").read_text()
    assert "trades opened: 1" in summary
    assert "open trades: 1" in summary
    assert "win rate: n/a" in summary
    assert "average R: n/a" in summary
    assert "total R: n/a" in summary


_SECOND_ZONE_LTF_CANDLES = _LTF_CANDLES + [
    (1.2000, 1.2020, 1.1980, 1.2010),  # 5 — a second, independent range: H=1.2020 L=1.1980
    (1.2010, 1.2035, 1.2000, 1.2015),  # 6 — anchor, purges High, at NY 12:00 -- OUTSIDE the default kill zone
    (1.2000, 1.2005, 1.1950, 1.1960),  # 7 — confirms
]


def test_signals_considered_measured_after_session_filter_narrows_population(tmp_path):
    """REQ-40.2: signals_considered is measured strictly AFTER the CLI's
    --session filter has already narrowed the population -- the session
    run's count equals its own detections.csv model1 row count, is > 0, and
    is strictly less than the unfiltered run's count."""
    unfiltered_exit, unfiltered_dir = _run_backtest_with_candles(
        tmp_path / "unfiltered", _SECOND_ZONE_LTF_CANDLES, extra_args=["--types", "model1"]
    )
    session_exit, session_dir = _run_backtest_with_candles(
        tmp_path / "session", _SECOND_ZONE_LTF_CANDLES, extra_args=["--types", "model1", "--session", "ny-killzone"]
    )

    assert unfiltered_exit == 0 and session_exit == 0

    def _signals_considered(output_dir):
        summary = (output_dir / "metrics_summary.txt").read_text()
        line = next(l for l in summary.splitlines() if l.startswith("signals considered:"))
        return int(line.split(":")[1].strip())

    unfiltered_considered = _signals_considered(unfiltered_dir)
    session_considered = _signals_considered(session_dir)
    session_model1_rows = len(_read_csv_rows(session_dir / "detections.csv")) - 1  # minus header

    assert session_considered == session_model1_rows
    assert session_considered > 0
    assert session_considered < unfiltered_considered
