from dataclasses import dataclass
from typing import Literal

from core.candle import Candle, OHLCSeries
from core.config import CRTRangeConfig


@dataclass(frozen=True)
class CRTRange:
    model: Literal["2-candle", "3-candle", "multi-inside", "multi-outside"]
    high: float
    low: float
    start_index: int
    end_index: int
    resolution: Literal["true_break", "false_break"]
    resolved_at_index: int


def first_breach_index(
    candles: tuple[Candle, ...],
    start: int,
    end: int,
    high: float | None = None,
    low: float | None = None,
) -> int | None:
    """First candle index in `(start, end]` whose wick breaches `high`
    and/or `low` — the purge concept shared by Model-1's own LTF anchor
    scan (one side at a time, via `high` xor `low`) and HTF/LTF alignment's
    purge-candle lookup (both sides in one pass, via `high` and `low`
    together).
    """
    for j in range(start + 1, end + 1):
        candle = candles[j]
        if high is not None and candle.high > high:
            return j
        if low is not None and candle.low < low:
            return j
    return None


@dataclass(frozen=True)
class _Resolution:
    kind: Literal["true_break", "false_break"]
    resolved_at_index: int
    first_action_offset: int
    resolved_offset: int


def detect_crt_ranges(
    series: OHLCSeries, config: CRTRangeConfig = CRTRangeConfig()
) -> list[CRTRange]:
    candles = series.candles
    ranges = []
    for i in range(len(candles) - 1):
        range_high = candles[i].high
        range_low = candles[i].low
        resolution = _resolve(candles, i, range_high, range_low, config.max_lookback)
        if resolution is None:
            continue
        ranges.append(
            CRTRange(
                model=_classify_model(resolution),
                high=range_high,
                low=range_low,
                start_index=i,
                end_index=resolution.resolved_at_index,
                resolution=resolution.kind,
                resolved_at_index=resolution.resolved_at_index,
            )
        )
    return ranges


def _resolve(
    candles: tuple[Candle, ...],
    i: int,
    range_high: float,
    range_low: float,
    max_lookback: int,
) -> _Resolution | None:
    last = min(i + max_lookback, len(candles) - 1)
    poke_side: Literal["high", "low"] | None = None
    first_action_offset: int | None = None

    for j in range(i + 1, last + 1):
        candle = candles[j]
        offset = j - i

        if candle.close > range_high or candle.close < range_low:
            if first_action_offset is None:
                first_action_offset = offset
            return _Resolution(
                kind="true_break",
                resolved_at_index=j,
                first_action_offset=first_action_offset,
                resolved_offset=offset,
            )

        if poke_side is not None:
            midpoint = (range_high + range_low) / 2
            if (poke_side == "low" and candle.close >= midpoint) or (
                poke_side == "high" and candle.close <= midpoint
            ):
                return _Resolution(
                    kind="false_break",
                    resolved_at_index=j,
                    first_action_offset=first_action_offset,
                    resolved_offset=offset,
                )

        if poke_side is None and (candle.high > range_high or candle.low < range_low):
            poke_side = "high" if candle.high > range_high else "low"
            first_action_offset = offset

    return None


def _classify_model(
    resolution: _Resolution,
) -> Literal["2-candle", "3-candle", "multi-inside", "multi-outside"]:
    if resolution.first_action_offset >= 2:
        return "multi-inside"
    if resolution.resolved_offset == 1:
        return "2-candle"
    if resolution.resolved_offset == 2:
        return "3-candle"
    return "multi-outside"
