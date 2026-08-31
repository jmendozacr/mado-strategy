import bisect
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from core.candle import Candle, OHLCSeries
from core.config import CRTRangeConfig, FVGConfig, Model1Config
from core.key_level import KeyLevel
from core.pairing_table import TIMEFRAME_DURATIONS
from entries.model1 import Model1Signal, detect_model1_signals
from primitives.crt_range import CRTRange, detect_crt_ranges, first_breach_index

Alignment = Literal["aligned", "unaligned", "insufficient_htf_data"]


@dataclass(frozen=True)
class AlignedSignal:
    ltf_signal: Model1Signal
    htf_context: CRTRange | None
    aligned: Alignment
    key_level: KeyLevel | None = None


def tag_alignment(
    htf_series: OHLCSeries,
    ltf_series: OHLCSeries,
    crt_config: CRTRangeConfig = CRTRangeConfig(),
    fvg_config: FVGConfig = FVGConfig(),
    model1_config: Model1Config = Model1Config(),
    ltf_signals: list[Model1Signal] | None = None,
    htf_ranges: list[CRTRange] | None = None,
    htf_key_levels: list[KeyLevel] | None = None,
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

    `htf_key_levels` breaks that convention deliberately (ADR-012): `None`
    means "no Key Level sources registered" (every `key_level` stays
    `None`), NOT "self-compute FVG key levels" — the caller (`cli.py`)
    injects sources so this module never imports a source detector.
    """
    htf_candles = htf_series.candles
    htf_timestamps = [c.timestamp for c in htf_candles]
    if ltf_signals is None:
        ltf_signals = detect_model1_signals(ltf_series, crt_config, fvg_config, model1_config)
    if htf_ranges is None:
        htf_ranges = detect_crt_ranges(htf_series, crt_config)
    purge_index_to_range = _purge_index_map(htf_candles, htf_ranges)
    key_level_credit_map = _key_level_credit_map(
        htf_candles, purge_index_to_range, htf_key_levels or []
    )
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
            tags.append(
                AlignedSignal(
                    ltf_signal=signal, htf_context=crt_range, aligned="aligned",
                    key_level=key_level_credit_map.get(relevant_index),
                )
            )
        else:
            tags.append(AlignedSignal(ltf_signal=signal, htf_context=None, aligned="unaligned"))

    return tags


def _purge_wick_extremes(purge_candle: Candle, crt_range: CRTRange) -> tuple[float, ...]:
    """The extreme(s) on the side(s) actually breached — the breach(es)
    that made this the purge candle (REQ-55.6/.7). Both sides can breach on
    the same candle (~14.1% of real H4 purges); NEVER derived from a
    signal's `direction` — that mapping is exactly what REQ-55.7 exists to
    catch as wrong."""
    extremes = []
    if purge_candle.high > crt_range.high:
        extremes.append(purge_candle.high)
    if purge_candle.low < crt_range.low:
        extremes.append(purge_candle.low)
    return tuple(extremes)


def _key_level_credit_map(
    candles: tuple[Candle, ...],
    purge_index_to_range: dict[int, CRTRange],
    key_levels: list[KeyLevel],
) -> dict[int, KeyLevel]:
    """Eager, keyed by purge index — O(purges x levels x extremes<=2),
    independent of LTF signal count (design §12). A level qualifies for a
    purge if some credited extreme satisfies all three: knowable before the
    purge (REQ-54.4), unexpired at-or-before the purge (REQ-55.9/.10/.11,
    right-closed), and inside the level's zone inclusive of both edges
    (REQ-55.4). Both extremes are evaluated independently and their
    qualifying levels pooled; the lowest origin_index wins across the pool
    (REQ-55.6/.12/.13) — no high-side preference."""
    credit_map: dict[int, KeyLevel] = {}
    for purge_index, crt_range in purge_index_to_range.items():
        extremes = _purge_wick_extremes(candles[purge_index], crt_range)
        qualifying = [
            level
            for extreme in extremes
            for level in key_levels
            if level.origin_index < purge_index
            and (level.expiry_index is None or purge_index <= level.expiry_index)
            and level.bottom <= extreme <= level.top
        ]
        if qualifying:
            credit_map[purge_index] = min(qualifying, key=lambda level: level.origin_index)
    return credit_map


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
