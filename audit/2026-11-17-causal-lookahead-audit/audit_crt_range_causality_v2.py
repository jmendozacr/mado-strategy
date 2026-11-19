"""CRT-range causality audit, v2 -- fixes the attribution bug the v1
script had (reconstructing winning_range via first_breach_index search
instead of reading origin_index directly from signal_id, which breaks
under confirm_in_ltf_window's retry-on-invalidation chain) and adds the
incremental-selection comparison (does the globally-computed ltf_ranges
set change which anchor gets picked, vs. what a causal/incremental
detector would have known at the same instant?).

Read-only: analyzes already-exported trades_c1.csv/trades_c2.csv, scoped
to window_open_ts >= 2015-01-01 per the user's priority. No rerun of the
full pipeline, no production change.
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
SCOPE_START = datetime(2015, 1, 1)


def available_at(idx, m15):
    return m15.candles[idx].timestamp + ci.M15_DURATION


# ---------------------------------------------------------------------------
# Task 1: direct attribution via origin_index (fixes v1's reconstruction bug)
# ---------------------------------------------------------------------------

def find_winning_range_by_origin(ranges_by_start, origin_index):
    """detect_crt_ranges emits AT MOST one CRTRange per start_index (the
    loop appends 0 or 1 per `i`, never more) -- a direct dict lookup is
    therefore exact, unlike v1's first_breach_index reconstruction, which
    silently breaks whenever confirm_in_ltf_window's retry-on-invalidation
    loop re-anchored (same origin_index, a DIFFERENT, later anchor_index
    than the one the winning_range's own first breach would produce)."""
    return ranges_by_start.get(origin_index)


def find_winning_range_by_reconstruction(m15, ltf_ranges_sorted, starts, anchor_index, direction, window_end_idx):
    """v1's (buggy) method, kept here ONLY to measure how often it
    disagrees with the direct attribution -- not used for the final
    classification."""
    lo = bisect.bisect_left(starts, max(0, anchor_index - 40))
    hi = bisect.bisect_right(starts, anchor_index - 1)
    candidates = []
    for r in ltf_ranges_sorted[lo:hi]:
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


# ---------------------------------------------------------------------------
# Task 2: A/B/C/D classification (refines v1's 3-way split)
# ---------------------------------------------------------------------------

def classify_abcd(range_resolved_ts, activation_ts, model1_available_ts):
    if range_resolved_ts <= activation_ts:
        return "A_RESUELTO_ANTES_DE_ACTIVACION"
    if range_resolved_ts <= model1_available_ts:
        return "B_RESUELTO_DESPUES_DE_ACTIVACION_ANTES_DE_MODELO1"
    return "C_RESUELTO_DESPUES_DE_MODELO1"


# ---------------------------------------------------------------------------
# Task 3: does the winning range's own classification (true/false break)
# depend on candles strictly AFTER the sweep/anchor candle itself?
# ---------------------------------------------------------------------------
#
# NOTE on a discarded approach: an earlier version of this check tried to
# re-run candidate selection restricted to ranges whose OWN resolution was
# already available by activation_ts, to see if an "incremental" detector
# would pick a different anchor. That check was WRONG: _resolve() in
# crt_range.py proves resolved_at_index >= first_breach_index ALWAYS (the
# wick-poke/breach must occur before or at the same candle as the candle
# that decides true_break/false_break). Since candidate anchors were only
# searched for at/after activation_ts, and a range can only be a candidate
# if its resolved_at_index is <= activation_ts, the two conditions are
# nearly contradictory by construction -- the restricted search returns
# ~0 candidates almost by definition, regardless of any real causal
# property of the data. That would have been reported as "100% of trades
# would have selected a different anchor causally", which is an artifact
# of the check's own design, not a finding -- discarded before reporting.
#
# The direct, non-tautological way to ask the same question: for the
# winning_range (identified via origin_index, Task 1), is resolved_at_index
# == anchor_index (the break decided on the SAME candle as the sweep --
# only the sweep candle's own close is in question, same magnitude as any
# causally-fine use of `available_at`) or resolved_at_index > anchor_index
# (the range's classification was NOT yet decided at the sweep candle and
# only became knowable on a STRICTLY LATER candle -- a genuine additional
# hindsight dependency, on top of what the A/B/C/D classification already
# shows against activation_ts/model1_available_ts).

def resolution_gap(m15, winning_range, anchor_index):
    gap_bars = winning_range.resolved_at_index - anchor_index
    decided_at_sweep = gap_bars == 0
    return {
        "model": winning_range.model,
        "gap_bars": gap_bars,
        "decided_at_sweep_candle": decided_at_sweep,
        "anchor_available_ts": available_at(anchor_index, m15).isoformat(),
        "resolved_available_ts": available_at(winning_range.resolved_at_index, m15).isoformat(),
    }


def classify_old_method(reconstructed_range, m15, window_end_idx, activation_ts, model1_available_ts):
    """Reproduces v1's own 3-way verdict (CAUSALMENTE_VALIDO / LEVE / ESTRICTA),
    but fed the SAME reconstructed_range v1 itself would have found -- used only
    to measure how much of the old 172-ESTRICTA figure survives when scoped to
    2015+, prior to the origin_index attribution fix."""
    if reconstructed_range is None:
        return "NO_EVALUABLE"
    range_resolved_ts = available_at(reconstructed_range.resolved_at_index, m15)
    if range_resolved_ts <= activation_ts:
        return "CAUSALMENTE_VALIDO"
    if range_resolved_ts <= model1_available_ts:
        return "DEPENDE_RESOLUCION_FUTURA_LEVE"
    return "DEPENDE_RESOLUCION_FUTURA_ESTRICTA"


def classify_trade(row, m15, m15_timestamps, ltf_ranges_sorted, starts, ranges_by_start):
    parts = row["signal_id"].split("-")
    origin_index = int(parts[0])
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
        return None
    window_start_idx, window_end_idx = window

    model1_available_ts = datetime.fromisoformat(row["model1_available_ts"])
    winning_range = find_winning_range_by_origin(ranges_by_start, origin_index)
    reconstructed_range = find_winning_range_by_reconstruction(
        m15, ltf_ranges_sorted, starts, anchor_index, direction, window_end_idx
    )
    attribution_agrees = (
        winning_range is not None and reconstructed_range is not None
        and winning_range.start_index == reconstructed_range.start_index
    )
    old_verdict = classify_old_method(reconstructed_range, m15, window_end_idx, activation_ts, model1_available_ts)

    if winning_range is None:
        return {
            "verdict": "D_NO_EVALUABLE", "attribution_agrees": attribution_agrees, "old_verdict": old_verdict,
            "origin_index": origin_index, "anchor_index": anchor_index,
            "range_resolved_ts": None, "activation_ts": activation_ts,
            "model1_available_ts": row["model1_available_ts"],
            "model": None, "gap_bars": None, "decided_at_sweep_candle": None,
            "anchor_available_ts": None, "resolved_available_ts": None,
        }

    range_resolved_ts = available_at(winning_range.resolved_at_index, m15)
    verdict = classify_abcd(range_resolved_ts, activation_ts, model1_available_ts)
    gap = resolution_gap(m15, winning_range, anchor_index)

    return {
        "verdict": verdict, "attribution_agrees": attribution_agrees, "old_verdict": old_verdict,
        "origin_index": origin_index, "anchor_index": anchor_index,
        "range_resolved_ts": range_resolved_ts.isoformat(), "activation_ts": activation_ts.isoformat(),
        "model1_available_ts": model1_available_ts.isoformat(),
        **gap,
    }


def main():
    symbols = ("EURUSD", "USDCAD", "AUDUSD")
    trades_by_arm = {}
    for arm in ("c1", "c2"):
        with open(f"audit/2026-11-17-causal-lookahead-audit/trades_{arm}.csv", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        # Task 4: scope to window_open_ts >= 2015-01-01
        scoped = [r for r in rows if datetime.fromisoformat(r["stable_id"].split("|")[3]) >= SCOPE_START]
        trades_by_arm[arm] = scoped
        print(f"{arm}: {len(rows)} total trades, {len(scoped)} in-scope (>= 2015-01-01)", flush=True)

    examples_abcd = {"A_RESUELTO_ANTES_DE_ACTIVACION": [], "B_RESUELTO_DESPUES_DE_ACTIVACION_ANTES_DE_MODELO1": [],
                      "C_RESUELTO_DESPUES_DE_MODELO1": [], "D_NO_EVALUABLE": []}
    examples_disagree = []
    examples_resolved_strictly_later = []
    model_counts_overall = {}
    old_verdict_totals = {"CAUSALMENTE_VALIDO": 0, "DEPENDE_RESOLUCION_FUTURA_LEVE": 0,
                           "DEPENDE_RESOLUCION_FUTURA_ESTRICTA": 0, "NO_EVALUABLE": 0}
    crosstab = {}  # (old_verdict, new_verdict) -> count, restricted to attribution disagreements only
    examples_crosstab_flip = []

    for symbol in symbols:
        h4_csv = _find_csv("data", symbol, "H4")
        m15_csv = _find_csv("data", symbol, "M15")
        h4, m15 = load_pair(htf_csv=h4_csv, htf_symbol=symbol, ltf_csv=m15_csv, ltf_symbol=symbol)
        config = DetectorConfig(backtest=SYMBOL_CONFIG[symbol])
        m15_timestamps = [c.timestamp for c in m15.candles]
        ltf_ranges = detect_crt_ranges(m15, config.crt_range)
        ranges_by_start = {r.start_index: r for r in ltf_ranges}
        assert len(ranges_by_start) == len(ltf_ranges), "detect_crt_ranges produced >1 range for some start_index"
        starts = [r.start_index for r in ltf_ranges]  # already sorted (detect_crt_ranges iterates i ascending)
        print(f"{symbol}: {len(ltf_ranges)} ranges, unique-start_index confirmed", flush=True)

        for arm in ("c1", "c2"):
            rows = [r for r in trades_by_arm[arm] if r["pair"] == symbol]
            counts = {k: 0 for k in examples_abcd}
            disagreements = 0
            gap_positive = 0  # resolved strictly AFTER the final sweep/anchor candle -- genuine extra hindsight
            gap_zero = 0      # resolved ON the same candle as the sweep -- no extra hindsight beyond that bar's own close
            gap_negative = 0  # resolved BEFORE the final sweep/anchor candle -- already causally known by then
            evaluated = 0
            for row in rows:
                result = classify_trade(row, m15, m15_timestamps, ltf_ranges, starts, ranges_by_start)
                if result is None:
                    continue
                evaluated += 1
                counts[result["verdict"]] += 1
                if len(examples_abcd[result["verdict"]]) < 3:
                    examples_abcd[result["verdict"]].append((arm, symbol, row["signal_id"], row["model"], result))
                if not result["attribution_agrees"]:
                    disagreements += 1
                    if len(examples_disagree) < 10:
                        examples_disagree.append((arm, symbol, row["signal_id"], result))
                    key = (result["old_verdict"], result["verdict"])
                    crosstab[key] = crosstab.get(key, 0) + 1
                    old_abc = {"CAUSALMENTE_VALIDO": "A", "DEPENDE_RESOLUCION_FUTURA_LEVE": "B",
                               "DEPENDE_RESOLUCION_FUTURA_ESTRICTA": "C", "NO_EVALUABLE": "D"}[result["old_verdict"]]
                    new_abc = result["verdict"][0]
                    if old_abc != new_abc and len(examples_crosstab_flip) < 10:
                        examples_crosstab_flip.append((arm, symbol, row["signal_id"], result))
                old_verdict_totals[result["old_verdict"]] += 1
                if result["model"] is not None:
                    model_counts_overall[result["model"]] = model_counts_overall.get(result["model"], 0) + 1
                gap = result["gap_bars"]
                if gap is None:
                    pass
                elif gap > 0:
                    gap_positive += 1
                    if len(examples_resolved_strictly_later) < 10:
                        examples_resolved_strictly_later.append((arm, symbol, row["signal_id"], row["model"], result))
                elif gap == 0:
                    gap_zero += 1
                else:
                    gap_negative += 1
            print(f"{arm} {symbol}: evaluated={evaluated} {counts} attribution_disagreements={disagreements} "
                  f"gap_positive(resolved_after_sweep)={gap_positive} gap_zero(same_candle)={gap_zero} "
                  f"gap_negative(resolved_before_sweep)={gap_negative}", flush=True)

    print("\n=== OLD METHOD'S OWN 3-WAY VERDICT, SAME 2015+ SCOPE (apples-to-apples vs. the 172-ESTRICTA figure) ===")
    print(old_verdict_totals)
    print("\n=== CROSSTAB (old_verdict, new_verdict) -- ONLY for the attribution-disagreement subset ===")
    for k, v in sorted(crosstab.items(), key=lambda kv: -kv[1]):
        print(k, v)
    print("\n=== EXAMPLES WHERE THE ATTRIBUTION FIX ACTUALLY FLIPS THE A/B/C/D BUCKET ===")
    for e in examples_crosstab_flip:
        print(e)
    print("\n=== ATTRIBUTION DISAGREEMENTS (v1 reconstruction vs. v2 direct origin_index lookup) ===")
    for e in examples_disagree:
        print(e)
    print("\n=== MODEL (resolution shape) DISTRIBUTION ACROSS ALL EVALUATED TRADES ===")
    print(model_counts_overall)
    print("\n=== EXAMPLES: winning range resolved on a candle STRICTLY AFTER the sweep/anchor candle ===")
    for e in examples_resolved_strictly_later:
        print(e)
    print("\n=== EXAMPLES PER A/B/C/D CLASS ===")
    for k, v in examples_abcd.items():
        print(f"--- {k} ---")
        for e in v:
            print(e)


if __name__ == "__main__":
    main()
