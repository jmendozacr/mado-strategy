"""Phase 10 Unit B orchestration: reconstruct confirmation paths for
every CONFIRMED D3/C2 signal, across the full 2015+ history, one
symbol at a time (the same per-process split Phase 9 used to avoid an
OS-level OOM kill when all three symbols run in one process --
`docs/78`'s commit record cites the same workaround).

Reuses `extract.funnel_reconstruction`'s own `_load_symbol_data`/
`SYMBOLS`/`WINDOWS_9AM`/`ARM_NAME`/`START_DATE` and
`extract.confirmation_path_diagnostics.run_d_c2_with_confirmation_paths`
unmodified -- this module only adds JSON-serializable bookkeeping
around their already-verified outputs (requirement: never recompute
the heavy pipeline a second time for the same symbol; never touch
`audit/2026-11-17-causal-lookahead-audit/` or its CSVs).
"""
from __future__ import annotations

import sys
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = LAB_ROOT.parent.parent
DETECTOR_ROOT = REPO_ROOT / "detector"
AUDIT_ROOT = REPO_ROOT / "audit" / "2026-11-17-causal-lookahead-audit"
for _path in (LAB_ROOT, DETECTOR_ROOT, AUDIT_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import causal_intrabar as ci  # noqa: E402
from causal_lib import build_key_levels  # noqa: E402
from core.config import DetectorConfig  # noqa: E402
from experimental.htf_trigger_1am_9am_backtest import SYMBOL_CONFIG  # noqa: E402
from primitives.swing import detect_swings  # noqa: E402

from control.sampling import period_bucket  # noqa: E402
from extract.confirmation_path_diagnostics import run_d_c2_with_confirmation_paths  # noqa: E402
from extract.funnel_reconstruction import (  # noqa: E402
    ARM_NAME, START_DATE, SYMBOLS, WINDOWS_9AM, _load_symbol_data,
)


def reconstruct_paths_for_symbol(symbol: str, start_date=START_DATE, end_date=None) -> dict:
    h4, m15, daily = _load_symbol_data(symbol)
    config = DetectorConfig(backtest=SYMBOL_CONFIG[symbol])
    m15_timestamps = [c.timestamp for c in m15.candles]
    detect_swings(m15, config.swing)  # same call order as funnel_reconstruction.py; result not needed here
    key_levels = build_key_levels(h4, daily, config.fvg)

    records_with_ids, counters, paths = run_d_c2_with_confirmation_paths(
        symbol, h4, m15, daily, config, m15_timestamps, key_levels,
        WINDOWS_9AM, ARM_NAME, start_date=start_date, end_date=end_date,
    )

    confirmed_sids = {sid for record, sid in records_with_ids if record.aligned is not None}
    reconstructed, unreconstructed = {}, []
    for sid in confirmed_sids:
        path = paths.get(sid)
        window_open_ts = _window_open_ts_from_stable_id(sid)
        if path is None or path.terminal_signal is None:
            unreconstructed.append(sid)
            continue
        model_name = sid.split("|")[2]
        reconstructed[sid] = {
            "symbol": symbol,
            "model": model_name,
            "period": period_bucket(window_open_ts),
            "internal_invalidation_count": path.internal_invalidation_count,
            "confirmation_attempt_count": path.confirmation_attempt_count,
            "first_anchor_at": ci.available_at(m15.candles[path.first_anchor_index], ci.M15_DURATION).isoformat(),
            "final_anchor_at": ci.available_at(m15.candles[path.final_anchor_index], ci.M15_DURATION).isoformat(),
        }

    return {
        "symbol": symbol,
        "n_confirmed": len(confirmed_sids),
        "n_reconstructed": len(reconstructed),
        "n_unreconstructed": len(unreconstructed),
        "unreconstructed_sids": sorted(unreconstructed),
        "paths": reconstructed,
    }


def _window_open_ts_from_stable_id(sid: str):
    from extract.model1_rejection_diagnostics import _window_open_ts_from_stable_id as _fn

    return _fn(sid)


def main() -> dict:
    import json

    symbol = sys.argv[1] if len(sys.argv) > 1 else None
    if symbol is None or symbol not in SYMBOLS:
        raise SystemExit(f"usage: python confirmation_path_reconstruction.py <symbol in {SYMBOLS}>")
    result = reconstruct_paths_for_symbol(symbol)
    artifacts_dir = LAB_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    out_path = artifacts_dir / f"phase10_confirmation_paths_{symbol}.json"
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(
        {"symbol": symbol, "n_confirmed": result["n_confirmed"],
         "n_reconstructed": result["n_reconstructed"], "n_unreconstructed": result["n_unreconstructed"]},
        indent=2,
    ))
    return result


if __name__ == "__main__":
    main()
