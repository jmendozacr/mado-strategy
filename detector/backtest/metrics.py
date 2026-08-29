"""Backtest metrics — win rate, aggregate R, population-reconciliation
disclosure (REQ-33.2, 36.4, 36.5, 39, 48.3, 49).
"""

from dataclasses import dataclass
from typing import Literal

from core.config import BacktestConfig

from backtest.simulate import ReconciliationReport, Trade

KillZoneGateState = Literal["enabled", "auto-disabled", "disabled"]


@dataclass(frozen=True)
class BacktestMetrics:
    win_rate: float | None
    closed_trades: int
    open_trades: int
    wins: int
    losses: int
    average_r_multiple: float | None
    total_r: float | None
    ambiguous_bar_count: int
    kill_zone_gate_state: KillZoneGateState
    config: BacktestConfig
    reconciliation: ReconciliationReport


def compute_metrics(
    trades: list[Trade],
    reconciliation: ReconciliationReport,
    config: BacktestConfig,
    kill_zone_gate_state: KillZoneGateState,
) -> BacktestMetrics:
    wins = sum(1 for t in trades if t.outcome == "win")
    losses = sum(1 for t in trades if t.outcome == "loss")
    open_trades = sum(1 for t in trades if t.outcome == "open")
    closed_trades = wins + losses
    ambiguous_bar_count = sum(1 for t in trades if t.ambiguous_bar)

    win_rate = wins / closed_trades if closed_trades else None
    closed_r_multiples = [t.r_multiple for t in trades if t.outcome != "open"]
    average_r_multiple = sum(closed_r_multiples) / closed_trades if closed_trades else None
    total_r = sum(closed_r_multiples) if closed_trades else None

    return BacktestMetrics(
        win_rate=win_rate,
        closed_trades=closed_trades,
        open_trades=open_trades,
        wins=wins,
        losses=losses,
        average_r_multiple=average_r_multiple,
        total_r=total_r,
        ambiguous_bar_count=ambiguous_bar_count,
        kill_zone_gate_state=kill_zone_gate_state,
        config=config,
        reconciliation=reconciliation,
    )
