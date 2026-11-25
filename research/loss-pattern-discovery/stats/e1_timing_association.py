"""Deliverable E: E1 Association Analysis (H1/H2/H3).

Model 0 (baseline, unadjusted E1) -> Model 1 (risk_atr-standardized, reusing
Phase 5's exact method) -> Model 2 (confirmation-timing-standardized, same
method applied to a new variable) -> Model 3 (Model 2's gap repeated
one-way within each instrument and period bucket -- never a combinatorial
grid). Reuses `stats.early_stop_hypothesis`'s generic standardization
machinery UNMODIFIED (`quintile_cutpoints`, `assign_stratum`,
`common_support`, `standardized_gap`) -- these functions only ever
consumed a `strata_by_id` dict, so plugging in a different continuous
variable (timing instead of risk) introduces no new causal assumption or
new statistical method, just a new stratifying variable, pre-registered in
docs/47/section 9 before this script's first real-data run.

Section 9's distinction (absolute minutes vs. relative position common
support are NOT equivalent, since the windows have different durations) is
handled by running Model 2 TWICE -- once on `confirmation_elapsed_minutes`
(absolute), once on `confirmation_relative_position` (relative) -- and
reporting both common-support diagnostics separately, never merged.
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

from control.sampling import period_bucket  # noqa: E402
from eligibility.stop_timing_decomposition import TimingCategory, classify_all_timing  # noqa: E402
from extract.from_causal_lookahead_audit import extract  # noqa: E402
from schema.events import EventRecord  # noqa: E402
from stats.early_stop_hypothesis import (  # noqa: E402
    assign_stratum, build_primary_population, common_support, quintile_cutpoints, standardized_gap,
    unadjusted_gap,
)
from stats.model_population_audit import load_all_series  # noqa: E402
from stats.temporal_feature_dataset import TemporalFeatureRow, build_temporal_feature_dataset  # noqa: E402

INSTRUMENTS = ("EURUSD", "USDCAD", "AUDUSD")
PERIOD_BUCKETS = ("2015-2017", "2018-2020", "2021-2023", "2024-2026")


def _records_by_model(records: list[EventRecord]) -> dict[str, list[EventRecord]]:
    out: dict[str, list[EventRecord]] = {}
    for r in records:
        out.setdefault(r.identification.session_label, []).append(r)
    return out


def _e1_flags(primary: list[EventRecord], timing_by_id: dict) -> dict[str, bool]:
    return {
        r.identification.event_id: timing_by_id[r.identification.event_id].category is TimingCategory.NEXT_BAR_SL
        for r in primary
    }


def _strata_from(dataset: dict[str, TemporalFeatureRow], field: str) -> tuple[dict[str, int | None], list[float]]:
    values = [getattr(row, field) for row in dataset.values() if getattr(row, field) is not None]
    cutpoints = quintile_cutpoints(values)
    strata_by_id = {
        event_id: (assign_stratum(getattr(row, field), cutpoints) if getattr(row, field) is not None else None)
        for event_id, row in dataset.items()
    }
    return strata_by_id, cutpoints


def model_0_baseline(primary: list[EventRecord], timing_by_id: dict) -> dict:
    flags = _e1_flags(primary, timing_by_id)
    return unadjusted_gap(_records_by_model(primary), flags)


def model_1_risk_standardized(
    primary: list[EventRecord], timing_by_id: dict, dataset: dict[str, TemporalFeatureRow],
) -> dict:
    flags = _e1_flags(primary, timing_by_id)
    strata_by_id, cutpoints = _strata_from(dataset, "risk_atr")
    records_by_model = _records_by_model(primary)
    support = common_support(records_by_model, strata_by_id)
    return {
        "cutpoints": cutpoints, "common_support": support,
        "standardized_gap": standardized_gap(records_by_model, flags, strata_by_id, support),
    }


def model_2_timing_standardized(
    primary: list[EventRecord], timing_by_id: dict, dataset: dict[str, TemporalFeatureRow], field: str,
    strata_by_id: dict | None = None, cutpoints: list[float] | None = None,
) -> dict:
    """`strata_by_id`/`cutpoints` default to being computed fresh from
    `dataset` (Model 2's own top-level use). `model_3_timing_by_subgroup`
    passes the SAME globally-computed strata/cutpoints for every subgroup
    instead -- re-deriving quintiles from a thin subgroup's own data would
    both crash on an empty subgroup and silently re-tune the
    stratification per subgroup, which Phase 5's own established
    discipline never does (cutpoints are fixed once on the pooled
    population)."""
    flags = _e1_flags(primary, timing_by_id)
    if strata_by_id is None or cutpoints is None:
        strata_by_id, cutpoints = _strata_from(dataset, field)
    records_by_model = _records_by_model(primary)
    support = common_support(records_by_model, strata_by_id)
    return {
        "field": field, "cutpoints": cutpoints, "common_support": support,
        "standardized_gap": standardized_gap(records_by_model, flags, strata_by_id, support),
    }


def model_3_timing_by_subgroup(
    primary: list[EventRecord], timing_by_id: dict, dataset: dict[str, TemporalFeatureRow], field: str,
) -> dict:
    """Model 2's gap repeated one-way within each instrument and each
    period bucket -- never a joint instrument x period grid, and never a
    per-subgroup re-stratification: the SAME global quintile cutpoints
    (computed once on the full pooled population) are reused for every
    subgroup, only the records entering common-support/standardization
    change."""
    global_strata_by_id, global_cutpoints = _strata_from(dataset, field)

    by_instrument = {}
    for instrument in INSTRUMENTS:
        sub_primary = [r for r in primary if r.identification.instrument == instrument]
        by_instrument[instrument] = model_2_timing_standardized(
            sub_primary, timing_by_id, dataset, field,
            strata_by_id=global_strata_by_id, cutpoints=global_cutpoints,
        )

    by_period = {}
    for bucket in PERIOD_BUCKETS:
        sub_primary = [r for r in primary if period_bucket(r.operation.entry_ts) == bucket]
        by_period[bucket] = model_2_timing_standardized(
            sub_primary, timing_by_id, dataset, field,
            strata_by_id=global_strata_by_id, cutpoints=global_cutpoints,
        )

    return {"by_instrument": by_instrument, "by_period": by_period}


def run() -> dict:
    records = extract(REPO_ROOT)
    series_by_instrument = load_all_series()
    timing_by_id = classify_all_timing(records, series_by_instrument)
    primary = build_primary_population(records)
    dataset = build_temporal_feature_dataset(primary, series_by_instrument)

    model_0 = model_0_baseline(primary, timing_by_id)
    model_1 = model_1_risk_standardized(primary, timing_by_id, dataset)
    model_2_absolute = model_2_timing_standardized(primary, timing_by_id, dataset, "confirmation_elapsed_minutes")
    model_2_relative = model_2_timing_standardized(primary, timing_by_id, dataset, "confirmation_relative_position")
    model_3_absolute = model_3_timing_by_subgroup(primary, timing_by_id, dataset, "confirmation_elapsed_minutes")

    return {
        "model_0_baseline": model_0,
        "model_1_risk_standardized": model_1,
        "model_2_timing_standardized_absolute_minutes": model_2_absolute,
        "model_2_timing_standardized_relative_position": model_2_relative,
        "model_3_timing_by_subgroup_absolute_minutes": model_3_absolute,
    }


def main() -> dict:
    result = run()
    artifacts_dir = LAB_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    (artifacts_dir / "phase7_e1_timing_association.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(
        {
            "model_0_baseline": result["model_0_baseline"],
            "model_1_risk_standardized": {
                "standardized_gap": result["model_1_risk_standardized"]["standardized_gap"],
            },
            "model_2_timing_standardized_absolute_minutes": {
                "standardized_gap": result["model_2_timing_standardized_absolute_minutes"]["standardized_gap"],
                "common_support_unsupported_share": {
                    "1am": result["model_2_timing_standardized_absolute_minutes"]["common_support"]["unsupported_share_1am"],
                    "9am": result["model_2_timing_standardized_absolute_minutes"]["common_support"]["unsupported_share_9am"],
                },
            },
            "model_2_timing_standardized_relative_position": {
                "standardized_gap": result["model_2_timing_standardized_relative_position"]["standardized_gap"],
                "common_support_unsupported_share": {
                    "1am": result["model_2_timing_standardized_relative_position"]["common_support"]["unsupported_share_1am"],
                    "9am": result["model_2_timing_standardized_relative_position"]["common_support"]["unsupported_share_9am"],
                },
            },
        },
        indent=2, default=str,
    ))
    return result


if __name__ == "__main__":
    main()
