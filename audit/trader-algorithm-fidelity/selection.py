"""Fixed-seed, outcome-blind pilot selection; internal strata never reach the API.

The no-signal stratum is proved by absence of a reference high/low sweep in
the complete D3/C2 activation window. Without a sweep, the causal trigger
cannot exist, regardless of Key Level or Model-1 state. This does not infer
absence of a signal from absence of a filled trade.
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from engine import M15, complete_bucket, feeder_open_utc, reference_open


SEED = 20261119
PAIRS = ("EURUSD", "USDCAD", "AUDUSD")
MODELS = ("1am", "9am")
TRADE_QUOTAS = {("EURUSD", "1am"): 2, ("EURUSD", "9am"): 2,
                ("USDCAD", "1am"): 1, ("USDCAD", "9am"): 2,
                ("AUDUSD", "1am"): 2, ("AUDUSD", "9am"): 1}
NO_SIGNAL_QUOTAS = {("EURUSD", "1am"): 1, ("EURUSD", "9am"): 2,
                    ("USDCAD", "1am"): 2, ("USDCAD", "9am"): 1,
                    ("AUDUSD", "1am"): 2, ("AUDUSD", "9am"): 2}
SPECIAL = [
    ("EURUSD", "1am", "2013-12-25"),
    ("USDCAD", "9am", "2015-03-09"),
    ("AUDUSD", "1am", "2015-11-02"),
    ("EURUSD", "9am", "2016-03-14"),
    ("USDCAD", "1am", "2016-11-07"),
    ("AUDUSD", "9am", "2017-03-13"),
    ("EURUSD", "1am", "2018-11-05"),
    ("USDCAD", "9am", "2020-03-09"),
    ("AUDUSD", "1am", "2023-11-06"),
    ("EURUSD", "9am", "2024-03-11"),
]


def no_sweep_proven(bars: list[dict], reference_at: datetime, start: datetime, end: datetime) -> bool:
    bars = sorted(bars, key=lambda bar: bar["instant"])
    if not complete_bucket(bars, reference_at):
        return False
    activation = [bar for bar in bars if start <= bar["instant"] < end]
    expected = int((end - start) / M15)
    if len(activation) != expected or any(bar["instant"] != start + i * M15 for i, bar in enumerate(activation)):
        return False
    reference = [bar for bar in bars if reference_at <= bar["instant"] < reference_at + timedelta(hours=4)]
    return all(bar["high"] <= max(ref["high"] for ref in reference) and
               bar["low"] >= min(ref["low"] for ref in reference) for bar in activation)


def _case(pair: str, model: str, day: str, category: str) -> dict:
    identity = f"{pair}|{model}|{day}"
    return {"id": hashlib.sha256(identity.encode()).hexdigest()[:16], "pair": pair,
            "model": model, "date_ny": day, "category": category}


def _trade_candidates(path: Path) -> dict[tuple[str, str], list[str]]:
    grouped = defaultdict(set)
    with path.open("r", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["arm"] != "d3_c2":
                continue
            pair, _, model, opening, _ = row["stable_id"].split("|", 4)
            # 1AM and 9AM NY both open on the same UTC calendar date.
            day = datetime.fromisoformat(opening).date().isoformat()
            grouped[(pair, model)].add(day)
    return {key: sorted(days) for key, days in grouped.items()}


def _bars_for_candidate_dates(path: Path, days: list[date]) -> dict[date, list[dict]]:
    wanted = set()
    for day in days:
        for offset in (-2, -1, 0, 1):
            wanted.add((day + timedelta(days=offset)).strftime("%Y.%m.%d"))
    grouped = defaultdict(list)
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            if row["<DATE>"] not in wanted:
                continue
            instant = datetime.strptime(row["<DATE>"] + " " + row["<TIME>"], "%Y.%m.%d %H:%M:%S")
            grouped[instant.date()].append({"instant": instant, "open": float(row["<OPEN>"]),
                                            "high": float(row["<HIGH>"]), "low": float(row["<LOW>"]),
                                            "close": float(row["<CLOSE>"])})
    return grouped


def generate_manifest(data_paths: dict[str, Path], trade_path: Path) -> list[dict]:
    rng = random.Random(SEED)
    trades = _trade_candidates(trade_path)
    chosen = [_case("EURUSD", "9am", "2015-01-07", "with_trade")]
    used = {("EURUSD", "9am", "2015-01-07")}
    for pair, model in PAIRS_MODELS:
        quota = TRADE_QUOTAS[(pair, model)] - (1 if (pair, model) == ("EURUSD", "9am") else 0)
        options = [day for day in trades.get((pair, model), []) if (pair, model, day) not in used]
        rng.shuffle(options)
        for day in options[:quota]:
            chosen.append(_case(pair, model, day, "with_trade"))
            used.add((pair, model, day))
    if len(chosen) != 10:
        raise RuntimeError("Not enough historical D3/C2 trade sessions")

    specials = [_case(pair, model, day, "boundary_or_gap") for pair, model, day in SPECIAL]
    used.update((case["pair"], case["model"], case["date_ny"]) for case in specials)
    candidate_days = [date(2015, 1, 1) + timedelta(days=offset) for offset in
                      rng.sample(range((date(2026, 1, 1) - date(2015, 1, 1)).days), 180)]
    candidates = []
    for pair in PAIRS:
        grouped = _bars_for_candidate_dates(data_paths[pair], candidate_days)
        for model in MODELS:
            quota = NO_SIGNAL_QUOTAS[(pair, model)]
            count = 0
            for day in candidate_days:
                identity = (pair, model, day.isoformat())
                if identity in used:
                    continue
                opening = feeder_open_utc(day, 1 if model == "1am" else 9)
                start = opening
                end = opening + timedelta(hours=4) if model == "1am" else feeder_open_utc(day, 11)
                case = {"date_ny": day.isoformat(), "model": model}
                ref = reference_open(case)
                relevant = []
                for utc_day in {ref.date(), (ref + timedelta(hours=4)).date(), opening.date(), end.date()}:
                    relevant.extend(grouped.get(utc_day, []))
                if no_sweep_proven(relevant, ref, start, end):
                    candidates.append(_case(pair, model, day.isoformat(), "no_signal"))
                    used.add(identity)
                    count += 1
                    if count == quota:
                        break
            if count != quota:
                raise RuntimeError(f"Insufficient no-sweep sessions for {pair} {model}: {count}/{quota}")
    all_cases = chosen + candidates + specials
    rng.shuffle(all_cases)
    if len(all_cases) != 30 or len({case["id"] for case in all_cases}) != 30:
        raise RuntimeError("Pilot must have 30 unique cases")
    return all_cases


PAIRS_MODELS = tuple((pair, model) for pair in PAIRS for model in MODELS)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    paths = {pair: next((root / "data").glob(f"{pair}_M15_*.csv")) for pair in PAIRS}
    trade_csv = root / "audit/2026-11-17-causal-lookahead-audit/trades_d3_c2_2015plus_run2.csv"
    manifest = Path(__file__).resolve().parent / "pilot_manifest.json"
    with manifest.open("x", encoding="utf-8") as stream:
        json.dump({"seed": SEED, "source": str(trade_csv.relative_to(root)),
                   "cases": generate_manifest(paths, trade_csv)}, stream, indent=2)
        stream.write("\n")
