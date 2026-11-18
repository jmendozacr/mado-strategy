"""Arm B1 (late-discovery / actual-scanner-behavior) fill mechanics.

Reuses `backtest.simulate`'s private sweep geometry (`_fill_sides`),
`core.sweep.two_heap_sweep`, and `backtest.simulate._resolve_exits`
UNMODIFIED, imported, never copied. The only thing that differs from the
production `_fill_pass` (detector/backtest/simulate.py) is WHICH M15 index
each candidate becomes eligible to fill from, and from which index its
`max_fill_wait` expiration is counted -- both anchored on PLACEMENT time
(when a live pending order could first exist, S3 Arm B1 points 3/4/8),
never on the historical `retest_index` the signal was actually found at.

This is the one, precisely-scoped divergence from production code this
investigation's Phase 1 identified: `_fill_pass` sweeps from
`candidate.retest_index` with no floor on real-world availability. Entry
price, stop-loss, take-profit, and partial price are NOT touched here --
those stay whatever `backtest.population.build_stage6_population` (also
unmodified) computed, per S3 Arm B1 point 5 ("conserva los niveles
originales... cuando sean válidos y utilizables" -- validity is
operationalized as: the SAME entry-touch sweep `_fill_sides` already runs,
just not permitted to start before the order could exist. If price already
left the entry level for good before placement, the sweep -- unmodified --
simply never finds a touch, and the candidate is correctly counted as
never-filled, not force-rejected by a separate check).
"""
from __future__ import annotations

from backtest.simulate import _fill_sides, _resolve_exits
from core.sweep import two_heap_sweep


def fill_pass_b1(candidates, candles, max_fill_wait, placement_index_by_signal_id):
    """B1 counterpart of `backtest.simulate._fill_pass`. A candidate whose
    placement_index could not be determined (missing from the map, or past
    the end of the M15 series) never fills -- `skipped` counts these
    separately from `never_filled` (price never returned to entry after a
    determinable placement) for reporting (S4 "operaciones no ejecutables"
    vs. ordinary non-fills)."""
    eligible = [c for c in candidates if placement_index_by_signal_id.get(c.signal_id) is not None]
    skipped_no_placement = len(candidates) - len(eligible)

    fill_order = sorted(eligible, key=lambda c: placement_index_by_signal_id[c.signal_id])
    fill_results = two_heap_sweep(
        candles, fill_order,
        eligible_at=lambda c: placement_index_by_signal_id[c.signal_id],
        sides=_fill_sides(), default=None,
    )
    filled = [
        (candidate, fill_index)
        for candidate, fill_index in zip(fill_order, fill_results)
        if fill_index is not None
        and fill_index - placement_index_by_signal_id[candidate.signal_id] <= max_fill_wait
    ]
    never_filled = len(fill_order) - len(filled)
    return filled, never_filled, skipped_no_placement


def simulate_b1(candidates, m15_candles, config, placement_index_by_signal_id):
    """B1 counterpart of `backtest.simulate.simulate`: same population (the
    caller passes Arm A's own `population.candidates`, unmodified), same
    `_resolve_exits` (unmodified, imported) for everything AFTER the fill
    -- SL/TP/partial/breakeven resolution has no causality defect of its
    own (Phase 1 finding), only `_fill_pass`'s missing floor does."""
    filled, never_filled, skipped_no_placement = fill_pass_b1(
        candidates, m15_candles, config.backtest.max_fill_wait, placement_index_by_signal_id
    )
    trades = _resolve_exits(
        filled, m15_candles, config.backtest.trading_cost_price, config.backtest.partial_fraction,
        breakeven_after_partial=config.backtest.breakeven_after_partial,
    )
    trades.sort(key=lambda t: (t.entry_index, t.signal_id))
    return trades, never_filled, skipped_no_placement
