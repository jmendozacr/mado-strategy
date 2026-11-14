"""EXPERIMENTAL redefinition of `key_level_reaction` against the credited
Key Level's own zone, instead of against the CRT range.

**The gap this probes.** charter-1 [00:12:59] and charter-6 [00:03:25]
describe three separate things happening on the purge candle: the wick
touches the Key Level, the candle **rejects the zone**, and it closes back
inside the CRT range. `alignment.htf_ltf._key_level_credit_map` implements
only the first (geometric wick-overlap against `[KeyLevel.bottom,
KeyLevel.top]`); `alignment.htf_ltf._purge_reaction` implements only the
third (`close` compared against `CRTRange.low/high`). Nothing anywhere
compares the close against the credited level's own zone, so a candle
whose close still sits inside the Key Level zone -- never having rejected
it -- can still be classified `reject_close_inside` today, as long as it
happens to close back inside the (separate) CRT range. The two ranges are
not the same object and are not guaranteed to nest one inside the other.

**What this module does, and does not do.** Not a change to anything, and
not a filter: nothing here alters `key_level` crediting, `AlignedSignal`,
or any production file. `redefine_reaction` is a pure, read-only
recomputation over the SAME credited `key_level` and the SAME HTF candles
production already has, answering a different question: did the candle's
CLOSE actually leave the credited zone, on the side away from it?

**Join key.** Rows are keyed on `signal.ltf_signal.signal_id`, which
`backtest/population.py` copies verbatim onto `Candidate.signal_id` and
from there onto `Trade.signal_id` (confirmed by reading
`backtest/population.py`'s own `signal_id=signal.signal_id` line) -- the
same key `experimental.scanner_baseline_runner` already uses to join a
reaction classification back onto engine fills WITHIN one run. This is
deliberately different from `experimental.discovery_comparison`'s
join-key story: that module compares TWO SEPARATE runs whose indices live
in different spaces, which is exactly why `signal_id` fails there -- here
there is only one run, one `Candidate` per signal, and `signal_id` is
exact.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Literal

from alignment.htf_ltf import AlignedSignal
from core.candle import Candle
from primitives.crt_range import first_breach_index

__all__ = [
    "Reaction",
    "REACTIONS",
    "KeyLevelReactionRedefinitionError",
    "ReactionRedefinitionRow",
    "ReactionRedefinitionReport",
    "redefine_reaction",
    "build_redefinition_rows",
]

Reaction = Literal["reject_close_inside", "continuation", "ambiguous"]

REACTIONS: tuple[Reaction, ...] = ("reject_close_inside", "continuation", "ambiguous")
"""Closed, in report order -- mirrors `experimental.discovery_comparison.VERDICTS`:
a value the function can return but the report cannot enumerate would vanish
from a tally while the total still matched."""


class KeyLevelReactionRedefinitionError(Exception):
    """Raised when a signal's credited `key_level` does not actually overlap
    either breached extreme of its own purge candle -- an inconsistent
    `AlignedSignal` the production gate should never produce. Never
    softened to `None`: that would hide a real join/crediting bug behind a
    missing-data case."""


def redefine_reaction(
    signal: AlignedSignal, htf_candles: tuple[Candle, ...]
) -> Reaction | None:
    """`None` when there is no credited Key Level to test (mirrors
    `AlignedSignal.key_level_reaction`'s own `None`-means-nothing-to-report
    convention) -- never a negative determination.

    Otherwise: locate the purge candle the SAME way
    `alignment.htf_ltf._purge_index_map` does (`first_breach_index` over
    `[crt_range.start_index, crt_range.resolved_at_index]`, the credited
    `CRTRange`'s own bounds), then test whichever breached extreme(s) fall
    inside the credited level's zone -- both are tested independently
    because ~14% of real H4 purges breach both sides (REQ-55.6/.7's own
    finding) -- and classify the close against THAT zone's near edge:
    `reject_close_inside` only when the close has actually left the zone on
    the side away from it. `"ambiguous"` when both sides breach AND both
    fall inside the same zone (the zone spans the whole purge candle) --
    reported, not guessed at.
    """
    if signal.key_level is None or signal.htf_context is None:
        return None

    crt_range = signal.htf_context
    level = signal.key_level
    purge_index = first_breach_index(
        htf_candles, crt_range.start_index, crt_range.resolved_at_index,
        high=crt_range.high, low=crt_range.low,
    )
    if purge_index is None:
        raise KeyLevelReactionRedefinitionError(
            f"credited key_level {level!r} but its own CRTRange "
            f"({crt_range.start_index}, {crt_range.resolved_at_index}) has no "
            "purge candle at all -- an inconsistent AlignedSignal"
        )
    candle = htf_candles[purge_index]

    high_in_zone = candle.high > crt_range.high and level.bottom <= candle.high <= level.top
    low_in_zone = candle.low < crt_range.low and level.bottom <= candle.low <= level.top

    if high_in_zone and low_in_zone:
        return "ambiguous"
    if high_in_zone:
        return "reject_close_inside" if candle.close < level.bottom else "continuation"
    if low_in_zone:
        return "reject_close_inside" if candle.close > level.top else "continuation"
    raise KeyLevelReactionRedefinitionError(
        f"credited key_level {level!r} overlaps neither breached extreme of "
        f"purge candle {purge_index} ({candle.high}/{candle.low}) -- an "
        "inconsistent AlignedSignal"
    )


@dataclass(frozen=True)
class ReactionRedefinitionRow:
    """One confluent signal, both definitions side by side. `outcome`/
    `r_multiple` are `None` when the signal never reached a `Trade` (e.g.
    excluded upstream of the fill pass) -- the row still counts toward the
    reaction crosstab, just not toward win-rate/R."""

    signal_id: str
    anchor_index: int
    direction: Literal["bullish", "bearish"]
    current_reaction: Reaction | None
    redefined_reaction: Reaction | None
    outcome: Literal["win", "loss", "open"] | None
    r_multiple: float | None


def build_redefinition_rows(
    aligned_signals: list[AlignedSignal],
    htf_candles: tuple[Candle, ...],
    trades: list,
) -> tuple[ReactionRedefinitionRow, ...]:
    """One row per confluent signal (`key_level is not None`), joined to its
    `Trade` (if any) on `signal_id`. Raises on a join-key collision rather
    than letting one trade's outcome silently attach to the wrong signal's
    reaction pair -- should not happen within one run (`signal_id` is
    unique per `backtest.population._dedup`), so a collision here means an
    inconsistent input, not a real case to tolerate."""
    trade_by_id: dict[str, object] = {}
    for trade in trades:
        if trade.signal_id in trade_by_id:
            raise KeyLevelReactionRedefinitionError(
                f"signal_id {trade.signal_id!r} is carried by two trades -- "
                "the join is ambiguous for this run"
            )
        trade_by_id[trade.signal_id] = trade

    rows = []
    for signal in aligned_signals:
        if signal.key_level is None:
            continue
        signal_id = signal.ltf_signal.signal_id
        trade = trade_by_id.get(signal_id)
        rows.append(
            ReactionRedefinitionRow(
                signal_id=signal_id,
                anchor_index=signal.ltf_signal.anchor_index,
                direction=signal.ltf_signal.direction,
                current_reaction=signal.key_level_reaction,
                redefined_reaction=redefine_reaction(signal, htf_candles),
                outcome=trade.outcome if trade is not None else None,
                r_multiple=trade.r_multiple if trade is not None else None,
            )
        )
    return tuple(rows)


@dataclass(frozen=True)
class ReactionRedefinitionReport:
    rows: tuple[ReactionRedefinitionRow, ...]

    @property
    def crosstab(self) -> dict[tuple[Reaction, Reaction], int]:
        """`(current, redefined) -> count`, over every row regardless of
        trade outcome -- the population-level agreement/disagreement
        picture."""
        return dict(
            Counter(
                (row.current_reaction, row.redefined_reaction)
                for row in self.rows
                if row.current_reaction is not None and row.redefined_reaction is not None
            )
        )

    @property
    def flipped_to_continuation(self) -> tuple[ReactionRedefinitionRow, ...]:
        """Today's `reject_close_inside` that the redefinition does NOT
        confirm -- the exact population the gap can dilute."""
        return tuple(
            row for row in self.rows
            if row.current_reaction == "reject_close_inside"
            and row.redefined_reaction != "reject_close_inside"
        )

    def stats_for(
        self, reaction: Reaction, *, using: Literal["current", "redefined"]
    ) -> dict[str, float | int]:
        """Win rate and average R over closed trades for one reaction
        bucket under one definition. `n` is the row count (includes rows
        with no trade); `n_closed` is how many of those actually had a
        win/loss outcome to average."""
        field = "current_reaction" if using == "current" else "redefined_reaction"
        bucket = [row for row in self.rows if getattr(row, field) == reaction]
        closed = [row for row in bucket if row.outcome in ("win", "loss")]
        wins = sum(1 for row in closed if row.outcome == "win")
        return {
            "n": len(bucket),
            "n_closed": len(closed),
            "win_rate": wins / len(closed) if closed else 0.0,
            "avg_r": (
                sum(row.r_multiple for row in closed if row.r_multiple is not None)
                / len(closed)
                if closed else 0.0
            ),
        }
