"""Deliverable D (limited robustness check): is the continuation-vs-control
difference an artifact of ONE particular control sample, or does it hold
under equally-valid alternative seeds?

Explicitly NOT a new investigation: everything except the control-sampling
seed is held fixed (same eligible population, same horizon, same NY-hour
tolerance, same pool size, same statistic). Seeds are declared here, before
running, as simple consecutive integers plus the lab's own original seed --
never chosen after looking at results, and the best one is never
cherry-picked for the report; every seed's result is printed.

SEEDS = (20261124, 1, 2, 3, 4) -- the original Phase-2/3 seed plus four
arbitrary small integers, fixed before this script's first run.
HORIZON = "1d" -- the same horizon already used as this lab's primary
reference point elsewhere, not chosen because it looks most favorable here.

Usage:
    uv run --project detector python research/loss-pattern-discovery/stats/seed_sensitivity.py
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

from control.sampling import control_to_event_record, sample_controls  # noqa: E402
from extract.from_causal_lookahead_audit import extract  # noqa: E402
from extract.post_stop_trajectory import load_m15_series  # noqa: E402
from stats.atlas import INSTRUMENTS, compare_to_controls, compute_behaviors, split_by_eligibility  # noqa: E402

SEEDS = (20261124, 1, 2, 3, 4)
HORIZON = "1d"


def run() -> dict:
    import config

    records = extract(REPO_ROOT)
    eligible = split_by_eligibility(records)["eligible"]
    series_by_instrument = {i: load_m15_series(i, config.resolve_data_dir()) for i in INSTRUMENTS}
    eligible_behaviors = compute_behaviors(eligible, series_by_instrument)

    results = []
    for seed in SEEDS:
        sampling_result = sample_controls(eligible, series_by_instrument, seed=seed)
        controls = sampling_result.controls
        control_records = [control_to_event_record(c, series_by_instrument[c.instrument]) for c in controls]
        control_records_by_matched_id = {c.matched_event_id: cr for c, cr in zip(controls, control_records)}
        control_behaviors = compute_behaviors(control_records, series_by_instrument)
        comparison = compare_to_controls(
            eligible, eligible_behaviors, control_records_by_matched_id, control_behaviors, HORIZON
        )
        diff = comparison["p_continuation_diff_sl_minus_control"]
        results.append({
            "seed": seed,
            "n": diff["n"],
            "point_estimate": diff["point_estimate"],
            "ci_low": diff["ci_low"],
            "ci_high": diff["ci_high"],
            "excludes_zero": (diff["ci_low"] > 0) or (diff["ci_high"] < 0),
        })

    signs = {1 if r["point_estimate"] < 0 else -1 for r in results}
    stable_sign = len(signs) == 1
    estimates = [r["point_estimate"] for r in results]
    return {
        "horizon": HORIZON,
        "seeds": results,
        "stable_sign_across_seeds": stable_sign,
        "point_estimate_range": [min(estimates), max(estimates)],
        "all_exclude_zero": all(r["excludes_zero"] for r in results),
        "any_exclude_zero": any(r["excludes_zero"] for r in results),
    }


def main() -> dict:
    result = run()
    artifacts_dir = LAB_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    (artifacts_dir / "phase3_1_seed_sensitivity.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(result, indent=2, default=str))
    return result


if __name__ == "__main__":
    main()
