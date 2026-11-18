"""Phase 2 orchestrator: Arm A (original), Arm B1 (ideal/realistic
late-discovery), Arm B2 (strict causal) over EURUSD/USDCAD/AUDUSD.

Nothing under detector/ or scanner/ is modified. Expensive, shared
detection (CRT ranges, swings, FVG/Order-Block key levels, H4 Turtle Soup
triggers) runs ONCE per symbol (causal_lib.compute_shared_detection) and is
reused by every arm -- only the per-trigger confirmation window (B2) or the
fill-eligibility floor (B1) differ. Arm A and Arm B2 both call
`backtest.simulate.simulate` UNMODIFIED; only B1 needs a custom fill pass
(fill_b1.py), because it deliberately keeps the (causally early) original
retest/confirmation and only changes when a fill may occur.
"""
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from dataclasses import asdict
from datetime import timedelta

AUDIT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(AUDIT_DIR, "..", ".."))
DETECTOR_DIR = os.path.join(REPO_ROOT, "detector")
SCANNER_DIR = os.path.join(REPO_ROOT, "scanner")
DATA_DIR = os.path.join(REPO_ROOT, "data")
OUT_DIR = AUDIT_DIR

sys.path.insert(0, DETECTOR_DIR)
sys.path.insert(0, AUDIT_DIR)
sys.path.insert(0, SCANNER_DIR)

from backtest.population import build_stage6_population  # noqa: E402
from backtest.simulate import simulate  # noqa: E402
from core.config import DetectorConfig  # noqa: E402
from execution import pending_order_type  # noqa: E402  (pure, MT5-free -- scanner/execution.py)
from experimental.htf_trigger_1am_9am_backtest import SYMBOL_CONFIG, _find_csv  # noqa: E402
from ingestion.loader import load_mt5_csv  # noqa: E402
from ingestion.pairing import load_pair  # noqa: E402

import causal_lib  # noqa: E402
from fill_b1 import simulate_b1  # noqa: E402

SYMBOLS = ("EURUSD", "USDCAD", "AUDUSD")
POLL_SECONDS = 120  # scanner/main.py:46 POLL_SECONDS -- B1-realista's discovery-delay model


def _git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", REPO_ROOT, *args], text=True).strip()


def load_symbol_data(symbol: str):
    h4_csv = _find_csv(DATA_DIR, symbol, "H4")
    m15_csv = _find_csv(DATA_DIR, symbol, "M15")
    d1_csv = _find_csv(DATA_DIR, symbol, "D1")
    h4, m15 = load_pair(htf_csv=h4_csv, htf_symbol=symbol, ltf_csv=m15_csv, ltf_symbol=symbol)
    daily = load_mt5_csv(d1_csv, symbol=symbol)
    return h4, m15, daily


def fmt_ts(series, index):
    if index is None:
        return ""
    return series.candles[index].timestamp.isoformat()


def placement_price(m15, index):
    """What `current_price` the scanner would see at this M15 index, for
    `pending_order_type` -- the M15 candle's own CLOSE (the most recent
    fully-known price at that instant), not a bid/ask this OHLC dataset
    does not carry. Documented modeling choice (README)."""
    if index is None or index >= len(m15.candles):
        return None
    return m15.candles[index].close


def build_placement_map(shared, candidates, signal_id_to_h4_close, delay_seconds: int):
    placement_time_by_signal_id = {}
    placement_index_by_signal_id = {}
    for c in candidates:
        h4_close = signal_id_to_h4_close.get(c.signal_id)
        if h4_close is None:
            continue
        placement_time = h4_close + timedelta(seconds=delay_seconds)
        idx = causal_lib.m15_index_at_or_after(shared, placement_time)
        placement_time_by_signal_id[c.signal_id] = placement_time
        if idx is not None:
            placement_index_by_signal_id[c.signal_id] = idx
    return placement_time_by_signal_id, placement_index_by_signal_id


def trades_to_rows(symbol, arm, trades, m15, model_by_signal_id, stable_id_by_signal_id, h4_close_by_signal_id,
                    placement_time_by_signal_id=None, placement_index_by_signal_id=None):
    rows = []
    for t in trades:
        placement_idx = None if placement_index_by_signal_id is None else placement_index_by_signal_id.get(t.signal_id)
        order_type = ""
        if placement_idx is not None:
            price = placement_price(m15, placement_idx)
            if price is not None:
                order_type = pending_order_type(t.direction, entry_price=t.entry_price, current_price=price)
        rows.append({
            "pair": symbol,
            "arm": arm,
            "stable_id": stable_id_by_signal_id.get(t.signal_id, ""),
            "signal_id": t.signal_id,
            "model": model_by_signal_id.get(t.signal_id, ""),
            "direction": t.direction,
            "h4_trigger_close": h4_close_by_signal_id.get(t.signal_id, "").isoformat()
            if h4_close_by_signal_id.get(t.signal_id) else "",
            "placement_time": placement_time_by_signal_id.get(t.signal_id, "").isoformat()
            if placement_time_by_signal_id and placement_time_by_signal_id.get(t.signal_id) else "",
            "order_type": order_type,
            "entry_index": t.entry_index,
            "entry_timestamp_broker": fmt_ts(m15, t.entry_index),
            "entry_price": t.entry_price,
            "stop_loss": t.stop_loss,
            "take_profit": t.take_profit,
            "partial_exit_index": "" if t.partial_exit_index is None else t.partial_exit_index,
            "partial_exit_timestamp_broker": fmt_ts(m15, t.partial_exit_index),
            "partial_exit_price": "" if t.partial_exit_price is None else t.partial_exit_price,
            "partial_r_multiple": "" if t.partial_r_multiple is None else t.partial_r_multiple,
            "exit_index": "" if t.exit_index is None else t.exit_index,
            "exit_timestamp_broker": fmt_ts(m15, t.exit_index),
            "exit_price": "" if t.exit_price is None else t.exit_price,
            "outcome": t.outcome,
            "r_multiple": "" if t.r_multiple is None else t.r_multiple,
            "ambiguous_bar": t.ambiguous_bar,
            "gap_filled": t.gap_filled,
        })
    return rows


TRADE_COLUMNS = [
    "pair", "arm", "stable_id", "signal_id", "model", "direction", "h4_trigger_close", "placement_time",
    "order_type", "entry_index", "entry_timestamp_broker", "entry_price", "stop_loss", "take_profit",
    "partial_exit_index", "partial_exit_timestamp_broker", "partial_exit_price", "partial_r_multiple",
    "exit_index", "exit_timestamp_broker", "exit_price", "outcome", "r_multiple", "ambiguous_bar", "gap_filled",
]


def write_csv(path, columns, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def trade_stats(trades):
    closed = [t for t in trades if t.outcome in ("win", "loss")]
    wins = sum(1 for t in closed if t.outcome == "win")
    total_r = sum(t.r_multiple for t in closed if t.r_multiple is not None)
    return {
        "trades": len(trades), "closed": len(closed),
        "win_rate": wins / len(closed) if closed else 0.0,
        "avg_r": total_r / len(closed) if closed else 0.0,
        "total_r": total_r,
    }


def max_drawdown_r(trades, m15):
    """Simple peak-to-trough R drawdown, chronological by exit time.
    Documented convention (not the prop-firm initial_balance_floor basis
    used elsewhere in this repo) -- stated plainly in the README."""
    closed = [(m15.candles[t.exit_index].timestamp, t.r_multiple) for t in trades
              if t.outcome in ("win", "loss") and t.exit_index is not None and t.r_multiple is not None]
    closed.sort(key=lambda pair: pair[0])
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for _, r in closed:
        equity += r
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return max_dd


def main():
    head_commit = _git("rev-parse", "HEAD")

    all_rows = {"arm_a": [], "b1_ideal": [], "b1_realistic": [], "b2": []}
    reconciliation_rows = []
    zero_signal_rows = []
    funnel_rows = []
    per_arm_stats = {"arm_a": {}, "b1_ideal": {}, "b1_realistic": {}, "b2": {}}

    for symbol in SYMBOLS:
        h4, m15, daily = load_symbol_data(symbol)
        config = DetectorConfig(backtest=SYMBOL_CONFIG[symbol])
        shared = causal_lib.compute_shared_detection(m15, h4, daily, config)

        # ---- Arm A (unmodified production pipeline) ----
        results_a, sig2stable_a, sig2h4close_a = causal_lib.arm_a_signals(shared, symbol)
        aligned_signals_a = [aligned for aligned, _model, _sid in results_a]
        model_by_sig_a = {aligned.ltf_signal.signal_id: model for aligned, model, _sid in results_a}
        population_a = build_stage6_population(aligned_signals_a, m15, config, swings=shared.swings)
        trades_a, report_a = simulate(aligned_signals_a, m15, config, swings=shared.swings)

        rows_a = trades_to_rows(symbol, "arm_a", trades_a, m15, model_by_sig_a, sig2stable_a, sig2h4close_a)
        all_rows["arm_a"] += rows_a
        funnel_rows.append({"pair": symbol, "arm": "arm_a", **asdict(report_a)})

        # ---- Arm B1 (ideal / realistic late discovery) ----
        placement_time_ideal, placement_index_ideal = build_placement_map(
            shared, population_a.candidates, sig2h4close_a, delay_seconds=0
        )
        trades_b1_ideal, never_filled_ideal, skipped_ideal = simulate_b1(
            population_a.candidates, m15.candles, config, placement_index_ideal
        )
        rows_b1_ideal = trades_to_rows(
            symbol, "b1_ideal", trades_b1_ideal, m15, model_by_sig_a, sig2stable_a, sig2h4close_a,
            placement_time_ideal, placement_index_ideal,
        )
        all_rows["b1_ideal"] += rows_b1_ideal

        placement_time_real, placement_index_real = build_placement_map(
            shared, population_a.candidates, sig2h4close_a, delay_seconds=POLL_SECONDS
        )
        trades_b1_real, never_filled_real, skipped_real = simulate_b1(
            population_a.candidates, m15.candles, config, placement_index_real
        )
        rows_b1_real = trades_to_rows(
            symbol, "b1_realistic", trades_b1_real, m15, model_by_sig_a, sig2stable_a, sig2h4close_a,
            placement_time_real, placement_index_real,
        )
        all_rows["b1_realistic"] += rows_b1_real

        funnel_rows.append({
            "pair": symbol, "arm": "b1_ideal",
            "candidates": len(population_a.candidates),
            "never_filled": never_filled_ideal, "skipped_no_placement": skipped_ideal,
            "closed": len([t for t in trades_b1_ideal if t.outcome in ("win", "loss")]),
        })
        funnel_rows.append({
            "pair": symbol, "arm": "b1_realistic",
            "candidates": len(population_a.candidates),
            "never_filled": never_filled_real, "skipped_no_placement": skipped_real,
            "closed": len([t for t in trades_b1_real if t.outcome in ("win", "loss")]),
        })

        # ---- Arm B2 (strict causal confirmation window) ----
        results_b2, sig2h4close_b2, zero_reason_b2 = causal_lib.arm_b2_signals(shared, symbol)
        aligned_signals_b2 = [aligned for aligned, _model, _sid in results_b2]
        model_by_sig_b2 = {aligned.ltf_signal.signal_id: model for aligned, model, _sid in results_b2}
        sid2stable_b2 = {aligned.ltf_signal.signal_id: sid for aligned, _model, sid in results_b2}
        population_b2 = build_stage6_population(aligned_signals_b2, m15, config, swings=shared.swings)
        trades_b2, report_b2 = simulate(aligned_signals_b2, m15, config, swings=shared.swings)

        rows_b2 = trades_to_rows(symbol, "b2", trades_b2, m15, model_by_sig_b2, sid2stable_b2, sig2h4close_b2)
        all_rows["b2"] += rows_b2
        funnel_rows.append({"pair": symbol, "arm": "b2", **asdict(report_b2)})

        for sid, reason in zero_reason_b2.items():
            zero_signal_rows.append({"pair": symbol, "stable_id": sid, "reason": reason})

        # ---- Reconciliation, keyed by stable_id (shared across A/B1/B2) ----
        by_stable = {}

        def _note(stable_id, arm, trade=None, candidate_signal_id=None):
            entry = by_stable.setdefault(stable_id, {"pair": symbol})
            if trade is not None:
                entry[f"{arm}_signal_id"] = trade.signal_id
                entry[f"{arm}_entry_ts"] = fmt_ts(m15, trade.entry_index)
                entry[f"{arm}_exit_ts"] = fmt_ts(m15, trade.exit_index)
                entry[f"{arm}_r_multiple"] = "" if trade.r_multiple is None else trade.r_multiple
                entry[f"{arm}_outcome"] = trade.outcome
                entry[f"{arm}_status"] = "open" if trade.outcome == "open" else "filled"
            elif candidate_signal_id is not None:
                entry.setdefault(f"{arm}_status", "placed_never_filled")
            else:
                entry.setdefault(f"{arm}_status", "no_fillable_candidate")

        for aligned, _model, sid in results_a:
            by_stable.setdefault(sid, {"pair": symbol})["h4_trigger_close"] = sig2h4close_a.get(
                aligned.ltf_signal.signal_id, ""
            )
        for t in trades_a:
            _note(sig2stable_a.get(t.signal_id, f"?{t.signal_id}"), "arm_a", trade=t)
        placed_a_ids = {c.signal_id for c in population_a.candidates}
        for sid_candidate in placed_a_ids - {t.signal_id for t in trades_a}:
            stable = sig2stable_a.get(sid_candidate)
            if stable:
                by_stable.setdefault(stable, {"pair": symbol}).setdefault("arm_a_status", "placed_never_filled")

        for t in trades_b1_ideal:
            _note(sig2stable_a.get(t.signal_id, f"?{t.signal_id}"), "b1_ideal", trade=t)
        for t in trades_b1_real:
            _note(sig2stable_a.get(t.signal_id, f"?{t.signal_id}"), "b1_realistic", trade=t)
        for t in trades_b2:
            _note(sid2stable_b2.get(t.signal_id, f"?{t.signal_id}"), "b2", trade=t)
        for sid, reason in zero_reason_b2.items():
            by_stable.setdefault(sid, {"pair": symbol})["b2_status"] = "no_signal"
            by_stable[sid]["b2_no_signal_reason"] = reason

        for stable_id, data in by_stable.items():
            row = {"stable_id": stable_id, "pair": symbol}
            row.update(data)
            reconciliation_rows.append(row)

        for arm_key, trades in (
            ("arm_a", trades_a), ("b1_ideal", trades_b1_ideal), ("b1_realistic", trades_b1_real), ("b2", trades_b2)
        ):
            per_arm_stats[arm_key][symbol] = {**trade_stats(trades), "max_drawdown_r": max_drawdown_r(trades, m15)}

        print(f"{symbol} done -- A:{len(trades_a)} B1i:{len(trades_b1_ideal)} B1r:{len(trades_b1_real)} B2:{len(trades_b2)}", flush=True)

    for arm, rows in all_rows.items():
        write_csv(os.path.join(OUT_DIR, f"trades_{arm}.csv"), TRADE_COLUMNS, rows)

    recon_columns = sorted({k for row in reconciliation_rows for k in row.keys()})
    write_csv(os.path.join(OUT_DIR, "reconciliation.csv"), recon_columns, reconciliation_rows)

    write_csv(os.path.join(OUT_DIR, "b2_zero_signal_reasons.csv"), ["pair", "stable_id", "reason"], zero_signal_rows)

    funnel_columns = sorted({k for row in funnel_rows for k in row.keys()})
    write_csv(os.path.join(OUT_DIR, "funnel_by_arm.csv"), funnel_columns, funnel_rows)

    combined_stats = {}
    for arm, per_symbol in per_arm_stats.items():
        combined_trades = sum(s["trades"] for s in per_symbol.values())
        combined_closed = sum(s["closed"] for s in per_symbol.values())
        combined_total_r = sum(s["total_r"] for s in per_symbol.values())
        combined_wins = sum(round(s["win_rate"] * s["closed"]) for s in per_symbol.values())
        combined_stats[arm] = {
            "per_symbol": per_symbol,
            "combined": {
                "trades": combined_trades, "closed": combined_closed,
                "win_rate": combined_wins / combined_closed if combined_closed else 0.0,
                "total_r": combined_total_r,
                "avg_r": combined_total_r / combined_closed if combined_closed else 0.0,
            },
        }
    with open(os.path.join(OUT_DIR, "metrics_by_arm.json"), "w", encoding="utf-8") as f:
        json.dump(combined_stats, f, indent=2, default=str)

    with open(os.path.join(OUT_DIR, "run_metadata.json"), "w", encoding="utf-8") as f:
        json.dump({
            "generated_from_commit": head_commit,
            "poll_seconds_assumption": POLL_SECONDS,
            "symbols": list(SYMBOLS),
        }, f, indent=2)

    for arm, data in combined_stats.items():
        c = data["combined"]
        print(f"{arm:<14} trades={c['trades']:<6} closed={c['closed']:<6} win_rate={c['win_rate']:.4f} total_r={c['total_r']:+.4f}")


if __name__ == "__main__":
    main()
