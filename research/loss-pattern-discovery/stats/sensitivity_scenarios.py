"""Deliverable D: Sensitivity Analysis (S0-S3).

S0 reproduces Phase 5 exactly, unmodified. S1 isolates E1 alone, never framed
as a conditional "survived bar 0" probability. S2 is a partial-identification
bound on the NOT-sequence-verifiable subset of E0 only -- those events are
never recoded as wins or as non-entries, only removed from the early-stop
NUMERATOR (the "min" scenario) while staying in the denominator, vs. kept per
the engine's own convention (the "max" scenario, identical to S0 restricted
to that subset). S3 drops that same NOT-verifiable subset entirely (numerator
AND denominator) and reports the exclusion as an explicit, possibly
model-asymmetric, selection effect -- never presented as equivalent to the
original population. See docs/37-phase6-design-and-pre-registration.md
section 5.

Phase 7 correction (docs/46-phase6-sensitivity-correction.md): S2's bounds on
the DIFFERENCE 1AM-9AM are NOT (rate_1am_min - rate_9am_min) and
(rate_1am_max - rate_9am_max) -- pairing the same scenario on both models
does not bound a difference of two independently-uncertain quantities. The
correct extrema are `Gap_min = rate_1am_min - rate_9am_max` and
`Gap_max = rate_1am_max - rate_9am_min` (interval arithmetic on a
subtraction: to minimize A-B you maximize what is subtracted). Each model's
own min/max rate is computed independently; the four cross-combinations
(min,min)/(min,max)/(max,min)/(max,max) are all contained within
[Gap_min, Gap_max] by construction (`test_sensitivity_scenarios.py`).
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

from eligibility.intrabar_ambiguity import classify_all_intrabar_uncertainty  # noqa: E402
from eligibility.stop_timing_decomposition import TimingCategory, classify_all_timing  # noqa: E402
from extract.from_causal_lookahead_audit import extract  # noqa: E402
from schema.events import EventRecord  # noqa: E402
from stats.bootstrap import block_key  # noqa: E402
from stats.early_stop_hypothesis import (  # noqa: E402
    N_RESAMPLES, PRIMARY_CI_LEVEL, SEED, build_primary_population, unadjusted_gap,
)
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


def _min_max_flags(primary: list[EventRecord], timing_by_id: dict, uncertainty_by_id: dict) -> tuple[dict, dict]:
    """Per-event flags for the two extreme scenarios on EACH model's own
    rate (never cross-model): `flags_min` excludes NOT-verifiable same-bar
    events from the early-stop numerator (they stay in the denominator --
    never recoded as a win or a non-entry); `flags_max` keeps the engine's
    own convention (identical to S0's flag for every event)."""
    flags_min: dict[str, bool] = {}
    flags_max: dict[str, bool] = {}
    for r in primary:
        event_id = r.identification.event_id
        category = timing_by_id[event_id].category
        if category is TimingCategory.NEXT_BAR_SL:
            flags_min[event_id] = True
            flags_max[event_id] = True
        elif category is TimingCategory.SAME_BAR_SL:
            verifiable = uncertainty_by_id[event_id].sequence_verifiable
            flags_min[event_id] = bool(verifiable)
            flags_max[event_id] = True
        else:
            flags_min[event_id] = False
            flags_max[event_id] = False
    return flags_min, flags_max


def _model_rate_bounds(records_for_model: list[EventRecord], flags_min: dict, flags_max: dict) -> dict:
    """One model's own rate_min/rate_max (point estimates) plus their joint
    block-bootstrap resampled distributions -- each resample draws ONE set
    of blocks and evaluates BOTH flag definitions on it, preserving their
    natural coupling (never resampled independently of each other)."""
    rows = [
        (
            flags_min[r.identification.event_id], flags_max[r.identification.event_id],
            block_key(r.identification.instrument, r.operation.entry_ts),
        )
        for r in records_for_model
    ]
    blocks: dict[tuple, list[tuple[bool, bool]]] = {}
    for f_min, f_max, block in rows:
        blocks.setdefault(block, []).append((f_min, f_max))
    block_list = list(blocks.values())
    n_total = sum(len(b) for b in block_list)

    def _rate(pairs: list[tuple[bool, bool]], idx: int) -> float:
        flags = [p[idx] for p in pairs]
        return sum(1.0 for f in flags if f) / len(flags) if flags else float("nan")

    pooled = [p for b in block_list for p in b]
    point_min, point_max = _rate(pooled, 0), _rate(pooled, 1)

    rng = random.Random(SEED)
    resampled_min, resampled_max = [], []
    for _ in range(N_RESAMPLES):
        chosen = [block_list[rng.randrange(len(block_list))] for _ in range(len(block_list))] if block_list else []
        pooled_resample = [p for b in chosen for p in b]
        resampled_min.append(_rate(pooled_resample, 0))
        resampled_max.append(_rate(pooled_resample, 1))
    return {
        "n": n_total, "point_min": point_min, "point_max": point_max,
        "resampled_min": resampled_min, "resampled_max": resampled_max,
    }


def _percentile(values: list[float], q: float) -> float | None:
    values = sorted(v for v in values if v == v)  # drop NaN
    if not values:
        return None
    idx = min(int(q * len(values)), len(values) - 1)
    return values[idx]


def scenario_s2(primary: list[EventRecord], timing_by_id: dict, uncertainty_by_id: dict) -> dict:
    """Partial-identification bounds on Gap = rate_1am - rate_9am, where
    each model's own rate is uncertain within [rate_min, rate_max] because
    of its NOT-verifiable same-bar events. The DIFFERENCE's extrema are
    `Gap_min = rate_1am_min - rate_9am_max` and
    `Gap_max = rate_1am_max - rate_9am_min` (not (min,min)/(max,max) --
    docs/46-phase6-sensitivity-correction.md).

    Reports TWO distinct things, never conflated (brief section 2,
    requirement 5/6): the `identified_interval` (point bounds -- pure
    identification uncertainty, no sampling noise) and a separate
    `ci_for_identified_set` (sampling uncertainty on top of it). The CI is a
    conservative outer-envelope block-bootstrap construction, not a formal
    Imbens-Manski interval: `ci_low` is the 2.5th percentile of the
    resampled `Gap_min` distribution and `ci_high` is the 97.5th percentile
    of the resampled `Gap_max` distribution -- each necessarily at least as
    wide as, and generally wider than, either single scenario's own 95% CI,
    because it must cover the whole identified interval rather than one
    point inside it. This is NOT the same thing as the individual CIs of
    the two extreme scenarios, and is not claimed to achieve the exact
    nominal coverage a calibrated Imbens-Manski procedure would.
    """
    by_model = _records_by_model(primary)
    flags_min, flags_max = _min_max_flags(primary, timing_by_id, uncertainty_by_id)

    bounds_1am = _model_rate_bounds(by_model.get("1am", []), flags_min, flags_max)
    bounds_9am = _model_rate_bounds(by_model.get("9am", []), flags_min, flags_max)

    gap_min_point = bounds_1am["point_min"] - bounds_9am["point_max"]
    gap_max_point = bounds_1am["point_max"] - bounds_9am["point_min"]

    resampled_gap_min = [
        r1 - r9 for r1, r9 in zip(bounds_1am["resampled_min"], bounds_9am["resampled_max"])
    ]
    resampled_gap_max = [
        r1 - r9 for r1, r9 in zip(bounds_1am["resampled_max"], bounds_9am["resampled_min"])
    ]
    alpha = (1 - PRIMARY_CI_LEVEL) / 2
    ci_low = _percentile(resampled_gap_min, alpha)
    ci_high = _percentile(resampled_gap_max, 1 - alpha)

    return {
        "n_1am": bounds_1am["n"], "n_9am": bounds_9am["n"],
        "rate_1am_min": bounds_1am["point_min"], "rate_1am_max": bounds_1am["point_max"],
        "rate_9am_min": bounds_9am["point_min"], "rate_9am_max": bounds_9am["point_max"],
        "identified_interval": {"gap_min": gap_min_point, "gap_max": gap_max_point},
        "ci_for_identified_set": {
            "ci_low": ci_low, "ci_high": ci_high, "ci_level": PRIMARY_CI_LEVEL,
            "method": "outer-envelope block bootstrap (docs/46): ci_low = 2.5th pct of the resampled "
                      "Gap_min distribution, ci_high = 97.5th pct of the resampled Gap_max distribution",
        },
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
