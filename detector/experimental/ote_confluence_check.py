"""EXPERIMENTAL: is the credited Key Level positioned inside the OTE
(Optimal Trade Entry) Fibonacci retracement band of the impulse leading
into it (charter-4 S4)? Reportable, never a crediting gate -- mirrors
`alignment.htf_ltf._purge_reaction`'s own convention. Reuses
`composite.ote` (impulse_leg/ote_zone/ote_overlaps_zone) and the same
purge-index lookup pattern as
`experimental.key_level_reaction_redefinition`; zero production files
touched.

Band is a required, explicit parameter throughout -- charter-4 names
60-75%, charter-7 names 62-79%, genuinely inconsistent across episodes
(see composite/ote.py's own docstring), so this module never silently
picks one.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Literal

from alignment.htf_ltf import AlignedSignal
from core.candle import Candle
from primitives.crt_range import first_breach_index
from primitives.swing import SwingPoint

from composite.ote import Band, impulse_leg, ote_overlaps_zone, ote_zone

__all__ = [
    "OteRow",
    "classify_ote",
    "build_ote_rows",
    "stats_for",
]


def classify_ote(
    signal: AlignedSignal, htf_candles: tuple[Candle, ...], swings: list[SwingPoint], band: Band,
) -> bool | None:
    """`None` when there is nothing to evaluate: no credited `key_level`,
    or no impulse leg yet knowable at the purge index (both kinds of
    swing must already exist, strictly before the purge)."""
    if signal.key_level is None or signal.htf_context is None:
        return None

    crt_range = signal.htf_context
    purge_index = first_breach_index(
        htf_candles, crt_range.start_index, crt_range.resolved_at_index,
        high=crt_range.high, low=crt_range.low,
    )
    if purge_index is None:
        return None

    leg = impulse_leg(swings, before_index=purge_index, direction=signal.ltf_signal.direction)
    if leg is None:
        return None

    zone = ote_zone(leg[0], leg[1], band)
    return ote_overlaps_zone(signal.key_level.bottom, signal.key_level.top, zone)


@dataclass(frozen=True)
class OteRow:
    signal_id: str
    key_level_kind: str
    in_ote: bool | None
    outcome: Literal["win", "loss", "open"] | None
    r_multiple: float | None


def build_ote_rows(
    aligned_signals: list[AlignedSignal],
    htf_candles: tuple[Candle, ...],
    swings: list[SwingPoint],
    trades: list,
    band: Band,
) -> tuple[OteRow, ...]:
    """One row per confluent signal (`key_level is not None`), joined to
    its `Trade` on `signal_id` -- the same within-one-run join convention
    `experimental.key_level_reaction_redefinition` already established
    and verified against `backtest/population.py`'s own
    `signal_id=signal.signal_id` propagation."""
    trade_by_id = {trade.signal_id: trade for trade in trades}

    rows = []
    for signal in aligned_signals:
        if signal.key_level is None:
            continue
        signal_id = signal.ltf_signal.signal_id
        trade = trade_by_id.get(signal_id)
        rows.append(
            OteRow(
                signal_id=signal_id,
                key_level_kind=signal.key_level.kind,
                in_ote=classify_ote(signal, htf_candles, swings, band),
                outcome=trade.outcome if trade is not None else None,
                r_multiple=trade.r_multiple if trade is not None else None,
            )
        )
    return tuple(rows)


def stats_for(
    rows: tuple[OteRow, ...], *, in_ote: bool, key_level_kind: str | None = None
) -> dict[str, float | int]:
    """Win rate / avg R over closed trades in one `in_ote` bucket,
    optionally scoped to one `key_level.kind` -- the FVG-vs-OB slice the
    exploration flagged as the decisive check, since FVG dominates ~98%
    of confluence credits."""
    bucket = [
        row for row in rows
        if row.in_ote == in_ote and (key_level_kind is None or row.key_level_kind == key_level_kind)
    ]
    closed = [row for row in bucket if row.outcome in ("win", "loss")]
    wins = sum(1 for row in closed if row.outcome == "win")
    total_r = sum(row.r_multiple for row in closed if row.r_multiple is not None)
    return {
        "n": len(bucket),
        "n_closed": len(closed),
        "win_rate": wins / len(closed) if closed else 0.0,
        "avg_r": total_r / len(closed) if closed else 0.0,
    }


def kind_breakdown(rows: tuple[OteRow, ...]) -> dict[str, int]:
    return dict(Counter(row.key_level_kind for row in rows))
