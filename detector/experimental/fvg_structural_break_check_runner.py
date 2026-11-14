"""Runnable entry point for `experimental.fvg_structural_break_check`
over a real series. Reuses `detect_fvgs` and `detect_mss_events`
unmodified; no production file touched.
"""
from __future__ import annotations

import argparse

from composite.mss import detect_mss_events
from ingestion.loader import load_mt5_csv
from primitives.fvg import detect_fvgs

from experimental.fvg_structural_break_check import summarize


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m experimental.fvg_structural_break_check_runner",
        description=(
            "EXPERIMENTAL measurement: of the FVGs primitives.fvg detects "
            "on a real series, how many are actually followed by a real "
            "structural break (MSS), same direction, before they fill?"
        ),
    )
    parser.add_argument("--csv", required=True, help="MT5 CSV for the series to measure")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--label", default=None, help="printed label for this series")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    series = load_mt5_csv(args.csv, symbol=args.symbol)

    fvgs = detect_fvgs(series)
    mss_events = detect_mss_events(series)

    by_direction = {}
    for direction in ("bullish", "bearish"):
        d_fvgs = [f for f in fvgs if f.direction == direction]
        by_direction[direction] = summarize(d_fvgs, mss_events)

    overall = summarize(fvgs, mss_events)
    label = args.label or f"{args.symbol} ({args.csv})"

    print(f"series: {label}")
    print(f"candles: {len(series.candles)}")
    print(f"MSS events detected: {len(mss_events)}")
    print(f"FVGs detected: {overall['total_fvgs']}")
    print(
        f"  followed by a same-direction real break before fill: "
        f"{overall['fvgs_followed_by_real_break']} ({overall['fraction']:.1%})"
    )
    for direction, stats in by_direction.items():
        print(
            f"  {direction}: {stats['total_fvgs']} FVGs, "
            f"{stats['fvgs_followed_by_real_break']} followed ({stats['fraction']:.1%})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
