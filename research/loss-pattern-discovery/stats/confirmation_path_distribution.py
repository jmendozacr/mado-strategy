"""Phase 10 Deliverable D: describe the confirmation-path distributions
by model, instrument, and period -- BEFORE looking at any E1 result
(execution order step 8, before step 9's baseline reproduction). Reads
only `extract.confirmation_path_identity_audit.load_all_symbol_paths`'s
already-reconstructed, already-equivalence-proven path data; never
touches the ledger or any outcome field.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = LAB_ROOT.parent.parent
for _path in (LAB_ROOT, REPO_ROOT / "detector"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from extract.confirmation_path_identity_audit import load_all_symbol_paths  # noqa: E402
from extract.funnel_reconstruction import PERIOD_BUCKETS, SYMBOLS  # noqa: E402

MODELS = ("1am", "9am")


def _rate(flags: list[bool]) -> float | None:
    return sum(flags) / len(flags) if flags else None


def summarize(paths_by_sid: dict[str, dict]) -> dict:
    by_model = {m: [] for m in MODELS}
    for sid, entry in paths_by_sid.items():
        by_model.setdefault(entry["model"], []).append(entry)

    out: dict = {"models": {}}
    for model in MODELS:
        entries = by_model.get(model, [])
        invalidation_counts = Counter(e["internal_invalidation_count"] for e in entries)
        attempt_counts = Counter(e["confirmation_attempt_count"] for e in entries)
        zero_invalidation = [e["internal_invalidation_count"] == 0 for e in entries]

        by_instrument = {}
        for instrument in SYMBOLS:
            sub = [e for e in entries if e["symbol"] == instrument]
            by_instrument[instrument] = {
                "n": len(sub),
                "share_zero_invalidation": _rate([e["internal_invalidation_count"] == 0 for e in sub]),
            }

        by_period = {}
        for period in PERIOD_BUCKETS:
            sub = [e for e in entries if e["period"] == period]
            by_period[period] = {
                "n": len(sub),
                "share_zero_invalidation": _rate([e["internal_invalidation_count"] == 0 for e in sub]),
            }

        out["models"][model] = {
            "n_total": len(entries),
            "internal_invalidation_count_distribution": dict(sorted(invalidation_counts.items())),
            "confirmation_attempt_count_distribution": dict(sorted(attempt_counts.items())),
            "share_zero_invalidation": _rate(zero_invalidation),
            "share_one_or_more_invalidation": 1 - _rate(zero_invalidation) if zero_invalidation else None,
            "n_zero_invalidation": sum(zero_invalidation),
            "n_one_or_more_invalidation": len(zero_invalidation) - sum(zero_invalidation),
            "by_instrument": by_instrument,
            "by_period": by_period,
        }
    return out


def run() -> dict:
    paths_by_sid = load_all_symbol_paths()
    return summarize(paths_by_sid)


def main() -> dict:
    result = run()
    artifacts_dir = LAB_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    (artifacts_dir / "phase10_confirmation_path_distribution.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8",
    )
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    main()
