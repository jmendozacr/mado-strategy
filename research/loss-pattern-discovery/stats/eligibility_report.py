"""Deliverable A: Stop Event Eligibility Report.

Classifies every loss/open event (`eligibility/stop_eligibility.py`) and
reports counts, percentages, reasons and confidence. Descriptive only -- no
post-stop behavior or Atlas computation here.

Usage (from the repo root, with detector's venv active):
    uv run --project detector python research/loss-pattern-discovery/stats/eligibility_report.py
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

from eligibility.stop_eligibility import StopEligibility, classify_all  # noqa: E402
from extract.from_causal_lookahead_audit import extract  # noqa: E402
from schema.events import EventRecord, Outcome  # noqa: E402


def build_report(records: list[EventRecord]) -> dict:
    results = classify_all(records)
    total_loss_open = len(results)
    total_win = sum(1 for r in records if r.operation.outcome is Outcome.WIN)

    by_category = Counter(r.category.value for r in results.values())
    by_instrument_category: dict[str, Counter] = {}
    for record in records:
        result = results.get(record.identification.event_id)
        if result is None:
            continue
        instrument = record.identification.instrument
        by_instrument_category.setdefault(instrument, Counter())[result.category.value] += 1

    confidence_by_category = {}
    sample_reasons = {}
    for cat in StopEligibility:
        matches = [r for r in results.values() if r.category is cat]
        confs = [r.confidence for r in matches]
        confidence_by_category[cat.value] = {
            "n": len(confs),
            "mean_confidence": (sum(confs) / len(confs)) if confs else None,
        }
        sample_reasons[cat.value] = list(matches[0].reasons) if matches else []

    eligible = by_category.get(StopEligibility.CONFIRMED_STOP.value, 0) + \
        by_category.get(StopEligibility.STOP_AFTER_PARTIAL.value, 0)

    return {
        "total_win": total_win,
        "total_loss_or_open": total_loss_open,
        "by_category": dict(by_category),
        "by_category_pct": (
            {k: v / total_loss_open for k, v in by_category.items()} if total_loss_open else {}
        ),
        "by_instrument_category": {k: dict(v) for k, v in by_instrument_category.items()},
        "confidence_by_category": confidence_by_category,
        "sample_reasons": sample_reasons,
        "eligible_for_atlas": eligible,
        "sensitivity_only_ambiguous": by_category.get(StopEligibility.AMBIGUOUS_STOP.value, 0),
        "open_censored": by_category.get(StopEligibility.OPEN_CENSORED.value, 0),
    }


def render_markdown(report: dict) -> str:
    lines = ["# Stop Event Eligibility Report (Phase 2, Unit A)", ""]
    lines.append(f"Wins (outside this taxonomy's scope): {report['total_win']}")
    lines.append(f"Losses + open-censored, classified: {report['total_loss_or_open']}")
    lines.append("")
    lines.append("## By category")
    for cat, n in report["by_category"].items():
        pct = report["by_category_pct"].get(cat, 0)
        conf = report["confidence_by_category"].get(cat, {}).get("mean_confidence")
        conf_str = f"{conf:.2f}" if conf is not None else "n/a"
        lines.append(f"- `{cat}`: {n} ({pct:.1%}), mean confidence {conf_str}")
    lines.append("")
    lines.append("## By instrument x category")
    for instrument, counts in report["by_instrument_category"].items():
        lines.append(f"- {instrument}: {dict(counts)}")
    lines.append("")
    lines.append(f"**Eligible for the Atlas (Confirmed + Stop-After-Partial): {report['eligible_for_atlas']}**")
    lines.append(f"**Reserved for sensitivity only (Ambiguous): {report['sensitivity_only_ambiguous']}**")
    lines.append(f"**Open/censored (its own category, not a stop judgment): {report['open_censored']}**")
    lines.append("")
    lines.append("## One sample classification reason per category")
    for cat, reasons in report["sample_reasons"].items():
        lines.append(f"- `{cat}`: {'; '.join(reasons) if reasons else '(no events in this category)'}")
    lines.append("")
    return "\n".join(lines)


def main() -> dict:
    records = extract(REPO_ROOT)
    report = build_report(records)
    artifacts_dir = LAB_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    (artifacts_dir / "phase2_eligibility_report.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    (artifacts_dir / "phase2_eligibility_report.md").write_text(render_markdown(report), encoding="utf-8")
    print(render_markdown(report))
    return report


if __name__ == "__main__":
    main()
