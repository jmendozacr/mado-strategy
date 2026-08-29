"""REQ-45/49: `trades.csv` (13-column trade ledger) and
`metrics_summary.txt` (literal disclosure template) — the backtest's two
output writers, mirroring `viz/table.py`'s `detections.csv` writer.
"""

from pathlib import Path

from core.candle import OHLCSeries

from backtest.metrics import BacktestMetrics
from backtest.simulate import Trade
from viz.table import write_csv

_TRADES_HEADER = [
    "signal_id", "anchor_timestamp", "entry_timestamp", "direction", "entry_price",
    "stop_loss", "take_profit", "exit_timestamp", "exit_price", "outcome",
    "r_multiple", "ambiguous_bar", "gap_filled",
]

_KILL_ZONE_GATE_LINES = {
    "enabled": "kill-zone gate: enabled (evaluating anchor_index against the NY kill zone)",
    "auto-disabled": "kill-zone gate: auto-disabled (--session already applied)",
    "disabled": "kill-zone gate: disabled (--kill-zone-gated false)",
}


def write_trades_csv(series: OHLCSeries, trades: list[Trade], output_path: str) -> None:
    write_csv(output_path, _TRADES_HEADER, (_trade_row(series, trade) for trade in trades))


def _trade_row(series: OHLCSeries, trade: Trade) -> list:
    exit_timestamp = "" if trade.exit_index is None else series.candles[trade.exit_index].timestamp.isoformat()
    return [
        trade.signal_id,
        series.candles[trade.anchor_index].timestamp.isoformat(),
        series.candles[trade.entry_index].timestamp.isoformat(),
        trade.direction,
        trade.entry_price,
        trade.stop_loss,
        trade.take_profit,
        exit_timestamp,
        "" if trade.exit_price is None else trade.exit_price,
        trade.outcome,
        "" if trade.r_multiple is None else trade.r_multiple,
        trade.ambiguous_bar,
        trade.gap_filled,
    ]


def write_metrics_summary(
    metrics: BacktestMetrics, output_path: str, types_excluded_population: bool = False
) -> None:
    """`sdd/crt-detector-backtest-engine/design/interfaces`'s literal
    wording contract — e2e tests assert these lines as substrings; never
    paraphrase.

    `types_excluded_population`: True when --types itself narrowed the
    backtest population to nothing (neither "model1" nor "alignment"
    requested) — distinct from a run that genuinely has zero tradeable
    signals. Without this note a --types-emptied run and a genuinely
    signal-free run render byte-identical, misleading a reader into
    thinking the strategy never sets up rather than that their own flag
    filtered it out."""
    r = metrics.reconciliation
    lines = [
        f"signals considered: {r.signals_considered}",
        f"trades opened: {r.trades_opened}",
        f"win rate: {_ratio(metrics.win_rate)} ({metrics.wins}W / {metrics.losses}L)",
        f"average R: {_ratio(metrics.average_r_multiple)} over {metrics.closed_trades} closed trades",
        f"total R: {_ratio(metrics.total_r)} over {metrics.closed_trades} closed trades",
        "note: average R and total R assume unlimited capital, no cap on concurrently open positions",
        f"open trades: {metrics.open_trades}",
        f"same-candle SL+TP resolutions: {metrics.ambiguous_bar_count}",
        _trading_cost_line(metrics.config.trading_cost_price),
        _KILL_ZONE_GATE_LINES[metrics.kill_zone_gate_state],
        f"max fill wait: {metrics.config.max_fill_wait}",
        f"sl buffer: {_fixed_decimal(metrics.config.sl_buffer_price)}",
        f"min R:R: {_fixed_decimal(metrics.config.min_risk_reward)}",
        "note: trades.csv entry_price and detections.csv entry_price are independently computed "
        "and may differ for wick-type signals — see REQ-47",
        "note: trade resolution uses the full series regardless of --from-date/--to-date",
        "note: prices are raw instrument units (5-digit FX assumed)",
    ]
    if types_excluded_population:
        lines.append(
            "note: --types excluded model1/alignment signals from this run's population "
            "- the zero counts above reflect that filter, not an empty result set"
        )
    lines += [
        "reconciliation:",
        f"  no crt range: {r.excluded_no_crt_range}",
        f"  unaligned: {r.excluded_unaligned}",
        f"  never confirmed: {r.excluded_never_confirmed}",
        f"  duplicate: {r.excluded_duplicate}",
        f"  kill zone: {r.excluded_kill_zone}",
        f"  rr floor: {r.excluded_rr_floor}",
        f"  never filled: {r.excluded_never_filled}",
    ]
    Path(output_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _ratio(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def _trading_cost_line(trading_cost_price: float) -> str:
    if trading_cost_price == 0.0:
        return "trading cost: 0.0 (frictionless)"
    return f"trading cost: {_fixed_decimal(trading_cost_price)} per trade"


def _fixed_decimal(value: float) -> str:
    """`str(float)` switches to scientific notation below ~1e-4 (e.g.
    `7e-05`), contradicting the report's own "raw instrument units, 5-digit
    FX" note for realistic small price-unit config values. Fixed-precision
    then strip trailing zeros keeps `str()`'s output for "nice" decimals."""
    text = f"{value:.10f}".rstrip("0")
    return text + "0" if text.endswith(".") else text
