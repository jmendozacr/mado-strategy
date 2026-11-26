"""Per-symbol orchestration: run `build_funnel_for_symbol` for the full
2015+ history and save a JSON artifact. One process per symbol -- the
same OS-level OOM workaround Phases 9/10 documented for the sibling
lab's own equivalent full-history runs.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))
SYMBOLS = ("EURUSD", "USDCAD", "AUDUSD")


def main() -> dict:
    from raza_extract.reference_candle_classification import build_funnel_for_symbol

    symbol = sys.argv[1] if len(sys.argv) > 1 else None
    if symbol is None or symbol not in SYMBOLS:
        raise SystemExit(f"usage: python -m raza_extract.build_and_save <symbol in {SYMBOLS}>")

    result = build_funnel_for_symbol(symbol)

    classifications = {sid: asdict(c) for sid, c in result["classifications"].items()}
    for c in classifications.values():
        c["current_open_ts"] = c["current_open_ts"].isoformat()
        c["h4_close_available_ts"] = c["h4_close_available_ts"].isoformat()

    executed = {
        sid: {
            "signal_id": t.signal_id, "direction": t.direction,
            "entry_index": t.entry_index, "entry_price": t.entry_price,
        }
        for sid, t in result["executed_by_sid"].items()
    }

    out = {
        "symbol": symbol,
        "n_triggers": result["n_triggers"],
        "classifications": classifications,
        "confirmed_sids": sorted(result["confirmed_sids"]),
        "candidate_sids": sorted(result["candidate_sids"]),
        "filled_sids": sorted(result["filled_sids"]),
        "executed": executed,
    }

    artifacts_dir = LAB_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    out_path = artifacts_dir / f"raza_9am_classification_{symbol}.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(
        {"symbol": symbol, "n_triggers": out["n_triggers"], "n_confirmed": len(out["confirmed_sids"]),
         "n_candidates": len(out["candidate_sids"]), "n_filled": len(out["filled_sids"]),
         "n_executed": len(out["executed"])},
        indent=2,
    ))
    return out


if __name__ == "__main__":
    main()
