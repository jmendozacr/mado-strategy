"""Deliverable A: Event-Level Identity Reconciliation.

Reads `artifacts/phase8_funnel_reconstruction.json` (produced by
`extract/funnel_reconstruction.py` -- run that script first) and compares
its `_reconstructed_identities` (built from the real `_resolve_exits`
function's own `Trade` objects) against the real trades CSV's own
`signal_id`/`entry_index`/`entry_price` columns
(`extract/event_identity_reconciliation.py::read_ledger_identities`, a
dedicated read-only reader, never the shared Phase-1 extractor).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = LAB_ROOT.parent.parent
for _path in (LAB_ROOT, REPO_ROOT / "detector"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from extract.event_identity_reconciliation import (  # noqa: E402
    compare_identities,
    detect_duplicate_signal_ids,
    read_ledger_identities,
)


def load_funnel_reconstruction() -> dict:
    path = LAB_ROOT / "artifacts" / "phase8_funnel_reconstruction.json"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found -- run extract/funnel_reconstruction.py first")
    return json.loads(path.read_text(encoding="utf-8"))


def run() -> dict:
    funnel_result = load_funnel_reconstruction()
    reconstructed = funnel_result["_reconstructed_identities"]
    ledger = read_ledger_identities(REPO_ROOT)

    comparison = compare_identities(reconstructed, ledger)
    duplicate_signal_ids_in_ledger = detect_duplicate_signal_ids(ledger)
    duplicate_signal_ids_in_reconstruction = detect_duplicate_signal_ids(reconstructed)

    return {
        "comparison": comparison,
        "duplicate_signal_ids_in_ledger": duplicate_signal_ids_in_ledger,
        "duplicate_signal_ids_in_reconstruction": duplicate_signal_ids_in_reconstruction,
        "validated_event_by_event": (
            comparison["fully_matched"]
            and not duplicate_signal_ids_in_ledger
            and not duplicate_signal_ids_in_reconstruction
        ),
    }


def main() -> dict:
    result = run()
    artifacts_dir = LAB_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    (artifacts_dir / "phase9_event_identity_reconciliation.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(
        {
            "n_reconstructed": result["comparison"]["n_reconstructed"],
            "n_ledger": result["comparison"]["n_ledger"],
            "n_both": result["comparison"]["n_both"],
            "n_only_in_ledger": len(result["comparison"]["only_in_ledger"]),
            "n_only_in_reconstruction": len(result["comparison"]["only_in_reconstruction"]),
            "n_field_mismatches": len(result["comparison"]["field_mismatches"]),
            "duplicate_signal_ids_in_ledger": result["duplicate_signal_ids_in_ledger"],
            "validated_event_by_event": result["validated_event_by_event"],
        },
        indent=2, default=str,
    ))
    return result


if __name__ == "__main__":
    main()
