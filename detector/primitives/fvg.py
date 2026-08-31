from dataclasses import dataclass
from typing import Literal

from core.candle import Candle, OHLCSeries
from core.config import FVGConfig
from core.key_level import KeyLevel
from core.sweep import SweepSide, two_heap_sweep

_ATR_PERIOD = 14


@dataclass(frozen=True)
class FVG:
    start_index: int
    end_index: int
    top: float
    bottom: float
    direction: Literal["bullish", "bearish"]
    fill_status: Literal["open", "filled"]
    fill_index: int | None = None


def detect_fvgs(series: OHLCSeries, config: FVGConfig = FVGConfig()) -> list[FVG]:
    candles = series.candles
    candidates: list[tuple[int, Literal["bullish", "bearish"], float, float]] = []
    for i in range(len(candles) - 2):
        formed = _formed_gap(candles[i], candles[i + 2])
        if formed is None:
            continue
        direction, top, bottom = formed
        if (top - bottom) < config.min_size_atr * _atr(candles, i + 2):
            continue
        candidates.append((i, direction, top, bottom))

    fill_results = _sweep_fill_status(candles, candidates)

    return [
        FVG(
            start_index=start,
            end_index=start + 2,
            top=top,
            bottom=bottom,
            direction=direction,
            fill_status=status,
            fill_index=fill_index,
        )
        for (start, direction, top, bottom), (status, fill_index) in zip(candidates, fill_results)
    ]


def to_key_levels(fvgs: list[FVG]) -> list[KeyLevel]:
    return [
        KeyLevel(kind="fvg", top=fvg.top, bottom=fvg.bottom, origin_index=fvg.end_index)
        for fvg in fvgs
    ]


def _formed_gap(
    candle1: Candle, candle3: Candle
) -> tuple[Literal["bullish", "bearish"], float, float] | None:
    if candle3.low > candle1.high:
        return "bullish", candle3.low, candle1.high
    if candle3.high < candle1.low:
        return "bearish", candle1.low, candle3.high
    return None


def _sweep_fill_status(
    candles: tuple[Candle, ...],
    candidates: list[tuple[int, Literal["bullish", "bearish"], float, float]],
) -> list[tuple[Literal["open", "filled"], int | None]]:
    """One forward pass resolves every FVG's fill status/index, using two
    heaps (one per direction) instead of rescanning the full still-open
    working set on every candle. The prior "sweep-line" (maintain a
    still-open set, re-check every member each candle) fixed the original
    O(n^2) restart-per-FVG scan, but is itself still O(n * open_count) —
    at real-data scale (100,000 M5 candles, ~18,000 FVGs, many staying open
    for thousands of candles) this measured 189s, the dominant real cost
    (see apply-progress). Fill is monotonic — an FVG's bottom/top threshold
    only ever needs to be checked against ONE extreme per candle (the
    smallest still-open bottom≥low can't fill without the largest also
    being checked... see below) — which is exactly what a heap answers in
    O(log n) instead of O(open_count):

    - bullish fills when low[j] <= bottom: for a fixed low[j], EVERY open
      bullish FVG with bottom >= low[j] fills now. A max-heap keyed by
      bottom lets us pop them all (largest bottom first — if it doesn't
      satisfy `bottom >= low[j]`, no smaller bottom can either).
    - bearish fills when high[j] >= top: symmetric, min-heap keyed by top.

    Each candidate is pushed once (when eligible, at start+3) and popped
    once (when filled, or never if it stays open) — O(n + m log m) total,
    not O(n * m). Which candle resolves each FVG is unchanged from the
    original per-instance scan — only the scan structure is (differential
    test: test_performance.py, against an independent reference
    reimplementation of the ORIGINAL per-instance scan). Uses the generic
    `two_heap_sweep` shared with mss.py's decisive-break resolution.
    """
    sides = (
        SweepSide(
            belongs=lambda c: c[1] == "bullish",
            heap_key=lambda c: -c[3],  # -bottom — max-heap by bottom
            resolves=lambda key, candle: -key >= candle.low,
            result=lambda j: ("filled", j),
        ),
        SweepSide(
            belongs=lambda c: c[1] == "bearish",
            heap_key=lambda c: c[2],  # top — min-heap by top
            resolves=lambda key, candle: key <= candle.high,
            result=lambda j: ("filled", j),
        ),
    )
    return two_heap_sweep(
        candles, candidates,
        eligible_at=lambda c: c[0] + 3,
        sides=sides,
        default=("open", None),
    )


def _true_range(candles: tuple[Candle, ...], index: int) -> float:
    candle = candles[index]
    if index == 0:
        return candle.high - candle.low
    prev_close = candles[index - 1].close
    return max(
        candle.high - candle.low,
        abs(candle.high - prev_close),
        abs(candle.low - prev_close),
    )


def _atr(candles: tuple[Candle, ...], index: int) -> float:
    start = max(0, index - _ATR_PERIOD + 1)
    true_ranges = [_true_range(candles, j) for j in range(start, index + 1)]
    return sum(true_ranges) / len(true_ranges)
