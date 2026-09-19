from __future__ import annotations
import bisect
from datetime import datetime

from core.broker_clock import (
    asia_range_timestamp,
    in_execution_window,
    in_priority_subwindow,
    is_london_crt_h4,
)
from core.candle import OHLCSeries
from core.forex_crt_context import ForexCRTContext, ForexCRTSignal
from alignment.htf_ltf import AlignedSignal


def detect_forex_crt_signals(
    aligned_signals: list[AlignedSignal],
    htf_series: OHLCSeries,
    ltf_series: OHLCSeries,
) -> list[ForexCRTSignal]:
    """Filter AlignedSignals to those satisfying the Forex broker-clock policy (REQ-73).

    Session identity is determined by the H4 candle that temporally encloses the M15
    anchor, derived via bisect_right — NOT CRTRange.start_index, which is the origin
    of a generic sliding window and carries no session information (REQ-73.7).
    """
    htf_timestamps = [c.timestamp for c in htf_series.candles]
    result = []

    for signal in aligned_signals:
        if signal.aligned != "aligned":
            continue

        m15_anchor_ts = ltf_series.candles[signal.ltf_signal.anchor_index].timestamp

        # Derive the H4 candle enclosing the M15 anchor (last H4 ts <= anchor).
        position = bisect.bisect_right(htf_timestamps, m15_anchor_ts)
        if position == 0:
            continue
        enclosing_h4_idx = position - 1

        if not is_london_crt_h4(htf_series.candles[enclosing_h4_idx].timestamp):
            continue
        if not in_execution_window(m15_anchor_ts):
            continue

        context = _build_forex_context(enclosing_h4_idx, htf_series)
        result.append(ForexCRTSignal(
            aligned_signal=signal,
            forex_context=context,
            priority=in_priority_subwindow(m15_anchor_ts),
        ))

    return result


def find_asia_range_index(
    london_crt_ts: datetime,
    htf_series: OHLCSeries,
) -> int | None:
    """Exact timestamp lookup for the 21:00 Asia range candle (REQ-71.2/71.3)."""
    target = asia_range_timestamp(london_crt_ts)
    for i, candle in enumerate(htf_series.candles):
        if candle.timestamp == target:
            return i
    return None


def _build_forex_context(
    enclosing_h4_idx: int,
    htf_series: OHLCSeries,
) -> ForexCRTContext:
    london_crt_ts = htf_series.candles[enclosing_h4_idx].timestamp
    asia_idx = find_asia_range_index(london_crt_ts, htf_series)
    if asia_idx is None:
        return ForexCRTContext(
            enclosing_h4_index=enclosing_h4_idx,
            asia_range_h4_index=None,
            asia_range_high=None,
            asia_range_low=None,
            asia_range_midpoint=None,
        )
    asia_candle = htf_series.candles[asia_idx]
    return ForexCRTContext(
        enclosing_h4_index=enclosing_h4_idx,
        asia_range_h4_index=asia_idx,
        asia_range_high=asia_candle.high,
        asia_range_low=asia_candle.low,
        asia_range_midpoint=(asia_candle.high + asia_candle.low) / 2,
    )
