"""Deliverable C: Intrabar Uncertainty Report.

Classifies every confirmed-stop event's intrabar execution-order
uncertainty (`eligibility.intrabar_ambiguity`) and reports counts/proportions
by model, scoped to E0 (same-bar) events specifically -- E1/E2 have no
entry-vs-stop same-bar ambiguity by construction (see docs/37 section 3).
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

from eligibility.intrabar_ambiguity import classify_all_intrabar_uncertainty  # noqa: E402
from eligibility.stop_timing_decomposition import TimingCategory, classify_all_timing  # noqa: E402
from extract.from_causal_lookahead_audit import extract  # noqa: E402
from schema.events import EventRecord  # noqa: E402
from stats.early_stop_hypothesis import build_primary_population  # noqa: E402
from stats.model_population_audit import load_all_series  # noqa: E402


def summarize_e0(records: list[EventRecord], timing_by_id: dict, uncertainty_by_id: dict) -> dict:
    by_model: dict[str, dict] = {}
    for r in records:
        event_id = r.identification.event_id
        if timing_by_id[event_id].category is not TimingCategory.SAME_BAR_SL:
            continue
        model = r.identification.session_label
        row = by_model.setdefault(model, {
            "n_e0": 0, "n_sequence_verifiable": 0, "n_not_verifiable": 0,
            "n_same_bar_multi_level_ambiguity": 0, "n_insufficient_evidence": 0,
        })
        u = uncertainty_by_id[event_id]
        row["n_e0"] += 1
        if u.insufficient_evidence:
            row["n_insufficient_evidence"] += 1
        elif u.sequence_verifiable:
            row["n_sequence_verifiable"] += 1
        else:
            row["n_not_verifiable"] += 1
        if u.same_bar_multi_level_ambiguity:
            row["n_same_bar_multi_level_ambiguity"] += 1

    for row in by_model.values():
        n = row["n_e0"]
        row["pct_sequence_verifiable"] = row["n_sequence_verifiable"] / n if n else None
        row["pct_not_verifiable"] = row["n_not_verifiable"] / n if n else None
    return by_model


def summarize_gap_affected(records: list[EventRecord], timing_by_id: dict, uncertainty_by_id: dict) -> dict:
    """E1/E2 gap_filled proportion by model -- category D, reported
    separately from category B/A (which apply only to E0)."""
    by_model: dict[str, dict] = {}
    for r in records:
        event_id = r.identification.event_id
        category = timing_by_id[event_id].category
        if category not in (TimingCategory.NEXT_BAR_SL, TimingCategory.LATER_SL):
            continue
        model = r.identification.session_label
        row = by_model.setdefault(model, {"n": 0, "n_gap_affected": 0})
        row["n"] += 1
        if uncertainty_by_id[event_id].gap_affected:
            row["n_gap_affected"] += 1
    for row in by_model.values():
        row["pct_gap_affected"] = row["n_gap_affected"] / row["n"] if row["n"] else None
    return by_model


def verify_no_ambiguous_bar_within_confirmed_stops(records: list[EventRecord], timing_by_id: dict) -> int:
    """Category C (same-bar multi-level ambiguity) should never co-occur
    with a confirmed stop in this dataset -- `ambiguous_bar=True` routes to
    AMBIGUOUS_STOP upstream in `eligibility.stop_eligibility.classify`.
    Returns the count of violations (expected: 0)."""
    violations = 0
    for r in records:
        event_id = r.identification.event_id
        category = timing_by_id[event_id].category
        if category in (TimingCategory.SAME_BAR_SL, TimingCategory.NEXT_BAR_SL, TimingCategory.LATER_SL):
            if r.operation.ambiguous_bar:
                violations += 1
    return violations


def run() -> dict:
    records = extract(REPO_ROOT)
    series_by_instrument = load_all_series()
    timing_by_id = classify_all_timing(records, series_by_instrument)
    uncertainty_by_id = classify_all_intrabar_uncertainty(records, timing_by_id, series_by_instrument)

    primary = build_primary_population(records)
    return {
        "e0_uncertainty_by_model": summarize_e0(primary, timing_by_id, uncertainty_by_id),
        "gap_affected_by_model": summarize_gap_affected(primary, timing_by_id, uncertainty_by_id),
        "same_bar_multi_level_ambiguity_violations_within_confirmed_stops":
            verify_no_ambiguous_bar_within_confirmed_stops(primary, timing_by_id),
    }


def main() -> dict:
    result = run()
    artifacts_dir = LAB_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    (artifacts_dir / "phase6_intrabar_uncertainty_report.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(result, indent=2, default=str))
    return result


if __name__ == "__main__":
    main()
