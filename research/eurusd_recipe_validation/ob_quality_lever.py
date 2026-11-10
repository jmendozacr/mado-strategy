"""EXPERIMENTAL quality-over-quantity lever, user-motivated (2026-11-10):
"ando buscando calidad sobre cantidad" -- the original question behind
this whole branch's Key Level investigation. Every quality-over-quantity
lever tested in September (R:R floor, Daily zone-width, NY-only session
-- see README.md/REPORT.md) ran against the ARCHIVED Order Block
detector. This one is the first to run against the REDEFINED detector
(`detector-order-block-redefinition`'s walking skeleton, ~3x the real
structural-break confirmation rate) -- filtering the recipe to ONLY
signals the redefined OB itself credits (`key_level.kind ==
"ict_order_block"`), pooled natively with FVG on H4 (not the Daily tier,
too sparse to sample at all) so the subset has a workable sample size.

Same rigor as `compare.py`: resolved through `backtest.simulate.simulate`
unmodified, the SAME two reconstructed account-level gates
(`concurrency.py`/`daily_risk.py`), and judged on the rolling-window
prop-firm survival simulation (`sizing.py`) -- never on aggregate stats
alone, per this project's own established discipline (every prior lever
that looked good on aggregate stats failed the windowed check).

RESEARCH TOOLING, not a production entry point. Reuses, never
reimplements.
"""
from __future__ import annotations

import argparse
import dataclasses
import os

from core.config import DetectorConfig
from backtest.simulate import simulate

from experimental.order_block_redefinition_backtest import recipe_signals_htf_pooled

from research.eurusd_recipe_validation.concurrency import simulate_bounded_concurrency
from research.eurusd_recipe_validation.daily_risk import apply_daily_loss_stop
from research.eurusd_recipe_validation.pipeline import (
    BASELINE,
    aggregate_stats,
    load_series,
    recipe_signals,
)
from research.eurusd_recipe_validation.sizing import simulate_rolling_windows
from research.eurusd_recipe_validation.trades import ClosedTrade

DEFAULT_H4 = os.path.join("pairs", "H4", "EURUSDm_H4_202001020000_202609042000.csv")
DEFAULT_M15 = os.path.join("pairs", "M15", "EURUSDm_M15_202207260000_202609042045.csv")
DEFAULT_DAILY = os.path.join("pairs", "D1", "EURUSDm_Daily_202001020000_202609040000.csv")

RISK_LEVELS: tuple[float, ...] = (0.50, 0.75, 1.00)
PHASE_1_MAX_DD_PCT = 10.0
DAILY_LOSS_LIMIT_PCT = 5.0
WINDOW_DAYS = 250
DRAWDOWN_BASIS = "initial_balance_floor"  # the user-confirmed static rule (see README.md)
PARTIAL_FRACTIONS: tuple[float, ...] = (0.0, 0.5)  # both published, same rigor as compare.py --
# "the exit model is load-bearing for the conclusion" (README.md)


def _gated_closed_trades(trades, m15) -> list[ClosedTrade]:
    """Mirrors `pipeline.build_variant`'s own Trade->ClosedTrade conversion
    and gate order exactly (concurrency, then daily-loss-stop)."""
    candles = m15.candles
    population = [
        ClosedTrade(
            signal_id=trade.signal_id,
            direction=trade.direction,
            entry_index=trade.entry_index,
            exit_index=trade.exit_index,
            entry_time=candles[trade.entry_index].timestamp,
            exit_time=None if trade.exit_index is None else candles[trade.exit_index].timestamp,
            outcome=trade.outcome,
            r_multiple=trade.r_multiple,
        )
        for trade in trades
    ]
    return apply_daily_loss_stop(simulate_bounded_concurrency(population))


def _report_row(label: str, closed_trades: list[ClosedTrade]) -> None:
    stats = aggregate_stats(tuple(closed_trades))
    print(f"\n--- {label} ---")
    print(
        f"trades={stats.trades} win_rate={stats.win_rate if stats.win_rate else 0:.4f} "
        f"avg_r={stats.average_r if stats.average_r else 0:+.4f} total_r={stats.total_r:+.2f} "
        f"max_dd_r={stats.max_drawdown_r:.2f} calmar={stats.calmar_ratio if stats.calmar_ratio else 0:.2f}"
    )
    for risk in RISK_LEVELS:
        window_result = simulate_rolling_windows(
            tuple(closed_trades), risk_per_trade_pct=risk, max_drawdown_pct=PHASE_1_MAX_DD_PCT,
            daily_loss_limit_pct=DAILY_LOSS_LIMIT_PCT, window_days=WINDOW_DAYS, drawdown_basis=DRAWDOWN_BASIS,
        )
        fail = window_result.fail_dd_fraction
        print(f"  risk={risk:.2f}%  windows={len(window_result.windows):<5}  fail_dd={('n/a' if fail is None else f'{fail*100:.1f}%')}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--h4-csv", default=DEFAULT_H4)
    parser.add_argument("--m15-csv", default=DEFAULT_M15)
    parser.add_argument("--daily-csv", default=DEFAULT_DAILY)
    parser.add_argument("--symbol", default="EURUSDm")
    args = parser.parse_args(argv)

    print(f"loading {args.symbol} series", flush=True)
    m15, h4, daily = load_series(args.h4_csv, args.m15_csv, args.daily_csv, args.symbol)
    base_config = DetectorConfig()

    # Detection + the OB-only selection run ONCE per exit model is unaffected
    # by partial_fraction (it only touches exit resolution) -- but to keep
    # this script simple and match compare.py's own per-fraction loop
    # structure, selection is recomputed per fraction too (cheap: it's the
    # existing pipeline, no new detection pass).
    for partial_fraction in PARTIAL_FRACTIONS:
        print(f"\n===== partial_fraction={partial_fraction} =====", flush=True)
        config = dataclasses.replace(
            base_config,
            backtest=dataclasses.replace(
                base_config.backtest, partial_fraction=partial_fraction, kill_zone_gated=False,
            ),
        )

        baseline_signals = recipe_signals(m15, h4, daily, config)
        baseline_trades, _ = simulate(baseline_signals, m15, config)
        _report_row(BASELINE.label, _gated_closed_trades(baseline_trades, m15))

        pooled_signals = recipe_signals_htf_pooled(m15, h4, config, redefined=True)
        ob_only_signals = [s for s in pooled_signals if s.key_level.kind == "ict_order_block"]
        ob_trades, _ = simulate(ob_only_signals, m15, config)
        _report_row(
            f"Lever: redefined OB only ({len(ob_only_signals)} signals)",
            _gated_closed_trades(ob_trades, m15),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
