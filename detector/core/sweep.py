import heapq
from dataclasses import dataclass
from typing import Any, Callable

from core.candle import Candle


@dataclass(frozen=True)
class SweepSide:
    """One side of a two-heap forward sweep (see `two_heap_sweep`).

    `belongs`: does this item resolve on this side?
    `heap_key`: value pushed into this side's heap for an eligible item
        (already sign-adjusted by the caller for min-heap semantics, e.g.
        negated to emulate a max-heap).
    `resolves`: given the current heap-top key and the candle being swept,
        should the top entry resolve now?
    `result`: the value written into the result slot when an entry
        resolves at candle index `j`.
    """

    belongs: Callable[[Any], bool]
    heap_key: Callable[[Any], float]
    resolves: Callable[[float, Candle], bool]
    result: Callable[[int], Any]


def two_heap_sweep(
    candles: tuple[Candle, ...],
    items: list[Any],
    eligible_at: Callable[[Any], int],
    sides: tuple[SweepSide, SweepSide],
    default: Any,
) -> list[Any]:
    """One forward pass over `candles` resolves every item in `items`
    against whichever of the two `sides` it `belongs` to, using one heap
    per side instead of rescanning the full still-open working set on
    every candle. Monotonic resolution — for a fixed candle, EVERY open
    entry whose heap-top key satisfies `resolves` resolves now — is what
    lets a heap answer "does the extreme qualify" in O(log n) instead of
    O(open_count). Each item is pushed once (at `eligible_at`) and popped
    once (when resolved, or never if it never resolves) — O(n + m log m)
    total, not O(n * m).
    """
    results: list[Any] = [default for _ in items]
    heaps: tuple[list[tuple[float, int]], list[tuple[float, int]]] = ([], [])

    pointer = 0
    total = len(items)

    for j, candle in enumerate(candles):
        while pointer < total and eligible_at(items[pointer]) <= j:
            item = items[pointer]
            for heap, side in zip(heaps, sides):
                if side.belongs(item):
                    heapq.heappush(heap, (side.heap_key(item), pointer))
                    break
            pointer += 1

        for heap, side in zip(heaps, sides):
            while heap and side.resolves(heap[0][0], candle):
                _, idx = heapq.heappop(heap)
                results[idx] = side.result(j)

        if pointer >= total and not heaps[0] and not heaps[1]:
            break

    return results
