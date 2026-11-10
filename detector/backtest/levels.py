"""Pure price arithmetic for the backtest layer (REQ-31, 32, 35, 44, 47,
48) — no I/O, no series scanning beyond the bounded swing-window lookup in
`stop_loss`.
"""

import bisect
from typing import Literal

from core.atr import atr
from core.candle import Candle
from core.config import BacktestConfig
from primitives.crt_range import CRTRange
from primitives.swing import SwingPoint

Direction = Literal["bullish", "bearish"]


def entry_price(anchor: Candle, direction: Direction, entry_type: Literal["wick", "body"]) -> float:
    """REQ-47: backtest-local entry price, independent of
    `Model1Signal.entry_price`/`detections.csv` (ADR-05). Wick entry is the
    anchor's own wick extreme (`anchor.high` bullish / `anchor.low`
    bearish) -- corrected 2026-11-10b: the original "retest-side body
    boundary" (max/min of open,close) was itself a misreading of ADR-05's
    rejected "entry at the wick extreme" alternative, which evaluated the
    SWEPT-side wick tip (the same point as `protected_extreme`, the stop's
    own anchor -- a real collapse risk), not this OPPOSITE-side one. Two
    real executed Model-1 trades (a GBPUSD buy and a EURUSD sell, both
    2026-11-10) confirmed entry sits at the full wick tip, never a body
    edge -- the sell's anchor had long wicks on both sides, cleanly ruling
    the body-edge formula out."""
    if entry_type == "body":
        return anchor.open
    return anchor.high if direction == "bullish" else anchor.low


def stop_loss(
    anchor: Candle,
    direction: Direction,
    swings: list[SwingPoint],
    indices: list[int],
    anchor_index: int,
    retest_index: int,
    candles: tuple[Candle, ...],
    config: BacktestConfig,
) -> float:
    """REQ-31: stop beyond a real structural level — the deepest qualifying
    swing within `[anchor_index, retest_index - 2]`, or the anchor's own
    swept extreme when none qualifies — offset by `sl_buffer_atr_multiple *
    atr(candles, anchor_index)` (REQ-31, scale-aware fix): a bare price-unit
    constant is proportionally tiny on a high-absolute-price instrument
    (e.g. DXY, ~90-110) relative to a ~1.05-1.20 FX pair, collapsing the
    risk denominator (entry - stop) toward zero. ATR is measured at
    `anchor_index` -- the same candle `protected_extreme` is drawn from --
    so the buffer reflects the volatility regime in which that level formed.

    The upper bound is `retest_index - 2`, not `retest_index - 1`:
    `detect_swings` only confirms a swing at index `i` once candle `i + 1`
    exists (its 3-candle local-extreme check), so a swing at `retest_index -
    1` would only become confirmable once candle `retest_index` closes —
    not yet knowable at `retest_index`, when the order can already fill
    (REQ-50.1). `i <= retest_index - 2` is exactly the set of swings
    confirmable from data available strictly before candle `retest_index`
    opens.

    `indices` is `[s.index for s in swings]`, precomputed once by the caller
    (`swings` is invariant across every candidate in one `simulate()` run)."""
    protected_extreme = anchor.low if direction == "bullish" else anchor.high
    kind: Literal["high", "low"] = "low" if direction == "bullish" else "high"

    window_end = retest_index - 2
    start = bisect.bisect_left(indices, anchor_index)
    end = bisect.bisect_right(indices, window_end)
    candidates = [
        s for s in swings[start:end]
        if s.kind == kind
        and (s.price < protected_extreme if direction == "bullish" else s.price > protected_extreme)
    ]

    if not candidates:
        level = protected_extreme
    elif direction == "bullish":
        level = min(candidates, key=lambda s: (s.price, s.index)).price
    else:
        level = max(candidates, key=lambda s: (s.price, -s.index)).price

    buffer = config.sl_buffer_atr_multiple * atr(candles, anchor_index)
    return level - buffer if direction == "bullish" else level + buffer


def take_profit(htf_context: CRTRange, direction: Direction) -> float:
    """REQ-32/44: the HTF CRT range's opposite extreme, sourced from
    `AlignedSignal.htf_context` — never recomputed from the LTF series."""
    return htf_context.high if direction == "bullish" else htf_context.low


def partial_price(entry_price: float, take_profit: float) -> float:
    """REQ-68 (V2): the trade's OWN entry-to-target midpoint -- not the
    HTF CRT range's midpoint (V1's formula, falsified by REQ-70's property
    test: 6.7-12.6% real ordering violations across the 3-instrument
    corpus, since the H4 range midpoint has no structural relationship to
    the LTF trade's entry/stop). entry_price and take_profit are already
    correctly ordered by REQ-35's R:R floor, so this formula satisfies
    REQ-70's ordering invariant by construction."""
    return (entry_price + take_profit) / 2


def risk_reward(entry: float, stop: float, target: float, direction: Direction) -> float:
    """REQ-35: signed distances — a target behind entry yields a negative
    ratio, caught by the same `< min_risk_reward` comparison (no separate
    bucket)."""
    if direction == "bullish":
        risk, reward = entry - stop, target - entry
    else:
        risk, reward = stop - entry, entry - target
    return reward / risk


def net_r_multiple(
    entry: float, exit_price: float, stop: float, direction: Direction, trading_cost_price: float
) -> float:
    """REQ-48/49: net of trading cost, applied once at closure. At the
    default `trading_cost_price=0.0` this is bit-identical to the gross
    formula (REQ-48.2)."""
    signed_move = exit_price - entry if direction == "bullish" else entry - exit_price
    risk = abs(entry - stop)
    return (signed_move - trading_cost_price) / risk
