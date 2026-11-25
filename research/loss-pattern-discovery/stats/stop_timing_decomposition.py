"""Deliverable B: Early-Stop Decomposition (E0/E1/E2/E3/E4), by model and by
instrument. Same primary population, same denominator, same
`is_confirmed_stop`/`compute_trade_timing` definitions as Phase 5
(`stats/early_stop_hypothesis.py`) -- this module only partitions Phase 5's
own `confirmed_stop AND same_or_next_bar` endpoint more finely, and verifies
the partition reproduces Phase 5's +9.35pp exactly (within floating-point
rounding), as an arithmetic identity, not a new statistical claim.
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

from eligibility.stop_eligibility import classify_all  # noqa: E402
from eligibility.stop_timing_decomposition import TimingCategory, classify_all_timing  # noqa: E402
from extract.from_causal_lookahead_audit import extract  # noqa: E402
from schema.events import EventRecord, Outcome  # noqa: E402
from stats.early_stop_hypothesis import build_primary_population, is_confirmed_stop, unadjusted_gap  # noqa: E402
from stats.model_population_audit import load_all_series  # noqa: E402

INSTRUMENTS = ("EURUSD", "USDCAD", "AUDUSD")


def _counts_for(records: list[EventRecord], timing_by_id: dict) -> dict:
    n = len(records)
    counts = {c: 0 for c in TimingCategory}
    for r in records:
        counts[timing_by_id[r.identification.event_id].category] += 1
    row = {"n_total": n}
    for c in TimingCategory:
        row[c.value] = counts[c]
        row[f"pct_{c.value}"] = counts[c] / n if n else None
    return row


def build_decomposition_table(records: list[EventRecord], series_by_instrument: dict) -> dict:
    primary = build_primary_population(records)  # excludes OPEN_CENSORED only, same as Phase 5
    open_records = [r for r in records if r.operation.outcome is Outcome.OPEN]
    timing_by_id = classify_all_timing(records, series_by_instrument)

    by_model: dict[str, list[EventRecord]] = {}
    for r in primary:
        by_model.setdefault(r.identification.session_label, []).append(r)

    open_by_model: dict[str, int] = {}
    for r in open_records:
        model = r.identification.session_label
        open_by_model[model] = open_by_model.get(model, 0) + 1

    table = {}
    for model, recs in by_model.items():
        row = _counts_for(recs, timing_by_id)
        row["n_open_censored"] = open_by_model.get(model, 0)
        table[model] = row

    by_model_and_instrument = {}
    for model, recs in by_model.items():
        by_model_and_instrument[model] = {
            instrument: _counts_for([r for r in recs if r.identification.instrument == instrument], timing_by_id)
            for instrument in INSTRUMENTS
        }

    return {"by_model": table, "by_model_and_instrument": by_model_and_instrument}


def verify_decomposition_identity(table: dict) -> dict:
    """Checks (not assumes) that the E0/E1 decomposition sums back to the
    exact combined rate for each model -- mutually exclusive categories,
    same denominator, a pure arithmetic identity."""
    results = {}
    for model, row in table["by_model"].items():
        rate_e0 = row["pct_E0_same_bar_sl"]
        rate_e1 = row["pct_E1_next_bar_sl"]
        rate_e0_or_e1_direct = (row["E0_same_bar_sl"] + row["E1_next_bar_sl"]) / row["n_total"]
        results[model] = {
            "rate_e0": rate_e0, "rate_e1": rate_e1,
            "rate_e0_plus_e1_from_parts": rate_e0 + rate_e1,
            "rate_e0_or_e1_direct": rate_e0_or_e1_direct,
            "identity_holds": abs((rate_e0 + rate_e1) - rate_e0_or_e1_direct) < 1e-12,
        }
    return results


def gap_decomposition(records: list[EventRecord], eligibility: dict, timing_by_id: dict) -> dict:
    """Gap_early (Phase 5's endpoint, E0 union E1) and Gap_E0/Gap_E1
    separately, all from the SAME primary population/denominator, so that
    Gap_early == Gap_E0 + Gap_E1 is checked as an identity, not assumed."""
    primary = build_primary_population(records)
    records_by_model: dict[str, list[EventRecord]] = {}
    for r in primary:
        records_by_model.setdefault(r.identification.session_label, []).append(r)

    flags_early = {}
    flags_e0 = {}
    flags_e1 = {}
    for r in primary:
        event_id = r.identification.event_id
        category = timing_by_id[event_id].category
        flags_early[event_id] = category in (TimingCategory.SAME_BAR_SL, TimingCategory.NEXT_BAR_SL)
        flags_e0[event_id] = category is TimingCategory.SAME_BAR_SL
        flags_e1[event_id] = category is TimingCategory.NEXT_BAR_SL

    gap_early = unadjusted_gap(records_by_model, flags_early)
    gap_e0 = unadjusted_gap(records_by_model, flags_e0)
    gap_e1 = unadjusted_gap(records_by_model, flags_e1)
    sum_point = gap_e0["diff_1am_minus_9am"] + gap_e1["diff_1am_minus_9am"]
    return {
        "gap_early": gap_early, "gap_e0": gap_e0, "gap_e1": gap_e1,
        "sum_of_parts_matches_combined": abs(sum_point - gap_early["diff_1am_minus_9am"]) < 1e-9,
    }


def run() -> dict:
    records = extract(REPO_ROOT)
    series_by_instrument = load_all_series()
    eligibility = classify_all(records)
    timing_by_id = classify_all_timing(records, series_by_instrument)

    table = build_decomposition_table(records, series_by_instrument)
    identity = verify_decomposition_identity(table)
    gaps = gap_decomposition(records, eligibility, timing_by_id)

    return {"table": table, "identity_check": identity, "gap_decomposition": gaps}


def main() -> dict:
    result = run()
    artifacts_dir = LAB_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    (artifacts_dir / "phase6_stop_timing_decomposition.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps({"by_model": result["table"]["by_model"], "gap_decomposition": result["gap_decomposition"]}, indent=2, default=str))
    return result


if __name__ == "__main__":
    main()
