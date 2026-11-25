"""Deliverables C+D: Early Stop-Loss Analysis & Failure Mechanism
Explanation.

H1 (primary): P(confirmed_stop AND same_or_next_bar | PRIMARY population --
every evaluable executed trade, win or loss, excluding only the 4
OPEN_CENSORED) differs between 1AM and 9AM. Computed unadjusted, then
risk_atr-standardized (direct standardization, pooled quintile strata,
common-support checked before trusting the adjustment), then checked for
sensitivity by instrument and by period (one-way only).

D: is the Phase-4 path-integrity gap (31.2% vs 15.3% ambiguous/insufficient)
a mechanical consequence of `duration_bars` (`same_or_next_bar` IS, by
`behavior.pre_stop_trajectory`'s own construction, identical to
`integrity != RECONSTRUCTIBLE`), rather than a separate signal? Checked by
recomputing `same_or_next_bar` over the SECONDARY population (confirmed-stop
losses only) and comparing directly to Phase 4's own integrity percentages.

All thresholds (risk_atr quintiles on the pooled distribution, >=20-per-
model common-support minimum, 5pp relevance bar, 95% primary CI) are
pre-declared in `docs/29-phase5-design-and-pre-registration.md`, fixed
before this module's first real-data run.
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

from behavior.pre_stop_trajectory import PathIntegrity, compute_pre_stop_trajectory  # noqa: E402
from common.trade_timing import compute_trade_timing  # noqa: E402
from control.sampling import period_bucket  # noqa: E402
from eligibility.stop_eligibility import StopEligibility, classify_all  # noqa: E402
from extract.from_causal_lookahead_audit import extract  # noqa: E402
from features.pre_entry_features import compute_pre_entry_features  # noqa: E402
from schema.events import EventRecord, Outcome  # noqa: E402
from stats.bootstrap import block_key  # noqa: E402
from stats.model_population_audit import load_all_series  # noqa: E402

N_QUINTILES = 5
MIN_COMMON_SUPPORT_PER_MODEL = 20
RELEVANT_DIFFERENCE_PP = 0.05
MAX_UNSUPPORTED_SHARE = 0.30
PRIMARY_CI_LEVEL = 0.95
N_RESAMPLES = 2000
SEED = 20261124


def build_primary_population(records: list[EventRecord]) -> list[EventRecord]:
    return [r for r in records if r.operation.outcome is not Outcome.OPEN]


def is_confirmed_stop(event_id: str, eligibility: dict) -> bool:
    result = eligibility.get(event_id)
    return result is not None and result.category in (
        StopEligibility.CONFIRMED_STOP, StopEligibility.STOP_AFTER_PARTIAL,
    )


def quintile_cutpoints(values: list[float], n_quantiles: int = N_QUINTILES) -> list[float]:
    ordered = sorted(values)
    n = len(ordered)
    return [ordered[min(int(n * i / n_quantiles), n - 1)] for i in range(1, n_quantiles)]


def assign_stratum(value: float, cutpoints: list[float]) -> int:
    for i, cut in enumerate(cutpoints):
        if value <= cut:
            return i
    return len(cutpoints)


def _proportion(flags: list[bool]) -> float:
    return sum(1.0 for f in flags if f) / len(flags) if flags else float("nan")


def unadjusted_gap(records_by_model: dict, flags_by_id: dict) -> dict:
    rng_data = {
        model: [(flags_by_id[r.identification.event_id], block_key(r.identification.instrument, r.operation.entry_ts))
                for r in recs if r.identification.event_id in flags_by_id]
        for model, recs in records_by_model.items()
    }
    rate = {model: _proportion([f for f, _ in rows]) for model, rows in rng_data.items()}
    diff_point = rate.get("1am", float("nan")) - rate.get("9am", float("nan"))

    rng = random.Random(SEED)
    blocks_1am = _group_by_block(rng_data.get("1am", []))
    blocks_9am = _group_by_block(rng_data.get("9am", []))
    resampled_diffs = []
    for _ in range(N_RESAMPLES):
        r1 = _resample_rate(blocks_1am, rng)
        r9 = _resample_rate(blocks_9am, rng)
        resampled_diffs.append(r1 - r9)
    ci_low, ci_high = _percentile_ci(resampled_diffs, PRIMARY_CI_LEVEL)
    return {
        "n_1am": len(rng_data.get("1am", [])), "n_9am": len(rng_data.get("9am", [])),
        "rate_1am": rate.get("1am"), "rate_9am": rate.get("9am"),
        "diff_1am_minus_9am": diff_point, "ci_low": ci_low, "ci_high": ci_high, "ci_level": PRIMARY_CI_LEVEL,
    }


def _group_by_block(rows: list) -> list[list[bool]]:
    blocks: dict = {}
    for flag, block in rows:
        blocks.setdefault(block, []).append(flag)
    return list(blocks.values())


def _resample_rate(blocks: list[list[bool]], rng: random.Random) -> float:
    if not blocks:
        return float("nan")
    chosen = [blocks[rng.randrange(len(blocks))] for _ in range(len(blocks))]
    pooled = [f for block in chosen for f in block]
    return _proportion(pooled)


def _percentile_ci(values: list[float], ci: float) -> tuple[float, float]:
    values = sorted(v for v in values if v == v)  # drop NaN
    if not values:
        return None, None
    n = len(values)
    alpha = (1 - ci) / 2
    lo = max(int(alpha * n), 0)
    hi = min(int((1 - alpha) * n), n - 1)
    return values[lo], values[hi]


def common_support(records_by_model: dict, strata_by_id: dict) -> dict:
    counts: dict[int, dict[str, int]] = {}
    for model, recs in records_by_model.items():
        for r in recs:
            stratum = strata_by_id.get(r.identification.event_id)
            if stratum is None:
                continue
            counts.setdefault(stratum, {}).setdefault(model, 0)
            counts[stratum][model] += 1

    supported = {}
    unsupported_share = {"1am": 0, "9am": 0}
    totals = {"1am": len(records_by_model.get("1am", [])), "9am": len(records_by_model.get("9am", []))}
    for stratum, by_model in counts.items():
        ok = by_model.get("1am", 0) >= MIN_COMMON_SUPPORT_PER_MODEL and by_model.get("9am", 0) >= MIN_COMMON_SUPPORT_PER_MODEL
        supported[stratum] = {"counts": by_model, "sufficient_common_support": ok}
        if not ok:
            unsupported_share["1am"] += by_model.get("1am", 0)
            unsupported_share["9am"] += by_model.get("9am", 0)

    return {
        "by_stratum": supported,
        "unsupported_share_1am": unsupported_share["1am"] / totals["1am"] if totals["1am"] else None,
        "unsupported_share_9am": unsupported_share["9am"] / totals["9am"] if totals["9am"] else None,
    }


def standardized_gap(records_by_model: dict, flags_by_id: dict, strata_by_id: dict, support: dict) -> dict:
    supported_strata = {s for s, v in support["by_stratum"].items() if v["sufficient_common_support"]}
    pooled_counts = {s: sum(v["counts"].values()) for s, v in support["by_stratum"].items() if s in supported_strata}
    total_pooled = sum(pooled_counts.values())
    weights = {s: n / total_pooled for s, n in pooled_counts.items()} if total_pooled else {}

    def _standardized_rate(recs: list[EventRecord]) -> float:
        rate = 0.0
        for s, w in weights.items():
            flags = [
                flags_by_id[r.identification.event_id] for r in recs
                if strata_by_id.get(r.identification.event_id) == s and r.identification.event_id in flags_by_id
            ]
            if flags:
                rate += w * _proportion(flags)
        return rate

    point_1am = _standardized_rate(records_by_model.get("1am", []))
    point_9am = _standardized_rate(records_by_model.get("9am", []))
    diff_point = point_1am - point_9am

    rng = random.Random(SEED)
    blocks_1am = _group_by_block_records(records_by_model.get("1am", []))
    blocks_9am = _group_by_block_records(records_by_model.get("9am", []))
    resampled_diffs = []
    for _ in range(N_RESAMPLES):
        r1 = _standardized_rate(_resample_records(blocks_1am, rng))
        r9 = _standardized_rate(_resample_records(blocks_9am, rng))
        resampled_diffs.append(r1 - r9)
    ci_low, ci_high = _percentile_ci(resampled_diffs, PRIMARY_CI_LEVEL)

    return {
        "weights_by_stratum": weights,
        "standardized_rate_1am": point_1am, "standardized_rate_9am": point_9am,
        "diff_1am_minus_9am": diff_point, "ci_low": ci_low, "ci_high": ci_high, "ci_level": PRIMARY_CI_LEVEL,
    }


def _group_by_block_records(records: list[EventRecord]) -> list[list[EventRecord]]:
    blocks: dict = {}
    for r in records:
        key = block_key(r.identification.instrument, r.operation.entry_ts)
        blocks.setdefault(key, []).append(r)
    return list(blocks.values())


def _resample_records(blocks: list[list[EventRecord]], rng: random.Random) -> list[EventRecord]:
    if not blocks:
        return []
    chosen = [blocks[rng.randrange(len(blocks))] for _ in range(len(blocks))]
    return [r for block in chosen for r in block]


def duration_explains_integrity(confirmed_stop_records: list[EventRecord], series_by_instrument: dict) -> dict:
    """Deliverable D core check: is `integrity` (Phase 4) mechanically
    determined by `duration_bars` (Phase 5)? Verified directly, not assumed."""
    mismatches = []
    by_model_same_next: dict[str, list[bool]] = {}
    for r in confirmed_stop_records:
        series = series_by_instrument[r.identification.instrument]
        timing = compute_trade_timing(r, series)
        trajectory = compute_pre_stop_trajectory(r, series)
        expected_non_reconstructible = timing.same_or_next_bar
        actual_non_reconstructible = trajectory.integrity != PathIntegrity.RECONSTRUCTIBLE
        if expected_non_reconstructible != actual_non_reconstructible:
            mismatches.append(r.identification.event_id)
        by_model_same_next.setdefault(r.identification.session_label, []).append(timing.same_or_next_bar)

    return {
        "n_checked": len(confirmed_stop_records),
        "n_mismatches": len(mismatches),
        "mismatch_event_ids": mismatches[:10],
        "same_or_next_bar_rate_by_model_among_confirmed_stops": {
            model: _proportion(flags) for model, flags in by_model_same_next.items()
        },
    }


def run() -> dict:
    records = extract(REPO_ROOT)
    series_by_instrument = load_all_series()
    eligibility = classify_all(records)

    primary_population = build_primary_population(records)
    records_by_model: dict[str, list[EventRecord]] = {}
    for r in primary_population:
        records_by_model.setdefault(r.identification.session_label, []).append(r)

    flags_by_id = {}
    for r in primary_population:
        series = series_by_instrument[r.identification.instrument]
        timing = compute_trade_timing(r, series)
        confirmed = is_confirmed_stop(r.identification.event_id, eligibility)
        flags_by_id[r.identification.event_id] = bool(confirmed and timing.same_or_next_bar)

    pre_entry_by_id = {
        r.identification.event_id: compute_pre_entry_features(r, series_by_instrument[r.identification.instrument])
        for r in primary_population
    }
    all_risk_atr = [f.risk_atr for f in pre_entry_by_id.values() if f.risk_atr is not None]
    cutpoints = quintile_cutpoints(all_risk_atr)
    strata_by_id = {
        event_id: (assign_stratum(f.risk_atr, cutpoints) if f.risk_atr is not None else None)
        for event_id, f in pre_entry_by_id.items()
    }

    unadjusted = unadjusted_gap(records_by_model, flags_by_id)
    support = common_support(records_by_model, strata_by_id)
    standardized = standardized_gap(records_by_model, flags_by_id, strata_by_id, support)

    # One-way sensitivity: same unadjusted gap, split by instrument and by period.
    sensitivity_by_instrument = {}
    for instrument in ("EURUSD", "USDCAD", "AUDUSD"):
        sub_by_model = {m: [r for r in recs if r.identification.instrument == instrument] for m, recs in records_by_model.items()}
        sensitivity_by_instrument[instrument] = unadjusted_gap(sub_by_model, flags_by_id)

    sensitivity_by_period = {}
    for bucket_label in ("2015-2017", "2018-2020", "2021-2023", "2024-2026"):
        sub_by_model = {
            m: [r for r in recs if period_bucket(r.operation.entry_ts) == bucket_label]
            for m, recs in records_by_model.items()
        }
        sensitivity_by_period[bucket_label] = unadjusted_gap(sub_by_model, flags_by_id)

    confirmed_stop_records = [
        r for r in records
        if is_confirmed_stop(r.identification.event_id, eligibility)
    ]
    mechanism = duration_explains_integrity(confirmed_stop_records, series_by_instrument)

    return {
        "n_primary_population": len(primary_population),
        "risk_atr_quintile_cutpoints": cutpoints,
        "unadjusted_gap": unadjusted,
        "common_support": support,
        "standardized_gap": standardized,
        "sensitivity_by_instrument": sensitivity_by_instrument,
        "sensitivity_by_period": sensitivity_by_period,
        "mechanism_duration_vs_integrity": mechanism,
    }


def main() -> dict:
    result = run()
    artifacts_dir = LAB_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    (artifacts_dir / "phase5_early_stop_hypothesis.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(
        {
            "n_primary_population": result["n_primary_population"],
            "unadjusted_gap": result["unadjusted_gap"],
            "common_support_unsupported_share": {
                "1am": result["common_support"]["unsupported_share_1am"],
                "9am": result["common_support"]["unsupported_share_9am"],
            },
            "standardized_gap": result["standardized_gap"],
            "mechanism_duration_vs_integrity": result["mechanism_duration_vs_integrity"],
        },
        indent=2, default=str,
    ))
    return result


if __name__ == "__main__":
    main()
