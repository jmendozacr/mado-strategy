"""Runnable entry point for `experimental.swing_structural_break_check`
over a real series. Reuses `detect_swings` and `detect_mss_events`
unmodified; no production file touched.
"""
from __future__ import annotations

import argparse

from composite.mss import detect_mss_events
from ingestion.loader import load_mt5_csv
from primitives.swing import detect_swings

from experimental.swing_structural_break_check import summarize


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m experimental.swing_structural_break_check_runner",
        description=(
            "EXPERIMENTAL measurement: of the swings primitives.swing "
            "detects on a real series, how many are ever confirmed by a "
            "real structural break (MSS)?"
        ),
    )
    parser.add_argument("--csv", required=True, help="MT5 CSV for the series to measure")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--label", default=None, help="printed label for this series")
    parser.add_argument(
        "--window", type=int, default=None,
        help="bound 'confirmed' to within this many candles of the swing's own index (None = unbounded)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    series = load_mt5_csv(args.csv, symbol=args.symbol)

    swings = detect_swings(series)
    mss_events = detect_mss_events(series, swings=swings)

    by_kind = {}
    for kind in ("high", "low"):
        k_swings = [s for s in swings if s.kind == kind]
        by_kind[kind] = summarize(k_swings, mss_events, window=args.window)

    overall = summarize(swings, mss_events, window=args.window)
    label = args.label or f"{args.symbol} ({args.csv})"

    print(f"series: {label}")
    print(f"candles: {len(series.candles)}")
    print(f"swings detected: {overall['total_swings']}")
    print(f"MSS events detected: {len(mss_events)}")
    print(f"window: {args.window if args.window is not None else 'unbounded'}")
    print(
        f"  swings confirmed by a real break within window: "
        f"{overall['swings_confirmed_by_mss']} ({overall['fraction']:.1%})"
    )
    for kind, stats in by_kind.items():
        print(
            f"  {kind}: {stats['total_swings']} swings, "
            f"{stats['swings_confirmed_by_mss']} confirmed ({stats['fraction']:.1%})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
