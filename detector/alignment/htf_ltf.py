import bisect
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from core.candle import Candle, OHLCSeries
from core.config import CRTRangeConfig, FVGConfig, Model1Config
from core.pairing_table import TIMEFRAME_DURATIONS
from entries.model1 import Model1Signal, detect_model1_signals
from primitives.crt_range import CRTRange, detect_crt_ranges, first_breach_index

Alignment = Literal["aligned", "unaligned", "insufficient_htf_data"]


@dataclass(frozen=True)
class AlignedSignal:
    ltf_signal: Model1Signal
    htf_context: CRTRange | None
    aligned: Alignment


def tag_alignment(
    htf_series: OHLCSeries,
    ltf_series: OHLCSeries,
    crt_config: CRTRangeConfig = CRTRangeConfig(),
    fvg_config: FVGConfig = FVGConfig(),
    model1_config: Model1Config = Model1Config(),
    ltf_signals: list[Model1Signal] | None = None,
    htf_ranges: list[CRTRange] | None = None,
) -> list[AlignedSignal]:
    """Tag each LTF Model-1 signal against the HTF CRT purge window it
    falls in (REQ-05). A resolved HTF CRTRange's "purge candle" is the
    first HTF candle whose wick exceeds the range's High/Low (the same
    purge concept Model-1 itself uses for its own LTF anchor, per
    charter-2 [00:04:23] "penetra por debajo/encima... para extraer
    liquidez") — its own 1-candle span IS the purge window (design 4.4).

    `ltf_signals`/`htf_ranges` let a caller that already computed them for
    the same series+config reuse them instead of a second detection pass
    (see `detect_model1_signals`'s `crt_ranges`/`fvgs` params for the same
    pattern). `None` (the default) preserves the original self-contained
    behavior.
    """
    htf_candles = htf_series.candles
    htf_timestamps = [c.timestamp for c in htf_candles]
    if ltf_signals is None:
        ltf_signals = detect_model1_signals(ltf_series, crt_config, fvg_config, model1_config)
    if htf_ranges is None:
        htf_ranges = detect_crt_ranges(htf_series, crt_config)
    purge_index_to_range = _purge_index_map(htf_candles, htf_ranges)
    htf_duration = TIMEFRAME_DURATIONS[htf_series.timeframe]
    last_htf_index = len(htf_candles) - 1

    tags = []
    for signal in ltf_signals:
        anchor_timestamp = ltf_series.candles[signal.anchor_index].timestamp
        relevant_index = _enclosing_htf_index(htf_timestamps, anchor_timestamp)

        if relevant_index is None:
            tags.append(AlignedSignal(ltf_signal=signal, htf_context=None, aligned="unaligned"))
            continue

        if relevant_index == last_htf_index:
            htf_candle_end = htf_candles[relevant_index].timestamp + htf_duration
            if ltf_series.candles[-1].timestamp < htf_candle_end:
                tags.append(
                    AlignedSignal(ltf_signal=signal, htf_context=None, aligned="insufficient_htf_data")
                )
                continue

        crt_range = purge_index_to_range.get(relevant_index)
        if crt_range is not None:
            tags.append(AlignedSignal(ltf_signal=signal, htf_context=crt_range, aligned="aligned"))
        else:
            tags.append(AlignedSignal(ltf_signal=signal, htf_context=None, aligned="unaligned"))

    return tags


def _purge_index_map(
    candles: tuple[Candle, ...], ranges: list[CRTRange]
) -> dict[int, CRTRange]:
    """Maps each HTF purge candle index to its resolved CRTRange. Ranges
    are NOT deduplicated by `detect_crt_ranges` (design 4.4), so two
    different candidate ranges can share the same purge candle — the
    earliest-established range (lowest start_index, matching iteration
    order) wins as the more likely intended HTF context.
    """
    mapping: dict[int, CRTRange] = {}
    for crt_range in ranges:
        purge_index = first_breach_index(
            candles, crt_range.start_index, crt_range.resolved_at_index,
            high=crt_range.high, low=crt_range.low,
        )
        if purge_index is not None:
            mapping.setdefault(purge_index, crt_range)
    return mapping


def _enclosing_htf_index(htf_timestamps: list[datetime], timestamp: datetime) -> int | None:
    """The last HTF candle whose own timestamp is <= `timestamp`. HTF
    timestamps are guaranteed sorted ascending, so `bisect` replaces what
    was a full linear scan per LTF signal (Bug 1: O(n) per lookup, O(n^2)
    total across all signals) with an O(log n) lookup.
    """
    position = bisect.bisect_right(htf_timestamps, timestamp)
    return position - 1 if position > 0 else None
