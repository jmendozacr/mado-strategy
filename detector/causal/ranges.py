"""Causal CRT range emission (REQ-CAUSAL-01/09): drives `causal.state`'s
bounded open-range machine chronologically over a series, so a range is
never visible before its own `resolved_at_index` candle has been processed.
"""

from core.candle import OHLCSeries
from core.config import CRTRangeConfig
from causal.state import OpenRangeState, advance_ranges
from primitives.crt_range import CRTRange


def causal_crt_ranges(series: OHLCSeries, config: CRTRangeConfig = CRTRangeConfig()) -> list[CRTRange]:
    """Every CRTRange resolved within `series`, in the same shape
    `detect_crt_ranges` would produce for that exact series — computed via
    the bounded incremental state machine rather than a monolithic pass, so
    a caller building this up candle-by-candle never sees a range before
    its own resolution index (REQ-CAUSAL-01)."""
    candles = series.candles
    state = OpenRangeState.initial()
    ranges: list[CRTRange] = []
    for new_index in range(len(candles)):
        resolved, state = advance_ranges(state, candles, new_index, config.max_lookback)
        ranges.extend(resolved)
    return ranges
