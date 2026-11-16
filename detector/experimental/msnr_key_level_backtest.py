"""EXPERIMENTAL backtest comparison: MSNR (Malaysian Support & Resistance)
A-shape/V-shape key levels REPLACING FVG/Order Block entirely -- user's
own framing (odd/tasks/msnr-key-levels.md S2): "probar esos key levels
apagando o no usando los FVG/OB", a standalone read on MSNR's own signal
quality, independent of the already-confirmed FVG-density bias in
`alignment.htf_ltf._key_level_credit_map`'s recency tiebreak (memory
#782, reconfirmed 4x this project's history for every "ADD another
source to the same pool" attempt -- Breaker Block, OB anchor variant,
OB-on-H4, zone-rejection, all null for that one structural reason).
Replacing removes that confound entirely: MSNR is the ONLY source in the
pool for either arm's "msnr only" run, so a null result here would mean
something different (MSNR itself lacks signal, not that FVG drowned it).

Same simplified wiring as `breaker_block_key_level_backtest.py`
(`entries.model1.detect_model1_signals` -> `alignment.htf_ltf.tag_alignment`)
for apples-to-apples comparability. Not a change to anything beyond
`primitives/msnr_levels.py` and the additive `core/key_level.py`
Literal/`core/config.py` field: no other production file touched.
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
from entries.model1 import detect_model1_signals
from primitives.crt_range import detect_crt_ranges
from primitives.fvg import detect_fvgs, to_key_levels as fvg_to_key_levels
from primitives.msnr_levels import (
    detect_msnr_levels, to_key_levels as msnr_to_key_levels,
    to_key_levels_with_sbr_rbs as msnr_to_key_levels_sbr_rbs,
)

from experimental.order_block_redefinition_backtest import trade_stats

__all__ = [
    "daily_key_levels", "htf_key_levels", "aligned_signals", "recipe_signals",
    "credit_counts_by_kind", "trade_stats", "main",
]


def _msnr_key_levels(series: OHLCSeries, config: DetectorConfig, *, sbr_rbs: bool) -> list[KeyLevel]:
    levels = detect_msnr_levels(series)
    if sbr_rbs:
        return msnr_to_key_levels_sbr_rbs(levels, series.candles, config.msnr)
    return msnr_to_key_levels(levels, series.candles, config.msnr)


def daily_key_levels(
    daily_series: OHLCSeries, config: DetectorConfig, *, use_msnr: bool, sbr_rbs: bool = False,
) -> list[KeyLevel]:
    if use_msnr:
        return _msnr_key_levels(daily_series, config, sbr_rbs=sbr_rbs)
    return order_block_to_key_levels(detect_order_blocks(daily_series))


def htf_key_levels(
    h4_series: OHLCSeries, config: DetectorConfig, *, use_msnr: bool, sbr_rbs: bool = False,
) -> list[KeyLevel]:
    if use_msnr:
        return _msnr_key_levels(h4_series, config, sbr_rbs=sbr_rbs)
    return fvg_to_key_levels(detect_fvgs(h4_series, config.fvg))


def aligned_signals(
    m15: OHLCSeries, h4: OHLCSeries, daily: OHLCSeries, config: DetectorConfig, *,
    use_msnr: bool, sbr_rbs: bool = False,
) -> list[AlignedSignal]:
    """The full tagged population, unfiltered by reaction type -- shared
    by `recipe_signals` and `credit_counts_by_kind`, so neither needs its
    own detection pass. LTF entry detection is untouched by `use_msnr`:
    only the HTF/Daily KEY LEVEL pools swap source."""
    ltf_crt_ranges = detect_crt_ranges(m15, config.crt_range)
    model1_signals = detect_model1_signals(
        m15, config.crt_range, config.fvg, config.model1, crt_ranges=ltf_crt_ranges,
    )
    htf_crt_ranges = detect_crt_ranges(h4, config.crt_range)
    htf_levels = htf_key_levels(h4, config, use_msnr=use_msnr, sbr_rbs=sbr_rbs)
    daily_levels = daily_key_levels(daily, config, use_msnr=use_msnr, sbr_rbs=sbr_rbs)

    return tag_alignment(
        h4, m15, config.crt_range, config.fvg, config.model1,
        ltf_signals=model1_signals, htf_ranges=htf_crt_ranges,
        htf_key_levels=htf_levels, daily_series=daily, daily_key_levels=daily_levels,
    )


def recipe_signals(
    m15: OHLCSeries, h4: OHLCSeries, daily: OHLCSeries, config: DetectorConfig, *,
    use_msnr: bool, sbr_rbs: bool = False,
) -> list[AlignedSignal]:
    """Mirrors the live recipe's own `reject_close_inside` filter -- the
    exact population the live scanner recipe considers, except for the
    Key Level source under test."""
    aligned = aligned_signals(m15, h4, daily, config, use_msnr=use_msnr, sbr_rbs=sbr_rbs)
    return [
        signal for signal in aligned
        if signal.key_level is not None and signal.key_level_reaction == "reject_close_inside"
    ]


def credit_counts_by_kind(aligned: list[AlignedSignal]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for signal in aligned:
        if signal.key_level is None:
            continue
        counts[signal.key_level.kind] = counts.get(signal.key_level.kind, 0) + 1
    return counts


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m experimental.msnr_key_level_backtest",
        description=(
            "EXPERIMENTAL: run the recipe's own reject_close_inside "
            "population through backtest.simulate.simulate, comparing "
            "today's FVG/Order Block Key Level pool against MSNR "
            "A-shape/V-shape REPLACING it entirely -- nothing else changes."
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
    arms = (
        ("FVG/OB (current)", False, False),
        ("MSNR only", True, False),
        ("MSNR + SBR/RBS", True, True),
    )
    for label, use_msnr, sbr_rbs in arms:
        aligned = aligned_signals(m15, h4, daily, config, use_msnr=use_msnr, sbr_rbs=sbr_rbs)
        signals = [
            signal for signal in aligned
            if signal.key_level is not None and signal.key_level_reaction == "reject_close_inside"
        ]
        trades, _ = simulate(signals, m15, config)
        stats = trade_stats(trades)
        counts = credit_counts_by_kind(aligned)
        print(
            f"{label:<20} signals={len(signals):<6} trades={stats['trades']:<6} "
            f"closed={stats['closed']:<6} win_rate={stats['win_rate']:.4f} "
            f"avg_r={stats['avg_r']:+.4f} total_r={stats['total_r']:+.2f} "
            f"credits={counts}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
