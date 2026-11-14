"""Runnable entry point for `experimental.ote_confluence_check` over a
real series. Reuses `experimental.order_block_redefinition_backtest
.recipe_signals` (the production recipe's own confluent,
reject_close_inside population, archived Daily OB source) and
`backtest.simulate.simulate`, both unmodified.
"""
from __future__ import annotations

import argparse

from backtest.simulate import simulate
from core.config import DetectorConfig
from primitives.swing import detect_swings

from composite.ote import DISCOUNT_PREMIUM_SPLIT
from experimental.ote_confluence_check import build_ote_rows, kind_breakdown, stats_for
from experimental.order_block_redefinition_backtest import recipe_signals

BANDS = {
    "60-75% (charter-4, OTE)": (0.60, 0.75),
    "62-79% (charter-7, OTE)": (0.62, 0.79),
    "0-50% (discount/premium, user request 2026-11-09)": DISCOUNT_PREMIUM_SPLIT,
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m experimental.ote_confluence_check_runner",
        description="EXPERIMENTAL: win-rate/avg-R split by OTE overlap on the credited Key Level.",
    )
    parser.add_argument("--m15-csv", required=True)
    parser.add_argument("--h4-csv", required=True)
    parser.add_argument("--daily-csv", required=True)
    parser.add_argument("--symbol", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    from ingestion.loader import load_mt5_csv
    from ingestion.pairing import load_pair

    h4, m15 = load_pair(
        htf_csv=args.h4_csv, htf_symbol=args.symbol, ltf_csv=args.m15_csv, ltf_symbol=args.symbol,
    )
    daily = load_mt5_csv(args.daily_csv, symbol=args.symbol)
    config = DetectorConfig()

    signals = recipe_signals(m15, h4, daily, config, redefined=False)
    trades, _ = simulate(signals, m15, config)
    swings = detect_swings(h4)

    print(f"symbol: {args.symbol}")
    print(f"recipe population (confluent, reject_close_inside): {len(signals)}")
    print(f"trades: {len(trades)}")

    for label, band in BANDS.items():
        rows = build_ote_rows(signals, h4.candles, swings, trades, band)
        no_leg = sum(1 for row in rows if row.in_ote is None)
        print(f"\n--- band {label} ---")
        print(f"kind breakdown: {kind_breakdown(rows)}")
        print(f"no impulse leg yet knowable: {no_leg} of {len(rows)}")
        for in_ote in (True, False):
            overall = stats_for(rows, in_ote=in_ote)
            print(
                f"  in_ote={in_ote!s:<5} n={overall['n']:<6} n_closed={overall['n_closed']:<6} "
                f"win_rate={overall['win_rate']:.4f} avg_r={overall['avg_r']:+.4f}"
            )
            for kind in ("fvg", "ict_order_block"):
                stats = stats_for(rows, in_ote=in_ote, key_level_kind=kind)
                if stats["n"]:
                    print(
                        f"    kind={kind:<16} n={stats['n']:<6} n_closed={stats['n_closed']:<6} "
                        f"win_rate={stats['win_rate']:.4f} avg_r={stats['avg_r']:+.4f}"
                    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
