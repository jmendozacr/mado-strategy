"""Step 5: entry/stop/target/RR floor, fill (bounded by 15:00 NY), and
exit resolution -- every price-level formula and the fill/exit
primitives are reused UNMODIFIED from `backtest.levels`/
`backtest.simulate`/`core.sweep`; only the TARGET's own context object
is new (the reference candle's high/low instead of the original HTF
CRT range), never a new formula.
"""
from __future__ import annotations

import bisect
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

LAB_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = LAB_ROOT.parent.parent
DETECTOR_ROOT = REPO_ROOT / "detector"
AUDIT_ROOT = REPO_ROOT / "audit" / "2026-11-17-causal-lookahead-audit"
for _path in (DETECTOR_ROOT, AUDIT_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import causal_intrabar as ci  # noqa: E402
from backtest.candidate import Candidate  # noqa: E402
from backtest.levels import (  # noqa: E402
    enforce_min_stop_distance, partial_price, risk_reward, stop_loss, take_profit,
)
from backtest.simulate import _fill_sides, _resolve_exits  # noqa: E402
from core.sweep import two_heap_sweep  # noqa: E402

_NY = ZoneInfo("America/New_York")
_UTC = ZoneInfo("UTC")


def _ny_instant_utc(ny_date, hour_ny: int) -> datetime:
    local = datetime(ny_date.year, ny_date.month, ny_date.day, hour_ny, tzinfo=_NY)
    return local.astimezone(_UTC).replace(tzinfo=None)


@dataclass(frozen=True)
class ResolutionResult:
    outcome: str  # "ENTERED" / "RR_FLOOR_REJECTED" / "UNFILLED_ORDER"
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    risk_reward: float | None = None
    trade: object | None = None  # the real, unmodified Trade if ENTERED


def resolve_candidate(
    signal, m15, config, swings, indices, reference_high: float, reference_low: float,
    current_open_ts: datetime, m15_timestamps: list[datetime],
) -> ResolutionResult:
    anchor = m15.candles[signal.anchor_index]
    entry = signal.entry_price

    sl = stop_loss(
        anchor, signal.direction, swings, indices, signal.anchor_index, signal.retest_index,
        m15.candles, config.backtest,
    )
    sl = enforce_min_stop_distance(entry, sl, signal.direction, config.backtest.min_stop_distance_price)
    tp = take_profit(SimpleNamespace(high=reference_high, low=reference_low), signal.direction)
    rr = risk_reward(entry, sl, tp, signal.direction)

    if rr < config.backtest.min_risk_reward:
        return ResolutionResult("RR_FLOOR_REJECTED", entry, sl, tp, rr)

    candidate = Candidate(
        signal_id=signal.signal_id, anchor_index=signal.anchor_index, origin_index=signal.origin_index,
        direction=signal.direction, entry_type=signal.entry_type, retest_index=signal.retest_index,
        entry_price=entry, stop_loss=sl, take_profit=tp, partial_price=partial_price(entry, tp),
    )

    order_placed_ts = ci.available_at(m15.candles[signal.confirmation_index], ci.M15_DURATION)
    first_fillable_index = bisect.bisect_left(m15_timestamps, order_placed_ts)

    session_date = current_open_ts.replace(tzinfo=_UTC).astimezone(_NY).date()
    cutoff_ts = _ny_instant_utc(session_date, 15)
    cutoff_idx = bisect.bisect_left(m15_timestamps, cutoff_ts)  # exclusive upper bound

    if first_fillable_index >= cutoff_idx:
        return ResolutionResult("UNFILLED_ORDER", entry, sl, tp, rr)

    truncated = m15.candles[:cutoff_idx]
    fill_results = two_heap_sweep(
        truncated, [candidate], eligible_at=lambda c: first_fillable_index, sides=_fill_sides(), default=None,
    )
    fill_index = fill_results[0]
    if fill_index is None:
        return ResolutionResult("UNFILLED_ORDER", entry, sl, tp, rr)

    trades = _resolve_exits(
        [(candidate, fill_index)], m15.candles, config.backtest.trading_cost_price,
        config.backtest.partial_fraction, breakeven_after_partial=config.backtest.breakeven_after_partial,
    )
    return ResolutionResult("ENTERED", entry, sl, tp, rr, trades[0])
