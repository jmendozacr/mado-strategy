"""Rolling-window prop-firm sizing simulator -- RESEARCH TOOLING, not a
production entry point.

RECONSTRUCTED, NOT RECOVERED. The memory record
`prop-firm-sizing-rolling-window-vs-aggregate` describes the methodology
as "a rolling simulation across every possible historical starting day,
capped at the challenge's real max window, measuring the worst-case
drawdown within ANY such window, at a given risk%, against the static
daily-5%-loss and the phase's own max-DD limit". The implementation that
produced that record's numbers is lost. What follows is a rebuild from
that sentence; the window length (250 days, Phase 1 + Phase 2 combined)
and the static-from-initial-balance basis are VERIFIED user-confirmed
parameters, everything else marked RECONSTRUCTED below is not.

Why a rolling window at all
---------------------------
Aggregate statistics over the whole backtest answer "was this edge
profitable". A prop-firm challenge asks a strictly harder question: "would
this edge have survived a FIXED-LENGTH window starting on the one day I
happened to start". A strategy can have a better Calmar ratio and a better
per-trade expectancy and still fail more often, because the thing that
fails an account is a local cluster of losses, not a lifetime average.
This simulator measures that directly: it starts a fresh notional account
on every possible historical day and counts how many of them would have
breached.

Algorithm
---------
1. Keep only RESOLVED trades. An unresolved trade never realised a P&L, so
   it cannot move an equity curve.
2. Attribute each trade's P&L to the NY-local session date it CLOSED on --
   realised P&L lands when the position closes, not when it opened.
3. Enumerate start days: every calendar date `d` (weekends included -- a
   challenge can be started on any day) such that the full window
   `[d, d + window_days - 1]` still fits inside the span from the first to
   the last realised trade date. PARTIAL windows at the end of the series
   are excluded: they would carry less exposure than a real challenge and
   would dilute the fail rate downward.
4. Within each window, start a notional account at balance 1.0 and walk its
   trades in close order. Each trade moves the balance by
   `r_multiple * risk_per_trade_pct / 100` of the account's INITIAL
   balance -- non-compounding, because the limits this is measured against
   are themselves static from the initial balance (a compounding P&L
   measured against a static cap would mix two bases).
5. A window BREACHES the max-drawdown cap when its worst drawdown, measured
   on `drawdown_basis`, reaches the cap. It breaches the daily-loss cap when
   any single session day's net P&L reaches it. Both comparisons are
   inclusive: a prop firm's cap is the first losing value that is not
   allowed, not the first one past it.
6. `fail_dd_fraction` is breaching windows over all windows.

RECONSTRUCTED `drawdown_basis`. The record's two phrasings pull apart and
the lost code settled it one way; both are offered here because the choice
changes the answer by an order of magnitude and the reader is entitled to
see that:

- `"initial_balance_floor"` (default) -- the drawdown is how far the
  balance ever fell BELOW the window's own starting balance. This is the
  literal static FTMO-style rule the user confirmed: max loss is measured
  from the account's initial balance, never trailing.
- `"peak_to_trough"` -- the largest fall from any running high inside the
  window. This is the literal reading of the record's own phrase
  "worst-case drawdown within any such window", and it is strictly harsher:
  a window that runs up and then gives back more than the cap breaches,
  even though the account never dipped below where it started.

RECONSTRUCTED absence of a profit target. A real challenge STOPS when its
profit target is hit, which truncates exposure. The record mentions no
profit target, so none is modelled: every window is run for its full
length. This makes the reported fail rates conservative (an upper bound) --
modelling a target can only lower them.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal, Sequence

from research.eurusd_recipe_validation.trades import ClosedTrade, session_day

DrawdownBasis = Literal["initial_balance_floor", "peak_to_trough"]
_BASES: tuple[DrawdownBasis, ...] = ("initial_balance_floor", "peak_to_trough")


@dataclass(frozen=True)
class WindowOutcome:
    """One notional account, started on `start_date` and run for the full
    window. `worst_drawdown_r` is basis-dependent and risk-independent;
    `worst_drawdown_pct` is the same number priced at the run's risk%, and
    is what the cap is actually compared against."""

    start_date: date
    end_date: date
    trades: int
    total_r: float
    worst_drawdown_r: float
    worst_drawdown_pct: float
    worst_daily_loss_pct: float
    breached_max_drawdown: bool
    breached_daily_loss: bool


@dataclass(frozen=True)
class RollingWindowResult:
    risk_per_trade_pct: float
    max_drawdown_pct: float
    daily_loss_limit_pct: float
    window_days: int
    drawdown_basis: DrawdownBasis
    windows: tuple[WindowOutcome, ...]

    @property
    def fail_dd_fraction(self) -> float | None:
        """`None` -- never 0.0 -- when the series is too short to hold a
        single full window, so "no window failed" is never confused with
        "no window was measurable"."""
        if not self.windows:
            return None
        return sum(1 for w in self.windows if w.breached_max_drawdown) / len(self.windows)

    @property
    def fail_daily_loss_fraction(self) -> float | None:
        if not self.windows:
            return None
        return sum(1 for w in self.windows if w.breached_daily_loss) / len(self.windows)


def _window_outcome(
    rows: list[tuple[date, float]],
    start: date,
    window_days: int,
    risk_per_trade_pct: float,
    max_drawdown_pct: float,
    daily_loss_limit_pct: float,
    drawdown_basis: DrawdownBasis,
) -> WindowOutcome:
    end = start + timedelta(days=window_days - 1)
    equity_r = peak_r = 0.0
    worst_floor_r = worst_peak_to_trough_r = 0.0
    total_r = 0.0
    count = 0
    by_day: dict[date, float] = {}

    for close_date, r_multiple in rows:
        if close_date < start or close_date > end:
            continue
        count += 1
        total_r += r_multiple
        equity_r += r_multiple
        peak_r = max(peak_r, equity_r)
        worst_floor_r = max(worst_floor_r, -equity_r)
        worst_peak_to_trough_r = max(worst_peak_to_trough_r, peak_r - equity_r)
        by_day[close_date] = by_day.get(close_date, 0.0) + r_multiple

    worst_drawdown_r = (
        worst_floor_r if drawdown_basis == "initial_balance_floor" else worst_peak_to_trough_r
    )
    worst_drawdown_pct = worst_drawdown_r * risk_per_trade_pct
    worst_daily_loss_pct = max(0.0, -min(by_day.values(), default=0.0)) * risk_per_trade_pct

    return WindowOutcome(
        start_date=start,
        end_date=end,
        trades=count,
        total_r=total_r,
        worst_drawdown_r=worst_drawdown_r,
        worst_drawdown_pct=worst_drawdown_pct,
        worst_daily_loss_pct=worst_daily_loss_pct,
        breached_max_drawdown=worst_drawdown_pct >= max_drawdown_pct,
        breached_daily_loss=worst_daily_loss_pct >= daily_loss_limit_pct,
    )


def simulate_rolling_windows(
    trades: Sequence[ClosedTrade],
    *,
    risk_per_trade_pct: float,
    max_drawdown_pct: float,
    daily_loss_limit_pct: float = 5.0,
    window_days: int = 250,
    drawdown_basis: DrawdownBasis = "initial_balance_floor",
) -> RollingWindowResult:
    """Percentages are in percent, not fractions: `risk_per_trade_pct=0.5`
    is half a percent of the account per trade, `max_drawdown_pct=10.0` is
    the Phase-1 cap."""
    if drawdown_basis not in _BASES:
        raise ValueError(f"unknown drawdown_basis: {drawdown_basis!r}, expected one of {_BASES}")

    rows = sorted(
        (session_day(trade.exit_time), trade.r_multiple)
        for trade in trades
        if trade.exit_time is not None and trade.r_multiple is not None
    )

    starts: list[date] = []
    if rows:
        first, last = rows[0][0], rows[-1][0]
        start = first
        while start + timedelta(days=window_days - 1) <= last:
            starts.append(start)
            start += timedelta(days=1)

    windows = tuple(
        _window_outcome(
            rows, start, window_days, risk_per_trade_pct,
            max_drawdown_pct, daily_loss_limit_pct, drawdown_basis,
        )
        for start in starts
    )
    return RollingWindowResult(
        risk_per_trade_pct=risk_per_trade_pct,
        max_drawdown_pct=max_drawdown_pct,
        daily_loss_limit_pct=daily_loss_limit_pct,
        window_days=window_days,
        drawdown_basis=drawdown_basis,
        windows=windows,
    )
