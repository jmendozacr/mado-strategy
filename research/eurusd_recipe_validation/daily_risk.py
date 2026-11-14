"""Daily-loss stop -- RESEARCH TOOLING, not a production entry point.

RECONSTRUCTED, NOT RECOVERED. The validated recipe's memory record states
the rule as "stop taking new trades after the 2nd loss of the day" and
records that the stricter "max 1 trade/day" variant was tested and
REJECTED for hurting results. The rule's intent is therefore a VERIFIED
historical fact; the implementation below is a rebuild, and the two
conventions the sentence does not pin are marked RECONSTRUCTED.

Algorithm
---------
Walk the population in `(entry_index, signal_id)` order, carrying the
trades accepted so far. Admit a candidate unless, at the moment it would
have been entered, the day already holds `max_losses_per_day` losses that
were ALREADY REALISED.

"Already realised" means an accepted trade that lost and whose
`exit_time` is at or before the candidate's `entry_time`. This is the one
convention here chosen on correctness rather than taste: a rule keyed on
losses that had not yet closed would be reading the future, and would
suppress trades an account could not have known to skip.

RECONSTRUCTED day key: a loss counts against the NY-local calendar date of
its own ENTRY, matched against the candidate's entry date. The alternative
-- keying a loss to the date it CLOSED, which is how a broker's realised
P&L would book it -- is equally defensible and differs only for trades held
across a session boundary. The NY-local key was chosen because the rule it
encodes is a trader's own ("my second loss today"), not a broker's
accounting, and because the recipe's session is defined in NY-local hours.
Measured on the real EURUSDm population, switching the key from NY-local to
UTC changes nothing at all (1642 trades either way), so at least the
timezone half of this choice is inert.

RECONSTRUCTED rejection accounting: a candidate the rule rejects contributes
nothing to the count, whatever its simulated outcome was. The account never
opened it, so it could not have lost. The alternative (counting a rejected
trade's loss) would let a day's count deepen from trades that were never
taken, which is incoherent rather than merely different.
"""
from __future__ import annotations

from typing import Sequence

from research.eurusd_recipe_validation.trades import ClosedTrade, ordered, session_day


def apply_daily_loss_stop(
    trades: Sequence[ClosedTrade],
    max_losses_per_day: int = 2,
) -> list[ClosedTrade]:
    """Accepted trades, in `(entry_index, signal_id)` order. Never reorders
    or rewrites a trade -- this rule only ever drops."""
    accepted: list[ClosedTrade] = []
    realised_losses: dict[object, list[ClosedTrade]] = {}

    for trade in ordered(trades):
        day = session_day(trade.entry_time)
        closed_losses = sum(
            1 for loser in realised_losses.get(day, ())
            if loser.exit_time is not None and loser.exit_time <= trade.entry_time
        )
        if closed_losses >= max_losses_per_day:
            continue
        accepted.append(trade)
        if trade.outcome == "loss":
            realised_losses.setdefault(day, []).append(trade)

    return accepted
