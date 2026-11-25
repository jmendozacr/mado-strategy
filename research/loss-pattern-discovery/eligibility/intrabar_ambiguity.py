"""Phase 6 Unit C: intrabar execution-order uncertainty, as INDEPENDENT
dimensions (never collapsed into one mutually-exclusive label -- a same-bar
SL can simultaneously be gap-affected AND multi-level-ambiguous in
principle, even though in this dataset the latter never co-occurs with a
confirmed stop; see below).

Only `sequence_verifiable` is new inference; everything else is a direct
read of fields this lab's pipeline already produces. The one inference this
module makes is derived in docs/37-phase6-design-and-pre-registration.md
section 2: for a same-bar (E0) stop, if the fill candle's own OPEN already
lies on the stop-loss side of (or at) the entry price, price-path
continuity within the bar forces entry to have been touched no later than
the stop -- no intrabar order is invented beyond that one geometric fact.
Every other same-bar case stays genuinely unresolved.
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass

from common.series_index import timestamps_for
from core.candle import OHLCSeries
from eligibility.stop_timing_decomposition import TimingCategory, TimingClassification
from schema.events import EventRecord


@dataclass(frozen=True)
class IntrabarUncertainty:
    event_id: str
    engine_conservative_same_bar: bool
    sequence_verifiable: bool | None  # meaningful only when engine_conservative_same_bar
    same_bar_multi_level_ambiguity: bool
    gap_affected: bool
    insufficient_evidence: bool
    evidence: tuple[str, ...]
    engine_rule: str
    can_affirm: tuple[str, ...]
    cannot_affirm: tuple[str, ...]


def _sequence_verifiable(entry_price: float, stop_loss: float, direction: str, fill_open: float) -> bool:
    if direction == "bullish":
        return fill_open >= entry_price
    return fill_open <= entry_price


def classify_intrabar_uncertainty(
    record: EventRecord, timing: TimingClassification, series: OHLCSeries,
) -> IntrabarUncertainty:
    event_id = record.identification.event_id
    op = record.operation
    ident = record.identification
    same_bar_multi_level = bool(op.ambiguous_bar)

    if timing.category is not TimingCategory.SAME_BAR_SL:
        return IntrabarUncertainty(
            event_id=event_id,
            engine_conservative_same_bar=False,
            sequence_verifiable=None,
            same_bar_multi_level_ambiguity=same_bar_multi_level,
            gap_affected=bool(op.gap_filled),
            insufficient_evidence=False,
            evidence=("duration_bars != 0 -- entry closed on a bar strictly before the exit bar",),
            engine_rule="_resolve_level_exit (post-fill sweep, SL-wins-ties)",
            can_affirm=("entry's own bar had already closed before the exit bar began",),
            cannot_affirm=(),
        )

    timestamps = timestamps_for(series)
    index = bisect.bisect_left(timestamps, op.entry_ts) if op.entry_ts is not None else None
    found = (
        index is not None and index < len(series.candles)
        and series.candles[index].timestamp == op.entry_ts
    )
    if not found:
        return IntrabarUncertainty(
            event_id=event_id,
            engine_conservative_same_bar=True,
            sequence_verifiable=None,
            same_bar_multi_level_ambiguity=same_bar_multi_level,
            gap_affected=False,
            insufficient_evidence=True,
            evidence=("entry_ts could not be matched to a candle in the loaded M15 series",),
            engine_rule="_fill_candle_immediate_loss",
            can_affirm=(),
            cannot_affirm=("whether entry preceded the stop touch within this bar",),
        )

    fill_candle = series.candles[index]
    # `_fill_candle_immediate_loss` hardcodes gap_filled=False on this path
    # (a gap-through-SL fill candle is exempted upstream, never reaches E0);
    # restated here as a check, never overridden.
    verifiable = _sequence_verifiable(op.entry_price, op.stop_loss, ident.original_direction, fill_candle.open)
    return IntrabarUncertainty(
        event_id=event_id,
        engine_conservative_same_bar=True,
        sequence_verifiable=verifiable,
        same_bar_multi_level_ambiguity=same_bar_multi_level,
        gap_affected=False,
        insufficient_evidence=False,
        evidence=(
            f"fill_candle.open={fill_candle.open}, entry_price={op.entry_price}, "
            f"stop_loss={op.stop_loss}, direction={ident.original_direction}",
        ),
        engine_rule="_fill_candle_immediate_loss (SL touched on the fill bar wins over entry; tie-break never invoked here since ambiguous_bar routes to AMBIGUOUS_STOP upstream)",
        can_affirm=(
            ("entry preceded the stop touch, by price-path continuity from the fill bar's own open",)
            if verifiable else ()
        ),
        cannot_affirm=(
            () if verifiable
            else ("whether entry preceded or followed the stop touch within this single M15 bar",)
        ),
    )


def classify_all_intrabar_uncertainty(
    records: list[EventRecord],
    timing_by_id: dict[str, TimingClassification],
    series_by_instrument: dict[str, OHLCSeries],
) -> dict[str, IntrabarUncertainty]:
    out: dict[str, IntrabarUncertainty] = {}
    for r in records:
        event_id = r.identification.event_id
        timing = timing_by_id[event_id]
        series = series_by_instrument[r.identification.instrument]
        out[event_id] = classify_intrabar_uncertainty(r, timing, series)
    return out
