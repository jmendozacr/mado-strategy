"""Orchestrates Arms C1 (causal trigger, broker H4 grid) and C2 (causal
trigger, NY-anchored feeder candles) across EURUSD/USDCAD/AUDUSD, full
2003-2026 history. Design: design-c1-c2.md. Nothing under detector/ or
scanner/ is modified; A/B1/B2 outputs are read-only inputs here, never
overwritten.
"""
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timedelta

AUDIT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(AUDIT_DIR, "..", ".."))
DETECTOR_DIR = os.path.join(REPO_ROOT, "detector")
DATA_DIR = os.path.join(REPO_ROOT, "data")
OUT_DIR = AUDIT_DIR

sys.path.insert(0, DETECTOR_DIR)
sys.path.insert(0, AUDIT_DIR)

from backtest.population import build_stage6_population  # noqa: E402
from backtest.simulate import _resolve_exits  # noqa: E402
from core.config import DetectorConfig  # noqa: E402
from experimental.htf_trigger_1am_9am_backtest import SYMBOL_CONFIG, _find_csv  # noqa: E402
from ingestion.loader import load_mt5_csv  # noqa: E402
from ingestion.pairing import load_pair  # noqa: E402
from primitives.crt_range import detect_crt_ranges  # noqa: E402
from primitives.swing import detect_swings  # noqa: E402

import causal_intrabar as ci  # noqa: E402
from causal_lib import build_key_levels  # noqa: E402

SYMBOLS = ("EURUSD", "USDCAD", "AUDUSD")


def _git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", REPO_ROOT, *args], text=True).strip()


def load_symbol_data(symbol: str):
    h4_csv = _find_csv(DATA_DIR, symbol, "H4")
    m15_csv = _find_csv(DATA_DIR, symbol, "M15")
    d1_csv = _find_csv(DATA_DIR, symbol, "D1")
    h4, m15 = load_pair(htf_csv=h4_csv, htf_symbol=symbol, ltf_csv=m15_csv, ltf_symbol=symbol)
    daily = load_mt5_csv(d1_csv, symbol=symbol)
    return h4, m15, daily


def fmt_ts(value) -> str:
    return value.isoformat() if isinstance(value, datetime) else ""


def stable_trigger_id(symbol: str, arm: str, model_name: str, window_open_ts: datetime, direction: str) -> str:
    return f"{symbol}|{arm}|{model_name}|{window_open_ts.isoformat()}|{direction}"


class FunnelCounters:
    def __init__(self):
        self.windows_considered = 0
        self.reference_incomplete_skipped = 0
        self.swept_bearish_only = 0
        self.swept_bullish_only = 0
        self.swept_both = 0
        self.swept_neither = 0
        self.triggers_with_key_level = 0
        self.model1_confirmed = 0
        self.zero_signal_reasons: Counter = Counter()

    def record_sweep(self, outcomes: dict):
        bearish, bullish = outcomes["bearish"].swept, outcomes["bullish"].swept
        if bearish and bullish:
            self.swept_both += 1
        elif bearish:
            self.swept_bearish_only += 1
        elif bullish:
            self.swept_bullish_only += 1
        else:
            self.swept_neither += 1

    def to_dict(self):
        return {
            "windows_considered": self.windows_considered,
            "reference_incomplete_skipped": self.reference_incomplete_skipped,
            "swept_bearish_only": self.swept_bearish_only,
            "swept_bullish_only": self.swept_bullish_only,
            "swept_both": self.swept_both,
            "swept_neither": self.swept_neither,
            "triggers_with_key_level": self.triggers_with_key_level,
            "model1_confirmed": self.model1_confirmed,
            "zero_signal_reason_categories": dict(self.zero_signal_reasons),
        }


def _categorize_reason(reason: str) -> str:
    if "window" in reason and "ends at or before" in reason:
        return "window_empty_before_search"
    if "no M15 candle falls inside" in reason:
        return "window_has_no_m15_data"
    if "resolved" in reason and "not CONFIRMED" in reason:
        return "model1_pending_or_invalidated"
    return "no_model1_anchor_found"


def run_c1(symbol: str, h4, m15, daily, config, m15_timestamps, ltf_ranges, swings, key_levels):
    counters = {"1am": FunnelCounters(), "9am": FunnelCounters()}
    records: list[ci.CausalSignalRecord] = []
    for model, model_name in ((ci.MODEL_1AM, "1am"), (ci.MODEL_9AM, "9am")):
        c = counters[model_name]
        for i in range(1, len(h4.candles)):
            if h4.candles[i].timestamp.hour != model.trigger_utc_hour or h4.candles[i].timestamp.minute != 0:
                continue
            reference = ci.complete_feeder_candle_broker(h4, i - 1)
            window_open_ts = h4.candles[i].timestamp
            window_close_ts = window_open_ts + ci.H4_DURATION
            c.windows_considered += 1
            outcomes = ci.detect_sweep_and_key_level(
                m15_timestamps, m15.candles, reference, window_open_ts, window_close_ts, key_levels, h4
            )
            c.record_sweep(outcomes)
            for direction, outcome in outcomes.items():
                if outcome.trigger is None:
                    continue
                c.triggers_with_key_level += 1
                record = ci.build_causal_signal(
                    model, model_name, outcome.trigger, window_open_ts, m15, ltf_ranges, config.model1, reference
                )
                if record.aligned is not None:
                    c.model1_confirmed += 1
                else:
                    c.zero_signal_reasons[_categorize_reason(record.zero_signal_reason)] += 1
                sid = stable_trigger_id(symbol, "c1", model_name, window_open_ts, direction)
                records.append((record, sid))
    return records, counters


def run_c2(symbol: str, h4, m15, daily, config, m15_timestamps, ltf_ranges, swings, key_levels):
    counters = {"1am": FunnelCounters(), "9am": FunnelCounters()}
    records: list[ci.CausalSignalRecord] = []
    first_day, last_day = m15.candles[0].timestamp.date(), m15.candles[-1].timestamp.date()
    one_day = timedelta(days=1)

    for model, model_name in ((ci.MODEL_1AM, "1am"), (ci.MODEL_9AM, "9am")):
        c = counters[model_name]
        ref_hour = ci.REFERENCE_HOUR_NY[model_name]
        cur_hour = ci.CURRENT_HOUR_NY[model_name]
        ref_prev_day = ci.REFERENCE_IS_PREVIOUS_DAY[model_name]
        day = first_day
        while day <= last_day:
            current_open_ts = ci.ny_anchored_open_utc(day, cur_hour)
            ref_day = (day - one_day) if ref_prev_day else day
            ref_open_ts = ci.ny_anchored_open_utc(ref_day, ref_hour)
            day += one_day

            reference = ci.complete_feeder_candle_ny(m15_timestamps, m15.candles, ref_open_ts)
            if reference is None:
                c.reference_incomplete_skipped += 1
                continue
            c.windows_considered += 1
            window_close_ts = current_open_ts + ci.H4_DURATION
            outcomes = ci.detect_sweep_and_key_level(
                m15_timestamps, m15.candles, reference, current_open_ts, window_close_ts, key_levels, h4
            )
            c.record_sweep(outcomes)
            for direction, outcome in outcomes.items():
                if outcome.trigger is None:
                    continue
                c.triggers_with_key_level += 1
                record = ci.build_causal_signal(
                    model, model_name, outcome.trigger, current_open_ts, m15, ltf_ranges, config.model1, reference
                )
                if record.aligned is not None:
                    c.model1_confirmed += 1
                else:
                    c.zero_signal_reasons[_categorize_reason(record.zero_signal_reason)] += 1
                sid = stable_trigger_id(symbol, "c2", model_name, current_open_ts, direction)
                records.append((record, sid))
    return records, counters




TRADE_COLUMNS = [
    "pair", "arm", "stable_id", "signal_id", "model", "direction",
    "feeder_ref_available_ts", "activation_instant_ts", "model1_available_ts", "order_placed_ts",
    "entry_index", "entry_timestamp_broker", "entry_price", "stop_loss", "take_profit",
    "partial_exit_index", "partial_exit_timestamp_broker", "partial_exit_price", "partial_r_multiple",
    "exit_index", "exit_timestamp_broker", "exit_price", "outcome", "r_multiple", "ambiguous_bar", "gap_filled",
]


def fmt_idx_ts(series, index):
    return "" if index is None else series.candles[index].timestamp.isoformat()


def trade_stats(trades):
    closed = [t for t in trades if t.outcome in ("win", "loss")]
    wins = sum(1 for t in closed if t.outcome == "win")
    total_r = sum(t.r_multiple for t in closed if t.r_multiple is not None)
    return {
        "trades": len(trades), "closed": len(closed),
        "win_rate": wins / len(closed) if closed else 0.0,
        "avg_r": total_r / len(closed) if closed else 0.0,
        "total_r": total_r,
        "expectancy_per_trade": total_r / len(trades) if trades else 0.0,
    }


def max_drawdown_r(trades, m15):
    closed = [(m15.candles[t.exit_index].timestamp, t.r_multiple) for t in trades
              if t.outcome in ("win", "loss") and t.exit_index is not None and t.r_multiple is not None]
    closed.sort(key=lambda pair: pair[0])
    equity = peak = max_dd = 0.0
    for _, r in closed:
        equity += r
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return max_dd


def write_csv(path, columns, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def process_arm(symbol, arm, records_with_ids, h4, m15, daily, config, m15_timestamps, swings):
    aligned_records = [(rec, sid) for rec, sid in records_with_ids if rec.aligned is not None]
    aligned_signals = [rec.aligned for rec, _sid in aligned_records]
    model_by_sig = {rec.aligned.ltf_signal.signal_id: rec.model_name for rec, _sid in aligned_records}
    stable_by_sig = {rec.aligned.ltf_signal.signal_id: sid for rec, sid in aligned_records}
    order_placed_by_sig = {rec.aligned.ltf_signal.signal_id: rec.order_placed_ts for rec, _sid in aligned_records}
    confirmation_idx_by_sig = {rec.aligned.ltf_signal.signal_id: rec.confirmation_index for rec, _sid in aligned_records}
    activation_by_sig = {rec.aligned.ltf_signal.signal_id: rec.activation_instant_ts for rec, _sid in aligned_records}
    ref_avail_by_sig = {rec.aligned.ltf_signal.signal_id: rec.feeder_ref_available_ts for rec, _sid in aligned_records}

    population = build_stage6_population(aligned_signals, m15, config, swings=swings)
    filled, never_filled, skipped_no_placement = ci.fill_pass_c(
        population.candidates, m15.candles, m15_timestamps, config.backtest.max_fill_wait,
        order_placed_by_sig, confirmation_idx_by_sig,
    )
    trades = _resolve_exits(
        filled, m15.candles, config.backtest.trading_cost_price, config.backtest.partial_fraction,
        breakeven_after_partial=config.backtest.breakeven_after_partial,
    )
    trades.sort(key=lambda t: (t.entry_index, t.signal_id))

    rows = []
    for t in trades:
        rows.append({
            "pair": symbol, "arm": arm, "stable_id": stable_by_sig.get(t.signal_id, ""),
            "signal_id": t.signal_id, "model": model_by_sig.get(t.signal_id, ""), "direction": t.direction,
            "feeder_ref_available_ts": fmt_ts(ref_avail_by_sig.get(t.signal_id)),
            "activation_instant_ts": fmt_ts(activation_by_sig.get(t.signal_id)),
            "model1_available_ts": fmt_ts(order_placed_by_sig.get(t.signal_id)),
            "order_placed_ts": fmt_ts(order_placed_by_sig.get(t.signal_id)),
            "entry_index": t.entry_index, "entry_timestamp_broker": fmt_idx_ts(m15, t.entry_index),
            "entry_price": t.entry_price, "stop_loss": t.stop_loss, "take_profit": t.take_profit,
            "partial_exit_index": "" if t.partial_exit_index is None else t.partial_exit_index,
            "partial_exit_timestamp_broker": fmt_idx_ts(m15, t.partial_exit_index),
            "partial_exit_price": "" if t.partial_exit_price is None else t.partial_exit_price,
            "partial_r_multiple": "" if t.partial_r_multiple is None else t.partial_r_multiple,
            "exit_index": "" if t.exit_index is None else t.exit_index,
            "exit_timestamp_broker": fmt_idx_ts(m15, t.exit_index),
            "exit_price": "" if t.exit_price is None else t.exit_price,
            "outcome": t.outcome, "r_multiple": "" if t.r_multiple is None else t.r_multiple,
            "ambiguous_bar": t.ambiguous_bar, "gap_filled": t.gap_filled,
        })

    return trades, rows, {
        "candidates_built": len(population.candidates),
        "filled": len(filled), "never_filled": never_filled, "skipped_no_placement": skipped_no_placement,
    }


def year_breakdown(trades, m15):
    by_year = defaultdict(list)
    for t in trades:
        if t.outcome in ("win", "loss") and t.exit_index is not None:
            year = m15.candles[t.exit_index].timestamp.year
            by_year[year].append(t)
    rows = []
    for year in sorted(by_year):
        yt = by_year[year]
        wins = sum(1 for t in yt if t.outcome == "win")
        total_r = sum(t.r_multiple for t in yt)
        rows.append({"year": year, "trades": len(yt), "win_rate": wins / len(yt), "total_r": total_r})
    return rows


def main():
    head_commit = _git("rev-parse", "HEAD")
    all_trade_rows = {"c1": [], "c2": []}
    all_trades_objs = {"c1": {}, "c2": {}}
    per_symbol_stats = {"c1": {}, "c2": {}}
    funnel_rows = []
    year_rows = []
    reconciliation_rows = []

    for symbol in SYMBOLS:
        h4, m15, daily = load_symbol_data(symbol)
        config = DetectorConfig(backtest=SYMBOL_CONFIG[symbol])
        m15_timestamps = [c.timestamp for c in m15.candles]
        ltf_ranges = detect_crt_ranges(m15, config.crt_range)
        swings = detect_swings(m15, config.swing)
        key_levels = build_key_levels(h4, daily, config.fvg)

        for arm, run_fn in (("c1", run_c1), ("c2", run_c2)):
            records_with_ids, counters = run_fn(symbol, h4, m15, daily, config, m15_timestamps, ltf_ranges, swings, key_levels)
            trades, rows, fill_stats = process_arm(symbol, arm, records_with_ids, h4, m15, daily, config, m15_timestamps, swings)
            all_trade_rows[arm] += rows
            all_trades_objs[arm][symbol] = trades
            per_symbol_stats[arm][symbol] = {**trade_stats(trades), "max_drawdown_r": max_drawdown_r(trades, m15)}

            for model_name, c in counters.items():
                funnel_rows.append({
                    "pair": symbol, "arm": arm, "model": model_name,
                    **c.to_dict(), **fill_stats,
                })
            for yr in year_breakdown(trades, m15):
                year_rows.append({"pair": symbol, "arm": arm, **yr})

            for rec, sid in records_with_ids:
                row = {
                    "pair": symbol, "arm": arm, "stable_id": sid, "model": rec.model_name, "direction": rec.direction,
                    "feeder_ref_available_ts": fmt_ts(rec.feeder_ref_available_ts),
                    "activation_instant_ts": fmt_ts(rec.activation_instant_ts),
                    "model1_available_ts": fmt_ts(rec.model1_available_ts),
                    "confirmed": rec.aligned is not None,
                    "zero_signal_reason": rec.zero_signal_reason or "",
                }
                reconciliation_rows.append(row)

        print(f"{symbol} done", flush=True)

    for arm in ("c1", "c2"):
        write_csv(os.path.join(OUT_DIR, f"trades_{arm}.csv"), TRADE_COLUMNS, all_trade_rows[arm])

    funnel_columns = sorted({k for row in funnel_rows for k in row.keys()})
    write_csv(os.path.join(OUT_DIR, "funnel_c1_c2.csv"), funnel_columns, funnel_rows)

    year_columns = sorted({k for row in year_rows for k in row.keys()})
    write_csv(os.path.join(OUT_DIR, "year_breakdown_c1_c2.csv"), year_columns, year_rows)

    recon_columns = sorted({k for row in reconciliation_rows for k in row.keys()})
    write_csv(os.path.join(OUT_DIR, "reconciliation_c1_c2.csv"), recon_columns, reconciliation_rows)

    metrics = {}
    for arm in ("c1", "c2"):
        per_symbol = per_symbol_stats[arm]
        combined_trades = sum(s["trades"] for s in per_symbol.values())
        combined_closed = sum(s["closed"] for s in per_symbol.values())
        combined_total_r = sum(s["total_r"] for s in per_symbol.values())
        combined_wins = sum(round(s["win_rate"] * s["closed"]) for s in per_symbol.values())
        metrics[arm] = {
            "per_symbol": per_symbol,
            "combined": {
                "trades": combined_trades, "closed": combined_closed,
                "win_rate": combined_wins / combined_closed if combined_closed else 0.0,
                "total_r": combined_total_r,
                "avg_r": combined_total_r / combined_closed if combined_closed else 0.0,
                "expectancy_per_trade": combined_total_r / combined_trades if combined_trades else 0.0,
            },
        }
    with open(os.path.join(OUT_DIR, "metrics_c1_c2.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, default=str)

    with open(os.path.join(OUT_DIR, "run_metadata_c1_c2.json"), "w", encoding="utf-8") as f:
        json.dump({"generated_from_commit": head_commit, "symbols": list(SYMBOLS)}, f, indent=2)

    for arm in ("c1", "c2"):
        c = metrics[arm]["combined"]
        print(f"{arm:<4} trades={c['trades']:<6} closed={c['closed']:<6} win_rate={c['win_rate']:.4f} total_r={c['total_r']:+.4f}")

    # Validation point 10: confirm the original baseline (Arm A) was never
    # touched by this run -- read-only check against the already-generated
    # file, no recompute.
    arm_a_path = os.path.join(OUT_DIR, "trades_arm_a.csv")
    with open(arm_a_path, newline="", encoding="utf-8") as f:
        arm_a_rows = list(csv.DictReader(f))
    arm_a_total_r = sum(float(r["r_multiple"]) for r in arm_a_rows if r["r_multiple"] != "")
    arm_a_closed = sum(1 for r in arm_a_rows if r["outcome"] in ("win", "loss"))
    print(f"Arm A baseline check (read-only, not rerun): {len(arm_a_rows)} rows, {arm_a_closed} closed, total_r={arm_a_total_r:+.4f}")
    assert len(arm_a_rows) == 2067 and arm_a_closed == 2060 and abs(arm_a_total_r - 1630.7719) < 0.01, (
        "trades_arm_a.csv has changed since Phase 2 -- it must stay untouched"
    )
    print("Arm A baseline intact.")


if __name__ == "__main__":
    main()
