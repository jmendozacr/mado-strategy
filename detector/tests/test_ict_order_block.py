from fixtures.synthetic import CandleSeriesBuilder

from primitives.ict_order_block import detect_ict_order_blocks, to_key_levels

# i closes bearish (close < open); a later engulfing bullish confirmation
# candle turns this into a bullish Order Block anchor.
_BEARISH_ANCHOR = dict(open=1.1005, high=1.1010, low=1.0985, close=1.0995)
# i closes bullish (close > open); anchor for a bearish Order Block.
_BULLISH_ANCHOR = dict(open=1.0995, high=1.1010, low=1.0985, close=1.1005)
_DOJI_ANCHOR = dict(open=1.1000, high=1.1010, low=1.0990, close=1.1000)  # open == close

# Fully engulfs both _BEARISH_ANCHOR and _BULLISH_ANCHOR's range [1.0985, 1.1010]
# and closes bullish -> valid bullish-OB confirmation.
_ENGULF_CLOSE_BULLISH = dict(open=1.0980, high=1.1015, low=1.0980, close=1.1012)
# Same engulfment, closes bearish -> valid bearish-OB confirmation.
_ENGULF_CLOSE_BEARISH = dict(open=1.1012, high=1.1015, low=1.0980, close=1.0982)
# Engulfs the high side only (doesn't reach the anchor's low) -> partial engulf.
_PARTIAL_ENGULF_BULLISH_CLOSE = dict(open=1.0990, high=1.1015, low=1.0990, close=1.1012)

_NEUTRAL_FILLER = dict(open=1.1000, high=1.1005, low=1.0995, close=1.1002)  # inert, no anchor/confirmation shape


def _series(*bodies):
    builder = CandleSeriesBuilder()
    for body in bodies:
        builder.candle(**body)
    return builder.build()


def test_bullish_order_block_detected_on_engulfing_pair():
    """REQ-61.1: candle i closes bearish, candle i+1 fully engulfs i's range
    and closes bullish -> a bullish ICTOrderBlock anchored at i, zone =
    i's body, confirmed at i+1."""
    series = _series(_BEARISH_ANCHOR, _ENGULF_CLOSE_BULLISH)

    blocks = detect_ict_order_blocks(series)

    assert len(blocks) == 1
    block = blocks[0]
    assert block.candle_index == 0
    assert block.confirmation_index == 1
    assert block.direction == "bullish"
    assert block.top == max(series.candles[0].open, series.candles[0].close)
    assert block.bottom == min(series.candles[0].open, series.candles[0].close)


def test_bearish_order_block_detected_on_engulfing_pair():
    """REQ-61.2: mirror of REQ-61.1 -- candle i closes bullish, candle i+1
    fully engulfs i and closes bearish."""
    series = _series(_BULLISH_ANCHOR, _ENGULF_CLOSE_BEARISH)

    blocks = detect_ict_order_blocks(series)

    assert len(blocks) == 1
    block = blocks[0]
    assert block.candle_index == 0
    assert block.confirmation_index == 1
    assert block.direction == "bearish"
    assert block.top == max(series.candles[0].open, series.candles[0].close)
    assert block.bottom == min(series.candles[0].open, series.candles[0].close)


def test_partial_engulf_yields_no_order_block():
    """REQ-61.3: candle i closes bearish and candle i+1 closes bullish, but
    i+1 does NOT fully engulf i's range (its low never reaches i's low) ->
    no ICTOrderBlock for this pair."""
    series = _series(_BEARISH_ANCHOR, _PARTIAL_ENGULF_BULLISH_CLOSE)

    blocks = detect_ict_order_blocks(series)

    assert blocks == []


def test_wrong_confirmation_close_yields_no_order_block():
    """REQ-61.4: candle i closes bearish and candle i+1 fully engulfs i's
    range, but i+1 itself closes bearish (not bullish) -> no ICTOrderBlock."""
    series = _series(_BEARISH_ANCHOR, _ENGULF_CLOSE_BEARISH)

    blocks = detect_ict_order_blocks(series)

    assert blocks == []


def test_doji_anchor_never_qualifies():
    """REQ-61.5: candle i is a doji (open == close) -> never qualifies as an
    anchor for either direction, even when i+1 would otherwise engulf and
    close directionally."""
    series = _series(_DOJI_ANCHOR, _ENGULF_CLOSE_BULLISH)

    blocks = detect_ict_order_blocks(series)

    assert blocks == []


def test_adjacent_overlapping_pairs_both_emit_independently():
    """REQ-61.6: candle B is simultaneously the confirmation of a bullish OB
    anchored at A (pair A,B) AND itself closes bullish, so B also qualifies
    as the anchor for the adjacent bearish-OB pair (B, C) when C fully
    engulfs B and closes bearish -> BOTH Order Blocks emitted independently."""
    candle_a = _BEARISH_ANCHOR
    candle_b = _ENGULF_CLOSE_BULLISH  # confirms A's bullish OB; itself bullish-bodied -> anchors B,C
    # C must fully engulf B's range and close bearish.
    b_high, b_low = candle_b["high"], candle_b["low"]
    candle_c = dict(open=b_high + 0.0010, high=b_high + 0.0015, low=b_low - 0.0015, close=b_low - 0.0010)
    series = _series(candle_a, candle_b, candle_c)

    blocks = detect_ict_order_blocks(series)

    assert len(blocks) == 2
    ab_block = next(b for b in blocks if b.candle_index == 0)
    bc_block = next(b for b in blocks if b.candle_index == 1)
    assert ab_block.direction == "bullish"
    assert ab_block.confirmation_index == 1
    assert bc_block.direction == "bearish"
    assert bc_block.confirmation_index == 2


def test_invalidated_on_first_range_overlap_after_confirmation():
    """REQ-62.1: a bullish Order Block confirmed at i+1, and the candle at
    i+2 has a range that overlaps the zone -> invalidated at i+2."""
    touching_candle = dict(open=1.1020, high=1.1025, low=1.0955, close=1.1022)  # low(1.0955) inside zone
    series = _series(_BEARISH_ANCHOR, _ENGULF_CLOSE_BULLISH, touching_candle)

    blocks = detect_ict_order_blocks(series)

    assert len(blocks) == 1
    block = blocks[0]
    assert block.status == "invalidated"
    assert block.invalidation_index == 2


def test_wick_only_touch_invalidates():
    """REQ-62.2: a later candle's wick merely dips to the zone boundary
    while its CLOSE stays entirely outside the zone -> still invalidates,
    since this is a touch test (any overlap), not a close-through test."""
    bottom = min(_BEARISH_ANCHOR["open"], _BEARISH_ANCHOR["close"])
    wick_only_candle = dict(open=1.1050, high=1.1055, low=bottom - 0.0002, close=1.1048)  # close far outside
    series = _series(_BEARISH_ANCHOR, _ENGULF_CLOSE_BULLISH, wick_only_candle)

    blocks = detect_ict_order_blocks(series)

    assert len(blocks) == 1
    block = blocks[0]
    assert series.candles[2].low < bottom
    assert block.status == "invalidated"
    assert block.invalidation_index == 2


def test_boundary_touch_invalidates():
    """REQ-62.3: a later candle's high exactly equals the zone's bottom ->
    counts as an overlap (boundary-inclusive) and invalidates."""
    bottom = min(_BEARISH_ANCHOR["open"], _BEARISH_ANCHOR["close"])
    boundary_candle = dict(open=1.0990, high=bottom, low=1.0985, close=1.0992)  # high == bottom exactly
    series = _series(_BEARISH_ANCHOR, _ENGULF_CLOSE_BULLISH, boundary_candle)

    blocks = detect_ict_order_blocks(series)

    assert len(blocks) == 1
    block = blocks[0]
    assert series.candles[2].high == bottom
    assert block.status == "invalidated"
    assert block.invalidation_index == 2


def test_confirmation_candle_itself_never_treated_as_invalidating():
    """REQ-62.4: the confirmation candle i+1 always overlaps the zone by
    definition of full engulfment -- it must never be treated as the
    invalidating candle. The invalidation scan starts at i+2, never i+1."""
    series = _series(_BEARISH_ANCHOR, _ENGULF_CLOSE_BULLISH)

    blocks = detect_ict_order_blocks(series)

    assert len(blocks) == 1
    block = blocks[0]
    # i+1 (index 1) itself overlaps the zone by construction (full engulf),
    # yet the block is NOT invalidated -- series ends right after i+1.
    assert block.status == "open"
    assert block.invalidation_index is None


def test_remains_open_when_never_touched_to_series_end():
    """REQ-62.5: no candle from i+2 onward ever overlaps the zone ->
    status="open", invalidation_index=None at series end."""
    far_away_candle = dict(open=1.2000, high=1.2010, low=1.1990, close=1.2005)  # nowhere near the zone
    series = _series(_BEARISH_ANCHOR, _ENGULF_CLOSE_BULLISH, far_away_candle)

    blocks = detect_ict_order_blocks(series)

    assert len(blocks) == 1
    block = blocks[0]
    assert block.status == "open"
    assert block.invalidation_index is None


def test_key_level_origin_index_is_the_confirmation_candle_not_the_anchor():
    """REQ-63.1: a bullish ICTOrderBlock anchored at i=0, confirmed at
    i+1=1, presents as a KeyLevel with origin_index=1, never 0."""
    series = _series(_BEARISH_ANCHOR, _ENGULF_CLOSE_BULLISH)
    blocks = detect_ict_order_blocks(series)

    levels = to_key_levels(blocks)

    assert len(levels) == 1
    level = levels[0]
    assert level.kind == "ict_order_block"
    assert level.origin_index == 1
    assert level.top == blocks[0].top
    assert level.bottom == blocks[0].bottom
    assert level.expiry_index is None


def test_key_level_expiry_index_matches_invalidation_index():
    """REQ-63.2: an ICTOrderBlock invalidated at some index, presented as a
    KeyLevel, carries expiry_index equal to that invalidation_index."""
    touching_candle = dict(open=1.1020, high=1.1025, low=1.0955, close=1.1022)
    series = _series(_BEARISH_ANCHOR, _ENGULF_CLOSE_BULLISH, touching_candle)
    blocks = detect_ict_order_blocks(series)

    levels = to_key_levels(blocks)

    assert len(levels) == 1
    assert levels[0].expiry_index == 2
