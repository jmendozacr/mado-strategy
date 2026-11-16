"""EXPERIMENTAL: backtest harness for the LIVE 1AM+9AM diversified
strategy -- `causal.htf_trigger.find_1am_9am_aligned_signals`, what
`scanner/main.py` polls MT5 for and alerts on -- which has no
backtest/historical-replay tool of its own. Every prior "1AM+9AM
diversification test" measurement this session (R:R floor sweep, FTMO
rolling-window, monthly breakdown) was done with a throwaway scratch
script, never committed; this is the first tested, reusable version.

Reuses, never reimplements: `causal.htf_trigger.find_1am_9am_aligned_
signals` (the trigger), `backtest.simulate.simulate` (resolution, which
calls `backtest.population.build_stage6_population` itself). No
production file touched.
"""
from __future__ import annotations

import argparse

from alignment.htf_ltf import AlignedSignal, _reindex_daily_key_levels
from backtest.simulate import simulate
from causal.htf_trigger import find_1am_9am_aligned_signals
from composite.ict_order_block import detect_order_blocks
from composite.ict_order_block import to_key_levels as ob_to_key_levels
from core.candle import OHLCSeries
from core.config import BacktestConfig, DetectorConfig, FVGConfig
from core.key_level import KeyLevel
from primitives.fvg import detect_fvgs, to_key_levels as fvg_to_key_levels

__all__ = ["build_key_levels", "backtest_1am_9am", "trade_stats", "main"]


def build_key_levels(htf_series: OHLCSeries, daily_series: OHLCSeries, fvg_config: FVGConfig) -> list[KeyLevel]:
    """Byte-for-byte `scanner.main._build_key_levels` -- HTF FVGs +
    Daily-tier Order Blocks reindexed to HTF-index-space -- replicated
    rather than imported because `scanner/main.py` pulls in MT5-only
    dependencies (`mt5_feed`, `telegram_notify`, ...) this suite cannot
    load."""
    htf_fvg_levels = fvg_to_key_levels(detect_fvgs(htf_series, fvg_config))
    daily_ob_levels = ob_to_key_levels(detect_order_blocks(daily_series))
    htf_timestamps = [c.timestamp for c in htf_series.candles]
    reindexed_daily = _reindex_daily_key_levels(
        daily_ob_levels, daily_series.candles, htf_series.candles, htf_timestamps
    )
    return htf_fvg_levels + reindexed_daily


def backtest_1am_9am(
    m15: OHLCSeries, h4: OHLCSeries, daily: OHLCSeries, config: DetectorConfig,
) -> tuple[list[AlignedSignal], dict[str, str]]:
    """The exact construction `scanner.main.run_once` uses, minus the
    live polling/alerting/execution machinery around it. Returns the
    aligned signals (feed straight into `backtest.simulate.simulate`)
    plus a `signal_id -> model` map for a per-model breakdown."""
    key_levels = build_key_levels(h4, daily, config.fvg)
    results = find_1am_9am_aligned_signals(h4.candles, m15, key_levels, config.crt_range, config.model1)
    aligned_signals = [aligned for aligned, _model in results]
    model_by_id = {aligned.ltf_signal.signal_id: model for aligned, model in results}
    return aligned_signals, model_by_id


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


# scanner/main.py's own validated per-symbol config (odd/tasks/
# scanner-1am-9am-diversified.md S2), keyed by the plain (non-broker-
# suffixed) symbol name this harness's own CLI uses.
SYMBOL_CONFIG: dict[str, BacktestConfig] = {
    "EURUSD": BacktestConfig(
        min_risk_reward=2.0, trading_cost_price=0.00013, kill_zone_gated=False, min_stop_distance_price=0.0006, breakeven_after_partial=True,
    ),
    # USDCAD/AUDUSD: calibrated 2026-11-16 (SL-floor swept 0/4/6/10 pips on
    # the 2022-2026 window) -- neither had a floor before, which let stops
    # go as tight as 1.6 pips and let the fixed trading_cost_price eat up
    # to 104% of the intended 1R (USDCAD) on the worst trades. 6 pips won
    # for USDCAD (matches EURUSD/GBPUSD's own winning floor); AUDUSD's own
    # sweep instead favored 4 pips -- kept as its own measured value
    # rather than copying USDCAD's, per that sweep's own total_r numbers.
    "USDCAD": BacktestConfig(
        min_risk_reward=2.0, trading_cost_price=0.000167, kill_zone_gated=False, min_stop_distance_price=0.0006, breakeven_after_partial=True,
    ),
    "AUDUSD": BacktestConfig(
        min_risk_reward=2.0, trading_cost_price=0.00013, kill_zone_gated=False, min_stop_distance_price=0.0004, breakeven_after_partial=True,
    ),
    # GBPUSD/USDJPY: calibrated this session (SL-floor swept 0/4/6/10 pips
    # on the 2019-2026 window, 6 pips won on total R for both -- same
    # pattern as EURUSD's own winning floor). trading_cost_price is an
    # ESTIMATE from web research (FTMO Standard-account average spread,
    # ~0.5 pip GBPUSD / ~1.0 pip USDJPY, padded with the same safety
    # margin EURUSD's own verified cost implicitly carries over its own
    # quoted average), NOT independently verified against FTMO's live
    # platform -- unlike EURUSD/USDCAD/AUDUSD's costs. USDJPY's floor is
    # scaled 100x (pip=0.01, not 0.0001) for the yen's price scale.
    "GBPUSD": BacktestConfig(
        min_risk_reward=2.0, trading_cost_price=0.00014, kill_zone_gated=False, min_stop_distance_price=0.0006, breakeven_after_partial=True,
    ),
    # USDJPY's own floor re-checked in the same 2026-11-16 sweep (6/10/15/20
    # pips): 10 pips beat the original 6-pip floor on total_r, so raised.
    "USDJPY": BacktestConfig(
        min_risk_reward=2.0, trading_cost_price=0.0275, kill_zone_gated=False, min_stop_distance_price=0.10, breakeven_after_partial=True,
    ),
}
# PENDING (not yet applied): scanner/main.py's own BACKTEST_CONFIG is a
# separate, hand-mirrored dict (not imported from here) and still has the
# pre-2026-11-16 USDCAD/AUDUSD/USDJPY floors -- the live scanner has NOT
# picked up this calibration yet. Apply the same three values there (and
# anywhere else SYMBOL_CONFIG gets hand-copied) before relying on it live.


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m experimental.htf_trigger_1am_9am_backtest",
        description="EXPERIMENTAL: backtest the live 1AM+9AM diversified strategy over historical data.",
    )
    parser.add_argument("--data-dir", required=True, help="Directory holding <SYMBOL>_{D1,H4,M15}_*.csv files")
    parser.add_argument("--symbols", default="EURUSD,USDCAD,AUDUSD")
    return parser


def _find_csv(data_dir: str, symbol: str, timeframe: str) -> str:
    import glob
    import os

    matches = glob.glob(os.path.join(data_dir, f"{symbol}_{timeframe}_*.csv"))
    if not matches:
        raise FileNotFoundError(f"no {timeframe} CSV for {symbol} under {data_dir}")
    return matches[0]


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    from ingestion.loader import load_mt5_csv
    from ingestion.pairing import load_pair

    combined_trades = []
    for symbol in args.symbols.split(","):
        h4_csv = _find_csv(args.data_dir, symbol, "H4")
        m15_csv = _find_csv(args.data_dir, symbol, "M15")
        d1_csv = _find_csv(args.data_dir, symbol, "D1")
        h4, m15 = load_pair(htf_csv=h4_csv, htf_symbol=symbol, ltf_csv=m15_csv, ltf_symbol=symbol)
        daily = load_mt5_csv(d1_csv, symbol=symbol)

        config = DetectorConfig(backtest=SYMBOL_CONFIG[symbol])
        aligned_signals, _model_by_id = backtest_1am_9am(m15, h4, daily, config)
        trades, _ = simulate(aligned_signals, m15, config)
        stats = trade_stats(trades)
        combined_trades += trades
        print(
            f"{symbol:<10} signals={len(aligned_signals):<6} trades={stats['trades']:<6} "
            f"closed={stats['closed']:<6} win_rate={stats['win_rate']:.4f} "
            f"avg_r={stats['avg_r']:+.4f} total_r={stats['total_r']:+.2f}"
        )

    combined = trade_stats(combined_trades)
    print(
        f"{'COMBINED':<10} {'':<14}trades={combined['trades']:<6} "
        f"closed={combined['closed']:<6} win_rate={combined['win_rate']:.4f} "
        f"avg_r={combined['avg_r']:+.4f} total_r={combined['total_r']:+.2f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
