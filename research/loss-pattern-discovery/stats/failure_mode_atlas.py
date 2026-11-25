"""Deliverable D: Failure Mode Atlas -- descriptive only, no modeling.

Layer A (pre-entry features) is computed for EVERY event regardless of
outcome (win/loss/open) -- the win-vs-loss comparison this phase needs
requires the SAME extraction methodology on both populations. Layer B
(pre-stop trajectory + failure-mode classification) is computed ONLY for
`eligibility.stop_eligibility`'s `CONFIRMED_STOP`/`STOP_AFTER_PARTIAL`
events -- `AMBIGUOUS_STOP` and `OPEN_CENSORED` events are never classified
as a failure mode, matching Phase 2/3's own eligible population exactly.

Stratification is one-way only (instrument, origin model, period bucket --
each alone), plus the pooled-overall result, for the same reason Phase 2/3
avoided a full cross-product grid: avoiding combinatorial subgroup search
over an already-modest 1262-event population.
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

from behavior.pre_stop_trajectory import PathIntegrity, compute_pre_stop_trajectory  # noqa: E402
from control.sampling import period_bucket  # noqa: E402
from eligibility.stop_eligibility import StopEligibility, classify_all  # noqa: E402
from extract.from_causal_lookahead_audit import extract  # noqa: E402
from extract.post_stop_trajectory import load_m15_series  # noqa: E402
from failure_modes.taxonomy import ExcursionClass, classify, duration_tercile_labels  # noqa: E402
from features.pre_entry_features import compute_pre_entry_features  # noqa: E402
from schema.events import EventRecord, Outcome  # noqa: E402
from stats.bootstrap import median, quantiles  # noqa: E402

INSTRUMENTS = ("EURUSD", "USDCAD", "AUDUSD")
MIN_HEADLINE_N = 30


def _data_dir():
    import config
    return config.resolve_data_dir()


def load_all_series() -> dict:
    return {i: load_m15_series(i, _data_dir()) for i in INSTRUMENTS}


def build_pre_entry_dataset(records: list[EventRecord], series_by_instrument: dict) -> list:
    return [
        compute_pre_entry_features(r, series_by_instrument[r.identification.instrument])
        for r in records
    ]


def build_failure_path_dataset(eligible_records: list[EventRecord], series_by_instrument: dict) -> list:
    rows = []
    for record in eligible_records:
        series = series_by_instrument[record.identification.instrument]
        entry_atr = compute_pre_entry_features(record, series).atr_m15_at_entry
        trajectory = compute_pre_stop_trajectory(record, series, atr_at_entry=entry_atr)
        classification = classify(trajectory)
        rows.append((record, trajectory, classification))
    return rows


def _numeric(values: list) -> dict:
    clean = [v for v in values if v is not None]
    if not clean:
        return {"n": 0, "median": None, "quantiles": {}}
    return {"n": len(clean), "median": median(clean), "quantiles": quantiles(clean)}


def summarize_failure_paths(rows: list) -> dict:
    n = len(rows)
    integrity_counts = Counter(c.integrity for _, _, c in rows)
    excursion_counts = Counter(c.excursion_class for _, _, c in rows)

    durations = [t.duration_bars for _, t, _ in rows]
    mfe_r_reconstructible = [t.mfe_pre_sl_r for _, t, c in rows if c.integrity == PathIntegrity.RECONSTRUCTIBLE]
    mae_r_reconstructible = [t.mae_pre_sl_atr for _, t, c in rows if c.integrity == PathIntegrity.RECONSTRUCTIBLE]
    retracement = [t.retracement_from_best_favorable_price for _, t, c in rows if c.integrity == PathIntegrity.RECONSTRUCTIBLE]
    pct_favorable_closes = [t.pct_bars_closed_favorable for _, t, c in rows if c.integrity == PathIntegrity.RECONSTRUCTIBLE]

    # Duration x excursion cross-tab (2 dimensions, not a 5-way grid).
    cross_tab: dict[str, Counter] = {}
    for _, t, c in rows:
        tercile = duration_tercile_labels(durations).get(t.duration_bars, "unknown")
        cross_tab.setdefault(tercile, Counter())[c.excursion_class] += 1

    return {
        "n_total": n,
        "integrity_counts": dict(integrity_counts),
        "integrity_pct": {k: v / n for k, v in integrity_counts.items()} if n else {},
        "excursion_class_counts": dict(excursion_counts),
        "excursion_class_pct": {k: v / n for k, v in excursion_counts.items()} if n else {},
        "duration_bars": _numeric(durations),
        "mfe_pre_sl_r_reconstructible_only": _numeric(mfe_r_reconstructible),
        "mae_pre_sl_atr_reconstructible_only": _numeric(mae_r_reconstructible),
        "retracement_from_best_favorable_price": _numeric(retracement),
        "pct_bars_closed_favorable": _numeric(pct_favorable_closes),
        "duration_x_excursion_cross_tab": {k: dict(v) for k, v in cross_tab.items()},
    }


def one_way_failure_path(rows: list, key_fn) -> dict:
    groups: dict[str, list] = {}
    for item in rows:
        groups.setdefault(key_fn(item[0]), []).append(item)
    return {group: summarize_failure_paths(items) for group, items in groups.items()}


def compare_pre_entry_win_vs_loss(pre_entry_rows: list) -> dict:
    def _by_outcome(outcome_value: str, attr: str) -> list:
        return [getattr(f, attr) for f in pre_entry_rows if f.outcome == outcome_value]

    attrs = ["atr_m15_at_entry", "risk_atr", "planned_rr", "ny_hour_at_entry",
             "time_activation_to_entry_s", "recent_range_atr", "position_in_recent_range"]
    result = {}
    for attr in attrs:
        result[attr] = {
            "win": _numeric(_by_outcome("win", attr)),
            "loss": _numeric(_by_outcome("loss", attr)),
        }
    return result


def run_atlas() -> dict:
    records = extract(REPO_ROOT)
    series_by_instrument = load_all_series()

    eligibility_results = classify_all(records)
    eligible_records = [
        r for r in records
        if eligibility_results.get(r.identification.event_id) is not None
        and eligibility_results[r.identification.event_id].category in
        (StopEligibility.CONFIRMED_STOP, StopEligibility.STOP_AFTER_PARTIAL)
    ]

    pre_entry_dataset = build_pre_entry_dataset(records, series_by_instrument)
    failure_path_rows = build_failure_path_dataset(eligible_records, series_by_instrument)

    one_way = {
        "instrument": one_way_failure_path(failure_path_rows, lambda r: r.identification.instrument),
        "origin_model": one_way_failure_path(failure_path_rows, lambda r: r.identification.session_label),
        "period_bucket": one_way_failure_path(failure_path_rows, lambda r: period_bucket(r.operation.exit_ts)),
    }

    return {
        "n_records_total": len(records),
        "n_eligible_failure_paths": len(eligible_records),
        "overall_failure_path_summary": summarize_failure_paths(failure_path_rows),
        "by_dimension": one_way,
        "pre_entry_win_vs_loss": compare_pre_entry_win_vs_loss(pre_entry_dataset),
        "pre_entry_coverage": {
            "n_total": len(pre_entry_dataset),
            "n_with_atr": sum(1 for f in pre_entry_dataset if f.atr_m15_at_entry is not None),
            "n_with_recent_range": sum(1 for f in pre_entry_dataset if f.recent_range_price is not None),
            "missing_reason_counts": dict(
                Counter(reason for f in pre_entry_dataset for reason in f.missing_reasons)
            ),
        },
    }


def main() -> dict:
    result = run_atlas()
    artifacts_dir = LAB_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    (artifacts_dir / "phase4_failure_mode_atlas.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(
        {
            "n_records_total": result["n_records_total"],
            "n_eligible_failure_paths": result["n_eligible_failure_paths"],
            "integrity_pct": result["overall_failure_path_summary"]["integrity_pct"],
            "excursion_class_pct": result["overall_failure_path_summary"]["excursion_class_pct"],
            "pre_entry_coverage": result["pre_entry_coverage"],
        },
        indent=2, default=str,
    ))
    return result


if __name__ == "__main__":
    main()
