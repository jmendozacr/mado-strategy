"""EXPERIMENTAL backtest comparison: swap ONLY the Daily-tier Order Block
Key Level source -- archived `primitives.ict_order_block` (2-candle
engulfment, body-only zone) vs the redefined
`composite.ict_order_block` (BOS->Displacement->backward-scan, wick-to-wick
zone, `odd/tasks/detector-order-block-redefinition.md`) -- through the
EXACT production pipeline otherwise: `cli._detect_all`'s own
HTF/Daily-key-level wiring, the `reject_close_inside` filter the live
scanner recipe uses, and `backtest.simulate.simulate` unmodified.

Not a change to anything: no production file touched. Reuses, never
reimplements, every detection/resolution step except the one source under
test.
"""
from __future__ import annotations

import argparse
from typing import Literal

from alignment.htf_ltf import AlignedSignal, tag_alignment
from backtest.simulate import simulate
from core.candle import OHLCSeries
from core.config import DetectorConfig
from core.key_level import KeyLevel
from primitives.crt_range import detect_crt_ranges
from primitives.fvg import detect_fvgs, to_key_levels as fvg_to_key_levels
from primitives.ict_order_block import detect_ict_order_blocks
from primitives.ict_order_block import to_key_levels as archived_to_key_levels
from entries.model1 import detect_model1_signals

from composite.ict_order_block import detect_order_blocks
from composite.ict_order_block import to_key_levels as redefined_to_key_levels


def daily_key_levels(daily_series: OHLCSeries, *, redefined: bool) -> list[KeyLevel]:
    """The one swappable piece: the Daily-tier Order Block Key Level
    source `cli._detect_all` feeds into `tag_alignment`'s
    `daily_key_levels` when `--daily-csv` is given."""
    if redefined:
        blocks = detect_order_blocks(daily_series)
        return redefined_to_key_levels(blocks)
    blocks = detect_ict_order_blocks(daily_series)
    return archived_to_key_levels(blocks)


def recipe_signals(
    m15: OHLCSeries, h4: OHLCSeries, daily: OHLCSeries, config: DetectorConfig, *,
    redefined: bool, credit_priority: dict[str, int] | None = None,
) -> list[AlignedSignal]:
    """Mirrors `cli._detect_all`'s own HTF/Daily key-level wiring (FVG on
    H4, Order Block on Daily) and `research.eurusd_recipe_validation
    .pipeline.recipe_signals`'s `reject_close_inside` filter -- the exact
    population the live scanner recipe considers, except for the one
    swapped source. `credit_priority` passes through to `tag_alignment`
    unchanged (`None` = the existing recency-only tiebreak)."""
    ltf_crt_ranges = detect_crt_ranges(m15, config.crt_range)
    model1_signals = detect_model1_signals(
        m15, config.crt_range, config.fvg, config.model1, crt_ranges=ltf_crt_ranges,
    )
    htf_crt_ranges = detect_crt_ranges(h4, config.crt_range)
    fvg_key_levels = fvg_to_key_levels(detect_fvgs(h4, config.fvg))
    order_block_key_levels = daily_key_levels(daily, redefined=redefined)

    aligned = tag_alignment(
        h4, m15, config.crt_range, config.fvg, config.model1,
        ltf_signals=model1_signals, htf_ranges=htf_crt_ranges,
        htf_key_levels=fvg_key_levels, daily_series=daily, daily_key_levels=order_block_key_levels,
        credit_priority=credit_priority,
    )
    return [
        signal for signal in aligned
        if signal.key_level is not None and signal.key_level_reaction == "reject_close_inside"
    ]


def trade_stats(trades: list) -> dict[str, float | int]:
    closed = [t for t in trades if t.outcome in ("win", "loss")]
    wins = sum(1 for t in closed if t.outcome == "win")
    total_r = sum(t.r_multiple for t in closed if t.r_multiple is not None)
    return {
        "trades": len(trades),
        "closed": len(closed),
        "win_rate": wins / len(closed) if closed else 0.0,
        "avg_r": total_r / len(closed) if closed else 0.0,
        "total_r": total_r,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m experimental.order_block_redefinition_backtest",
        description=(
            "EXPERIMENTAL: run the recipe's own reject_close_inside "
            "population through backtest.simulate.simulate, comparing "
            "the archived Daily Order Block source against the redefined "
            "one -- nothing else changes."
        ),
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

    print(f"symbol: {args.symbol}")
    for label, redefined in (("archived (today)", False), ("redefined", True)):
        signals = recipe_signals(m15, h4, daily, config, redefined=redefined)
        trades, _ = simulate(signals, m15, config)
        stats = trade_stats(trades)
        print(
            f"{label:<18} signals={len(signals):<6} trades={stats['trades']:<6} "
            f"closed={stats['closed']:<6} win_rate={stats['win_rate']:.4f} "
            f"avg_r={stats['avg_r']:+.4f} total_r={stats['total_r']:+.2f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
