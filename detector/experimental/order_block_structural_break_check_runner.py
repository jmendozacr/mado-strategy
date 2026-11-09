"""Runnable entry point for `experimental.order_block_structural_break_check`
over a real series. With `--redefined` it measures
`composite.ict_order_block.detect_order_blocks` (the structural
BOS->Displacement->backward-scan chain, `odd/tasks/
detector-order-block-redefinition.md` T5) instead of the archived
`primitives.ict_order_block.detect_ict_order_blocks` (the bare 2-candle
engulfment rule this change is meant to replace) -- same
`summarize`/`ob_followed_by_real_break` measurement either way, so the
two numbers are directly comparable. Reuses `detect_mss_events`
unmodified; no production file touched.
"""
from __future__ import annotations

import argparse

from composite.mss import detect_mss_events
from ingestion.loader import load_mt5_csv
from primitives.ict_order_block import detect_ict_order_blocks

from experimental.order_block_structural_break_check import summarize


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m experimental.order_block_structural_break_check_runner",
        description=(
            "EXPERIMENTAL measurement: of the Order Blocks detected on a "
            "real series, how many are actually followed by a real "
            "structural break (MSS), same direction, before they "
            "invalidate?"
        ),
    )
    parser.add_argument("--csv", required=True, help="MT5 CSV for the series to measure")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--label", default=None, help="printed label for this series")
    parser.add_argument(
        "--redefined", action="store_true",
        help="measure composite.ict_order_block (structural) instead of the archived engulfing rule",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    series = load_mt5_csv(args.csv, symbol=args.symbol)

    mss_events = detect_mss_events(series)
    if args.redefined:
        from composite.ict_order_block import detect_order_blocks
        obs = detect_order_blocks(series, mss_events=mss_events)
    else:
        obs = detect_ict_order_blocks(series)

    by_direction = {}
    for direction in ("bullish", "bearish"):
        d_obs = [ob for ob in obs if ob.direction == direction]
        by_direction[direction] = summarize(d_obs, mss_events)

    overall = summarize(obs, mss_events)
    label = args.label or f"{args.symbol} ({args.csv})"

    print(f"series: {label}")
    print(f"candles: {len(series.candles)}")
    print(f"MSS events detected: {len(mss_events)}")
    print(f"ICT Order Blocks detected: {overall['total_obs']}")
    print(
        f"  followed by a same-direction real break before invalidation: "
        f"{overall['obs_followed_by_real_break']} ({overall['fraction']:.1%})"
    )
    for direction, stats in by_direction.items():
        print(
            f"  {direction}: {stats['total_obs']} OBs, "
            f"{stats['obs_followed_by_real_break']} followed ({stats['fraction']:.1%})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
