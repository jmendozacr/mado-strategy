"""Comparison report: funnel/outcome aggregation for the new H4 FVG +
Model-1 variant, plus a session-level comparison against the original
D3/C2 9AM population on the same instruments/dates.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

LAB_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = LAB_ROOT.parent.parent
DETECTOR_ROOT = REPO_ROOT / "detector"
LPD_ROOT = REPO_ROOT / "research" / "loss-pattern-discovery"
for _path in (DETECTOR_ROOT, LPD_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from extract.from_causal_lookahead_audit import extract as extract_ledger  # noqa: E402
from extract.model1_rejection_diagnostics import _window_open_ts_from_stable_id  # noqa: E402

SYMBOLS = ("EURUSD", "USDCAD", "AUDUSD")
QUALIFYING_OUTCOMES = (
    "ENTERED", "DISCARD_SWEPT_EXTREME_BREACH", "DISCARD_TARGET_BEFORE_ENTRY",
    "EXPIRED", "RR_FLOOR_REJECTED", "UNFILLED_ORDER",
)
_UTC = ZoneInfo("UTC")
_NY = ZoneInfo("America/New_York")


def load_all_sessions() -> dict[str, dict]:
    merged = {}
    missing = []
    for symbol in SYMBOLS:
        path = LAB_ROOT / "artifacts" / f"h4fvg_sessions_{symbol}.json"
        if not path.exists():
            missing.append(symbol)
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for day_key, record in data["sessions"].items():
            merged[(symbol, day_key)] = record
    if missing:
        raise FileNotFoundError(f"missing session artifacts for {missing}")
    return merged


def outcome_funnel(sessions: dict) -> dict:
    counts = Counter(r["outcome"] for r in sessions.values())
    n_total = len(sessions)
    n_qualifying = sum(counts[o] for o in QUALIFYING_OUTCOMES)
    return {
        "n_total_sessions": n_total,
        "n_qualifying_h4_setup": n_qualifying,
        "counts": dict(counts),
        "n_entered": counts.get("ENTERED", 0),
    }


def outcome_funnel_by_instrument(sessions: dict) -> dict:
    out = {}
    for symbol in SYMBOLS:
        sub = {k: v for k, v in sessions.items() if k[0] == symbol}
        out[symbol] = outcome_funnel(sub)
    return out


def net_r_per_qualifying_setup(sessions: dict) -> dict:
    qualifying = [r for r in sessions.values() if r["outcome"] in QUALIFYING_OUTCOMES]
    rs = [r.get("r_multiple") if r["outcome"] == "ENTERED" and r.get("r_multiple") is not None else 0.0 for r in qualifying]
    entered_rs = [r["r_multiple"] for r in qualifying if r["outcome"] == "ENTERED" and r.get("r_multiple") is not None]
    return {
        "n_qualifying": len(qualifying),
        "n_entered_with_r": len(entered_rs),
        "mean_net_r_per_qualifying_setup": (sum(rs) / len(rs)) if rs else None,
        "total_net_r": sum(rs),
        "entered_r_values": sorted(entered_rs),
    }


def _d3c2_executed_dates_by_instrument() -> dict[str, set[str]]:
    """Every (instrument, NY date) on which the ORIGINAL D3/C2 9AM model
    produced an executed trade -- the NY date is recovered from each
    trade's own `stable_id` (the SAME `window_open_ts` this lab has
    used as the trigger's own identity since Phase 8), never guessed
    from `entry_ts` (which can fall on a different calendar day)."""
    ledger = extract_ledger(REPO_ROOT)
    out: dict[str, set[str]] = {s: set() for s in SYMBOLS}
    for r in ledger:
        if r.identification.session_label != "9am":
            continue
        instrument = r.identification.instrument
        if instrument not in out:
            continue
        window_open_ts = _window_open_ts_from_stable_id(r.identification.event_id)
        ny_date = window_open_ts.replace(tzinfo=_UTC).astimezone(_NY).date()
        out[instrument].add(ny_date.isoformat())
    return out


def compare_with_d3c2(sessions: dict) -> dict:
    d3c2_dates = _d3c2_executed_dates_by_instrument()
    out = {}
    both = only_variant = only_d3c2 = neither = 0
    for symbol in SYMBOLS:
        symbol_both = symbol_only_variant = symbol_only_d3c2 = symbol_neither = 0
        for (sym, day_key), record in sessions.items():
            if sym != symbol:
                continue
            variant_executed = record["outcome"] == "ENTERED"
            d3c2_executed = day_key in d3c2_dates[symbol]
            if variant_executed and d3c2_executed:
                symbol_both += 1
            elif variant_executed and not d3c2_executed:
                symbol_only_variant += 1
            elif d3c2_executed and not variant_executed:
                symbol_only_d3c2 += 1
            else:
                symbol_neither += 1
        out[symbol] = {
            "both": symbol_both, "only_variant": symbol_only_variant,
            "only_d3c2": symbol_only_d3c2, "neither": symbol_neither,
            "n_d3c2_executed_dates": len(d3c2_dates[symbol]),
        }
        both += symbol_both
        only_variant += symbol_only_variant
        only_d3c2 += symbol_only_d3c2
        neither += symbol_neither
    out["pooled"] = {
        "both": both, "only_variant": only_variant, "only_d3c2": only_d3c2, "neither": neither,
        "n_d3c2_executed_dates_pooled": sum(len(v) for v in d3c2_dates.values()),
    }
    return out


def run() -> dict:
    sessions = load_all_sessions()
    return {
        "funnel_pooled": outcome_funnel(sessions),
        "funnel_by_instrument": outcome_funnel_by_instrument(sessions),
        "net_r_pooled": net_r_per_qualifying_setup(sessions),
        "net_r_by_instrument": {
            s: net_r_per_qualifying_setup({k: v for k, v in sessions.items() if k[0] == s}) for s in SYMBOLS
        },
        "comparison_with_d3c2": compare_with_d3c2(sessions),
    }


def main() -> dict:
    result = run()
    artifacts_dir = LAB_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    (artifacts_dir / "h4fvg_report.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(json.dumps(result, indent=2, default=str))
    return result


if __name__ == "__main__":
    main()
