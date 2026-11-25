"""Deliverable A: Model Population Audit.

Starts from ALL 2047 executed trades (778 win / 1265 loss / 4 open) --
never from the 1262-confirmed-stop population alone (that was Phase 4's
scope; see docs/29-phase5-design-and-pre-registration.md section 2 for why
mixing the two is a selection-bias risk). Every proportion below states its
own denominator explicitly in its field name.
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

from common.trade_timing import compute_trade_timing  # noqa: E402
from eligibility.stop_eligibility import StopEligibility, classify_all  # noqa: E402
from extract.from_causal_lookahead_audit import extract  # noqa: E402
from extract.post_stop_trajectory import load_m15_series  # noqa: E402
from features.pre_entry_features import compute_pre_entry_features  # noqa: E402
from schema.events import EventRecord, Outcome  # noqa: E402
from stats.bootstrap import median, quantiles  # noqa: E402

INSTRUMENTS = ("EURUSD", "USDCAD", "AUDUSD")


def _data_dir():
    import config
    return config.resolve_data_dir()


def load_all_series() -> dict:
    return {i: load_m15_series(i, _data_dir()) for i in INSTRUMENTS}


def _numeric(values: list) -> dict:
    clean = [v for v in values if v is not None]
    if not clean:
        return {"n": 0, "median": None, "quantiles": {}}
    return {"n": len(clean), "median": median(clean), "quantiles": quantiles(clean)}


def build_population_table(records: list[EventRecord], series_by_instrument: dict) -> dict:
    eligibility = classify_all(records)
    by_model: dict[str, list[EventRecord]] = {}
    for r in records:
        by_model.setdefault(r.identification.session_label, []).append(r)

    table = {}
    for model, model_records in by_model.items():
        n_total = len(model_records)
        outcome_counts = Counter(r.operation.outcome.value for r in model_records)
        n_win = outcome_counts.get("win", 0)
        n_loss = outcome_counts.get("loss", 0)
        n_open = outcome_counts.get("open", 0)

        eligibility_counts = Counter()
        for r in model_records:
            result = eligibility.get(r.identification.event_id)
            if result is not None:
                eligibility_counts[result.category.value] += 1
        n_confirmed = eligibility_counts.get(StopEligibility.CONFIRMED_STOP.value, 0) + \
            eligibility_counts.get(StopEligibility.STOP_AFTER_PARTIAL.value, 0)
        n_ambiguous = eligibility_counts.get(StopEligibility.AMBIGUOUS_STOP.value, 0)

        durations = []
        for r in model_records:
            series = series_by_instrument[r.identification.instrument]
            timing = compute_trade_timing(r, series)
            if timing.duration_bars is not None:
                durations.append(timing.duration_bars)

        pre_entry = [compute_pre_entry_features(r, series_by_instrument[r.identification.instrument]) for r in model_records]
        risk_price = [f.risk_price for f in pre_entry]
        risk_atr = [f.risk_atr for f in pre_entry]
        cost_to_risk = [f.cost_to_risk_ratio for f in pre_entry]
        n_partial = sum(1 for r in model_records if r.operation.has_partial_exit)
        atr_m15_at_entry = [f.atr_m15_at_entry for f in pre_entry]
        planned_rr = [f.planned_rr for f in pre_entry]
        ny_hour_at_entry = [f.ny_hour_at_entry for f in pre_entry]
        day_of_week_ny = [f.day_of_week_ny for f in pre_entry]
        time_activation_to_entry_s = [f.time_activation_to_entry_s for f in pre_entry]
        recent_range_atr = [f.recent_range_atr for f in pre_entry]
        position_in_recent_range = [f.position_in_recent_range for f in pre_entry]

        table[model] = {
            "n_total": n_total,
            "n_win": n_win,
            "n_loss": n_loss,
            "n_confirmed_stop": n_confirmed,
            "n_ambiguous_stop": n_ambiguous,
            "n_open_censored": n_open,
            "pct_negative_over_total": n_loss / n_total if n_total else None,
            "pct_confirmed_over_loss": n_confirmed / n_loss if n_loss else None,
            "pct_confirmed_over_total": n_confirmed / n_total if n_total else None,
            "duration_bars_all_evaluable": _numeric(durations),
            "risk_price": _numeric(risk_price),
            "risk_atr": _numeric(risk_atr),
            "cost_to_risk_ratio": _numeric(cost_to_risk),
            "pct_partial_exit_over_total": n_partial / n_total if n_total else None,
            "atr_m15_at_entry": _numeric(atr_m15_at_entry),
            "planned_rr": _numeric(planned_rr),
            "ny_hour_at_entry": _numeric(ny_hour_at_entry),
            "day_of_week_ny": _numeric(day_of_week_ny),
            "time_activation_to_entry_s": _numeric(time_activation_to_entry_s),
            "recent_range_atr": _numeric(recent_range_atr),
            "position_in_recent_range": _numeric(position_in_recent_range),
        }
    return table


def main() -> dict:
    records = extract(REPO_ROOT)
    series_by_instrument = load_all_series()
    table = build_population_table(records, series_by_instrument)
    artifacts_dir = LAB_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    (artifacts_dir / "phase5_model_population_audit.json").write_text(
        json.dumps(table, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(table, indent=2, default=str))
    return table


if __name__ == "__main__":
    main()
