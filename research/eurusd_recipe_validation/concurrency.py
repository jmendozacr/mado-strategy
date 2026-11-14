"""Bounded within-pair concurrency gate -- RESEARCH TOOLING, not a
production entry point.

RECONSTRUCTED, NOT RECOVERED. The validated recipe's memory record cites a
module named `concurrency_sim` with a function
`simulate_bounded_concurrency`; no such file exists anywhere in this
repository's history (`git log --all --diff-filter=A` finds nothing), so
the original implementation is lost and this is a rebuild from the one-line
description "within-pair cap 2R". Every convention below that the
description did not pin is marked RECONSTRUCTED and its alternative stated.

Algorithm
---------
`backtest.simulate` resolves every candidate independently: it answers
"what would this trade have done", never "could this trade have been taken
while others were already open". A real account cannot do that -- risk is
shared. This gate replays the resolved population as an account would have
experienced it.

Walk the population in `(entry_index, signal_id)` order. Carry a set of
slots, one per ACCEPTED trade that is still open. At each candidate:

1. Free every slot whose trade has already exited (see the tie convention
   below).
2. If admitting this candidate would put `(open slots + 1) *
   risk_per_trade_r` ABOVE `max_open_risk_r`, reject it and move on. A
   rejected candidate consumes nothing -- the account never opened it, so
   it cannot occupy a slot or shift any later decision except by its own
   absence.
3. Otherwise accept it and occupy a slot until its own exit.

With the recipe's `max_open_risk_r=2.0` and the detector's stop-loss
definition -- every trade risks exactly one R by construction, because the
stop IS the 1R denominator -- this reduces to "at most two positions open
at any instant". `risk_per_trade_r` is a parameter rather than a hardcoded
1.0 only so that reduction stays visible instead of implicit.

RECONSTRUCTED tie convention: a trade whose `exit_index` equals the
candidate's `entry_index` has already closed on that bar, so it frees its
slot. The alternative (the exiting trade still occupies its slot on its own
exit bar) is equally defensible -- M15 intrabar ordering is unknowable --
and is measurably different: on the real EURUSDm population it yields 1826
accepted trades where this convention yields 1885, and after the daily-loss
rule 1613 against 1642 (the historical record's figure is 1681, which this
convention lands nearer to). Neither was recovered; this one was chosen on
the merit that a closed position is not an open position, and the
difference is reported rather than hidden.

An unresolved trade (`exit_index is None`) never frees its slot: the
account would still be carrying it at the end of the series.
"""
from __future__ import annotations

from typing import Sequence

from research.eurusd_recipe_validation.trades import ClosedTrade, ordered


def simulate_bounded_concurrency(
    trades: Sequence[ClosedTrade],
    max_open_risk_r: float = 2.0,
    risk_per_trade_r: float = 1.0,
) -> list[ClosedTrade]:
    """Accepted trades, in `(entry_index, signal_id)` order. Never reorders
    or rewrites a trade -- this gate only ever drops."""
    accepted: list[ClosedTrade] = []
    open_exits: list[int | None] = []

    for trade in ordered(trades):
        open_exits = [exit_index for exit_index in open_exits
                      if exit_index is None or exit_index > trade.entry_index]
        if (len(open_exits) + 1) * risk_per_trade_r > max_open_risk_r:
            continue
        accepted.append(trade)
        open_exits.append(trade.exit_index)

    return accepted
