"""Per-symbol orchestration for the Section 3/4 (13:00-confirmation)
experiment: full 2015+ history, one process per symbol -- the same OOM
workaround used throughout this lab and its sibling.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))
SYMBOLS = ("EURUSD", "USDCAD", "AUDUSD")


def main() -> dict:
    from raza_extract.thirteen_oclock_experiment import build_experiment_for_symbol

    symbol = sys.argv[1] if len(sys.argv) > 1 else None
    if symbol is None or symbol not in SYMBOLS:
        raise SystemExit(f"usage: python build_and_save_thirteen_oclock.py <symbol in {SYMBOLS}>")

    result = build_experiment_for_symbol(symbol)

    artifacts_dir = LAB_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    out_path = artifacts_dir / f"raza_thirteen_oclock_{symbol}.json"
    out_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"symbol": symbol, "n_population": result["n_population"]}, indent=2))
    return result


if __name__ == "__main__":
    main()
