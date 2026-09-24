"""Bounded state primitives for causal candidate generation (REQ-CAUSAL-09).

Two pieces of state, each bounded independently of series length:

- `OpenRangeState` — LTF CRT range candidates not yet resolved. Capped at
  `max_lookback` entries at any time: a start older than that has
  necessarily already resolved or expired (`primitives.crt_range._resolve`'s
  own bounded window).
- H-A's HTF pointer — folded via `fold_htf_context`, a running "best
  eligible context so far" (max `purge_index`, tie-break lowest
  `start_index`, REQ-CAUSAL-08) rather than a retained buffer of every HTF
  range ever seen.

Both reuse `primitives.crt_range`'s own resolution logic unmodified —
no re-implementation of CRT range detection, only incremental sequencing of
it (REQ-CAUSAL-11-style reuse discipline).
"""

from dataclasses import dataclass

from core.candle import Candle
from primitives.crt_range import CRTRange, _classify_model, _resolve


@dataclass(frozen=True)
class OpenRangeState:
    """`pending_starts`: LTF candle indices that could still resolve into a
    CRTRange — every start not yet resolved and not yet expired."""

    pending_starts: tuple[int, ...]

    @staticmethod
    def initial() -> "OpenRangeState":
        return OpenRangeState(pending_starts=())


def advance_ranges(
    state: OpenRangeState,
    candles: tuple[Candle, ...],
    new_index: int,
    series_config_max_lookback: int,
) -> tuple[list[CRTRange], OpenRangeState]:
    """Fold in one more available candle (`new_index`, 0-based, the newest
    index now visible). Every candle strictly before `new_index` is a
    potential range start (a range needs at least one following candle to
    test for a breach) and joins the pending set; every already-pending
    start is re-tested for resolution using only candles up to `new_index`
    (inclusive) — the same bounded window `_resolve` itself uses, just fed
    incrementally instead of all at once. A start whose `max_lookback`
    window has been exhausted without resolving is dropped (REQ-14: never
    emitted), exactly matching `detect_crt_ranges`'s own behavior.

    Returns `(newly_resolved_ranges, updated_state)`.
    """
    pending = set(state.pending_starts)
    if new_index >= 1:
        pending.add(new_index - 1)

    resolved: list[CRTRange] = []
    still_pending: list[int] = []
    window = candles[: new_index + 1]

    for start in sorted(pending):
        resolution = _resolve(
            window, start, candles[start].high, candles[start].low, series_config_max_lookback
        )
        if resolution is not None:
            resolved.append(
                CRTRange(
                    model=_classify_model(resolution),
                    high=candles[start].high,
                    low=candles[start].low,
                    start_index=start,
                    end_index=resolution.resolved_at_index,
                    resolution=resolution.kind,
                    resolved_at_index=resolution.resolved_at_index,
                )
            )
        elif new_index - start < series_config_max_lookback:
            still_pending.append(start)
        # else: max_lookback window exhausted with no resolution -> dropped

    return resolved, OpenRangeState(pending_starts=tuple(still_pending))


HTFBest = tuple[int, CRTRange] | None


def fold_htf_context(current_best: HTFBest, candidate_purge_index: int, candidate_range: CRTRange) -> HTFBest:
    """H-A's own comparison rule (REQ-CAUSAL-08), as an incremental
    reducer: the largest `purge_index` wins; ties break on the lowest
    `start_index`. Folding candidates one at a time (in any order) yields
    the same result as evaluating them all at once, so this doubles as
    both the incremental HTF pointer update and `causal.htf`'s batch
    selection reducer."""
    if current_best is None:
        return (candidate_purge_index, candidate_range)
    best_purge_index, best_range = current_best
    if candidate_purge_index > best_purge_index:
        return (candidate_purge_index, candidate_range)
    if candidate_purge_index == best_purge_index and candidate_range.start_index < best_range.start_index:
        return (candidate_purge_index, candidate_range)
    return current_best
