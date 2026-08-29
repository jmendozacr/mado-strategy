"""CLI entry point — single-series mode plus HTF/LTF pair mode
(--htf-csv/--htf-symbol) and, when --backtest is passed, the backtest
simulation path (trades.csv + metrics_summary.txt), including the 5
BacktestConfig CLI overrides and the 3-state kill-zone gate resolution
(REQ-36, REQ-51).
"""

import argparse
import math
import sys
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path

from alignment.htf_ltf import AlignedSignal, tag_alignment
from composite.mss import MSSEvent, detect_mss_events
from core.candle import OHLCSeries
from core.config import BacktestConfig, DetectorConfig, KillZoneConfig
from core.kill_zone import in_ny_kill_zone
from core.pairing_table import PairingError
from core.results import DetectionStatus
from entries.model1 import Model1Signal, detect_model1_signals
from ingestion.loader import LoadError, load_mt5_csv
from ingestion.pairing import load_pair
from primitives.crt_range import CRTRange, detect_crt_ranges
from primitives.fvg import FVG, detect_fvgs
from primitives.swing import SwingPoint, detect_swings
from viz.chart import render_chart
from viz.table import write_detections_csv

from backtest.metrics import KillZoneGateState, compute_metrics
from backtest.simulate import simulate
from viz.trades_table import write_metrics_summary, write_trades_csv

_ALL_TYPES = {"swing", "fvg", "crt_range", "mss", "model1", "alignment"}
_SESSIONS = {"ny-killzone"}


@dataclass
class _Detections:
    swings: list[SwingPoint]
    fvgs: list[FVG]
    crt_ranges: list[CRTRange]
    mss_events: list[MSSEvent]
    model1_signals: list[Model1Signal] | None
    aligned_signals: list[AlignedSignal] | None
    htf_crt_ranges: list[CRTRange]


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m detector.cli")
    parser.add_argument("--csv", required=True, help="Path to the MT5-exported OHLC CSV (LTF in pair mode)")
    parser.add_argument("--symbol", required=True, help="Instrument identity, e.g. EURUSD (LTF in pair mode)")
    parser.add_argument("--htf-csv", help="Path to the HTF CSV — enables pair mode with --htf-symbol")
    parser.add_argument("--htf-symbol", help="HTF instrument identity — enables pair mode with --htf-csv")
    parser.add_argument("--output-dir", required=True, help="Directory for overlay.png/detections.csv")
    parser.add_argument("--from-date", help="YYYY-MM-DD — filters RESULTS, never the input series")
    parser.add_argument("--to-date", help="YYYY-MM-DD — filters RESULTS, never the input series")
    parser.add_argument("--types", help="Comma-separated subset of swing,fvg,crt_range,mss,model1,alignment")
    parser.add_argument("--session", help="Restrict RESULTS to a named kill zone — currently: ny-killzone")
    parser.add_argument(
        "--backtest", action="store_true",
        help="Simulate the tradeable population -> trades.csv + metrics_summary.txt. Requires --htf-csv/--htf-symbol.",
    )
    # Deliberately no type=float/int/BooleanOptionalAction here: argparse's
    # own type= conversion raises and exits 2 before our code ever runs,
    # bypassing the flag/value/constraint-naming ValueError path. All 5
    # values arrive as raw strings (or None) and are converted, range- and
    # finiteness-checked in `_parse_backtest_config` instead.
    parser.add_argument("--sl-buffer", default=None, help="Override BacktestConfig.sl_buffer_price (raw price units)")
    parser.add_argument("--min-rr", default=None, help="Override BacktestConfig.min_risk_reward")
    parser.add_argument("--trading-cost", default=None, help="Override BacktestConfig.trading_cost_price (raw price units, per trade)")
    parser.add_argument(
        "--kill-zone-gated", nargs="?", const="true", default=None,
        help="Override BacktestConfig.kill_zone_gated -- true/false (e.g. --kill-zone-gated false); "
        "omitting the value means true",
    )
    parser.add_argument("--max-fill-wait", default=None, help="Override BacktestConfig.max_fill_wait (candles)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    if bool(args.htf_csv) != bool(args.htf_symbol):
        print("error: --htf-csv and --htf-symbol must be provided together", file=sys.stderr)
        return 1

    if args.backtest and not (args.htf_csv and args.htf_symbol):
        print("error: --backtest requires both --htf-csv and --htf-symbol", file=sys.stderr)
        return 1

    try:
        types = _parse_types(args.types)
        from_date, to_date = _parse_date(args.from_date, "--from-date"), _parse_date(args.to_date, "--to-date")
        session = _parse_session(args.session)
        backtest_config = _parse_backtest_config(args)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    try:
        if args.htf_csv:
            htf_series, ltf_series = load_pair(
                htf_csv=args.htf_csv, htf_symbol=args.htf_symbol,
                ltf_csv=args.csv, ltf_symbol=args.symbol,
            )
        else:
            htf_series, ltf_series = None, load_mt5_csv(args.csv, symbol=args.symbol)
    except (LoadError, PairingError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    config = DetectorConfig(backtest=backtest_config)
    detections = _detect_all(ltf_series, htf_series, config)
    ltf_swings = detections.swings  # captured before the filter chain below may narrow/clear detections.swings
    detections = _filter_by_date_range(detections, ltf_series, htf_series, from_date, to_date)
    detections = _filter_by_session(detections, ltf_series, htf_series, session, config.kill_zone)
    types_excludes_backtest_population = not ("model1" in types or "alignment" in types)
    population = [] if types_excludes_backtest_population else (detections.aligned_signals or [])
    detections = _filter_by_types(detections, types)

    output_dir = Path(args.output_dir)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        chartable = _exclude_invalidated_model1(detections)
        render_chart(
            ltf_series, detections.swings, str(output_dir / "overlay.png"),
            fvgs=detections.fvgs, crt_ranges=detections.crt_ranges, mss_events=detections.mss_events,
            model1_signals=chartable.model1_signals, aligned_signals=chartable.aligned_signals,
            htf_series=htf_series, htf_crt_ranges=detections.htf_crt_ranges,
            ltf_index_range=_index_range_for_dates(ltf_series, from_date, to_date),
            htf_index_range=None if htf_series is None else _index_range_for_dates(htf_series, from_date, to_date),
        )
        write_detections_csv(
            ltf_series, str(output_dir / "detections.csv"),
            swings=detections.swings, fvgs=detections.fvgs, crt_ranges=detections.crt_ranges,
            mss_events=detections.mss_events, model1_signals=detections.model1_signals,
            aligned_signals=detections.aligned_signals,
            include_signal_id=args.backtest,
        )
        if args.backtest:
            backtest_run_config, kill_zone_gate_state = _resolve_kill_zone_gate(config, session)
            trades, reconciliation = simulate(population, ltf_series, backtest_run_config, swings=ltf_swings)
            metrics = compute_metrics(
                trades, reconciliation, backtest_run_config.backtest, kill_zone_gate_state=kill_zone_gate_state
            )
            write_trades_csv(ltf_series, trades, str(output_dir / "trades.csv"))
            write_metrics_summary(
                metrics, str(output_dir / "metrics_summary.txt"),
                types_excluded_population=types_excludes_backtest_population,
            )
    except OSError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    return 0


def _detect_all(
    ltf_series: OHLCSeries, htf_series: OHLCSeries | None, config: DetectorConfig
) -> _Detections:
    """LTF crt_ranges/fvgs and (in pair mode) HTF crt_ranges are each
    computed exactly ONCE here and reused by `detect_model1_signals`/
    `tag_alignment` (perf fix — cli.py was previously triggering a second,
    redundant detection pass for each: detect_crt_ranges twice for LTF,
    twice for HTF, detect_fvgs twice for LTF, per run).
    """
    ltf_crt_ranges = detect_crt_ranges(ltf_series, config.crt_range)
    ltf_fvgs = detect_fvgs(ltf_series, config.fvg)
    ltf_swings = detect_swings(ltf_series, config.swing)
    model1_signals = detect_model1_signals(
        ltf_series, config.crt_range, config.fvg, config.model1,
        crt_ranges=ltf_crt_ranges, fvgs=ltf_fvgs,
    )

    aligned_signals = None
    htf_crt_ranges: list[CRTRange] = []

    if htf_series is not None:
        htf_crt_ranges = detect_crt_ranges(htf_series, config.crt_range)
        aligned_signals = tag_alignment(
            htf_series, ltf_series, config.crt_range, config.fvg, config.model1,
            ltf_signals=model1_signals, htf_ranges=htf_crt_ranges,
        )

    return _Detections(
        swings=ltf_swings,
        fvgs=ltf_fvgs,
        crt_ranges=ltf_crt_ranges,
        mss_events=detect_mss_events(ltf_series, config.mss, swings=ltf_swings),
        model1_signals=model1_signals,
        aligned_signals=aligned_signals,
        htf_crt_ranges=htf_crt_ranges,
    )


def _index_range_for_dates(
    series: OHLCSeries, from_date: date | None, to_date: date | None
) -> tuple[int, int] | None:
    """Bug 3: DISPLAY-ONLY windowing of the plotted candles when
    --from-date/--to-date are set — detection itself always runs on the
    full, unfiltered series (see `_filter_by_date_range`). None means "plot
    everything", matching today's behavior when no filter is given.
    """
    if from_date is None and to_date is None:
        return None

    indices = [
        i for i, candle in enumerate(series.candles)
        if (from_date is None or candle.timestamp.date() >= from_date)
        and (to_date is None or candle.timestamp.date() <= to_date)
    ]
    if not indices:
        return (0, -1)
    return (indices[0], indices[-1])


def _filter_by_date_range(
    detections: _Detections,
    ltf_series: OHLCSeries,
    htf_series: OHLCSeries | None,
    from_date: date | None,
    to_date: date | None,
) -> _Detections:
    """REQ-28: filters apply to RESULTS after detection, never the input series."""
    if from_date is None and to_date is None:
        return detections

    def keep(timestamp: datetime) -> bool:
        return (from_date is None or timestamp.date() >= from_date) and (to_date is None or timestamp.date() <= to_date)

    def date_filter(items, series, index_of):
        return None if items is None else [x for x in items if keep(series.candles[index_of(x)].timestamp)]

    return replace(
        detections,
        swings=date_filter(detections.swings, ltf_series, lambda s: s.index),
        fvgs=date_filter(detections.fvgs, ltf_series, lambda f: f.start_index),
        crt_ranges=date_filter(detections.crt_ranges, ltf_series, lambda r: r.start_index),
        mss_events=date_filter(detections.mss_events, ltf_series, lambda m: m.index),
        model1_signals=date_filter(detections.model1_signals, ltf_series, lambda s: s.anchor_index),
        aligned_signals=date_filter(detections.aligned_signals, ltf_series, lambda t: t.ltf_signal.anchor_index),
        htf_crt_ranges=detections.htf_crt_ranges if htf_series is None
        else date_filter(detections.htf_crt_ranges, htf_series, lambda r: r.start_index),
    )


def _filter_by_session(
    detections: _Detections,
    ltf_series: OHLCSeries,
    htf_series: OHLCSeries | None,
    session: str | None,
    config: KillZoneConfig,
) -> _Detections:
    """New REQ-29: filters apply to RESULTS after detection, never the
    input series — same shape as `_filter_by_date_range` (REQ-28).
    """
    if session is None:
        return detections

    def keep(timestamp: datetime) -> bool:
        return in_ny_kill_zone(timestamp, config)

    def session_filter(items, series, index_of):
        return None if items is None else [x for x in items if keep(series.candles[index_of(x)].timestamp)]

    return replace(
        detections,
        swings=session_filter(detections.swings, ltf_series, lambda s: s.index),
        fvgs=session_filter(detections.fvgs, ltf_series, lambda f: f.start_index),
        crt_ranges=session_filter(detections.crt_ranges, ltf_series, lambda r: r.start_index),
        mss_events=session_filter(detections.mss_events, ltf_series, lambda m: m.index),
        model1_signals=session_filter(detections.model1_signals, ltf_series, lambda s: s.anchor_index),
        aligned_signals=session_filter(detections.aligned_signals, ltf_series, lambda t: t.ltf_signal.anchor_index),
        htf_crt_ranges=detections.htf_crt_ranges if htf_series is None
        else session_filter(detections.htf_crt_ranges, htf_series, lambda r: r.start_index),
    )


def _filter_by_types(detections: _Detections, types: set[str]) -> _Detections:
    """REQ-28.1: e.g. --types fvg,model1 — only those markers/rows appear;
    dependencies (like CRT range feeding Model-1) stay computed internally.
    """
    include_model1 = "model1" in types or "alignment" in types
    return replace(
        detections,
        swings=detections.swings if "swing" in types else [],
        fvgs=detections.fvgs if "fvg" in types else [],
        crt_ranges=detections.crt_ranges if "crt_range" in types else [],
        mss_events=detections.mss_events if "mss" in types else [],
        model1_signals=detections.model1_signals if include_model1 else [],
        aligned_signals=detections.aligned_signals if "alignment" in types else None,
    )


def _exclude_invalidated_model1(detections: _Detections) -> _Detections:
    """A dead/INVALIDATED anchor (REQ-18) renders identically to a live
    PENDING/CONFIRMED one on the chart, which is misleading — excluded
    from what's plotted only; `detections.csv` keeps every status (chart
    call site consumes this, `detections` itself stays unfiltered for the
    CSV writer).
    """
    model1_signals = detections.model1_signals
    aligned_signals = detections.aligned_signals
    return replace(
        detections,
        model1_signals=None if model1_signals is None else [
            s for s in model1_signals if s.status != DetectionStatus.INVALIDATED
        ],
        aligned_signals=None if aligned_signals is None else [
            t for t in aligned_signals if t.ltf_signal.status != DetectionStatus.INVALIDATED
        ],
    )


def _parse_types(raw: str | None) -> set[str]:
    if raw is None:
        return set(_ALL_TYPES)
    tokens = {token.strip() for token in raw.split(",") if token.strip()}
    unknown = tokens - _ALL_TYPES
    if unknown:
        raise ValueError(
            f"unknown --types token(s): {', '.join(sorted(unknown))} (expected subset of {', '.join(sorted(_ALL_TYPES))})"
        )
    return tokens


def _parse_session(raw: str | None) -> str | None:
    if raw is None:
        return None
    if raw not in _SESSIONS:
        raise ValueError(f"unknown --session value: {raw} (expected one of {', '.join(sorted(_SESSIONS))})")
    return raw


def _parse_backtest_config(args: argparse.Namespace) -> BacktestConfig:
    """REQ-51: each of the 5 flags overrides exactly one BacktestConfig
    field; an omitted flag falls through to that field's default. Validation
    order matches the design's flag table, top to bottom; the first
    violation wins (REQ-51.3). Every flag arrives as a raw string (argparse
    does no type= conversion, see `_build_arg_parser`), so non-numeric and
    non-finite values are rejected here too, through the same ValueError ->
    exit 1 path as range violations -- never argparse's own exit 2."""
    defaults = BacktestConfig()

    sl_buffer = _parse_float(args.sl_buffer, defaults.sl_buffer_price, "--sl-buffer")
    if sl_buffer <= 0:
        raise ValueError(f"invalid --sl-buffer value: {args.sl_buffer} (expected a positive number)")

    min_rr = _parse_float(args.min_rr, defaults.min_risk_reward, "--min-rr")
    if min_rr < 0:
        raise ValueError(f"invalid --min-rr value: {args.min_rr} (expected a non-negative number)")

    trading_cost = _parse_float(args.trading_cost, defaults.trading_cost_price, "--trading-cost")
    if trading_cost < 0:
        raise ValueError(f"invalid --trading-cost value: {args.trading_cost} (expected a non-negative number)")

    kill_zone_gated = _parse_kill_zone_gated(args.kill_zone_gated, defaults.kill_zone_gated)

    max_fill_wait = _parse_int(args.max_fill_wait, defaults.max_fill_wait, "--max-fill-wait")
    if max_fill_wait <= 0:
        raise ValueError(f"invalid --max-fill-wait value: {args.max_fill_wait} (expected a positive integer)")

    return BacktestConfig(
        sl_buffer_price=sl_buffer, min_risk_reward=min_rr, trading_cost_price=trading_cost,
        kill_zone_gated=kill_zone_gated, max_fill_wait=max_fill_wait,
    )


def _parse_float(raw: str | None, default: float, flag: str) -> float:
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        raise ValueError(f"invalid {flag} value: {raw} (expected a number)")
    if not math.isfinite(value):
        raise ValueError(f"invalid {flag} value: {raw} (expected a finite number)")
    return value


def _parse_int(raw: str | None, default: int, flag: str) -> int:
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"invalid {flag} value: {raw} (expected an integer)")


def _parse_kill_zone_gated(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    raise ValueError(f"invalid --kill-zone-gated value: {raw} (expected true or false)")


def _resolve_kill_zone_gate(
    config: DetectorConfig, session: str | None
) -> tuple[DetectorConfig, KillZoneGateState]:
    """REQ-36.2/36.4/36.5: `--session` always wins, forcing the gate off for
    the run (excluded_kill_zone=0 by construction) regardless of an explicit
    `--kill-zone-gated true`. Resolved ONCE, before simulate()/compute_metrics(),
    so the effective and disclosed gate state cannot drift."""
    if session is not None:
        return replace(config, backtest=replace(config.backtest, kill_zone_gated=False)), "auto-disabled"
    if config.backtest.kill_zone_gated:
        return config, "enabled"
    return config, "disabled"


def _parse_date(raw: str | None, flag: str) -> date | None:
    if raw is None:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"invalid {flag} value: {raw} (expected YYYY-MM-DD)")


if __name__ == "__main__":
    sys.exit(main())
