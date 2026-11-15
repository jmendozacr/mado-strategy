"""Rolling-window prop-firm survival check for the LIVE 1AM+9AM
diversified strategy (EURUSD+USDCAD+AUDUSD) -- RESEARCH TOOLING, not a
production entry point.

No rolling-window simulator existed for this strategy (only the OLD
EURUSD-only recipe has one, `research.eurusd_recipe_validation.sizing`).
Reuses that simulator's `sizing`/`daily_risk`/`trades` modules UNMODIFIED
-- only the per-pair-trades -> merged-account conversion is new here.

Scope decision, stated rather than hidden (matching this package's own
convention): `concurrency.simulate_bounded_concurrency` (the within-pair
2R-open gate) is NOT applied here. That gate compares `entry_index`/
`exit_index` bar positions, which are only meaningful within one
instrument's own M15 series -- comparing them across EURUSD/USDCAD/AUDUSD
directly would be comparing unrelated numbers. `daily_risk.
apply_daily_loss_stop` IS applied, account-wide across all three pairs
combined, because it keys on real calendar time (NY-local session date),
which merges correctly regardless of which pair's series a trade came
from.
"""
from __future__ import annotations

from backtest.simulate import Trade
from core.candle import OHLCSeries

from research.eurusd_recipe_validation.daily_risk import apply_daily_loss_stop
from research.eurusd_recipe_validation.sizing import RollingWindowResult, DrawdownBasis, simulate_rolling_windows
from research.eurusd_recipe_validation.trades import ClosedTrade, ordered

__all__ = ["to_closed_trades", "combined_rolling_window", "main"]


def to_closed_trades(trades: list[Trade], series: OHLCSeries) -> list[ClosedTrade]:
    """`backtest.simulate.Trade` carries bar indices into `series`; the
    rolling-window simulator needs real calendar timestamps -- resolves
    each trade's `entry_index`/`exit_index` against this series' own
    candles. An unresolved trade (`exit_index is None`) keeps
    `exit_time=None`, matching `ClosedTrade`'s own "still open" shape."""
    return [
        ClosedTrade(
            signal_id=trade.signal_id,
            direction=trade.direction,
            entry_index=trade.entry_index,
            exit_index=trade.exit_index,
            entry_time=series.candles[trade.entry_index].timestamp,
            exit_time=series.candles[trade.exit_index].timestamp if trade.exit_index is not None else None,
            outcome=trade.outcome,
            r_multiple=trade.r_multiple,
        )
        for trade in trades
    ]


def combined_rolling_window(
    trades_by_symbol: dict[str, tuple[list[Trade], OHLCSeries]],
    *,
    risk_per_trade_pct: float,
    max_drawdown_pct: float = 10.0,
    daily_loss_limit_pct: float = 5.0,
    window_days: int = 250,
    drawdown_basis: DrawdownBasis = "initial_balance_floor",
    max_losses_per_day: int = 2,
) -> RollingWindowResult:
    """One notional account trading all of `trades_by_symbol`'s pairs
    together: converts each pair's `Trade` list to `ClosedTrade`s against
    its OWN series, merges them (safe -- `ClosedTrade.entry_time`/
    `exit_time` are real calendar timestamps, comparable across any
    series), applies the account-wide daily-loss stop, then runs the
    existing rolling-window simulator over the merged, gated population."""
    merged: list[ClosedTrade] = []
    for trades, series in trades_by_symbol.values():
        merged += to_closed_trades(trades, series)

    gated = apply_daily_loss_stop(ordered(merged), max_losses_per_day=max_losses_per_day)

    return simulate_rolling_windows(
        gated,
        risk_per_trade_pct=risk_per_trade_pct,
        max_drawdown_pct=max_drawdown_pct,
        daily_loss_limit_pct=daily_loss_limit_pct,
        window_days=window_days,
        drawdown_basis=drawdown_basis,
    )


def main(argv: list[str] | None = None) -> int:
    import argparse

    from experimental.htf_trigger_1am_9am_backtest import SYMBOL_CONFIG, backtest_1am_9am, _find_csv
    from backtest.simulate import simulate
    from core.config import DetectorConfig
    from ingestion.loader import load_mt5_csv
    from ingestion.pairing import load_pair

    parser = argparse.ArgumentParser(
        description="Rolling-window prop-firm survival for the live 1AM+9AM diversified strategy.",
    )
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--symbols", default="EURUSD,USDCAD,AUDUSD")
    parser.add_argument("--risk-levels", default="0.5,0.75,1.0")
    parser.add_argument("--max-drawdown-pct", type=float, default=10.0)
    parser.add_argument("--window-days", type=int, default=250)
    args = parser.parse_args(argv)

    trades_by_symbol: dict[str, tuple[list[Trade], OHLCSeries]] = {}
    for symbol in args.symbols.split(","):
        h4_csv = _find_csv(args.data_dir, symbol, "H4")
        m15_csv = _find_csv(args.data_dir, symbol, "M15")
        d1_csv = _find_csv(args.data_dir, symbol, "D1")
        h4, m15 = load_pair(htf_csv=h4_csv, htf_symbol=symbol, ltf_csv=m15_csv, ltf_symbol=symbol)
        daily = load_mt5_csv(d1_csv, symbol=symbol)

        config = DetectorConfig(backtest=SYMBOL_CONFIG[symbol])
        aligned_signals, _model_by_id = backtest_1am_9am(m15, h4, daily, config)
        trades, _ = simulate(aligned_signals, m15, config)
        trades_by_symbol[symbol] = (trades, m15)
        print(f"{symbol}: {len(trades)} trades", flush=True)

    for risk_pct in (float(r) for r in args.risk_levels.split(",")):
        result = combined_rolling_window(
            trades_by_symbol, risk_per_trade_pct=risk_pct,
            max_drawdown_pct=args.max_drawdown_pct, window_days=args.window_days,
        )
        fail = result.fail_dd_fraction
        fail_daily = result.fail_daily_loss_fraction
        print(
            f"risk={risk_pct:.2f}% windows={len(result.windows):<6} "
            f"fail_dd={'n/a' if fail is None else f'{fail:.1%}'} "
            f"fail_daily_loss={'n/a' if fail_daily is None else f'{fail_daily:.1%}'}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
