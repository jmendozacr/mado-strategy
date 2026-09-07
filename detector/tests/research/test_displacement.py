import itertools

from fixtures.synthetic import CandleSeriesBuilder

from research.displacement import DisplacementEvent, detect_displacements, most_recent_before

# ---------------------------------------------------------------------------
# detect_displacements
# ---------------------------------------------------------------------------


def test_detect_displacements_known_bullish_shape():
    """Hand-verified: candles 0-1 are small/flat (ATR14 stays tiny). Candle 2
    is a large bullish body that alone clears ATR14 over the <=3-candle
    window ending at i=2 -> one bullish DisplacementEvent at index 2."""
    series = (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1005, low=1.0995, close=1.1002)  # 0 — filler
        .candle(open=1.1002, high=1.1007, low=1.0997, close=1.1004)  # 1 — filler
        .candle(open=1.1004, high=1.1210, low=1.0999, close=1.1200)  # 2 — large bullish body
        .build()
    )

    events = detect_displacements(series)

    assert len(events) == 1
    assert events[0] == DisplacementEvent(index=2, direction="bullish")


def test_detect_displacements_known_bearish_shape():
    series = (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1005, low=1.0995, close=1.1002)  # 0 — filler
        .candle(open=1.1002, high=1.1007, low=1.0997, close=1.1004)  # 1 — filler
        .candle(open=1.1200, high=1.1205, low=1.0995, close=1.1000)  # 2 — large bearish body
        .build()
    )

    events = detect_displacements(series)

    assert len(events) == 1
    assert events[0] == DisplacementEvent(index=2, direction="bearish")


def test_detect_displacements_no_body_never_clears_atr():
    """Small, flat bodies throughout -> body sum never clears ATR14 ->
    no events."""
    series = (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1005, low=1.0995, close=1.1002)
        .candle(open=1.1002, high=1.1007, low=1.0997, close=1.1004)
        .candle(open=1.1004, high=1.1009, low=1.0999, close=1.1006)
        .candle(open=1.1006, high=1.1011, low=1.1001, close=1.1008)
        .build()
    )

    assert detect_displacements(series) == []


# ---------------------------------------------------------------------------
# most_recent_before
# ---------------------------------------------------------------------------

_EVENTS = [
    DisplacementEvent(index=2, direction="bullish"),
    DisplacementEvent(index=5, direction="bearish"),
    DisplacementEvent(index=9, direction="bullish"),
]


def test_most_recent_before_picks_latest_qualifying_event():
    assert most_recent_before(_EVENTS, cutoff_index=10) == DisplacementEvent(index=9, direction="bullish")


def test_most_recent_before_right_closed_at_cutoff():
    """Same right-closed boundary convention as `research.order_block.is_active`
    -- an event AT the cutoff index itself still qualifies."""
    assert most_recent_before(_EVENTS, cutoff_index=5) == DisplacementEvent(index=5, direction="bearish")


def test_most_recent_before_excludes_events_after_cutoff():
    result = most_recent_before(_EVENTS, cutoff_index=6)
    assert result == DisplacementEvent(index=5, direction="bearish")
    assert result.index < 9


def test_most_recent_before_returns_none_when_no_event_qualifies():
    assert most_recent_before(_EVENTS, cutoff_index=1) is None


def test_most_recent_before_returns_none_for_empty_events():
    assert most_recent_before([], cutoff_index=100) is None


def test_most_recent_before_permutation_invariant():
    """Shuffled input list still picks the same event, by index not list
    position."""
    cutoff_index = 6
    expected = most_recent_before(_EVENTS, cutoff_index)

    for permutation in itertools.permutations(_EVENTS):
        assert most_recent_before(list(permutation), cutoff_index) == expected
