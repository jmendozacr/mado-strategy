from dataclasses import dataclass
from typing import Literal

from core.candle import Candle, OHLCSeries
from core.config import MSSConfig
from core.sweep import SweepSide, two_heap_sweep
from primitives.swing import SwingPoint, detect_swings


@dataclass(frozen=True)
class MSSEvent:
    index: int
    direction: Literal["bullish", "bearish"]
    broken_swing: SwingPoint


def detect_mss_events(
    series: OHLCSeries,
    config: MSSConfig = MSSConfig(),
    swings: list[SwingPoint] | None = None,
) -> list[MSSEvent]:
    """`swings` lets a caller that already computed them for the same
    `series` reuse them instead of a second O(n) fractal-swing pass —
    matching the `crt_ranges`/`fvgs` reuse pattern in
    `detect_model1_signals`. `None` (the default) preserves the original
    self-contained behavior.
    """
    candles = series.candles
    if swings is None:
        swings = detect_swings(series)

    pending = _pending_breaks(swings, config.decisive_close_ratio)
    break_indices = _sweep_decisive_breaks(candles, pending)

    events = []
    for (broken_swing, _threshold), break_index in zip(pending, break_indices):
        if break_index is None:
            continue
        direction: Literal["bullish", "bearish"] = (
            "bullish" if broken_swing.kind == "high" else "bearish"
        )
        events.append(
            MSSEvent(index=break_index, direction=direction, broken_swing=broken_swing)
        )

    return events


def _pending_breaks(
    swings: list[SwingPoint], decisive_close_ratio: float
) -> list[tuple[SwingPoint, float]]:
    """For each swing, pairs it with the threshold to break its most recent
    OPPOSITE-kind swing before it — in one forward pass over `swings`
    (already index-ascending) instead of re-filtering+max()'ing the whole
    list per swing (profiled as the dominant real-data cost, bigger than
    the decisive-break scan itself: O(n) per swing => O(n^2) overall).
    Swings sharing the same index (an outside candle setting both a new
    high and a new low) must not see each other as "before" — matching the
    original strict `s.index < index` — so trackers only update once an
    entire same-index group has been evaluated against the prior state.
    """
    pending: list[tuple[SwingPoint, float]] = []
    last_high: SwingPoint | None = None
    last_low: SwingPoint | None = None

    i = 0
    while i < len(swings):
        j = i
        while j < len(swings) and swings[j].index == swings[i].index:
            j += 1
        group = swings[i:j]

        for broken_swing in group:
            opposite_swing = last_low if broken_swing.kind == "high" else last_high
            if opposite_swing is None:
                continue
            distance = abs(broken_swing.price - opposite_swing.price)
            if distance <= 0:
                continue
            pending.append((broken_swing, distance * decisive_close_ratio))

        for swing in group:
            if swing.kind == "high":
                last_high = swing
            else:
                last_low = swing

        i = j

    return pending


def _sweep_decisive_breaks(
    candles: tuple[Candle, ...],
    pending: list[tuple[SwingPoint, float]],
) -> list[int | None]:
    """One forward pass resolves every swing's decisive break, using two
    heaps (one per swing kind) instead of rescanning the full still-open
    working set on every candle. The prior "sweep-line" (maintain a
    still-open set, re-check every member each candle) fixed the original
    O(n^2) restart-per-swing scan, but is itself still O(n * open_count) —
    at real-data scale (100,000 M5 candles, ~42,000 swings) this measured
    212s, the dominant real cost together with fvg.py's equivalent fix (see
    apply-progress). Resolution is monotonic — for a fixed close[j], EVERY
    open "high"-kind entry with (price+threshold) <= close[j] resolves now
    (min-heap by level), and EVERY open "low"-kind entry with
    (price-threshold) >= close[j] resolves now (max-heap by level) — a
    heap answers "does any/all of the extreme(s) qualify" in O(log n)
    instead of O(open_count). Each entry is pushed once (when eligible, at
    index+1) and popped once (when resolved, or never if it never breaks)
    — O(n + m log m) total, not O(n * m). Which candle resolves each swing
    is unchanged from the original per-instance scan — only the scan
    structure is (differential test: test_performance.py, against an
    independent reference reimplementation of the ORIGINAL per-instance
    scan). Uses the generic `two_heap_sweep` shared with fvg.py's
    fill-status resolution.
    """
    sides = (
        SweepSide(
            belongs=lambda p: p[0].kind == "high",
            heap_key=lambda p: p[0].price + p[1],  # level = price + threshold — min-heap
            resolves=lambda key, candle: key <= candle.close,
            result=lambda j: j,
        ),
        SweepSide(
            belongs=lambda p: p[0].kind == "low",
            heap_key=lambda p: -(p[0].price - p[1]),  # -level, level = price - threshold — max-heap
            resolves=lambda key, candle: -key >= candle.close,
            result=lambda j: j,
        ),
    )
    return two_heap_sweep(
        candles, pending,
        eligible_at=lambda p: p[0].index + 1,
        sides=sides,
        default=None,
    )
