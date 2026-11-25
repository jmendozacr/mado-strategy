"""Deliverable E: Secondary Behavioral Analysis (limited, exploratory).

Only run if H1/H2's common-support check (`stats.early_stop_hypothesis`)
passes -- this module does not re-decide that; it is invoked conditionally
by the Phase-5 report, not by itself.

Reuses `behavior.post_stop_metrics.compute_post_stop_behavior` and
`behavior.recovery_analysis` COMPLETELY UNMODIFIED -- same horizons, same
0.25R/5pp thresholds as Phase 2/3. This module only re-stratifies their
EXISTING per-event outputs by the SAME risk_atr quintile cutpoints computed
in `stats.early_stop_hypothesis`, at a SINGLE fixed horizon (1d, already
this lab's established reference point) -- never a new horizon search.
"""
from __future__ import annotations

import json
import sys
from datetime import timedelta
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = LAB_ROOT.parent.parent
for _path in (LAB_ROOT, REPO_ROOT / "detector"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from behavior.post_stop_metrics import compute_post_stop_behavior  # noqa: E402
from eligibility.stop_eligibility import StopEligibility, classify_all  # noqa: E402
from extract.from_causal_lookahead_audit import extract  # noqa: E402
from features.pre_entry_features import compute_pre_entry_features  # noqa: E402
from schema.events import EventRecord  # noqa: E402
from stats.bootstrap import median  # noqa: E402
from stats.early_stop_hypothesis import assign_stratum, quintile_cutpoints  # noqa: E402
from stats.model_population_audit import load_all_series  # noqa: E402

HORIZON = "1d"  # this lab's established reference horizon -- not re-chosen here


def _proportion(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def run() -> dict:
    records = extract(REPO_ROOT)
    series_by_instrument = load_all_series()
    eligibility = classify_all(records)

    confirmed_stop_records = [
        r for r in records
        if (result := eligibility.get(r.identification.event_id)) is not None
        and result.category in (StopEligibility.CONFIRMED_STOP, StopEligibility.STOP_AFTER_PARTIAL)
    ]

    pre_entry_by_id = {
        r.identification.event_id: compute_pre_entry_features(r, series_by_instrument[r.identification.instrument])
        for r in confirmed_stop_records
    }
    risk_atr_values = [f.risk_atr for f in pre_entry_by_id.values() if f.risk_atr is not None]
    cutpoints = quintile_cutpoints(risk_atr_values)

    rows = []
    for r in confirmed_stop_records:
        series = series_by_instrument[r.identification.instrument]
        [behavior_1d] = compute_post_stop_behavior(r, series, horizons=(("1d", timedelta(days=1)),))
        features = pre_entry_by_id[r.identification.event_id]
        stratum = assign_stratum(features.risk_atr, cutpoints) if features.risk_atr is not None else None
        rows.append({
            "model": r.identification.session_label,
            "stratum": stratum,
            "mae_r": behavior_1d.mae_r,
            "recovered": behavior_1d.recovered_to_entry_price if not behavior_1d.censored else None,
        })

    def _summarize(subset: list[dict]) -> dict:
        mae = [x["mae_r"] for x in subset if x["mae_r"] is not None]
        recovered = [1.0 if x["recovered"] else 0.0 for x in subset if x["recovered"] is not None]
        return {"n": len(subset), "mae_r_median": median(mae) if mae else None, "p_recovered": _proportion(recovered)}

    by_model_unadjusted = {
        model: _summarize([x for x in rows if x["model"] == model])
        for model in ("1am", "9am")
    }
    by_model_by_stratum = {}
    for stratum in range(5):
        by_model_by_stratum[stratum] = {
            model: _summarize([x for x in rows if x["model"] == model and x["stratum"] == stratum])
            for model in ("1am", "9am")
        }

    return {
        "horizon": HORIZON,
        "risk_atr_quintile_cutpoints": cutpoints,
        "unadjusted_by_model": by_model_unadjusted,
        "by_model_within_risk_atr_stratum": by_model_by_stratum,
    }


def main() -> dict:
    result = run()
    artifacts_dir = LAB_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    (artifacts_dir / "phase5_secondary_behavioral_adjustment.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(result, indent=2, default=str))
    return result


if __name__ == "__main__":
    main()
