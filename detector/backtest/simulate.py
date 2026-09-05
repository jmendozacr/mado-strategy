"""Candle-by-candle trade lifecycle simulation (REQ-30, 33, 34, 37, 38, 40,
46, 50). The 7-stage population pipeline, the unified fill pass, and SL/TP
resolution — one algorithm, no branch by candidate type (ADR-01..05).
"""

from dataclasses import dataclass
from typing import Literal

from alignment.htf_ltf import AlignedSignal
from backtest.levels import Direction
from backtest.levels import entry_price as _entry_price
from backtest.levels import net_r_multiple as _net_r_multiple
from backtest.levels import partial_price as _partial_price
from backtest.levels import risk_reward as _risk_reward
from backtest.levels import stop_loss as _stop_loss
from backtest.levels import take_profit as _take_profit
from core.candle import OHLCSeries
from core.config import DetectorConfig
from core.kill_zone import in_ny_kill_zone
from core.sweep import SweepSide, two_heap_sweep
from primitives.swing import SwingPoint, detect_swings


@dataclass(frozen=True)
class Candidate:
    """Everything about a tradeable setup that is knowable AT `retest_index`
    — the moment the resting entry order goes live."""

    signal_id: str
    anchor_index: int
    origin_index: int
    direction: Direction
    entry_type: Literal["wick", "body"]
    retest_index: int
    entry_price: float
    stop_loss: float
    take_profit: float
    partial_price: float


@dataclass(frozen=True)
class Trade:
    signal_id: str
    anchor_index: int
    direction: Direction
    entry_index: int
    entry_price: float
    stop_loss: float
    take_profit: float
    exit_index: int | None
    exit_price: float | None
    outcome: Literal["win", "loss", "open"]
    r_multiple: float | None
    ambiguous_bar: bool
    gap_filled: bool
    partial_exit_index: int | None
    partial_exit_price: float | None
    partial_r_multiple: float | None
    partial_gap_filled: bool


@dataclass(frozen=True)
class ReconciliationReport:
    signals_considered: int
    trades_opened: int
    excluded_no_crt_range: int
    excluded_unaligned: int
    excluded_never_confirmed: int
    excluded_no_key_level: int
    excluded_duplicate: int
    excluded_kill_zone: int
    excluded_rr_floor: int
    excluded_never_filled: int


@dataclass(frozen=True)
class _PopulationCuts:
    """Named-field record, not a positional tuple (ADR-015) — a swap
    between two adjacent same-typed int counts at the unpack site would
    otherwise pass the REQ-40.1 sum invariant silently."""

    survivors: list[AlignedSignal]
    no_crt_range: int
    unaligned: int
    never_confirmed: int
    no_key_level: int


def _build_candidate(
    tagged: AlignedSignal, swings, indices: list[int], ltf_series: OHLCSeries, backtest_config
) -> Candidate:
    signal = tagged.ltf_signal
    anchor = ltf_series.candles[signal.anchor_index]
    ep = _entry_price(anchor, signal.direction, signal.entry_type)
    sl = _stop_loss(
        anchor, signal.direction, swings, indices, signal.anchor_index, signal.retest_index, backtest_config
    )
    tp = _take_profit(tagged.htf_context, signal.direction)
    pp = _partial_price(ep, tp)
    return Candidate(
        signal_id=signal.signal_id,
        anchor_index=signal.anchor_index,
        origin_index=signal.origin_index,
        direction=signal.direction,
        entry_type=signal.entry_type,
        retest_index=signal.retest_index,
        entry_price=ep,
        stop_loss=sl,
        take_profit=tp,
        partial_price=pp,
    )


def _directional_sides(get_price, get_direction, invert_bullish: bool = False) -> tuple[SweepSide, SweepSide]:
    """Shared SweepSide-pair shape for the fill/SL/TP sweeps (ADR-02): bullish
    and bearish are mirror images — one side's heap-key negated to emulate a
    max-heap, the other raw — differing only in which price field is read
    and, for TP, which direction resolves on which side of the candle
    (`invert_bullish` flips the sense)."""
    negate_bullish = not invert_bullish
    return (
        SweepSide(
            belongs=lambda item: get_direction(item) == "bullish",
            heap_key=lambda item: -get_price(item) if negate_bullish else get_price(item),
            resolves=(lambda key, candle: -key >= candle.low)
            if negate_bullish
            else (lambda key, candle: key <= candle.high),
            result=lambda j: j,
        ),
        SweepSide(
            belongs=lambda item: get_direction(item) == "bearish",
            heap_key=lambda item: get_price(item) if negate_bullish else -get_price(item),
            resolves=(lambda key, candle: key <= candle.high)
            if negate_bullish
            else (lambda key, candle: -key >= candle.low),
            result=lambda j: j,
        ),
    )


def _fill_sides() -> tuple[SweepSide, SweepSide]:
    return _directional_sides(lambda c: c.entry_price, lambda c: c.direction)


def _sl_sides() -> tuple[SweepSide, SweepSide]:
    return _directional_sides(lambda pair: pair[0].stop_loss, lambda pair: pair[0].direction)


def _tp_sides() -> tuple[SweepSide, SweepSide]:
    return _directional_sides(
        lambda pair: pair[0].take_profit, lambda pair: pair[0].direction, invert_bullish=True
    )


def _partial_sides() -> tuple[SweepSide, SweepSide]:
    """REQ-68: the equilibrium level sits on the SAME side of entry as
    take_profit (same-side/monotonic geometry) -- mirrors `_tp_sides()`
    exactly, reading `partial_price` instead of `take_profit`."""
    return _directional_sides(
        lambda pair: pair[0].partial_price, lambda pair: pair[0].direction, invert_bullish=True
    )


def _exit_gap_beyond(open_price: float, level: float, direction: Direction, chosen_is_stop: bool) -> bool:
    """REQ-34: does the resolving exit candle's open already lie beyond the
    CHOSEN level? Stop is on the adverse side of entry, target on the
    favorable side — the comparison direction flips accordingly."""
    if direction == "bullish":
        return open_price < level if chosen_is_stop else open_price > level
    return open_price > level if chosen_is_stop else open_price < level


def _population_cuts(aligned_signals: list[AlignedSignal]) -> _PopulationCuts:
    """Stages 1-4: population-status cuts — no CRT range, unaligned, never
    confirmed (`retest_index is None`, regardless of status), no Key Level
    (REQ-30.7) — confluence is READ here, never recomputed (REQ-59); it was
    determined once in `alignment.tag_alignment` and stored on
    `AlignedSignal.key_level`."""
    survivors: list[AlignedSignal] = []
    excluded_no_crt_range = excluded_unaligned = excluded_never_confirmed = excluded_no_key_level = 0
    for tagged in aligned_signals:
        signal = tagged.ltf_signal
        if signal.confirmation_type == "fvg_fill":
            excluded_no_crt_range += 1
        elif tagged.aligned != "aligned":
            excluded_unaligned += 1
        elif signal.retest_index is None:
            excluded_never_confirmed += 1
        elif tagged.key_level is None:
            excluded_no_key_level += 1
        else:
            survivors.append(tagged)
    return _PopulationCuts(
        survivors=survivors, no_crt_range=excluded_no_crt_range, unaligned=excluded_unaligned,
        never_confirmed=excluded_never_confirmed, no_key_level=excluded_no_key_level,
    )


def _dedup(candidates: list[Candidate]) -> tuple[list[Candidate], int]:
    """Stage 4: collapse candidates sharing identity — lowest origin_index
    survives (REQ-46)."""
    by_key: dict[tuple, list[Candidate]] = {}
    for candidate in candidates:
        key = (candidate.anchor_index, candidate.direction, candidate.entry_price, candidate.entry_type)
        by_key.setdefault(key, []).append(candidate)
    survivors = [min(group, key=lambda c: c.origin_index) for group in by_key.values()]
    return survivors, len(candidates) - len(survivors)


def _kill_zone_cut(
    candidates: list[Candidate], candles: tuple, config: DetectorConfig
) -> tuple[list[Candidate], int]:
    """Stage 5: kill-zone gate, anchor-time basis only (REQ-36)."""
    survivors, excluded = [], 0
    for candidate in candidates:
        if config.backtest.kill_zone_gated and not in_ny_kill_zone(
            candles[candidate.anchor_index].timestamp, config.kill_zone
        ):
            excluded += 1
        else:
            survivors.append(candidate)
    return survivors, excluded


def _rr_floor_cut(candidates: list[Candidate], min_risk_reward: float) -> tuple[list[Candidate], int]:
    """Stage 6: risk:reward floor, signed distances (REQ-35)."""
    survivors, excluded = [], 0
    for candidate in candidates:
        rr = _risk_reward(candidate.entry_price, candidate.stop_loss, candidate.take_profit, candidate.direction)
        if rr < min_risk_reward:
            excluded += 1
        else:
            survivors.append(candidate)
    return survivors, excluded


def _fill_pass(
    candidates: list[Candidate], candles: tuple, max_fill_wait: int
) -> tuple[list[tuple[Candidate, int]], int]:
    """Stage 7: unified entry-fill sweep, eligible_at = retest_index for
    every candidate — no candidate-type branch (ADR-02)."""
    fill_order = sorted(candidates, key=lambda c: c.retest_index)
    fill_results = two_heap_sweep(
        candles, fill_order, eligible_at=lambda c: c.retest_index, sides=_fill_sides(), default=None
    )
    filled = [
        (candidate, fill_index)
        for candidate, fill_index in zip(fill_order, fill_results)
        if fill_index is not None and fill_index - candidate.retest_index <= max_fill_wait
    ]
    return filled, len(fill_order) - len(filled)


def _resolve_single_leg(
    candidate: Candidate, fill_index: int, sl_index: int | None, tp_index: int | None,
    candles: tuple, trading_cost_price: float,
) -> Trade:
    """REQ-33/34/38: fixed-order resolution — open, else SL-wins-ties,
    else gap-through-the-chosen-level fill. This is this codebase's
    original, pre-REQ-68 resolution -- unchanged -- reused by
    `_resolve_trade` both when no partial level is in play and, byte-for-
    byte, at `partial_fraction=0.0` (REQ-68.5)."""
    if sl_index is None and tp_index is None:
        return Trade(
            signal_id=candidate.signal_id, anchor_index=candidate.anchor_index, direction=candidate.direction,
            entry_index=fill_index, entry_price=candidate.entry_price, stop_loss=candidate.stop_loss,
            take_profit=candidate.take_profit, exit_index=None, exit_price=None, outcome="open",
            r_multiple=None, ambiguous_bar=False, gap_filled=False,
            partial_exit_index=None, partial_exit_price=None, partial_r_multiple=None, partial_gap_filled=False,
        )

    sl_wins = tp_index is None or (sl_index is not None and sl_index <= tp_index)
    exit_index = sl_index if sl_wins else tp_index
    level = candidate.stop_loss if sl_wins else candidate.take_profit
    ambiguous_bar = sl_index is not None and tp_index is not None and sl_index == tp_index

    exit_candle = candles[exit_index]
    gap_filled = _exit_gap_beyond(exit_candle.open, level, candidate.direction, chosen_is_stop=sl_wins)
    exit_price = exit_candle.open if gap_filled else level
    r_multiple = _net_r_multiple(
        candidate.entry_price, exit_price, candidate.stop_loss, candidate.direction, trading_cost_price
    )
    return Trade(
        signal_id=candidate.signal_id, anchor_index=candidate.anchor_index, direction=candidate.direction,
        entry_index=fill_index, entry_price=candidate.entry_price, stop_loss=candidate.stop_loss,
        take_profit=candidate.take_profit, exit_index=exit_index, exit_price=exit_price,
        # REQ-38: "win" means closed profitably — net of trading cost (REQ-48) —
        # not merely "take-profit resolved first" (a large cost can flip a
        # TP-first resolution into a net loss). Breakeven counts as "loss".
        outcome="win" if r_multiple > 0 else "loss", r_multiple=r_multiple,
        ambiguous_bar=ambiguous_bar, gap_filled=gap_filled,
        partial_exit_index=None, partial_exit_price=None, partial_r_multiple=None, partial_gap_filled=False,
    )


def _resolve_trade(
    candidate: Candidate, fill_index: int, sl_index: int | None, tp_index: int | None,
    partial_index: int | None, candles: tuple, trading_cost_price: float, partial_fraction: float,
) -> Trade:
    """REQ-68/69: extends REQ-33's pessimistic SL-wins-ties precedent to
    the partial level. `partial_fraction=0.0` (REQ-68.5) makes leg 1 never
    eligible to fire regardless of index ordering -- the stop-loss winning
    at or before the partial index has the same effect. Either way this
    collapses to `_resolve_single_leg`'s exact pre-existing behavior -- no
    partial leg recorded. Otherwise leg 1 closes at `partial_price` (or its
    gap-open price, REQ-34 applied identically), and leg 2 re-resolves the
    SAME, unmoved stop-loss/take-profit -- reusing `sl_index`/`tp_index`
    from the one sweep already run from `fill_index + 1` (ADR-02: same-
    side/monotonic geometry means neither can resolve strictly before the
    partial) -- restricted to indices strictly after `partial_index`."""
    partial_fires = (
        partial_fraction > 0.0 and partial_index is not None and (sl_index is None or partial_index < sl_index)
    )
    if not partial_fires:
        return _resolve_single_leg(candidate, fill_index, sl_index, tp_index, candles, trading_cost_price)

    partial_exit_candle = candles[partial_index]
    partial_gap_filled = _exit_gap_beyond(
        partial_exit_candle.open, candidate.partial_price, candidate.direction, chosen_is_stop=False
    )
    partial_exit_price = partial_exit_candle.open if partial_gap_filled else candidate.partial_price
    cost_leg1 = partial_fraction * trading_cost_price
    partial_r_multiple = _net_r_multiple(
        candidate.entry_price, partial_exit_price, candidate.stop_loss, candidate.direction, cost_leg1
    )

    # leg2_sl_index is guaranteed None or > partial_index, given partial_fires. TP,
    # however, CAN tie with the partial index — same-side/monotonic geometry means a
    # candle touching TP necessarily also touches the partial level, so the two can
    # resolve within the very same bar (price travels through both intrabar); `>=`
    # keeps that tie as leg 2's exit rather than losing it to "never resolves".
    leg2_sl_index = sl_index
    leg2_tp_index = tp_index if tp_index is not None and tp_index >= partial_index else None

    if leg2_sl_index is None and leg2_tp_index is None:
        return Trade(
            signal_id=candidate.signal_id, anchor_index=candidate.anchor_index, direction=candidate.direction,
            entry_index=fill_index, entry_price=candidate.entry_price, stop_loss=candidate.stop_loss,
            take_profit=candidate.take_profit, exit_index=None, exit_price=None, outcome="open",
            r_multiple=None, ambiguous_bar=False, gap_filled=False,
            partial_exit_index=partial_index, partial_exit_price=partial_exit_price,
            partial_r_multiple=partial_r_multiple, partial_gap_filled=partial_gap_filled,
        )

    leg2_sl_wins = leg2_tp_index is None or (leg2_sl_index is not None and leg2_sl_index <= leg2_tp_index)
    leg2_exit_index = leg2_sl_index if leg2_sl_wins else leg2_tp_index
    leg2_level = candidate.stop_loss if leg2_sl_wins else candidate.take_profit
    ambiguous_bar = leg2_sl_index is not None and leg2_tp_index is not None and leg2_sl_index == leg2_tp_index

    leg2_exit_candle = candles[leg2_exit_index]
    leg2_gap_filled = _exit_gap_beyond(
        leg2_exit_candle.open, leg2_level, candidate.direction, chosen_is_stop=leg2_sl_wins
    )
    leg2_exit_price = leg2_exit_candle.open if leg2_gap_filled else leg2_level
    cost_leg2 = trading_cost_price - cost_leg1
    leg2_r_multiple = _net_r_multiple(
        candidate.entry_price, leg2_exit_price, candidate.stop_loss, candidate.direction, cost_leg2
    )

    blended_r = partial_fraction * partial_r_multiple + (1 - partial_fraction) * leg2_r_multiple
    return Trade(
        signal_id=candidate.signal_id, anchor_index=candidate.anchor_index, direction=candidate.direction,
        entry_index=fill_index, entry_price=candidate.entry_price, stop_loss=candidate.stop_loss,
        take_profit=candidate.take_profit, exit_index=leg2_exit_index, exit_price=leg2_exit_price,
        outcome="win" if blended_r > 0 else "loss", r_multiple=blended_r,
        ambiguous_bar=ambiguous_bar, gap_filled=leg2_gap_filled,
        partial_exit_index=partial_index, partial_exit_price=partial_exit_price,
        partial_r_multiple=partial_r_multiple, partial_gap_filled=partial_gap_filled,
    )


def _resolve_exits(
    filled: list[tuple[Candidate, int]], candles: tuple, trading_cost_price: float, partial_fraction: float
) -> list[Trade]:
    """SL/TP/partial resolution sweeps, eligible_at = fill_index + 1 for
    every candidate (REQ-37)."""
    exit_order = sorted(filled, key=lambda pair: pair[1])
    sl_results = two_heap_sweep(
        candles, exit_order, eligible_at=lambda pair: pair[1] + 1, sides=_sl_sides(), default=None
    )
    tp_results = two_heap_sweep(
        candles, exit_order, eligible_at=lambda pair: pair[1] + 1, sides=_tp_sides(), default=None
    )
    partial_results = two_heap_sweep(
        candles, exit_order, eligible_at=lambda pair: pair[1] + 1, sides=_partial_sides(), default=None
    )
    return [
        _resolve_trade(
            candidate, fill_index, sl_index, tp_index, partial_index, candles, trading_cost_price, partial_fraction
        )
        for (candidate, fill_index), sl_index, tp_index, partial_index
        in zip(exit_order, sl_results, tp_results, partial_results)
    ]


def simulate(
    aligned_signals: list[AlignedSignal],
    ltf_series: OHLCSeries,
    config: DetectorConfig,
    swings: list[SwingPoint] | None = None,
) -> tuple[list[Trade], ReconciliationReport]:
    """`swings` lets a caller that already computed them for the same
    `ltf_series`+config reuse them instead of triggering a second O(n)+
    detection pass — cli.py's `_detect_all` was computing them first, then
    `simulate()` recomputed the identical result. `None` (the default)
    preserves the original self-contained behavior for every existing call
    site."""
    candles = ltf_series.candles

    cuts = _population_cuts(aligned_signals)
    swings = swings if swings is not None else detect_swings(ltf_series, config.swing)
    indices = [s.index for s in swings]
    candidates = [
        _build_candidate(tagged, swings, indices, ltf_series, config.backtest) for tagged in cuts.survivors
    ]

    candidates, excluded_duplicate = _dedup(candidates)
    candidates, excluded_kill_zone = _kill_zone_cut(candidates, candles, config)
    candidates, excluded_rr_floor = _rr_floor_cut(candidates, config.backtest.min_risk_reward)
    filled, excluded_never_filled = _fill_pass(candidates, candles, config.backtest.max_fill_wait)

    trades = _resolve_exits(
        filled, candles, config.backtest.trading_cost_price, config.backtest.partial_fraction
    )
    trades.sort(key=lambda t: (t.entry_index, t.signal_id))

    report = ReconciliationReport(
        signals_considered=len(aligned_signals),
        trades_opened=len(trades),
        excluded_no_crt_range=cuts.no_crt_range,
        excluded_unaligned=cuts.unaligned,
        excluded_never_confirmed=cuts.never_confirmed,
        excluded_no_key_level=cuts.no_key_level,
        excluded_duplicate=excluded_duplicate,
        excluded_kill_zone=excluded_kill_zone,
        excluded_rr_floor=excluded_rr_floor,
        excluded_never_filled=excluded_never_filled,
    )
    return trades, report
