"""Deliverable D: Confirmation Timing Distribution.

Purely descriptive (Unit C) -- distributions of WHEN each model's Model-1
confirmation falls inside its own window, BEFORE any E1 adjustment is
attempted (Deliverable E). Continuous variables throughout; the one
grouped table uses a fixed, pre-declared 30-minute bin width (two M15
bars) chosen for interpretability, never tuned to maximize an E1
difference -- bins are NEVER built from E1 outcomes.
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

from extract.from_causal_lookahead_audit import extract  # noqa: E402
from stats.bootstrap import median, quantiles  # noqa: E402
from stats.early_stop_hypothesis import build_primary_population  # noqa: E402
from stats.model_population_audit import load_all_series  # noqa: E402
from stats.temporal_feature_dataset import TemporalFeatureRow, build_temporal_feature_dataset  # noqa: E402

BIN_WIDTH_MINUTES = 30.0  # pre-declared, two M15 bars -- never tuned on E1
INSTRUMENTS = ("EURUSD", "USDCAD", "AUDUSD")
PERIOD_BUCKETS = ("2015-2017", "2018-2020", "2021-2023", "2024-2026")


def _numeric(values: list[float]) -> dict:
    clean = [v for v in values if v is not None]
    if not clean:
        return {"n": 0, "median": None, "quantiles": {}}
    return {"n": len(clean), "median": median(clean), "quantiles": quantiles(clean)}


def _bin_histogram(rows: list[TemporalFeatureRow], bin_width: float) -> dict[int, int]:
    counts: dict[int, int] = {}
    for row in rows:
        if row.confirmation_elapsed_minutes is None:
            continue
        bin_index = int(row.confirmation_elapsed_minutes // bin_width)
        counts[bin_index] = counts.get(bin_index, 0) + 1
    return dict(sorted(counts.items()))


def summarize_model(rows: list[TemporalFeatureRow]) -> dict:
    return {
        "n": len(rows),
        "confirmation_elapsed_minutes": _numeric([r.confirmation_elapsed_minutes for r in rows]),
        "confirmation_remaining_minutes": _numeric([r.confirmation_remaining_minutes for r in rows]),
        "confirmation_relative_position": _numeric([r.confirmation_relative_position for r in rows]),
        "order_to_fill_minutes": _numeric([r.order_to_fill_minutes for r in rows]),
        "elapsed_minutes_histogram_30min_bins": _bin_histogram(rows, BIN_WIDTH_MINUTES),
    }


def run() -> dict:
    records = extract(REPO_ROOT)
    series_by_instrument = load_all_series()
    primary = build_primary_population(records)
    dataset = build_temporal_feature_dataset(primary, series_by_instrument)

    by_model: dict[str, list[TemporalFeatureRow]] = {}
    for row in dataset.values():
        by_model.setdefault(row.origin_model, []).append(row)

    result = {"by_model": {m: summarize_model(rows) for m, rows in by_model.items()}}

    by_model_instrument = {}
    for model, rows in by_model.items():
        by_model_instrument[model] = {
            instrument: summarize_model([r for r in rows if r.instrument == instrument])
            for instrument in INSTRUMENTS
        }
    result["by_model_and_instrument"] = by_model_instrument

    by_model_period = {}
    for model, rows in by_model.items():
        by_model_period[model] = {
            bucket: summarize_model([r for r in rows if r.period_bucket == bucket])
            for bucket in PERIOD_BUCKETS
        }
    result["by_model_and_period"] = by_model_period

    return result


def main() -> dict:
    result = run()
    artifacts_dir = LAB_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    (artifacts_dir / "phase7_confirmation_timing_distribution.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(result["by_model"], indent=2, default=str))
    return result


if __name__ == "__main__":
    main()
