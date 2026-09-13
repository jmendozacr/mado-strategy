"""HTF visibility rule H-A (REQ-CAUSAL-08): at LTF event time `t`, the
selected HTF context is the resolved range with the LARGEST `purge_index`
among ranges whose OWN `resolved_at_index` candle has fully closed by `t` —
tie-break lowest `start_index`. This supersedes legacy `tag_alignment`'s
`_enclosing_htf_index` (keyed on the LTF anchor's earlier timestamp, and
blind to whether the mapped range's resolution was itself knowable yet) for
causal purposes (Section D1 of the spec proves the literal-preserving
alternative, H-B, is degenerate).
"""

from datetime import datetime

from causal.state import fold_htf_context
from core.candle import OHLCSeries
from core.pairing_table import TIMEFRAME_DURATIONS
from primitives.crt_range import CRTRange, first_breach_index


def select_htf_context(
    htf_series: OHLCSeries, htf_ranges: list[CRTRange], t: datetime
) -> CRTRange | None:
    """`htf_ranges` may include ranges resolved arbitrarily far in the
    future relative to `t` (e.g. detected from a longer HTF series than
    was actually knowable at `t`) — REQ-CAUSAL-08's closure condition
    (`resolved_at candle closed by t`) is what enforces causality here, not
    the caller having to pre-truncate `htf_ranges` itself. This is what
    lets a caller feed the full currently-available HTF range set for many
    different LTF signals' different `t` values without re-detecting per
    signal (REQ-CAUSAL-09's complexity bound)."""
    htf_candles = htf_series.candles
    htf_duration = TIMEFRAME_DURATIONS[htf_series.timeframe]

    best = None
    for htf_range in htf_ranges:
        if htf_candles[htf_range.resolved_at_index].timestamp + htf_duration > t:
            continue  # not yet closed by t -- not causally observable
        purge_index = first_breach_index(
            htf_candles, htf_range.start_index, htf_range.resolved_at_index,
            high=htf_range.high, low=htf_range.low,
        )
        if purge_index is not None:
            best = fold_htf_context(best, purge_index, htf_range)

    return best[1] if best is not None else None
