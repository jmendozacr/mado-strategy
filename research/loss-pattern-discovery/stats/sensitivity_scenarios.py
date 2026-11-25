"""Deliverable D: Sensitivity Analysis (S0-S3).

S0 reproduces Phase 5 exactly, unmodified. S1 isolates E1 alone, never framed
as a conditional "survived bar 0" probability. S2 is a partial-identification
bound on the NOT-sequence-verifiable subset of E0 only -- those events are
never recoded as wins or as non-entries, only removed from the early-stop
NUMERATOR while staying in the denominator (lower bound) vs. kept per the
engine's own convention (upper bound, identical to S0 restricted to that
subset). S3 drops that same NOT-verifiable subset entirely (numerator AND
denominator) and reports the exclusion as an explicit, possibly
model-asymmetric, selection effect -- never presented as equivalent to the
original population. See docs/37-phase6-design-and-pre-registration.md
section 5.
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
from stats.early_stop_hypothesis import build_primary_population, unadjusted_gap  # noqa: E402
from stats.model_population_audit import load_all_series  # noqa: E402


def _records_by_model(records: list[EventRecord]) -> dict[str, list[EventRecord]]:
    out: dict[str, list[EventRecord]] = {}
    for r in records:
        out.setdefault(r.identification.session_label, []).append(r)
    return out


def scenario_s0(primary: list[EventRecord], timing_by_id: dict) -> dict:
    flags = {
        r.identification.event_id: timing_by_id[r.identification.event_id].category
        in (TimingCategory.SAME_BAR_SL, TimingCategory.NEXT_BAR_SL)
        for r in primary
    }
    return unadjusted_gap(_records_by_model(primary), flags)


def scenario_s1(primary: list[EventRecord], timing_by_id: dict) -> dict:
    flags = {
        r.identification.event_id: timing_by_id[r.identification.event_id].category is TimingCategory.NEXT_BAR_SL
        for r in primary
    }
    return unadjusted_gap(_records_by_model(primary), flags)


def scenario_s2(primary: list[EventRecord], timing_by_id: dict, uncertainty_by_id: dict) -> dict:
    def _flag(record: EventRecord, upper: bool) -> bool:
        category = timing_by_id[record.identification.event_id].category
        if category is TimingCategory.NEXT_BAR_SL:
            return True
        if category is not TimingCategory.SAME_BAR_SL:
            return False
        u = uncertainty_by_id[record.identification.event_id]
        if u.sequence_verifiable:
            return True
        # NOT-verifiable E0: upper bound keeps the engine's own convention
        # (counted as an early stop); lower bound removes it from the
        # numerator only -- never recoded as a win or as a non-entry.
        return upper

    by_model = _records_by_model(primary)
    lower_flags = {r.identification.event_id: _flag(r, upper=False) for r in primary}
    upper_flags = {r.identification.event_id: _flag(r, upper=True) for r in primary}
    return {
        "lower_bound": unadjusted_gap(by_model, lower_flags),
        "upper_bound": unadjusted_gap(by_model, upper_flags),
    }


def scenario_s3(primary: list[EventRecord], timing_by_id: dict, uncertainty_by_id: dict) -> dict:
    def _is_not_verifiable_e0(record: EventRecord) -> bool:
        category = timing_by_id[record.identification.event_id].category
        if category is not TimingCategory.SAME_BAR_SL:
            return False
        u = uncertainty_by_id[record.identification.event_id]
        return not u.sequence_verifiable

    excluded = [r for r in primary if _is_not_verifiable_e0(r)]
    retained = [r for r in primary if not _is_not_verifiable_e0(r)]

    flags = {
        r.identification.event_id: timing_by_id[r.identification.event_id].category
        in (TimingCategory.SAME_BAR_SL, TimingCategory.NEXT_BAR_SL)
        for r in retained
    }
    gap = unadjusted_gap(_records_by_model(retained), flags)

    n_by_model = {m: len(recs) for m, recs in _records_by_model(primary).items()}
    n_excluded_by_model = {m: len(recs) for m, recs in _records_by_model(excluded).items()}
    exclusion_share_by_model = {
        m: (n_excluded_by_model.get(m, 0) / n_by_model[m] if n_by_model[m] else None) for m in n_by_model
    }
    return {
        "gap_on_verifiable_subset": gap,
        "n_excluded_total": len(excluded),
        "n_excluded_by_model": n_excluded_by_model,
        "n_total_by_model": n_by_model,
        "exclusion_share_by_model": exclusion_share_by_model,
        "reason": "duration_bars == 0 (same-bar SL) and entry-vs-stop order not sequence-verifiable "
                  "from the fill candle's own open (docs/37 section 2)",
    }


def run() -> dict:
    records = extract(REPO_ROOT)
    series_by_instrument = load_all_series()
    timing_by_id = classify_all_timing(records, series_by_instrument)
    uncertainty_by_id = classify_all_intrabar_uncertainty(records, timing_by_id, series_by_instrument)
    primary = build_primary_population(records)

    return {
        "s0_baseline": scenario_s0(primary, timing_by_id),
        "s1_next_bar_alone": scenario_s1(primary, timing_by_id),
        "s2_same_bar_indeterminate_bounds": scenario_s2(primary, timing_by_id, uncertainty_by_id),
        "s3_verifiable_subset_only": scenario_s3(primary, timing_by_id, uncertainty_by_id),
    }


def main() -> dict:
    result = run()
    artifacts_dir = LAB_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    (artifacts_dir / "phase6_sensitivity_scenarios.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(result, indent=2, default=str))
    return result


if __name__ == "__main__":
    main()
