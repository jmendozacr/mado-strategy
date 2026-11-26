"""Phase 10 Deliverable E: E1 association with the pre-registered
confirmation-path contrast (`internal_invalidation_count == 0` vs.
`>= 1`), WITHIN each model separately (H1/H2), plus a descriptive
standardization of the 1AM/9AM E1 gap by that same contrast (H3).

Reuses, never reimplements: `extract.from_causal_lookahead_audit.extract`,
`eligibility.stop_timing_decomposition.classify_all_timing` (E1 is
EXACTLY `TimingCategory.NEXT_BAR_SL`, unchanged since Phase 6),
`stats.early_stop_hypothesis.build_primary_population`, and that same
module's own block-bootstrap helpers (`_proportion`, `_percentile_ci`,
`_group_by_block`, `_resample_rate`, `_group_by_block_records`,
`_resample_records`) -- this module adds no new bootstrap methodology,
only a different grouping variable.

A signal that never confirmed (no anchor / PENDING / window-empty)
never appears here -- it has no reconstructed confirmation path AND no
E1 outcome, by construction (Phase 9's own finding, restated in
`docs/79` section 0): E1 is never assigned to a signal that never
executed.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = LAB_ROOT.parent.parent
for _path in (LAB_ROOT, REPO_ROOT / "detector"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from eligibility.stop_eligibility import StopEligibility, classify_all  # noqa: E402
from eligibility.stop_timing_decomposition import TimingCategory, classify_all_timing  # noqa: E402
from extract.confirmation_path_identity_audit import load_all_symbol_paths  # noqa: E402
from extract.from_causal_lookahead_audit import extract  # noqa: E402
from schema.events import EventRecord  # noqa: E402
from stats.bootstrap import block_key  # noqa: E402
from stats.early_stop_hypothesis import (  # noqa: E402
    MIN_COMMON_SUPPORT_PER_MODEL, N_RESAMPLES, PRIMARY_CI_LEVEL, SEED,
    _group_by_block, _group_by_block_records, _percentile_ci, _proportion, _resample_rate,
    _resample_records, build_primary_population,
)
from stats.model_population_audit import load_all_series  # noqa: E402

MODELS = ("1am", "9am")


def is_confirmed_stop(event_id: str, eligibility: dict) -> bool:
    result = eligibility.get(event_id)
    return result is not None and result.category in (
        StopEligibility.CONFIRMED_STOP, StopEligibility.STOP_AFTER_PARTIAL,
    )


def build_e1_flags(records: list[EventRecord], series_by_instrument: dict) -> dict[str, bool]:
    """E1 = CONFIRMED_STOP AND duration_bars == 1, exactly as Phase 6
    defined `TimingCategory.NEXT_BAR_SL` -- reused unmodified, never
    redefined for this phase."""
    timing_by_id = classify_all_timing(records, series_by_instrument)
    return {
        r.identification.event_id: timing_by_id[r.identification.event_id].category is TimingCategory.NEXT_BAR_SL
        for r in records
    }


def path_complexity_population(
    primary_population: list[EventRecord], paths_by_sid: dict[str, dict],
) -> tuple[list[EventRecord], float, list[str]]:
    """Restricts the primary (executed, evaluable) population to events
    whose confirmation path was successfully reconstructed -- reports
    coverage and any missing id explicitly, never silently drops."""
    covered = [r for r in primary_population if r.identification.event_id in paths_by_sid]
    missing = [r.identification.event_id for r in primary_population if r.identification.event_id not in paths_by_sid]
    coverage = len(covered) / len(primary_population) if primary_population else None
    return covered, coverage, missing


def two_group_gap(
    group_a: list[EventRecord], group_b: list[EventRecord], flags_by_id: dict[str, bool],
    label_a: str, label_b: str,
) -> dict:
    """Same block-bootstrap algorithm as `early_stop_hypothesis.
    unadjusted_gap`, generalized to arbitrary group labels (that
    function hardcodes "1am"/"9am") -- imports its own private helpers
    rather than re-deriving the methodology."""
    def _rows(recs):
        return [
            (flags_by_id[r.identification.event_id], block_key(r.identification.instrument, r.operation.entry_ts))
            for r in recs if r.identification.event_id in flags_by_id
        ]

    rows_a, rows_b = _rows(group_a), _rows(group_b)
    rate_a = _proportion([f for f, _ in rows_a])
    rate_b = _proportion([f for f, _ in rows_b])
    diff_point = rate_a - rate_b

    rng = random.Random(SEED)
    blocks_a = _group_by_block(rows_a)
    blocks_b = _group_by_block(rows_b)
    diffs = [
        _resample_rate(blocks_a, rng) - _resample_rate(blocks_b, rng)
        for _ in range(N_RESAMPLES)
    ]
    ci_low, ci_high = _percentile_ci(diffs, PRIMARY_CI_LEVEL)
    return {
        f"n_{label_a}": len(rows_a), f"n_{label_b}": len(rows_b),
        f"rate_{label_a}": rate_a, f"rate_{label_b}": rate_b,
        "diff": diff_point, "ci_low": ci_low, "ci_high": ci_high, "ci_level": PRIMARY_CI_LEVEL,
    }


def within_model_contrast(
    records_by_model: dict[str, list[EventRecord]], flags_by_id: dict[str, bool], paths_by_sid: dict[str, dict],
) -> dict:
    """H1/H2: `internal_invalidation_count == 0` vs. `>= 1`, computed
    WITHIN each model separately -- never pooled across models."""
    out = {}
    for model in MODELS:
        recs = records_by_model.get(model, [])
        zero = [r for r in recs if paths_by_sid[r.identification.event_id]["internal_invalidation_count"] == 0]
        one_or_more = [r for r in recs if paths_by_sid[r.identification.event_id]["internal_invalidation_count"] >= 1]
        sufficient = len(zero) >= MIN_COMMON_SUPPORT_PER_MODEL and len(one_or_more) >= MIN_COMMON_SUPPORT_PER_MODEL
        gap = two_group_gap(zero, one_or_more, flags_by_id, "zero_invalidation", "one_or_more_invalidation")
        out[model] = {**gap, "sufficient_support": sufficient}
    return out


def standardize_model_gap_by_path_complexity(
    records_by_model: dict[str, list[EventRecord]], flags_by_id: dict[str, bool], paths_by_sid: dict[str, dict],
) -> dict:
    """H3: descriptively standardize the 1AM/9AM E1 gap against the
    pooled zero/>=1-invalidation composition -- same direct-
    standardization pattern as Phase 5's `standardized_gap`, with a
    2-stratum split instead of risk_atr quintiles. Never a causal
    decomposition -- a descriptive comparison to the +5.38pp unadjusted
    gap."""
    def _stratum(event_id):
        return 0 if paths_by_sid[event_id]["internal_invalidation_count"] == 0 else 1

    all_ids = [
        r.identification.event_id for recs in records_by_model.values() for r in recs
        if r.identification.event_id in paths_by_sid
    ]
    pooled_counts = {0: 0, 1: 0}
    for event_id in all_ids:
        pooled_counts[_stratum(event_id)] += 1
    total = sum(pooled_counts.values())
    weights = {s: n / total for s, n in pooled_counts.items()} if total else {}

    def _standardized_rate(recs):
        rate = 0.0
        for s, w in weights.items():
            flags = [
                flags_by_id[r.identification.event_id] for r in recs
                if r.identification.event_id in paths_by_sid and _stratum(r.identification.event_id) == s
                and r.identification.event_id in flags_by_id
            ]
            if flags:
                rate += w * _proportion(flags)
        return rate

    covered_by_model = {
        m: [r for r in recs if r.identification.event_id in paths_by_sid]
        for m, recs in records_by_model.items()
    }
    point_1am = _standardized_rate(covered_by_model.get("1am", []))
    point_9am = _standardized_rate(covered_by_model.get("9am", []))
    diff_point = point_1am - point_9am

    rng = random.Random(SEED)
    blocks_1am = _group_by_block_records(covered_by_model.get("1am", []))
    blocks_9am = _group_by_block_records(covered_by_model.get("9am", []))
    diffs = [
        _standardized_rate(_resample_records(blocks_1am, rng)) - _standardized_rate(_resample_records(blocks_9am, rng))
        for _ in range(N_RESAMPLES)
    ]
    ci_low, ci_high = _percentile_ci(diffs, PRIMARY_CI_LEVEL)
    return {
        "pooled_weights": weights,
        "standardized_rate_1am": point_1am, "standardized_rate_9am": point_9am,
        "diff_1am_minus_9am": diff_point, "ci_low": ci_low, "ci_high": ci_high, "ci_level": PRIMARY_CI_LEVEL,
    }


def run() -> dict:
    records = extract(REPO_ROOT)
    series_by_instrument = load_all_series()
    classify_all(records)
    paths_by_sid = load_all_symbol_paths()

    primary_population = build_primary_population(records)
    covered, coverage, missing = path_complexity_population(primary_population, paths_by_sid)

    records_by_model: dict[str, list[EventRecord]] = {}
    for r in covered:
        records_by_model.setdefault(r.identification.session_label, []).append(r)

    flags_by_id = build_e1_flags(covered, series_by_instrument)

    contrast = within_model_contrast(records_by_model, flags_by_id, paths_by_sid)
    standardized = standardize_model_gap_by_path_complexity(records_by_model, flags_by_id, paths_by_sid)

    composition = {
        model: {
            "n": len(recs),
            "share_zero_invalidation": (
                sum(1 for r in recs if paths_by_sid[r.identification.event_id]["internal_invalidation_count"] == 0)
                / len(recs) if recs else None
            ),
        }
        for model, recs in records_by_model.items()
    }

    return {
        "n_primary_population": len(primary_population),
        "path_reconstruction_coverage": coverage,
        "missing_path_event_ids": missing,
        "within_model_contrast": contrast,
        "composition_by_model": composition,
        "standardized_model_gap": standardized,
    }


def main() -> dict:
    result = run()
    artifacts_dir = LAB_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    (artifacts_dir / "phase10_confirmation_path_e1_association.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8",
    )
    print(json.dumps(result, indent=2, default=str))
    return result


if __name__ == "__main__":
    main()
