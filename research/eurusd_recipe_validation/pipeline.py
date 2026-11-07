"""Variant construction over the detector's own, unmodified pipeline --
RESEARCH TOOLING, not a production entry point.

Nothing here detects, aligns, or resolves anything. Detection is
`cli._detect_all` (the exact function the live scanner calls), candidate
construction and trade resolution are `backtest.simulate.simulate` (which
calls `build_stage6_population` itself), the session test is copied from
`scanner/rules.py` and pinned to it by test, and the two account-level
gating rules are this package's own reconstructions. A "lever" is only ever
a filter over the aligned-signal population, or a value in
`BacktestConfig` -- never a reimplementation of a detector rule.

ONE FORCED DEVIATION from the library defaults, and it is load-bearing:
`kill_zone_gated` is set to False. `DetectorConfig()` defaults it to True,
which cuts the candidate population to the NY 07:00-11:00 kill zone inside
`build_stage6_population`. That gate is STRICTLY NARROWER than the
recipe's own 02:00-11:00 session, so with the default on, the recipe's
session filter changes nothing at all (1014 trades with or without it) and
the baseline cannot reconcile with the historical count of 1681. Turning
the gate off is what lets the recipe's stated session be the session that
governs. See README.md -- this is also a live/backtest mismatch worth the
reader's attention, not merely a knob.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import date

from alignment.htf_ltf import AlignedSignal
from backtest.simulate import simulate
from cli import _detect_all
from core.candle import OHLCSeries
from core.config import DetectorConfig
from experimental.key_level_reaction_redefinition import redefine_reaction
from ingestion.loader import load_mt5_csv
from ingestion.pairing import load_pair

from research.eurusd_recipe_validation.concurrency import simulate_bounded_concurrency
from research.eurusd_recipe_validation.daily_risk import apply_daily_loss_stop
from research.eurusd_recipe_validation.trades import (
    RECIPE_SESSION_END_HOUR,
    RECIPE_SESSION_START_HOUR,
    ClosedTrade,
    ny_hour,
    session_day,
)

# EURUSD quotes to 5 decimals, so one pip is 1e-4 -- the factor that turns a
# key level's price width into the pips lever B is specified in.
EURUSD_PIP_FACTOR = 10_000.0


@dataclass(frozen=True)
class VariantSpec:
    """One row of the comparison. `key` names its data files; `baseline` is
    the recipe actually running live."""

    key: str
    label: str
    session_start_hour: int = RECIPE_SESSION_START_HOUR
    session_end_hour: int = RECIPE_SESSION_END_HOUR
    max_key_level_zone_pips: float | None = None
    min_risk_reward: float = 2.0
    require_zone_rejection: bool = False
    """Candidate lever from the Key Level reaction redefinition probe
    (`experimental.key_level_reaction_redefinition`): every variant already
    starts from `reject_close_inside` vs the CRT RANGE
    (`recipe_signals`); this additionally requires the purge candle's close
    to have actually left the credited Key Level's own ZONE. Needs `htf`
    threaded through `build_variant` -- see that function's docstring."""


BASELINE = VariantSpec("baseline", "Baseline - the live, unfiltered recipe")

VARIANTS: tuple[VariantSpec, ...] = (
    BASELINE,
    VariantSpec("lever_a", "Lever A - R:R floor raised to 2.5 (RECONSTRUCTED value)", min_risk_reward=2.5),
    VariantSpec("lever_b", "Lever B - key-level zone width <= 25 pips", max_key_level_zone_pips=25.0),
    VariantSpec(
        "lever_c", "Lever C - NY-only session 07:00-11:00 (RECONSTRUCTED window)",
        session_start_hour=7, session_end_hour=11,
    ),
    VariantSpec(
        "lever_a_plus_b", "Levers A+B combined", max_key_level_zone_pips=25.0, min_risk_reward=2.5
    ),
    VariantSpec(
        "lever_d_zone_reject",
        "Lever D (candidate) - require genuine Key Level zone rejection, not just CRT-range close",
        require_zone_rejection=True,
    ),
)


def _filter_zone_rejection(
    signals: list[AlignedSignal], htf: OHLCSeries
) -> list[AlignedSignal]:
    """Lever D's filter, isolated so it is unit-testable without the full
    `simulate()` pass. Keeps only signals whose purge candle actually left
    the credited Key Level's zone -- see
    `experimental.key_level_reaction_redefinition` for the charter evidence
    (charter-1 [00:12:59]/charter-6 [00:03:25]) that today's
    `reject_close_inside` (CRT-range-relative) can let a non-rejecting
    close through."""
    return [
        signal for signal in signals
        if redefine_reaction(signal, htf.candles) == "reject_close_inside"
    ]


@dataclass(frozen=True)
class AggregateStats:
    """Non-windowed statistics over the whole backtest -- the view that
    favoured the rejected levers."""

    trades: int
    closed: int
    wins: int
    losses: int
    win_rate: float | None
    total_r: float
    average_r: float | None
    max_drawdown_r: float
    calmar_ratio: float | None
    first_close: date | None
    last_close: date | None


@dataclass(frozen=True)
class VariantResult:
    spec: VariantSpec
    signals: int
    trades_before_gating: int
    trades: tuple[ClosedTrade, ...]
    stats: AggregateStats


def load_series(
    h4_csv: str, m15_csv: str, daily_csv: str | None, symbol: str
) -> tuple[OHLCSeries, OHLCSeries, OHLCSeries | None]:
    """Returns `(m15, h4, daily)`. `daily_csv` is optional exactly as
    `cli._detect_all` makes it optional; with it the detector credits Daily
    order blocks as a separate key-level tier, without it they fold into
    the H4 tier."""
    h4, m15 = load_pair(htf_csv=h4_csv, htf_symbol=symbol, ltf_csv=m15_csv, ltf_symbol=symbol)
    daily = load_mt5_csv(daily_csv, symbol=symbol) if daily_csv else None
    return m15, h4, daily


def recipe_signals(
    m15: OHLCSeries, h4: OHLCSeries, daily: OHLCSeries | None, config: DetectorConfig
) -> list[AlignedSignal]:
    """Every aligned signal the live recipe would consider: it has a
    credited Key Level and its purge reacted with `reject_close_inside`.
    Detection runs ONCE here and every variant filters this one result."""
    detections = _detect_all(m15, h4, daily, config)
    return [
        signal
        for signal in (detections.aligned_signals or [])
        if signal.key_level is not None and signal.key_level_reaction == "reject_close_inside"
    ]


def aggregate_stats(trades: tuple[ClosedTrade, ...]) -> AggregateStats:
    """`calmar_ratio` is a RECONSTRUCTED definition -- the memory record
    quotes values but not a formula. Defined here as annualised R per year
    over the worst peak-to-trough R drawdown, which makes it independent of
    the risk% an account would have traded."""
    closed = [t for t in trades if t.outcome != "open" and t.r_multiple is not None]
    wins = sum(1 for t in closed if t.outcome == "win")
    losses = sum(1 for t in closed if t.outcome == "loss")
    total_r = sum(t.r_multiple for t in closed)

    equity = peak = max_drawdown = 0.0
    for trade in sorted(closed, key=lambda t: t.exit_time):
        equity += trade.r_multiple
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)

    dates = sorted(session_day(t.exit_time) for t in closed)
    first_close, last_close = (dates[0], dates[-1]) if dates else (None, None)
    years = (last_close - first_close).days / 365.25 if dates else 0.0
    calmar = (total_r / years) / max_drawdown if years > 0 and max_drawdown > 0 else None

    return AggregateStats(
        trades=len(trades),
        closed=len(closed),
        wins=wins,
        losses=losses,
        win_rate=wins / len(closed) if closed else None,
        total_r=total_r,
        average_r=total_r / len(closed) if closed else None,
        max_drawdown_r=max_drawdown,
        calmar_ratio=calmar,
        first_close=first_close,
        last_close=last_close,
    )


def build_variant(
    spec: VariantSpec,
    signals: list[AlignedSignal],
    m15: OHLCSeries,
    config: DetectorConfig,
    pip_factor: float = EURUSD_PIP_FACTOR,
    htf: OHLCSeries | None = None,
) -> VariantResult:
    """Filter the recipe population by this variant's levers, resolve it
    through the detector's own simulator, then apply the two reconstructed
    account-level gates in that order: concurrency first (an account cannot
    open a position it has no risk budget for), then the daily-loss stop
    (which can only ever react to positions that were actually opened).

    `htf` is optional for every existing lever and REQUIRED for
    `spec.require_zone_rejection` (lever D) -- raises rather than silently
    skipping the filter when it's missing."""
    if spec.require_zone_rejection and htf is None:
        raise ValueError(
            f"variant {spec.key!r} sets require_zone_rejection but build_variant "
            "was not given htf"
        )
    selected = [
        signal
        for signal in signals
        if spec.session_start_hour
        <= ny_hour(m15.candles[signal.ltf_signal.anchor_index].timestamp)
        < spec.session_end_hour
    ]
    if spec.max_key_level_zone_pips is not None:
        selected = [
            signal
            for signal in selected
            if (signal.key_level.top - signal.key_level.bottom) * pip_factor
            <= spec.max_key_level_zone_pips
        ]
    if spec.require_zone_rejection:
        selected = _filter_zone_rejection(selected, htf)

    variant_config = dataclasses.replace(
        config,
        backtest=dataclasses.replace(
            config.backtest,
            kill_zone_gated=False,  # see this module's docstring -- forced, not chosen
            min_risk_reward=spec.min_risk_reward,
        ),
    )
    resolved, _report = simulate(selected, m15, variant_config)

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
        for trade in resolved
    ]

    gated = apply_daily_loss_stop(simulate_bounded_concurrency(population))
    return VariantResult(
        spec=spec,
        signals=len(selected),
        trades_before_gating=len(population),
        trades=tuple(gated),
        stats=aggregate_stats(tuple(gated)),
    )
