import bisect
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Literal

from core.candle import Candle, OHLCSeries, first_overlap_index
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
    key_level_reaction: Literal["reject_close_inside", "continuation"] | None = None


def tag_alignment(
    htf_series: OHLCSeries,
    ltf_series: OHLCSeries,
    crt_config: CRTRangeConfig = CRTRangeConfig(),
    fvg_config: FVGConfig = FVGConfig(),
    model1_config: Model1Config = Model1Config(),
    ltf_signals: list[Model1Signal] | None = None,
    htf_ranges: list[CRTRange] | None = None,
    htf_key_levels: list[KeyLevel] | None = None,
    daily_series: OHLCSeries | None = None,
    daily_key_levels: list[KeyLevel] | None = None,
    credit_priority: dict[str, int] | None = None,
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

    `daily_series`/`daily_key_levels` (V3, ADR-E): `daily_key_levels` carry
    indices into `daily_series`, a DIFFERENT series than `htf_series` —
    they are reindexed into H4-index-space (`_reindex_daily_key_levels`)
    before joining `htf_key_levels` in the credit map. Both must be
    provided together; either omitted means no Daily-sourced Key Levels
    (mirrors `htf_key_levels`'s own None-means-none convention).

    `credit_priority` (opt-in, `None` default preserves the existing
    highest-`origin_index`-wins tiebreak exactly): a `KeyLevel.kind ->
    int` ranking, highest wins, `origin_index` only breaks a tie WITHIN
    the same priority tier. Grounded in measurement, not a guess —
    `sdd/crt-detector-order-block-redefinition` found a ~2x real-break
    confirmation-rate gap between Key Level sources (fvg ~48-50% vs a
    redefined ict_order_block ~75-82%) that pure recency cannot express:
    FVG is H4-native and continuously refreshed, so it wins the
    highest-origin_index tiebreak almost by construction regardless of
    which source is actually more trustworthy. An unlisted `kind`
    defaults to priority `0`.
    """
    htf_candles = htf_series.candles
    htf_timestamps = [c.timestamp for c in htf_candles]
    if ltf_signals is None:
        ltf_signals = detect_model1_signals(ltf_series, crt_config, fvg_config, model1_config)
    if htf_ranges is None:
        htf_ranges = detect_crt_ranges(htf_series, crt_config)
    purge_index_to_range = _purge_index_map(htf_candles, htf_ranges)
    all_key_levels = list(htf_key_levels or [])
    if daily_series is not None and daily_key_levels:
        all_key_levels += _reindex_daily_key_levels(
            daily_key_levels, daily_series.candles, htf_candles, htf_timestamps
        )
    key_level_credit_map = _key_level_credit_map(
        htf_candles, purge_index_to_range, all_key_levels, credit_priority=credit_priority
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
            credited_key_level = key_level_credit_map.get(relevant_index)
            tags.append(
                AlignedSignal(
                    ltf_signal=signal, htf_context=crt_range, aligned="aligned",
                    key_level=credited_key_level,
                    key_level_reaction=(
                        _purge_reaction(htf_candles[relevant_index], crt_range)
                        if credited_key_level is not None else None
                    ),
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


def _purge_reaction(purge_candle: Candle, crt_range: CRTRange) -> Literal["reject_close_inside", "continuation"]:
    """Reportable alongside `key_level` (never gates it): charter-1
    [00:12:59]/charter-6 [00:03:25] describe the methodology's own
    'confirmación real' as the purge candle closing back inside the CRT
    range after touching the Key Level — the M-shaped reaction (charter-2
    [00:21:14]). charter-1 [00:13:45-00:14:40]/charter-2 [00:22:03] also
    document a second valid shape where the same candle instead closes
    through, continuing straight to the opposite extreme (V-shaped) — this
    purely classifies which shape the credited purge candle took; it does
    not change whether `key_level` itself is credited."""
    return (
        "reject_close_inside" if crt_range.low <= purge_candle.close <= crt_range.high else "continuation"
    )


def _key_level_credit_map(
    candles: tuple[Candle, ...],
    purge_index_to_range: dict[int, CRTRange],
    key_levels: list[KeyLevel],
    credit_priority: dict[str, int] | None = None,
) -> dict[int, KeyLevel]:
    """Eager, keyed by purge index — O(purges x levels x extremes<=2),
    independent of LTF signal count (design §12). A level qualifies for a
    purge if some credited extreme satisfies all three: knowable before the
    purge (REQ-54.4), unexpired at-or-before the purge (REQ-55.9/.10/.11,
    right-closed), and inside the level's zone inclusive of both edges
    (REQ-55.4). Both extremes are evaluated independently and their
    qualifying levels pooled; the HIGHEST origin_index (most recent) wins
    across the pool (REQ-63.4, V3 — was lowest/oldest under V2's REQ-55.6,
    flipped because the most-recent Key Level is the more relevant one for
    a Daily-tier source, ADR-E) — unless `credit_priority` ranks `kind`
    above pure recency, in which case `origin_index` only breaks a tie
    within the top-ranked tier. `credit_priority=None` (the default)
    reproduces the original tiebreak exactly, byte-for-byte — every
    existing caller is unaffected."""
    tiebreak_key = (
        (lambda level: level.origin_index)
        if credit_priority is None
        else (lambda level: (credit_priority.get(level.kind, 0), level.origin_index))
    )
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
            credit_map[purge_index] = max(qualifying, key=tiebreak_key)
    return credit_map


def _reindex_daily_key_levels(
    levels: list[KeyLevel], daily_candles: tuple[Candle, ...], htf_candles: tuple[Candle, ...],
    htf_timestamps: list[datetime],
) -> list[KeyLevel]:
    """V4/REQ-63.7: translates Daily-sourced KeyLevels into H4-index-space.
    origin_index reindexes from the CONFIRMATION daily candle's CLOSE
    (conservative: never knowable earlier) — unchanged from V3. expiry_index
    is NOT translated from a Daily-native invalidation boundary at all
    (that was V3's mistake — a Daily candle's high/low blends 24h of
    movement into one blunt touch test) — it is freshly computed by
    scanning H4 candles one by one, starting at the reindexed origin_index,
    for the first H4 candle whose OWN range overlaps the zone."""
    reindexed = []
    for level in levels:
        origin = _ceiling_htf_index(htf_timestamps, _daily_close(daily_candles, level.origin_index))
        expiry = _htf_expiry_index(htf_candles, origin, level.top, level.bottom)
        reindexed.append(replace(level, origin_index=origin, expiry_index=expiry))
    return reindexed


def _daily_close(daily_candles: tuple[Candle, ...], index: int) -> datetime:
    """A Daily candle's own close = the next Daily candle's open when one
    exists; falls back to +1 day for the series' own last candle (Daily
    bars are UTC-daily per the confirmed broker-is-UTC+0 finding)."""
    if index + 1 < len(daily_candles):
        return daily_candles[index + 1].timestamp
    return daily_candles[index].timestamp + timedelta(days=1)


def _ceiling_htf_index(htf_timestamps: list[datetime], timestamp: datetime) -> int:
    """First H4 index whose own timestamp >= `timestamp` — the mirror image
    of `_enclosing_htf_index`'s floor lookup. Returns `len(htf_timestamps)`
    (an out-of-range sentinel, never a real H4 index) when the boundary is
    beyond the last available H4 candle — `_htf_expiry_index`'s scan below
    then naturally covers zero candles and returns `None`, and
    `_key_level_credit_map`'s `level.origin_index < purge_index` correctly
    never matches — both the intended 'not yet knowable within this
    series' outcome."""
    return bisect.bisect_left(htf_timestamps, timestamp)


def _htf_expiry_index(
    htf_candles: tuple[Candle, ...], start_index: int, top: float, bottom: float,
) -> int | None:
    """REQ-63.7 (V4): the H4-native invalidation scan a Daily-sourced Order
    Block needs — NOT a translation of `detect_ict_order_blocks`'s own
    Daily-native invalidation_index. Scans H4 candles from `start_index`
    (inclusive) onward for the first whose range overlaps `[bottom, top]`.
    Starts AT start_index, not start_index + 1 — unlike
    `detect_ict_order_blocks`'s own i+2 exclusion (REQ-62.4), `start_index`
    here is a reindexed ORIGIN boundary, not a same-series confirmation
    candle guaranteed to overlap the zone by construction (full
    engulfment) — there is no structural reason to exclude it."""
    return first_overlap_index(htf_candles, start_index, top, bottom)


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
