"""EXPERIMENTAL backtest comparison: does adding Breaker Block to the
Daily-tier Key Level pool change the recipe's `reject_close_inside`
population and outcomes -- through the SAME simplified wiring
`order_block_redefinition_backtest.py` already used for its own OB
comparison (`entries.model1.detect_model1_signals` ->
`alignment.htf_ltf.tag_alignment`, not the newer `causal/generate.py`
merge `cli._detect_all` now runs for `purge_engulf` signals), kept
deliberately for apples-to-apples comparability with that prior
measurement (`odd/tasks/detector-order-block-redefinition.md`, memory
#782) rather than because it is the full current production path.

Not a change to anything beyond `entries/breaker_block.py` and the
additive `core/key_level.py` Literal: no other production file touched.

Three arms, run by `main()`:
  - "without breaker"        -- today's Daily-tier Order Block pool alone
  - "with breaker (recency)" -- Breaker Block key levels added to the
                                 pool, default tiebreak (highest
                                 origin_index wins)
  - "with breaker (priority)" -- same pool, `credit_priority` ranks
                                 breaker_block above every other kind, to
                                 measure what happens WITHOUT FVG's
                                 recency bias drowning it out
                                 (`alignment/htf_ltf.py`'s own
                                 `credit_priority` escape hatch).

Memory #782 predicted the "recency" arm would be a null result, for the
same reason OB's own 3x structural-confirmation gain was invisible: FVG
dominates `_key_level_credit_map`'s highest-origin_index tiebreak almost
regardless of which other source is on offer.
"""
from __future__ import annotations

import argparse

from alignment.htf_ltf import AlignedSignal, tag_alignment
from backtest.simulate import simulate
from composite.ict_order_block import detect_order_blocks
from composite.ict_order_block import to_key_levels as order_block_to_key_levels
from core.candle import OHLCSeries
from core.config import DetectorConfig
from core.key_level import KeyLevel
from entries.breaker_block import detect_breaker_blocks
from entries.breaker_block import to_key_levels as breaker_to_key_levels
from entries.model1 import detect_model1_signals
from primitives.crt_range import detect_crt_ranges
from primitives.fvg import detect_fvgs, to_key_levels as fvg_to_key_levels

from experimental.order_block_redefinition_backtest import trade_stats

__all__ = [
    "daily_key_levels", "aligned_signals", "recipe_signals",
    "credit_counts_by_kind", "trade_stats", "main",
]


def _breaker_key_levels(series: OHLCSeries, config: DetectorConfig) -> list[KeyLevel]:
    """Breaker Block has no meaning at the LTF entry level -- it needs its
    own Model-1 detection pass on whichever series it is being OFFERED as
    a Key Level, exactly like FVG/Order Block are each detected directly
    on that tier's own series rather than reused from the LTF pass."""
    crt_ranges = detect_crt_ranges(series, config.crt_range)
    model1_signals = detect_model1_signals(
        series, config.crt_range, config.fvg, config.model1, crt_ranges=crt_ranges,
    )
    blocks = detect_breaker_blocks(series.candles, model1_signals, config.model1)
    return breaker_to_key_levels(blocks)


def daily_key_levels(
    daily_series: OHLCSeries, config: DetectorConfig, *, include_breaker: bool,
) -> list[KeyLevel]:
    """The Daily-tier pool `cli._detect_all` feeds into `tag_alignment`'s
    `daily_key_levels` when `--daily-csv` is given -- Order Block always
    present (current production source), Breaker Block appended only when
    `include_breaker`."""
    order_block_key_levels = order_block_to_key_levels(detect_order_blocks(daily_series))
    if not include_breaker:
        return order_block_key_levels
    return order_block_key_levels + _breaker_key_levels(daily_series, config)


def aligned_signals(
    m15: OHLCSeries, h4: OHLCSeries, daily: OHLCSeries, config: DetectorConfig, *,
    include_breaker: bool, credit_priority: dict[str, int] | None = None,
) -> list[AlignedSignal]:
    """The full tagged population, unfiltered by reaction type -- shared
    by `recipe_signals` (the live recipe's own filter) and
    `credit_counts_by_kind` (the #782-style credit-share measurement), so
    neither needs its own detection pass."""
    ltf_crt_ranges = detect_crt_ranges(m15, config.crt_range)
    model1_signals = detect_model1_signals(
        m15, config.crt_range, config.fvg, config.model1, crt_ranges=ltf_crt_ranges,
    )
    htf_crt_ranges = detect_crt_ranges(h4, config.crt_range)
    fvg_key_levels = fvg_to_key_levels(detect_fvgs(h4, config.fvg))
    daily_levels = daily_key_levels(daily, config, include_breaker=include_breaker)

    return tag_alignment(
        h4, m15, config.crt_range, config.fvg, config.model1,
        ltf_signals=model1_signals, htf_ranges=htf_crt_ranges,
        htf_key_levels=fvg_key_levels, daily_series=daily, daily_key_levels=daily_levels,
        credit_priority=credit_priority,
    )


def recipe_signals(
    m15: OHLCSeries, h4: OHLCSeries, daily: OHLCSeries, config: DetectorConfig, *,
    include_breaker: bool, credit_priority: dict[str, int] | None = None,
) -> list[AlignedSignal]:
    """Mirrors `order_block_redefinition_backtest.recipe_signals`'s own
    `reject_close_inside` filter -- the exact population the live scanner
    recipe considers, except for the one pool addition under test."""
    aligned = aligned_signals(
        m15, h4, daily, config, include_breaker=include_breaker, credit_priority=credit_priority,
    )
    return [
        signal for signal in aligned
        if signal.key_level is not None and signal.key_level_reaction == "reject_close_inside"
    ]


def credit_counts_by_kind(aligned: list[AlignedSignal]) -> dict[str, int]:
    """How many signals in the (unfiltered) aligned population were
    credited to each `KeyLevel.kind` -- the same measurement memory #782
    made directly against `_key_level_credit_map` ("FVG credits ~117,553
    ... Daily OB credits only 914") made reusable without touching that
    function's own internals."""
    counts: dict[str, int] = {}
    for signal in aligned:
        if signal.key_level is None:
            continue
        counts[signal.key_level.kind] = counts.get(signal.key_level.kind, 0) + 1
    return counts


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m experimental.breaker_block_key_level_backtest",
        description=(
            "EXPERIMENTAL: run the recipe's own reject_close_inside "
            "population through backtest.simulate.simulate, comparing "
            "the Daily-tier Key Level pool with and without Breaker "
            "Block -- nothing else changes."
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
    arms: list[tuple[str, bool, dict[str, int] | None]] = [
        ("without breaker", False, None),
        ("with breaker (recency)", True, None),
        ("with breaker (priority)", True, {"breaker_block": 1}),
    ]
    for label, include_breaker, credit_priority in arms:
        aligned = aligned_signals(
            m15, h4, daily, config, include_breaker=include_breaker, credit_priority=credit_priority,
        )
        signals = [
            signal for signal in aligned
            if signal.key_level is not None and signal.key_level_reaction == "reject_close_inside"
        ]
        trades, _ = simulate(signals, m15, config)
        stats = trade_stats(trades)
        counts = credit_counts_by_kind(aligned)
        print(
            f"{label:<24} signals={len(signals):<6} trades={stats['trades']:<6} "
            f"closed={stats['closed']:<6} win_rate={stats['win_rate']:.4f} "
            f"avg_r={stats['avg_r']:+.4f} total_r={stats['total_r']:+.2f} "
            f"credits={counts}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
