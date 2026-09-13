"""Group 1 (REQ-CAUSAL-09): the causal generator's bounded state machine —
open LTF range tracking and the H-A HTF pointer — tested in isolation from
signal generation."""

from causal.state import (
    OpenRangeState,
    advance_ranges,
    fold_htf_context,
)
from core.config import CRTRangeConfig
from primitives.crt_range import CRTRange, detect_crt_ranges
from tests.fixtures.synthetic import three_candle_crt_setup, crt_range_never_resolves_setup


def test_open_range_state_starts_empty():
    state = OpenRangeState.initial()
    assert state.pending_starts == ()


def _drive(candles, max_lookback):
    """Feed `advance_ranges` one candle at a time, exactly like a
    chronological causal pass would — returns (resolved_by_new_index, all
    resolved in order)."""
    state = OpenRangeState.initial()
    by_index: dict[int, list[CRTRange]] = {}
    everything: list[CRTRange] = []
    for new_index in range(len(candles)):
        resolved, state = advance_ranges(state, candles, new_index, max_lookback)
        by_index[new_index] = resolved
        everything.extend(resolved)
    return by_index, everything, state


def test_advance_ranges_range_not_resolved_before_its_own_index():
    """A CRT range candidate must not exist in state output before the
    candle that resolves it — mirrors `detect_crt_ranges`'s own
    `resolved_at_index` semantics (REQ-CAUSAL-01/P1). The range starting at
    index 0 resolves at index 2 (true_break); it must be absent from every
    `new_index < 2` and present exactly once at `new_index == 2`.
    """
    series = three_candle_crt_setup()
    by_index, _, _ = _drive(series.candles, max_lookback=20)

    assert by_index[0] == []
    assert by_index[1] == []
    resolved_at_2 = {r.start_index: r for r in by_index[2]}
    assert 0 in resolved_at_2
    assert resolved_at_2[0].resolved_at_index == 2
    assert resolved_at_2[0].resolution == "true_break"


def test_advance_ranges_matches_full_series_detection():
    """The incremental state machine, driven candle-by-candle, must produce
    exactly the same set of ranges as calling `detect_crt_ranges` once on
    the complete series (the state machine is a resequencing of the same
    proven logic, not a different algorithm)."""
    series = three_candle_crt_setup()
    _, everything, _ = _drive(series.candles, max_lookback=20)

    expected = detect_crt_ranges(series)
    assert sorted(everything, key=lambda r: r.start_index) == sorted(expected, key=lambda r: r.start_index)


def test_advance_ranges_drops_unresolved_after_max_lookback():
    """REQ-14: a range that never resolves within its own max_lookback
    window is dropped from pending state, never emitted -- matching
    legacy's own "never emitted" behavior for
    `crt_range_never_resolves_setup`, and must agree with
    `detect_crt_ranges` on the full series."""
    series = crt_range_never_resolves_setup()
    _, everything, final_state = _drive(series.candles, max_lookback=2)

    assert everything == detect_crt_ranges(series, CRTRangeConfig(max_lookback=2))
    assert everything == []
    # start=0's 2-candle window is exhausted by the last candle (index 2);
    # start=1's window is not yet exhausted (needs one more candle than the
    # 3-candle fixture provides), so it legitimately remains pending — this
    # is the exact "still open, not yet emitted" state a longer series would
    # either resolve or later expire, never a currently-unaccounted range.
    assert 0 not in final_state.pending_starts


def test_fold_htf_context_picks_largest_purge_index():
    range_a = CRTRange(model="2-candle", high=1.2, low=1.1, start_index=0, end_index=1, resolution="true_break", resolved_at_index=1)
    range_b = CRTRange(model="2-candle", high=1.3, low=1.2, start_index=1, end_index=2, resolution="true_break", resolved_at_index=2)
    best = fold_htf_context(None, 5, range_a)
    best = fold_htf_context(best, 8, range_b)
    assert best == (8, range_b)


def test_fold_htf_context_tie_break_lowest_start_index():
    range_a = CRTRange(model="2-candle", high=1.2, low=1.1, start_index=5, end_index=6, resolution="true_break", resolved_at_index=6)
    range_b = CRTRange(model="2-candle", high=1.3, low=1.2, start_index=1, end_index=2, resolution="true_break", resolved_at_index=2)
    best = fold_htf_context(None, 8, range_a)
    best = fold_htf_context(best, 8, range_b)
    assert best == (8, range_b)  # same purge_index, range_b has lower start_index


def test_fold_htf_context_keeps_current_best_when_candidate_is_worse():
    range_a = CRTRange(model="2-candle", high=1.2, low=1.1, start_index=0, end_index=1, resolution="true_break", resolved_at_index=1)
    range_b = CRTRange(model="2-candle", high=1.3, low=1.2, start_index=1, end_index=2, resolution="true_break", resolved_at_index=2)
    best = fold_htf_context(None, 8, range_a)
    best = fold_htf_context(best, 3, range_b)
    assert best == (8, range_a)
