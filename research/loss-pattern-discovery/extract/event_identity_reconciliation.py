"""Phase 9 Unit A: event-level identity reconciliation.

Reads `signal_id`/`entry_index`/`entry_price` directly from the real
trades CSV -- fields the lab's own `extract/from_causal_lookahead_audit.py`
extractor (Phase 1) never carries onto `EventRecord` (it only keeps
`stable_id` as `event_id`). This is a SEPARATE, read-only reader, kept
isolated from that extractor rather than changing its output shape for
every prior phase that already depends on it.
"""
from __future__ import annotations

import csv
from pathlib import Path

SOURCE_RELATIVE_PATH = "audit/2026-11-17-causal-lookahead-audit/trades_d3_c2_2015plus_run2.csv"


def read_ledger_identities(repo_root: Path) -> dict[str, dict]:
    path = repo_root / SOURCE_RELATIVE_PATH
    if not path.exists():
        raise FileNotFoundError(f"expected read-only source at {path}")
    out: dict[str, dict] = {}
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            out[row["stable_id"]] = {
                "signal_id": row["signal_id"], "pair": row["pair"], "model": row["model"],
                "direction": row["direction"], "entry_index": int(row["entry_index"]),
                "entry_price": float(row["entry_price"]),
            }
    return out


def compare_identities(reconstructed: dict[str, dict], ledger: dict[str, dict]) -> dict:
    """Never claims event-level validation if any set difference or field
    mismatch exists -- `fully_matched` is the single authoritative gate
    callers must check before saying "validated event by event."""
    recon_ids = set(reconstructed.keys())
    ledger_ids = set(ledger.keys())
    only_in_ledger = sorted(ledger_ids - recon_ids)
    only_in_reconstruction = sorted(recon_ids - ledger_ids)
    both = recon_ids & ledger_ids

    field_mismatches = []
    uncomparable_fields = set()
    for stable_id in sorted(both):
        r, l = reconstructed[stable_id], ledger[stable_id]
        mismatched = [f for f in ("signal_id", "pair", "model", "direction", "entry_index") if r.get(f) != l.get(f)]
        r_price, l_price = r.get("entry_price"), l.get("entry_price")
        if r_price is None or l_price is None:
            uncomparable_fields.add("entry_price")
        elif abs(r_price - l_price) > 1e-9:
            mismatched.append("entry_price")
        if mismatched:
            field_mismatches.append({"stable_id": stable_id, "fields": mismatched})

    return {
        "n_reconstructed": len(recon_ids), "n_ledger": len(ledger_ids), "n_both": len(both),
        "only_in_ledger": only_in_ledger, "only_in_reconstruction": only_in_reconstruction,
        "field_mismatches": field_mismatches,
        "uncomparable_fields": sorted(uncomparable_fields),
        "fully_matched": (
            not only_in_ledger and not only_in_reconstruction and not field_mismatches
            and not uncomparable_fields
        ),
    }


def detect_duplicate_signal_ids(ledger: dict[str, dict]) -> list[str]:
    seen: dict[str, int] = {}
    for row in ledger.values():
        sid = row["signal_id"]
        seen[sid] = seen.get(sid, 0) + 1
    return sorted(sid for sid, count in seen.items() if count > 1)
