"""Deliverables B/C/D: Model-Specific Funnel Reconstruction, Identity &
Cardinality Audit, Funnel Conversion Report.

Reads `artifacts/phase8_funnel_reconstruction.json` (produced by
`extract/funnel_reconstruction.py` -- run that script first) and
cross-reconciles it against the real executed-trade ledger. Never
recomputes the heavy detection pipeline itself -- this module is pure
reporting over already-reconstructed, already-cross-checked counts.
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

from eligibility.stop_eligibility import classify_all  # noqa: E402
from eligibility.stop_timing_decomposition import TimingCategory, classify_all_timing  # noqa: E402
from extract.from_causal_lookahead_audit import extract  # noqa: E402
from schema.events import EventRecord, Outcome  # noqa: E402
from stats.early_stop_hypothesis import build_primary_population, unadjusted_gap  # noqa: E402
from stats.model_population_audit import load_all_series  # noqa: E402

INSTRUMENTS = ("EURUSD", "USDCAD", "AUDUSD")
MODELS = ("1am", "9am")
EXPECTED_BASELINE = {
    "1am": {"executed": 620, "evaluable": 619, "open": 1},
    "9am": {"executed": 1427, "evaluable": 1424, "open": 3},
}


def load_funnel_reconstruction() -> dict:
    path = LAB_ROOT / "artifacts" / "phase8_funnel_reconstruction.json"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found -- run `extract/funnel_reconstruction.py` first; this report "
            "never re-runs that heavy pipeline itself."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _ledger_counts_by_model_and_instrument(records: list[EventRecord]) -> dict:
    """Requirement 8: a record whose model/instrument falls outside this
    phase's known sets is never silently dropped from the loop -- it is
    collected into `unresolved` and reported explicitly (empty list in
    the normal, fully-reconciled case)."""
    out = {m: {i: {"executed": 0, "open": 0, "evaluable": 0} for i in INSTRUMENTS} for m in MODELS}
    unresolved: list[str] = []
    for r in records:
        model = r.identification.session_label
        instrument = r.identification.instrument
        if model not in out or instrument not in out[model]:
            unresolved.append(r.identification.event_id)
            continue
        out[model][instrument]["executed"] += 1
        if r.operation.outcome is Outcome.OPEN:
            out[model][instrument]["open"] += 1
        else:
            out[model][instrument]["evaluable"] += 1
    return {"counts": out, "unresolved_event_ids": unresolved}


def detect_duplicate_event_ids(records: list[EventRecord]) -> list[str]:
    """Requirement 7: never assume `event_id` is unique -- count and
    report any value seen more than once, instead of silently trusting
    it as a primary key."""
    seen: dict[str, int] = {}
    for r in records:
        event_id = r.identification.event_id
        seen[event_id] = seen.get(event_id, 0) + 1
    return sorted(event_id for event_id, count in seen.items() if count > 1)


def build_reconciliation_table(funnel_result: dict, records: list[EventRecord]) -> dict:
    duplicate_event_ids = detect_duplicate_event_ids(records)
    ledger_resolution = _ledger_counts_by_model_and_instrument(records)
    ledger_counts = ledger_resolution["counts"]

    rows = {}
    for instrument in INSTRUMENTS:
        splits = funnel_result[instrument]["splits"]
        for model in MODELS:
            reconstructed_filled = splits[model]["filled"]
            ledger = ledger_counts[model][instrument]
            rows[f"{model}_{instrument}"] = {
                "reconstructed_candidates_built": splits[model]["candidates_built"],
                "reconstructed_filled": reconstructed_filled,
                "reconstructed_never_filled": splits[model]["never_filled"],
                "reconstructed_skipped_no_placement": splits[model]["skipped_no_placement"],
                "ledger_executed": ledger["executed"],
                "ledger_evaluable": ledger["evaluable"],
                "ledger_open": ledger["open"],
                "filled_matches_ledger_executed": reconstructed_filled == ledger["executed"],
            }

    sum_by_model = {
        model: {
            k: sum(rows[f"{model}_{i}"][k] for i in INSTRUMENTS)
            for k in ("reconstructed_filled", "ledger_executed", "ledger_evaluable", "ledger_open")
        }
        for model in MODELS
    }
    total_executed = sum(sum_by_model[m]["ledger_executed"] for m in MODELS)
    total_evaluable = sum(sum_by_model[m]["ledger_evaluable"] for m in MODELS)
    total_open = sum(sum_by_model[m]["ledger_open"] for m in MODELS)

    baseline_check = {
        model: {
            "expected": EXPECTED_BASELINE[model],
            "observed": {
                "executed": sum_by_model[model]["ledger_executed"],
                "evaluable": sum_by_model[model]["ledger_evaluable"],
                "open": sum_by_model[model]["ledger_open"],
            },
            "matches": (
                sum_by_model[model]["ledger_executed"] == EXPECTED_BASELINE[model]["executed"]
                and sum_by_model[model]["ledger_evaluable"] == EXPECTED_BASELINE[model]["evaluable"]
                and sum_by_model[model]["ledger_open"] == EXPECTED_BASELINE[model]["open"]
            ),
        }
        for model in MODELS
    }

    return {
        "rows": rows, "sum_by_model": sum_by_model,
        "total_executed": total_executed, "total_evaluable": total_evaluable, "total_open": total_open,
        "baseline_check": baseline_check,
        "all_filled_match_ledger": all(rows[k]["filled_matches_ledger_executed"] for k in rows),
        "duplicate_event_ids": duplicate_event_ids,
        "unresolved_event_ids": ledger_resolution["unresolved_event_ids"],
        "fully_reconciled": (
            not duplicate_event_ids and not ledger_resolution["unresolved_event_ids"]
            and all(rows[k]["filled_matches_ledger_executed"] for k in rows)
        ),
    }


def e1_reconciliation(records: list[EventRecord], series_by_instrument: dict) -> dict:
    """Re-run Phase 6/7's own E1 endpoint on the exact same primary
    population -- must reproduce 72/619 and 89/1424 exactly."""
    timing_by_id = classify_all_timing(records, series_by_instrument)
    primary = build_primary_population(records)
    flags = {
        r.identification.event_id: timing_by_id[r.identification.event_id].category is TimingCategory.NEXT_BAR_SL
        for r in primary
    }
    records_by_model = {}
    for r in primary:
        records_by_model.setdefault(r.identification.session_label, []).append(r)
    return unadjusted_gap(records_by_model, flags)


def e0_e4_reconciliation(records: list[EventRecord], series_by_instrument: dict) -> dict:
    timing_by_id = classify_all_timing(records, series_by_instrument)
    primary = build_primary_population(records)
    counts = {m: {c.value: 0 for c in TimingCategory} for m in MODELS}
    for r in primary:
        model = r.identification.session_label
        if model in counts:
            counts[model][timing_by_id[r.identification.event_id].category.value] += 1
    return counts


def run() -> dict:
    funnel_result = load_funnel_reconstruction()
    records = extract(REPO_ROOT)
    series_by_instrument = load_all_series()
    classify_all(records)

    reconciliation = build_reconciliation_table(funnel_result, records)
    e1 = e1_reconciliation(records, series_by_instrument)
    e_buckets = e0_e4_reconciliation(records, series_by_instrument)

    return {"reconciliation": reconciliation, "e1_endpoint": e1, "e0_e4_buckets": e_buckets}


def main() -> dict:
    result = run()
    artifacts_dir = LAB_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    (artifacts_dir / "phase8_funnel_reconciliation.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(
        {
            "baseline_check": result["reconciliation"]["baseline_check"],
            "all_filled_match_ledger": result["reconciliation"]["all_filled_match_ledger"],
            "fully_reconciled": result["reconciliation"]["fully_reconciled"],
            "duplicate_event_ids": result["reconciliation"]["duplicate_event_ids"],
            "unresolved_event_ids": result["reconciliation"]["unresolved_event_ids"],
            "e1_endpoint": result["e1_endpoint"],
        },
        indent=2, default=str,
    ))
    return result


if __name__ == "__main__":
    main()
