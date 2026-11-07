"""Runnable entry point for `experimental.key_level_reaction_redefinition`
over a real H4/M15(/Daily) pair. Reuses the production pipeline
unmodified (`cli._detect_all`, `backtest.simulate.simulate`) and reports
the redefinition's crosstab plus win-rate/avg-R under both definitions.

No charter 8-11 content is applied. `docs/` stays read-only.
"""
from __future__ import annotations

import argparse
import sys

from core.config import DetectorConfig
from experimental.key_level_reaction_redefinition import (
    ReactionRedefinitionReport,
    build_redefinition_rows,
)

REACTIONS_TO_REPORT = ("reject_close_inside", "continuation", "ambiguous")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m experimental.key_level_reaction_redefinition_runner",
        description=(
            "EXPERIMENTAL measurement: does redefining key_level_reaction "
            "against the credited Key Level's own zone (instead of the CRT "
            "range) open a win-rate/avg-R gap the current definition misses?"
        ),
    )
    parser.add_argument("--csv", required=True, help="LTF (M15 execution) MT5 CSV")
    parser.add_argument("--htf-csv", required=True, help="HTF (H4) MT5 CSV")
    parser.add_argument("--daily-csv", default=None, help="Daily MT5 CSV (optional)")
    parser.add_argument("--symbol", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    from cli import _detect_all
    from ingestion.loader import LoadError, load_mt5_csv
    from ingestion.pairing import load_pair

    try:
        htf, ltf = load_pair(
            htf_csv=args.htf_csv, htf_symbol=args.symbol,
            ltf_csv=args.csv, ltf_symbol=args.symbol,
        )
        daily = (
            load_mt5_csv(args.daily_csv, symbol=args.symbol)
            if args.daily_csv
            else None
        )
    except (LoadError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    config = DetectorConfig()
    detections = _detect_all(ltf, htf, daily, config)
    aligned = detections.aligned_signals or []

    from backtest.simulate import simulate

    trades, _ = simulate(aligned, ltf, config)
    rows = build_redefinition_rows(aligned, htf.candles, trades)
    report = ReactionRedefinitionReport(rows=rows)

    print(_render(report, symbol=args.symbol))
    return 0


def _render(report: ReactionRedefinitionReport, *, symbol: str) -> str:
    lines = [f"symbol: {symbol}", f"confluent signals (key_level is not None): {len(report.rows)}", ""]

    lines.append("crosstab (current_reaction -> redefined_reaction):")
    for current in REACTIONS_TO_REPORT:
        for redefined in REACTIONS_TO_REPORT:
            count = report.crosstab.get((current, redefined), 0)
            if count:
                lines.append(f"  {current:<22} -> {redefined:<22} : {count}")
    lines.append("")

    lines.append("stats_for('reject_close_inside', using='current') vs using='redefined':")
    for using in ("current", "redefined"):
        stats = report.stats_for("reject_close_inside", using=using)
        lines.append(
            f"  using={using:<10} n={stats['n']:<6} n_closed={stats['n_closed']:<6} "
            f"win_rate={stats['win_rate']:.4f} avg_r={stats['avg_r']:.4f}"
        )
    lines.append("")

    flipped = report.flipped_to_continuation
    lines.append(
        f"flipped (today reject_close_inside, redefinition says otherwise): {len(flipped)}"
    )
    closed_flipped = [row for row in flipped if row.outcome in ("win", "loss")]
    if closed_flipped:
        wins = sum(1 for row in closed_flipped if row.outcome == "win")
        avg_r = sum(row.r_multiple for row in closed_flipped if row.r_multiple is not None) / len(closed_flipped)
        lines.append(
            f"  of those, closed trades: {len(closed_flipped)}, "
            f"win_rate={wins / len(closed_flipped):.4f}, avg_r={avg_r:.4f}"
        )

    agree_reject = [
        row for row in report.rows
        if row.current_reaction == "reject_close_inside" and row.redefined_reaction == "reject_close_inside"
    ]
    closed_agree = [row for row in agree_reject if row.outcome in ("win", "loss")]
    if closed_agree:
        wins = sum(1 for row in closed_agree if row.outcome == "win")
        avg_r = sum(row.r_multiple for row in closed_agree if row.r_multiple is not None) / len(closed_agree)
        lines.append(
            f"agree reject_close_inside under both definitions: n_closed={len(closed_agree)}, "
            f"win_rate={wins / len(closed_agree):.4f}, avg_r={avg_r:.4f}"
        )

    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
