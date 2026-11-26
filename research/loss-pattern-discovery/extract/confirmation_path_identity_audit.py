"""Phase 10 Unit C: verify that every executed trade in the real
ledger links to its own real confirmation path, using `stable_id`
(this lab's primary key since Phase 1, re-confirmed as the only safe
cross-instrument identifier by Phase 9's `signal_id` collision
investigation) -- never a global join on `signal_id` alone.
"""
from __future__ import annotations

import json
from pathlib import Path

from extract.funnel_reconstruction import SYMBOLS

LAB_ROOT = Path(__file__).resolve().parent.parent


def load_all_symbol_paths(artifacts_dir: Path | None = None) -> dict[str, dict]:
    artifacts_dir = artifacts_dir or (LAB_ROOT / "artifacts")
    merged: dict[str, dict] = {}
    missing_symbols = []
    for symbol in SYMBOLS:
        path = artifacts_dir / f"phase10_confirmation_paths_{symbol}.json"
        if not path.exists():
            missing_symbols.append(symbol)
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for sid, entry in data["paths"].items():
            merged[sid] = entry
    if missing_symbols:
        raise FileNotFoundError(
            f"missing per-symbol path artifacts for {missing_symbols} -- run "
            "`extract/confirmation_path_reconstruction.py <symbol>` for each first."
        )
    return merged


def reconcile_with_ledger(paths_by_sid: dict[str, dict], ledger_records: list) -> dict:
    """Requirement (Unit C): every executed trade links to its real
    confirmation path; duplicates and cross-instrument mixing are
    detected, never assumed absent; the 4 censored (OPEN) trades keep
    their own identity; unreconstructable events are reported, never
    silently dropped."""
    seen: dict[str, int] = {}
    for r in ledger_records:
        seen[r.identification.event_id] = seen.get(r.identification.event_id, 0) + 1
    duplicate_event_ids = sorted(sid for sid, count in seen.items() if count > 1)

    matched, missing_path, cross_instrument_mismatch = [], [], []
    open_trades_matched = []
    for r in ledger_records:
        sid = r.identification.event_id
        instrument = r.identification.instrument
        entry = paths_by_sid.get(sid)
        if entry is None:
            missing_path.append(sid)
            continue
        if entry["symbol"] != instrument or sid.split("|")[0] != instrument:
            cross_instrument_mismatch.append(sid)
            continue
        matched.append(sid)
        if r.operation.outcome.name == "OPEN":
            open_trades_matched.append(sid)

    return {
        "n_ledger": len(ledger_records),
        "n_matched": len(matched),
        "n_missing_path": len(missing_path),
        "missing_path_sids": missing_path,
        "n_cross_instrument_mismatch": len(cross_instrument_mismatch),
        "cross_instrument_mismatch_sids": cross_instrument_mismatch,
        "duplicate_event_ids": duplicate_event_ids,
        "n_open_trades_matched": len(open_trades_matched),
        "open_trade_sids": open_trades_matched,
        "fully_reconciled": (
            not missing_path and not cross_instrument_mismatch and not duplicate_event_ids
        ),
    }
