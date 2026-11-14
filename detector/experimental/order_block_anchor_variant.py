"""EXPERIMENTAL: alternate Order Block anchor-selection rule -- "most
extreme candle in the impulse leg" (`smartmoneyconcepts`'s own `ob()`,
github.com/joshyattridge/smart-money-concepts) instead of this
codebase's own "nearest opposite-colored candle before displacement"
(`composite/order_block_scan.py::scan_for_anchor`).

Reuses `detect_swings`/`detect_mss_events`/`confirm_displacement`/
`_resolve_lifecycle` UNMODIFIED -- only the anchor step changes. Not
wired into production: a diagnostic, legal to import any production
layer per `.importlinter`'s own top-layer design, never the reverse.
"""
from __future__ import annotations

from typing import Literal

from alignment.htf_ltf import AlignedSignal, tag_alignment
from backtest.simulate import simulate
from composite.displacement import confirm_displacement
from composite.ict_order_block import ICTOrderBlock, Status, _resolve_lifecycle
from composite.ict_order_block import detect_order_blocks
from composite.ict_order_block import to_key_levels as order_block_to_key_levels
from composite.mss import MSSEvent, detect_mss_events
from core.candle import Candle, OHLCSeries
from core.config import DetectorConfig
from core.key_level import KeyLevel
from entries.model1 import detect_model1_signals
from primitives.crt_range import detect_crt_ranges
from primitives.fvg import detect_fvgs, to_key_levels as fvg_to_key_levels
from primitives.swing import SwingPoint, detect_swings

from experimental.order_block_redefinition_backtest import trade_stats

Direction = Literal["bullish", "bearish"]

__all__ = ["extreme_anchor", "detect_order_blocks_extreme_anchor", "daily_key_levels", "recipe_signals", "trade_stats", "main"]


def extreme_anchor(
    candles: tuple[Candle, ...], swing_index: int, break_index: int, direction: Direction,
) -> int:
    """The candle with the most extreme price strictly between the
    broken swing and the break candle -- a bullish OB anchors on the
    LOWEST low in that span (the deepest point of the pullback before
    the impulse), a bearish OB on the HIGHEST high. Falls back to the
    candle immediately before the break when the span is empty (the
    break happens on the very next candle after the swing), mirroring
    smartmoneyconcepts' own default-index behavior rather than raising
    or returning `None`."""
    start, end = swing_index + 1, break_index
    if end <= start:
        return break_index - 1
    if direction == "bullish":
        return min(range(start, end), key=lambda i: candles[i].low)
    return max(range(start, end), key=lambda i: candles[i].high)


def detect_order_blocks_extreme_anchor(
    series: OHLCSeries,
    swings: list[SwingPoint] | None = None,
    mss_events: list[MSSEvent] | None = None,
) -> list[ICTOrderBlock]:
    """Byte-for-byte `composite.ict_order_block.detect_order_blocks`
    except for the one swapped step: `extreme_anchor` in place of
    `composite.order_block_scan.scan_for_anchor`."""
    candles = series.candles
    if swings is None:
        swings = detect_swings(series)
    if mss_events is None:
        mss_events = detect_mss_events(series, swings=swings)

    blocks = []
    for event in mss_events:
        confirmation_index = confirm_displacement(candles, event.index, event.direction)
        if confirmation_index is None:
            continue
        anchor_index = extreme_anchor(candles, event.broken_swing.index, event.index, event.direction)
        anchor = candles[anchor_index]
        top, bottom = anchor.high, anchor.low
        mitigation_index, invalidation_index = _resolve_lifecycle(
            candles, confirmation_index, event.direction, top, bottom
        )
        status: Status = (
            "invalidated" if invalidation_index is not None
            else "mitigated" if mitigation_index is not None
            else "active"
        )
        blocks.append(
            ICTOrderBlock(
                anchor_index=anchor_index, break_index=event.index,
                confirmation_index=confirmation_index, direction=event.direction,
                top=top, bottom=bottom, status=status,
                mitigation_index=mitigation_index, invalidation_index=invalidation_index,
            )
        )
    return blocks


def daily_key_levels(daily_series: OHLCSeries, *, extreme: bool) -> list[KeyLevel]:
    """Mirrors `order_block_redefinition_backtest.daily_key_levels`'s own
    toggle shape: the Daily-tier Order Block pool `cli._detect_all` feeds
    into `tag_alignment`'s `daily_key_levels`."""
    blocks = (
        detect_order_blocks_extreme_anchor(daily_series) if extreme
        else detect_order_blocks(daily_series)
    )
    return order_block_to_key_levels(blocks)


def recipe_signals(
    m15: OHLCSeries, h4: OHLCSeries, daily: OHLCSeries, config: DetectorConfig, *, extreme: bool,
) -> list[AlignedSignal]:
    """Mirrors `order_block_redefinition_backtest.recipe_signals`'s own
    `reject_close_inside` filter -- the exact population the live scanner
    recipe considers, except for the one swapped anchor rule."""
    ltf_crt_ranges = detect_crt_ranges(m15, config.crt_range)
    model1_signals = detect_model1_signals(
        m15, config.crt_range, config.fvg, config.model1, crt_ranges=ltf_crt_ranges,
    )
    htf_crt_ranges = detect_crt_ranges(h4, config.crt_range)
    fvg_key_levels = fvg_to_key_levels(detect_fvgs(h4, config.fvg))
    order_block_key_levels = daily_key_levels(daily, extreme=extreme)

    aligned = tag_alignment(
        h4, m15, config.crt_range, config.fvg, config.model1,
        ltf_signals=model1_signals, htf_ranges=htf_crt_ranges,
        htf_key_levels=fvg_key_levels, daily_series=daily, daily_key_levels=order_block_key_levels,
    )
    return [
        signal for signal in aligned
        if signal.key_level is not None and signal.key_level_reaction == "reject_close_inside"
    ]


def _build_parser():
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m experimental.order_block_anchor_variant",
        description=(
            "EXPERIMENTAL: compare today's Order Block anchor rule "
            "(nearest opposite-colored candle) against smartmoneyconcepts' "
            "own rule (most extreme candle in the impulse leg) through the "
            "real recipe -- nothing else changes."
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
    for label, extreme in (("today (nearest opposite color)", False), ("extreme anchor (smc-style)", True)):
        signals = recipe_signals(m15, h4, daily, config, extreme=extreme)
        trades, _ = simulate(signals, m15, config)
        stats = trade_stats(trades)
        print(
            f"{label:<32} signals={len(signals):<6} trades={stats['trades']:<6} "
            f"closed={stats['closed']:<6} win_rate={stats['win_rate']:.4f} "
            f"avg_r={stats['avg_r']:+.4f} total_r={stats['total_r']:+.2f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
