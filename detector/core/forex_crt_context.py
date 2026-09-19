from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class ForexCRTContext:
    """Links the enclosing H4 candle (01:00 broker clock) with its 21:00 Asia reference range.

    enclosing_h4_index is bisect-derived: last H4 index whose timestamp <= M15 anchor timestamp.
    It is NOT CRTRange.start_index.
    asia_range_* fields are None when the 21:00 candle is absent (series starts after it).
    """
    enclosing_h4_index: int
    asia_range_h4_index: int | None
    asia_range_high: float | None
    asia_range_low: float | None
    asia_range_midpoint: float | None  # (high + low) / 2 [charter-8, 00:11:33]


@dataclass(frozen=True)
class ForexCRTSignal:
    """AlignedSignal that satisfies the Forex broker-clock policy.

    Does NOT imply trade eligibility — profiles, order flow, daily narrative, and
    target policy are all deferred.
    """
    aligned_signal: object  # AlignedSignal — typed as object to avoid circular import at core layer
    forex_context: ForexCRTContext
    priority: bool  # True when M15 anchor is in 03:00–04:00 [charter-9, 00:05:18]
