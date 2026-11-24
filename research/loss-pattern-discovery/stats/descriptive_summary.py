"""Phase-1 descriptive summary: coverage and data-quality only.

No pattern mining, no modeling, no profitability claims -- this script exists
to answer docs/01-objectives-and-hypotheses.md's prerequisite question "what
do we actually have, and how clean is it," per
docs/04-methodology-safeguards.md's "descriptive statistics first" rule.

Usage (from the repo root, with detector's venv active):
    uv run --project detector python research/loss-pattern-discovery/stats/descriptive_summary.py
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = LAB_ROOT.parent.parent
for _path in (LAB_ROOT, REPO_ROOT / "detector"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from extract.from_causal_lookahead_audit import extract  # noqa: E402
from schema.events import EventRecord, Outcome  # noqa: E402
from validate.integrity import validate_all  # noqa: E402

KNOWN_CAVEATS = [
    (
        "EURUSD rows in this source have prior documented evidence of being "
        "statistically indistinguishable from noise: a block-bootstrap check "
        "put P(expectancy<=0) around 50%, and the pair's sign flips removing "
        "8 of 12 years (a coin-flip signature). Treat EURUSD rows as weaker "
        "evidence for 'this pair has a real edge' even though they remain "
        "valid as *behavioral* observations of what price did."
    ),
    (
        "The combined +78.603R headline associated with this strategy has no "
        "genuine out-of-sample period: the entire edge is concentrated in "
        "2021-2026 (2015-2020 was net -16.7R combined), and USDCAD/AUDUSD's "
        "stop-floor calibration window overlaps the evaluation window itself."
    ),
    (
        "This ledger was produced by the audit's own standalone corrected "
        "pipeline (causal_intrabar.py and friends), not by detector/'s "
        "production backtest engine -- a repo grep confirms those fixes were "
        "never merged into detector/. See docs/02-source-inventory.md."
    ),
]


def _rate(count: int, total: int) -> float:
    return count / total if total else 0.0


def summarize(records: list[EventRecord]) -> dict:
    total = len(records)
    by_instrument: dict[str, int] = {}
    by_outcome: dict[str, int] = {}
    by_config: dict[str, int] = {}
    by_session: dict[str, int] = {}
    r_by_instrument: dict[str, list[float]] = {}
    ambiguous = 0
    gap_filled = 0
    partials = 0
    missing_feeder_ref = 0
    missing_activation = 0
    missing_model1 = 0
    missing_order_placed = 0
    entry_dates: list = []

    for r in records:
        instrument = r.identification.instrument
        outcome = r.operation.outcome.value
        config_id = r.identification.config_id
        session = r.identification.session_label

        by_instrument[instrument] = by_instrument.get(instrument, 0) + 1
        by_outcome[outcome] = by_outcome.get(outcome, 0) + 1
        by_config[config_id] = by_config.get(config_id, 0) + 1
        by_session[session] = by_session.get(session, 0) + 1
        if r.operation.r_multiple is not None:
            # Right-censored (still-open) trades have no r_multiple yet --
            # excluded from R stats, but still counted in by_outcome above.
            r_by_instrument.setdefault(instrument, []).append(r.operation.r_multiple)

        if r.operation.ambiguous_bar:
            ambiguous += 1
        if r.operation.gap_filled:
            gap_filled += 1
        if r.operation.has_partial_exit:
            partials += 1
        if r.features_pre_entry.feeder_ref_available_ts is None:
            missing_feeder_ref += 1
        if r.features_pre_entry.activation_instant_ts is None:
            missing_activation += 1
        if r.features_pre_entry.model1_available_ts is None:
            missing_model1 += 1
        if r.features_pre_entry.order_placed_ts is None:
            missing_order_placed += 1
        if r.operation.entry_ts is not None:
            entry_dates.append(r.operation.entry_ts)

    r_stats_by_instrument = {
        instrument: {
            "count": len(values),
            "mean": statistics.fmean(values),
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
            "win_rate": _rate(sum(1 for v in values if v > 0), len(values)),
        }
        for instrument, values in r_by_instrument.items()
    }

    issues = validate_all(records)
    issues_by_check: dict[str, int] = {}
    for issue in issues:
        issues_by_check[issue.check] = issues_by_check.get(issue.check, 0) + 1

    return {
        "total_events": total,
        "date_range": {
            "min_entry_ts": min(entry_dates).isoformat() if entry_dates else None,
            "max_entry_ts": max(entry_dates).isoformat() if entry_dates else None,
        },
        "by_instrument": by_instrument,
        "by_outcome": by_outcome,
        "by_config_id": by_config,
        "by_session_label": by_session,
        "r_multiple_by_instrument": r_stats_by_instrument,
        "flags": {
            "ambiguous_bar_rate": _rate(ambiguous, total),
            "gap_filled_rate": _rate(gap_filled, total),
            "has_partial_exit_rate": _rate(partials, total),
        },
        "missing_pre_entry_timestamps": {
            "feeder_ref_available_ts": missing_feeder_ref,
            "activation_instant_ts": missing_activation,
            "model1_available_ts": missing_model1,
            "order_placed_ts": missing_order_placed,
        },
        "validation_issues": {
            "total": len(issues),
            "by_check": issues_by_check,
        },
    }


def render_markdown(summary: dict) -> str:
    lines = ["# Loss Pattern Discovery -- Phase 1 Descriptive Summary", ""]
    lines.append(f"Total events: **{summary['total_events']}**")
    lines.append(
        f"Entry date range: {summary['date_range']['min_entry_ts']} .. "
        f"{summary['date_range']['max_entry_ts']}"
    )
    lines.append("")
    lines.append("## Counts")
    lines.append(f"- By instrument: {summary['by_instrument']}")
    lines.append(f"- By outcome: {summary['by_outcome']}")
    lines.append(f"- By config_id (arm): {summary['by_config_id']}")
    lines.append(f"- By session_label (model): {summary['by_session_label']}")
    lines.append("")
    lines.append("## R-multiple by instrument")
    for instrument, stats in summary["r_multiple_by_instrument"].items():
        lines.append(
            f"- {instrument}: n={stats['count']} mean={stats['mean']:.3f} "
            f"median={stats['median']:.3f} min={stats['min']:.3f} "
            f"max={stats['max']:.3f} win_rate={stats['win_rate']:.1%}"
        )
    lines.append("")
    lines.append("## Execution flags")
    for key, value in summary["flags"].items():
        lines.append(f"- {key}: {value:.2%}")
    lines.append("")
    lines.append("## Missing pre-entry provenance timestamps (count)")
    for key, value in summary["missing_pre_entry_timestamps"].items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("## Validation issues")
    lines.append(f"- Total: {summary['validation_issues']['total']}")
    for check, count in summary["validation_issues"]["by_check"].items():
        lines.append(f"  - {check}: {count}")
    lines.append("")
    lines.append("## Known caveats on this source (do not treat all rows as equally strong evidence)")
    for caveat in KNOWN_CAVEATS:
        lines.append(f"- {caveat}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    records = extract(REPO_ROOT)
    summary = summarize(records)

    artifacts_dir = LAB_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    (artifacts_dir / "phase1_summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )
    (artifacts_dir / "phase1_summary.md").write_text(
        render_markdown(summary), encoding="utf-8"
    )
    print(render_markdown(summary))


if __name__ == "__main__":
    main()
