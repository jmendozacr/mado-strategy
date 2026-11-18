"""Independent audit export for the live 1AM+9AM EURUSD/USDCAD/AUDUSD recipe.

Read-only with respect to production code: imports and calls
`detector/experimental/htf_trigger_1am_9am_backtest.py` and
`detector/backtest/simulate.py` exactly as they exist on HEAD. Nothing in
`detector/` or `scanner/` is modified, recalibrated, or reimplemented here.
This script only (a) runs the existing backtest harness over the existing
`data/<SYMBOL>_{D1,H4,M15}_*.csv` files for EURUSD/USDCAD/AUDUSD, and
(b) serializes its real output (per-trade records + config) into the five
audit deliverables. See README.md in this directory for column docs,
units, and limitations.
"""
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from dataclasses import asdict

AUDIT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(AUDIT_DIR, "..", ".."))
DETECTOR_DIR = os.path.join(REPO_ROOT, "detector")
DATA_DIR = os.path.join(REPO_ROOT, "data")

sys.path.insert(0, DETECTOR_DIR)

from backtest.simulate import simulate  # noqa: E402
from core.config import DetectorConfig  # noqa: E402
from experimental.htf_trigger_1am_9am_backtest import (  # noqa: E402
    SYMBOL_CONFIG,
    _find_csv,
    backtest_1am_9am,
    trade_stats,
)
from ingestion.loader import load_mt5_csv  # noqa: E402
from ingestion.pairing import load_pair  # noqa: E402

SYMBOLS = ("EURUSD", "USDCAD", "AUDUSD")


def _git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", REPO_ROOT, *args], text=True).strip()


def run_backtest(symbol: str):
    h4_csv = _find_csv(DATA_DIR, symbol, "H4")
    m15_csv = _find_csv(DATA_DIR, symbol, "M15")
    d1_csv = _find_csv(DATA_DIR, symbol, "D1")
    h4, m15 = load_pair(htf_csv=h4_csv, htf_symbol=symbol, ltf_csv=m15_csv, ltf_symbol=symbol)
    daily = load_mt5_csv(d1_csv, symbol=symbol)

    config = DetectorConfig(backtest=SYMBOL_CONFIG[symbol])
    aligned_signals, model_by_id = backtest_1am_9am(m15, h4, daily, config)
    trades, report = simulate(aligned_signals, m15, config)
    return {
        "m15": m15,
        "config": config,
        "trades": trades,
        "report": report,
        "model_by_id": model_by_id,
        "csv_paths": {"h4": h4_csv, "m15": m15_csv, "d1": d1_csv},
    }


def fmt_ts(series, index):
    if index is None:
        return ""
    return series.candles[index].timestamp.isoformat()


def build_trades_rows(symbol, result):
    m15 = result["m15"]
    model_by_id = result["model_by_id"]
    rows = []
    for t in result["trades"]:
        rows.append({
            "pair": symbol,
            "signal_id": t.signal_id,
            "model": model_by_id.get(t.signal_id, ""),
            "direction": t.direction,
            "entry_index": t.entry_index,
            "entry_timestamp_broker": fmt_ts(m15, t.entry_index),
            "entry_price": t.entry_price,
            "stop_loss": t.stop_loss,
            "take_profit": t.take_profit,
            "partial_exit_index": "" if t.partial_exit_index is None else t.partial_exit_index,
            "partial_exit_timestamp_broker": fmt_ts(m15, t.partial_exit_index),
            "partial_exit_price": "" if t.partial_exit_price is None else t.partial_exit_price,
            "partial_r_multiple": "" if t.partial_r_multiple is None else t.partial_r_multiple,
            "partial_gap_filled": t.partial_gap_filled,
            "exit_index": "" if t.exit_index is None else t.exit_index,
            "exit_timestamp_broker": fmt_ts(m15, t.exit_index),
            "exit_price": "" if t.exit_price is None else t.exit_price,
            "outcome": t.outcome,
            "r_multiple": "" if t.r_multiple is None else t.r_multiple,
            "ambiguous_bar": t.ambiguous_bar,
            "gap_filled": t.gap_filled,
            "breakeven_after_partial_config": result["config"].backtest.breakeven_after_partial,
        })
    return rows


TRADES_COLUMNS = [
    "pair", "signal_id", "model", "direction",
    "entry_index", "entry_timestamp_broker", "entry_price", "stop_loss", "take_profit",
    "partial_exit_index", "partial_exit_timestamp_broker", "partial_exit_price",
    "partial_r_multiple", "partial_gap_filled",
    "exit_index", "exit_timestamp_broker", "exit_price",
    "outcome", "r_multiple", "ambiguous_bar", "gap_filled",
    "breakeven_after_partial_config",
]


def build_execution_events_rows(symbol, result):
    m15 = result["m15"]
    model_by_id = result["model_by_id"]
    partial_fraction = result["config"].backtest.partial_fraction
    breakeven_after_partial = result["config"].backtest.breakeven_after_partial
    rows = []
    for t in result["trades"]:
        rows.append({
            "pair": symbol,
            "signal_id": t.signal_id,
            "model": model_by_id.get(t.signal_id, ""),
            "event_type": "entry_fill",
            "bar_index": t.entry_index,
            "timestamp_broker": fmt_ts(m15, t.entry_index),
            "price": t.entry_price,
            "position_fraction_closed": "",
            "r_multiple_leg": "",
            "derived": False,
            "note": "position opened at the signal's limit entry price",
        })
        if t.partial_exit_index is not None:
            rows.append({
                "pair": symbol,
                "signal_id": t.signal_id,
                "model": model_by_id.get(t.signal_id, ""),
                "event_type": "partial_close",
                "bar_index": t.partial_exit_index,
                "timestamp_broker": fmt_ts(m15, t.partial_exit_index),
                "price": t.partial_exit_price,
                "position_fraction_closed": partial_fraction,
                "r_multiple_leg": t.partial_r_multiple,
                "derived": False,
                "note": "equilibrium-level partial take-profit fired (leg 1)",
            })
            if breakeven_after_partial:
                rows.append({
                    "pair": symbol,
                    "signal_id": t.signal_id,
                    "model": model_by_id.get(t.signal_id, ""),
                    "event_type": "sl_update_to_breakeven",
                    "bar_index": t.partial_exit_index,
                    "timestamp_broker": fmt_ts(m15, t.partial_exit_index),
                    "price": t.entry_price,
                    "position_fraction_closed": "",
                    "r_multiple_leg": "",
                    "derived": True,
                    "note": (
                        "remaining position's stop-loss moved from the original stop_loss "
                        "to entry_price (breakeven). Not a separately persisted field on "
                        "the Trade record -- derived from partial_exit_index being set "
                        "combined with breakeven_after_partial=True "
                        "(detector/backtest/simulate.py::_resolve_trade, same bar as the "
                        "partial fill per the code's own tie-handling rule)."
                    ),
                })
        if t.exit_index is not None:
            rows.append({
                "pair": symbol,
                "signal_id": t.signal_id,
                "model": model_by_id.get(t.signal_id, ""),
                "event_type": "exit",
                "bar_index": t.exit_index,
                "timestamp_broker": fmt_ts(m15, t.exit_index),
                "price": t.exit_price,
                "position_fraction_closed": (1 - partial_fraction) if t.partial_exit_index is not None else 1.0,
                "r_multiple_leg": t.r_multiple,
                "derived": False,
                "note": f"trade closed, outcome={t.outcome}",
            })
        else:
            rows.append({
                "pair": symbol,
                "signal_id": t.signal_id,
                "model": model_by_id.get(t.signal_id, ""),
                "event_type": "still_open_at_data_end",
                "bar_index": "",
                "timestamp_broker": "",
                "price": "",
                "position_fraction_closed": "",
                "r_multiple_leg": "",
                "derived": False,
                "note": "neither stop-loss nor take-profit touched before the M15 series ends",
            })
    return rows


EVENTS_COLUMNS = [
    "pair", "signal_id", "model", "event_type", "bar_index", "timestamp_broker",
    "price", "position_fraction_closed", "r_multiple_leg", "derived", "note",
]


def write_csv(path, columns, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main():
    head_commit = _git("rev-parse", "HEAD")
    generated_at = _git("show", "-s", "--format=%cI", "HEAD")

    results = {}
    all_trades_rows = []
    all_events_rows = []
    per_symbol_stats = {}
    for symbol in SYMBOLS:
        result = run_backtest(symbol)
        results[symbol] = result
        all_trades_rows += build_trades_rows(symbol, result)
        all_events_rows += build_execution_events_rows(symbol, result)
        per_symbol_stats[symbol] = trade_stats(result["trades"])

    combined_trades = [t for r in results.values() for t in r["trades"]]
    combined_stats = trade_stats(combined_trades)

    write_csv(os.path.join(AUDIT_DIR, "trades.csv"), TRADES_COLUMNS, all_trades_rows)
    write_csv(os.path.join(AUDIT_DIR, "execution_events.csv"), EVENTS_COLUMNS, all_events_rows)

    backtest_config = {
        "_provenance": {
            "generated_from_commit": head_commit,
            "generated_at_commit_timestamp": generated_at,
            "source_file": "detector/experimental/htf_trigger_1am_9am_backtest.py (SYMBOL_CONFIG, lines 76-113)",
            "cross_checked_against": "scanner/main.py (BACKTEST_CONFIG, lines 78-99) -- byte-identical for EURUSD/USDCAD/AUDUSD as of this commit",
        },
        "global": {
            "risk_pct_per_trade": 1.0,
            "initial_balance_usd": 10000.0,
            "balance_model": "fixed, non-compounding -- scanner/main.py:123 INITIAL_BALANCE, never the live account balance",
            "max_fill_wait_candles": 20,
            "source_file_global": "scanner/main.py (RISK_PCT line 114, INITIAL_BALANCE line 123, PARTIAL_FRACTION line 125)",
        },
        "pairs": {},
        "data_sources": {},
    }
    for symbol in SYMBOLS:
        cfg = results[symbol]["config"].backtest
        backtest_config["pairs"][symbol] = asdict(cfg)
        backtest_config["data_sources"][symbol] = {
            k: os.path.relpath(v, REPO_ROOT) for k, v in results[symbol]["csv_paths"].items()
        }

    with open(os.path.join(AUDIT_DIR, "backtest_config.json"), "w", encoding="utf-8") as f:
        json.dump(backtest_config, f, indent=2, default=str)

    reconciliation = {
        "generated_from_commit": head_commit,
        "per_symbol": per_symbol_stats,
        "combined": combined_stats,
        "trades_csv_row_count": len(all_trades_rows),
        "trades_csv_closed_total_r_recomputed": sum(
            float(r["r_multiple"]) for r in all_trades_rows if r["r_multiple"] != ""
        ),
        "trades_csv_closed_count_recomputed": sum(1 for r in all_trades_rows if r["outcome"] in ("win", "loss")),
    }
    with open(os.path.join(AUDIT_DIR, "_reconciliation_check.json"), "w", encoding="utf-8") as f:
        json.dump(reconciliation, f, indent=2, default=str)

    for symbol in SYMBOLS:
        s = per_symbol_stats[symbol]
        print(
            f"{symbol:<10} trades={s['trades']:<6} closed={s['closed']:<6} "
            f"win_rate={s['win_rate']:.4f} total_r={s['total_r']:+.4f}"
        )
    print(
        f"{'COMBINED':<10} trades={combined_stats['trades']:<6} closed={combined_stats['closed']:<6} "
        f"win_rate={combined_stats['win_rate']:.4f} total_r={combined_stats['total_r']:+.4f}"
    )
    print(f"recomputed total_r from trades.csv = {reconciliation['trades_csv_closed_total_r_recomputed']:+.4f}")
    assert abs(reconciliation["trades_csv_closed_total_r_recomputed"] - combined_stats["total_r"]) < 1e-6, (
        "trades.csv does not reconcile against the harness's own in-memory trade_stats() total"
    )
    assert reconciliation["trades_csv_closed_count_recomputed"] == combined_stats["closed"], (
        "trades.csv closed-trade count does not reconcile against trade_stats()"
    )
    print("RECONCILED: trades.csv sums match the backtest harness's own in-run aggregate exactly.")


if __name__ == "__main__":
    main()
