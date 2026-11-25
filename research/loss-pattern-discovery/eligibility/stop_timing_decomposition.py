"""Phase 6 Unit B: decompose Phase 5's early-stop endpoint
(`confirmed_stop AND duration_bars <= 1`) into five mutually exclusive,
same-denominator timing categories (E0..E4).

Adds no new causal assumption: reuses `eligibility.stop_eligibility.classify_all`
and `common.trade_timing.compute_trade_timing` exactly as Phase 5 did -- this
is a finer partition of the SAME facts, never a new population or a new
engine rule. See docs/37-phase6-design-and-pre-registration.md section 4.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from common.trade_timing import compute_trade_timing
from core.candle import OHLCSeries
from eligibility.stop_eligibility import EligibilityResult, StopEligibility, classify_all
from schema.events import EventRecord, Outcome


class TimingCategory(str, Enum):
    SAME_BAR_SL = "E0_same_bar_sl"
    NEXT_BAR_SL = "E1_next_bar_sl"
    LATER_SL = "E2_later_sl"
    OTHER_EXIT = "E3_other_exit"
    OPEN_CENSORED = "E4_open_censored"


def is_confirmed_stop_category(category: StopEligibility) -> bool:
    return category in (StopEligibility.CONFIRMED_STOP, StopEligibility.STOP_AFTER_PARTIAL)


@dataclass(frozen=True)
class TimingClassification:
    event_id: str
    category: TimingCategory
    duration_bars: int | None


def classify_timing(
    record: EventRecord, series: OHLCSeries, eligibility: dict[str, EligibilityResult],
) -> TimingClassification:
    event_id = record.identification.event_id
    op = record.operation

    if op.outcome is Outcome.OPEN:
        return TimingClassification(event_id, TimingCategory.OPEN_CENSORED, None)
    if op.outcome is Outcome.WIN:
        return TimingClassification(event_id, TimingCategory.OTHER_EXIT, None)

    result = eligibility.get(event_id)
    if result is None or not is_confirmed_stop_category(result.category):
        # AMBIGUOUS_STOP / OTHER_NEGATIVE_EXIT: a loss, but not a confirmed
        # stop execution -- "otras salidas", never silently promoted to a
        # same/next/later-bar stop.
        return TimingClassification(event_id, TimingCategory.OTHER_EXIT, None)

    timing = compute_trade_timing(record, series)
    if timing.duration_bars is None:
        return TimingClassification(event_id, TimingCategory.OTHER_EXIT, None)
    if timing.duration_bars == 0:
        return TimingClassification(event_id, TimingCategory.SAME_BAR_SL, 0)
    if timing.duration_bars == 1:
        return TimingClassification(event_id, TimingCategory.NEXT_BAR_SL, 1)
    return TimingClassification(event_id, TimingCategory.LATER_SL, timing.duration_bars)


def classify_all_timing(
    records: list[EventRecord], series_by_instrument: dict[str, OHLCSeries],
) -> dict[str, TimingClassification]:
    eligibility = classify_all(records)
    out: dict[str, TimingClassification] = {}
    for r in records:
        series = series_by_instrument[r.identification.instrument]
        out[r.identification.event_id] = classify_timing(r, series, eligibility)
    return out
