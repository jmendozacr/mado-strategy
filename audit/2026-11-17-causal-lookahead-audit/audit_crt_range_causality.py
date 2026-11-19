"""Offline, targeted audit: does confirm_in_ltf_window's candidate-range
selection (via CRTRange.resolved_at_index) ever use a CRT range whose
resolution was not yet knowable at the real-time instant it mattered?
Reuses detect_crt_ranges/first_breach_index/confirmation_window_utc/
ltf_window_indices/available_at UNMODIFIED. Read-only: analyzes already-
exported trades_c1.csv/trades_c2.csv, no full rerun, no production change.
"""
import bisect
import csv
import sys
from datetime import datetime

sys.path.insert(0, "detector")
sys.path.insert(0, "audit/2026-11-17-causal-lookahead-audit")

from causal.htf_trigger import MODEL_1AM, MODEL_9AM, confirmation_window_utc, ltf_window_indices
from core.config import DetectorConfig
from experimental.htf_trigger_1am_9am_backtest import SYMBOL_CONFIG, _find_csv
from ingestion.pairing import load_pair
from primitives.crt_range import detect_crt_ranges, first_breach_index

import causal_intrabar as ci

MODEL_BY_NAME = {"1am": MODEL_1AM, "9am": MODEL_9AM}


def available_at(idx, m15):
    return m15.candles[idx].timestamp + ci.M15_DURATION


def find_winning_range(m15, ltf_ranges, anchor_index, direction, window_end_idx):
    candidates = []
    for r in ltf_ranges:
        resolved_at = min(r.resolved_at_index, window_end_idx)
        if r.start_index >= resolved_at:
            continue
        found = (
            first_breach_index(m15.candles, r.start_index, resolved_at, high=r.high)
            if direction == "bearish"
            else first_breach_index(m15.candles, r.start_index, resolved_at, low=r.low)
        )
        if found == anchor_index:
            candidates.append(r)
    if not candidates:
        return None
    return min(candidates, key=lambda r: r.start_index)


def classify_trade(row, m15, m15_timestamps, ltf_ranges):
    parts = row["signal_id"].split("-")
    anchor_index = int(parts[1])
    direction = row["direction"]
    model = MODEL_BY_NAME[row["model"]]
    window_open_ts = datetime.fromisoformat(row["stable_id"].split("|")[3])
    window_start, window_end = confirmation_window_utc(
        type("P", (), {"timestamp": window_open_ts})(), model
    )
    activation_ts = datetime.fromisoformat(row["activation_instant_ts"])
    eligible_start = max(window_start, activation_ts)
    window = ltf_window_indices(m15.candles, eligible_start, window_end)
    if window is None:
        return "NO_EVALUABLE", None, None, None
    _start_idx, end_idx = window

    winning_range = find_winning_range(m15, ltf_ranges, anchor_index, direction, end_idx)
    if winning_range is None:
        return "NO_EVALUABLE", None, None, None

    range_resolved_at_ts = available_at(winning_range.resolved_at_index, m15)
    model1_available_ts = datetime.fromisoformat(row["model1_available_ts"])

    if range_resolved_at_ts <= activation_ts:
        verdict = "CAUSALMENTE_VALIDO"
    elif range_resolved_at_ts <= model1_available_ts:
        verdict = "DEPENDE_RESOLUCION_FUTURA_LEVE"  # after activation search start, but before order could place
    else:
        verdict = "DEPENDE_RESOLUCION_FUTURA_ESTRICTA"  # resolution known only AFTER the order could already place
    return verdict, winning_range, range_resolved_at_ts, model1_available_ts


def main():
    symbols = ("EURUSD", "USDCAD", "AUDUSD")
    examples = []
    totals = {}
    trades_by_arm = {}
    for arm in ("c1", "c2"):
        with open(f"audit/2026-11-17-causal-lookahead-audit/trades_{arm}.csv", newline="", encoding="utf-8") as f:
            trades_by_arm[arm] = list(csv.DictReader(f))

    for symbol in symbols:
        h4_csv = _find_csv("data", symbol, "H4")
        m15_csv = _find_csv("data", symbol, "M15")
        h4, m15 = load_pair(htf_csv=h4_csv, htf_symbol=symbol, ltf_csv=m15_csv, ltf_symbol=symbol)
        config = DetectorConfig(backtest=SYMBOL_CONFIG[symbol])
        m15_timestamps = [c.timestamp for c in m15.candles]
        ltf_ranges = detect_crt_ranges(m15, config.crt_range)
        print(f"{symbol}: ltf_ranges computed ({len(ltf_ranges)} ranges)", flush=True)

        for arm in ("c1", "c2"):
            rows = [r for r in trades_by_arm[arm] if r["pair"] == symbol]
            counts = {"CAUSALMENTE_VALIDO": 0, "DEPENDE_RESOLUCION_FUTURA_LEVE": 0,
                      "DEPENDE_RESOLUCION_FUTURA_ESTRICTA": 0, "NO_EVALUABLE": 0}
            for row in rows:
                verdict, winning_range, range_ts, model1_ts = classify_trade(row, m15, m15_timestamps, ltf_ranges)
                counts[verdict] += 1
                if verdict != "CAUSALMENTE_VALIDO" and len(examples) < 20:
                    examples.append((arm, symbol, row["signal_id"], row["model"], row["direction"], verdict,
                                      str(range_ts), row["model1_available_ts"],
                                      winning_range.start_index if winning_range else None,
                                      winning_range.resolved_at_index if winning_range else None))
            totals[(arm, symbol)] = (len(rows), counts)
            print(f"{arm} {symbol}: total={len(rows)} {counts}", flush=True)

    print("\n=== EXAMPLES (non-valid or non-evaluable) ===")
    for e in examples:
        print(e)


if __name__ == "__main__":
    main()
