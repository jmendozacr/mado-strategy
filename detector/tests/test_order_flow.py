from datetime import datetime, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from fixtures.synthetic import CandleSeriesBuilder

from core.candle import Candle, OHLCSeries
from composite.order_flow import OrderFlowEvent, detect_order_flow_events


def _ohlc_candle(draw, index: int) -> Candle:
    open_ = draw(st.floats(min_value=1.0, max_value=2.0, allow_nan=False))
    close = draw(st.floats(min_value=1.0, max_value=2.0, allow_nan=False))
    wick_up = draw(st.floats(min_value=0.0, max_value=0.05, allow_nan=False))
    wick_down = draw(st.floats(min_value=0.0, max_value=0.05, allow_nan=False))
    return Candle(
        timestamp=datetime(2026, 1, 1) + timedelta(hours=index),
        open=open_,
        high=max(open_, close) + wick_up,
        low=min(open_, close) - wick_down,
        close=close,
    )


@st.composite
def _ohlc_series(draw, min_size=3, max_size=30):
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    candles = tuple(_ohlc_candle(draw, i) for i in range(size))
    return OHLCSeries(candles=candles, instrument="EURUSD", timeframe="1H")


def test_bullish_order_flow_event_fundamental():
    """REQ-OF-01.1: a confirmed SwingLow is rejected (wick below, close back
    above), then a later candle's close breaks a confirmed SwingHigh ->
    bullish OrderFlowEvent at the break candle.

    Swing low @1 (price 1.0950). Candle 4 rejects it (wick to 1.0940, close
    back to 1.0960). Swing high @6 (price 1.1050). Candle 8 closes at
    1.1060, breaking it -> bullish event.
    """
    series = (
        CandleSeriesBuilder()
        .candle(open=1.0980, high=1.0985, low=1.0975, close=1.0980)  # 0 — filler
        .candle(open=1.0960, high=1.0965, low=1.0950, close=1.0955)  # 1 — swing low
        .candle(open=1.0975, high=1.0990, low=1.0970, close=1.0985)  # 2 — filler
        .candle(open=1.0980, high=1.0990, low=1.0975, close=1.0985)  # 3 — filler
        .candle(open=1.0970, high=1.0980, low=1.0940, close=1.0960)  # 4 — rejection: wick<1.0950, close back above
        .candle(open=1.0965, high=1.0975, low=1.0955, close=1.0970)  # 5 — filler
        .candle(open=1.0975, high=1.1050, low=1.0970, close=1.1010)  # 6 — swing high
        .candle(open=1.1010, high=1.1020, low=1.1000, close=1.1015)  # 7 — filler
        .candle(open=1.1015, high=1.1070, low=1.1010, close=1.1060)  # 8 — break: close > 1.1050
        .build()
    )

    events = detect_order_flow_events(series)

    assert len(events) == 1
    event = events[0]
    assert event.direction == "bullish"
    assert event.rejection_reference.index == 1
    assert event.rejection_reference.kind == "low"
    assert event.break_reference.index == 6
    assert event.break_reference.kind == "high"
    assert event.rejection_index == 4
    assert event.confirmation_index == 8


def test_no_close_back_means_no_rejection_candidate():
    """REQ-OF-01.2: a candle wicks below a confirmed SwingLow but its own
    close does NOT return above it -> no rejection candidate is ever
    created, even though a later candle's close decisively breaks a
    confirmed SwingHigh.

    Identical to the fundamental bullish fixture except candle 4's close
    (1.0945) stays below the swing low (1.0950) instead of returning above
    it.
    """
    series = (
        CandleSeriesBuilder()
        .candle(open=1.0980, high=1.0985, low=1.0975, close=1.0980)  # 0 — filler
        .candle(open=1.0960, high=1.0965, low=1.0950, close=1.0955)  # 1 — swing low
        .candle(open=1.0975, high=1.0990, low=1.0970, close=1.0985)  # 2 — filler
        .candle(open=1.0980, high=1.0990, low=1.0975, close=1.0985)  # 3 — filler
        .candle(open=1.0970, high=1.0980, low=1.0940, close=1.0945)  # 4 — wick below, close STAYS below -> no rejection
        .candle(open=1.0965, high=1.0975, low=1.0955, close=1.0970)  # 5 — filler
        .candle(open=1.0975, high=1.1050, low=1.0970, close=1.1010)  # 6 — swing high
        .candle(open=1.1010, high=1.1020, low=1.1000, close=1.1015)  # 7 — filler
        .candle(open=1.1015, high=1.1070, low=1.1010, close=1.1060)  # 8 — decisively beyond swing high, but excluded
        .build()
    )

    events = detect_order_flow_events(series)

    assert events == []


def test_wick_only_break_stays_pending_until_a_real_close_break():
    """REQ-OF-01.3: a valid rejection is pending; a later candle's wick
    crosses the break reference but its close does not -> no event, the
    candidate remains pending (proven by a SUBSEQUENT candle's genuine
    close break still firing the event, rather than the candidate having
    been silently discarded).
    """
    series = (
        CandleSeriesBuilder()
        .candle(open=1.0980, high=1.0985, low=1.0975, close=1.0980)  # 0 — filler
        .candle(open=1.0960, high=1.0965, low=1.0950, close=1.0955)  # 1 — swing low
        .candle(open=1.0975, high=1.0990, low=1.0970, close=1.0985)  # 2 — filler
        .candle(open=1.0980, high=1.0990, low=1.0975, close=1.0985)  # 3 — filler
        .candle(open=1.0970, high=1.0980, low=1.0940, close=1.0960)  # 4 — rejection: wick<1.0950, close back above
        .candle(open=1.0965, high=1.0975, low=1.0955, close=1.0970)  # 5 — filler
        .candle(open=1.0975, high=1.1050, low=1.0970, close=1.1010)  # 6 — swing high
        .candle(open=1.1010, high=1.1020, low=1.1000, close=1.1015)  # 7 — filler
        .candle(open=1.1020, high=1.1060, low=1.1010, close=1.1030)  # 8 — wick beyond 1.1050, close (1.1030) does NOT -> stays pending
        .candle(open=1.1030, high=1.1070, low=1.1020, close=1.1060)  # 9 — real close break -> event
        .build()
    )

    events = detect_order_flow_events(series)

    assert len(events) == 1
    event = events[0]
    assert event.direction == "bullish"
    assert event.rejection_index == 4
    assert event.confirmation_index == 9


def test_close_exactly_at_break_reference_does_not_break():
    """REQ-OF-03.1/03.3: a close exactly equal to the break reference's
    price does NOT break it (strict inequality only); a close one tick
    beyond it does.
    """
    series = (
        CandleSeriesBuilder()
        .candle(open=1.0980, high=1.0985, low=1.0975, close=1.0980)  # 0 — filler
        .candle(open=1.0960, high=1.0965, low=1.0950, close=1.0955)  # 1 — swing low
        .candle(open=1.0975, high=1.0990, low=1.0970, close=1.0985)  # 2 — filler
        .candle(open=1.0980, high=1.0990, low=1.0975, close=1.0985)  # 3 — filler
        .candle(open=1.0970, high=1.0980, low=1.0940, close=1.0960)  # 4 — rejection: wick<1.0950, close back above
        .candle(open=1.0965, high=1.0975, low=1.0955, close=1.0970)  # 5 — filler
        .candle(open=1.0975, high=1.1050, low=1.0970, close=1.1010)  # 6 — swing high, price=1.1050
        .candle(open=1.1010, high=1.1020, low=1.1000, close=1.1015)  # 7 — filler
        .candle(open=1.1020, high=1.1050, low=1.1010, close=1.1050)  # 8 — close EXACTLY 1.1050 -> not broken, stays pending
        .candle(open=1.1050, high=1.1070, low=1.1040, close=1.1051)  # 9 — close one tick beyond -> event
        .build()
    )

    events = detect_order_flow_events(series)

    assert len(events) == 1
    assert events[0].confirmation_index == 9


def test_close_exactly_at_rejection_reference_does_not_invalidate():
    """REQ-OF-03.1 applied to invalidation (REQ-OF-04.3 reuses the same
    predicate, REQ-OF-03): a candle whose close exactly equals the pending
    candidate's rejection_reference price does NOT invalidate it; the
    candidate remains pending and a later genuine break still confirms.
    """
    series = (
        CandleSeriesBuilder()
        .candle(open=1.0980, high=1.0985, low=1.0975, close=1.0980)  # 0 — filler
        .candle(open=1.0960, high=1.0965, low=1.0950, close=1.0955)  # 1 — swing low, price=1.0950
        .candle(open=1.0975, high=1.0990, low=1.0970, close=1.0985)  # 2 — filler
        .candle(open=1.0980, high=1.0990, low=1.0975, close=1.0985)  # 3 — filler
        .candle(open=1.0970, high=1.0980, low=1.0940, close=1.0960)  # 4 — rejection: wick<1.0950, close back above
        .candle(open=1.0965, high=1.0970, low=1.0950, close=1.0950)  # 5 — close EXACTLY 1.0950 -> NOT invalidated
        .candle(open=1.0960, high=1.0970, low=1.0955, close=1.0965)  # 6 — filler
        .candle(open=1.0970, high=1.1050, low=1.0965, close=1.1010)  # 7 — swing high, price=1.1050
        .candle(open=1.1010, high=1.1020, low=1.1000, close=1.1015)  # 8 — filler
        .candle(open=1.1015, high=1.1070, low=1.1010, close=1.1060)  # 9 — break -> event
        .build()
    )

    events = detect_order_flow_events(series)

    assert len(events) == 1
    event = events[0]
    assert event.direction == "bullish"
    assert event.rejection_index == 4
    assert event.confirmation_index == 9


def test_most_recently_confirmed_swing_governs_over_more_extreme_ancient_one():
    """REQ-OF-02.1: an old, more extreme SwingHigh (H1, price 1.1200) and a
    newer, less extreme SwingHigh (H2, price 1.1050) are both confirmed and
    unbroken. A close beyond H2 (1.1060) but NOT beyond H1 must still fire
    the event — selection is by recency (`confirmation_index`), never by
    price magnitude (the anti-anchoring defect `explore.md` Section M.A
    documents for magnitude-based selection, SS5).
    """
    series = (
        CandleSeriesBuilder()
        .candle(open=1.0980, high=1.0985, low=1.0975, close=1.0980)  # 0 — filler
        .candle(open=1.0960, high=1.0965, low=1.0950, close=1.0955)  # 1 — swing low, price=1.0950
        .candle(open=1.0975, high=1.0990, low=1.0970, close=1.0985)  # 2 — filler
        .candle(open=1.0980, high=1.0990, low=1.0975, close=1.0985)  # 3 — filler
        .candle(open=1.0970, high=1.0980, low=1.0940, close=1.0960)  # 4 — rejection
        .candle(open=1.0965, high=1.0975, low=1.0955, close=1.0970)  # 5 — filler
        .candle(open=1.0975, high=1.1200, low=1.0970, close=1.1100)  # 6 — H1 (old, extreme), price=1.1200
        .candle(open=1.1100, high=1.1150, low=1.1080, close=1.1120)  # 7 — filler
        .candle(open=1.1030, high=1.1040, low=1.1010, close=1.1020)  # 8 — filler
        .candle(open=1.1020, high=1.1050, low=1.1010, close=1.1035)  # 9 — H2 (newer, less extreme), price=1.1050
        .candle(open=1.1035, high=1.1045, low=1.1020, close=1.1030)  # 10 — filler
        .candle(open=1.1030, high=1.1065, low=1.1025, close=1.1060)  # 11 — close beyond H2, NOT beyond H1
        .build()
    )

    events = detect_order_flow_events(series)

    assert len(events) == 1
    event = events[0]
    assert event.break_reference.index == 9
    assert event.break_reference.price == 1.1050
    assert event.confirmation_index == 11


def test_equal_price_swing_highs_broken_by_confirmation_index_recency():
    """REQ-OF-02.3: two eligible SwingHighs share an IDENTICAL price
    (1.1050) at different confirmation indices (a double top) -> the one
    with the greater `confirmation_index` (index 9) governs as
    break_reference, not the older one (index 6), even though a close
    beyond either would equally satisfy the raw price test.
    """
    series = (
        CandleSeriesBuilder()
        .candle(open=1.0980, high=1.0985, low=1.0975, close=1.0980)  # 0 — filler
        .candle(open=1.0960, high=1.0965, low=1.0950, close=1.0955)  # 1 — swing low
        .candle(open=1.0975, high=1.0990, low=1.0970, close=1.0985)  # 2 — filler
        .candle(open=1.0980, high=1.0990, low=1.0975, close=1.0985)  # 3 — filler
        .candle(open=1.0970, high=1.0980, low=1.0940, close=1.0960)  # 4 — rejection
        .candle(open=1.0965, high=1.0975, low=1.0955, close=1.0970)  # 5 — filler
        .candle(open=1.0975, high=1.1050, low=1.0970, close=1.1010)  # 6 — older SwingHigh, price=1.1050
        .candle(open=1.1010, high=1.1040, low=1.1000, close=1.1020)  # 7 — filler
        .candle(open=1.1020, high=1.1030, low=1.1010, close=1.1025)  # 8 — filler
        .candle(open=1.1025, high=1.1050, low=1.1015, close=1.1035)  # 9 — newer SwingHigh, SAME price=1.1050
        .candle(open=1.1035, high=1.1045, low=1.1020, close=1.1030)  # 10 — filler
        .candle(open=1.1030, high=1.1065, low=1.1025, close=1.1060)  # 11 — break
        .build()
    )

    events = detect_order_flow_events(series)

    assert len(events) == 1
    event = events[0]
    assert event.break_reference.index == 9
    assert event.break_reference.price == 1.1050


def test_equal_price_swing_lows_broken_by_confirmation_index_recency():
    """Bearish mirror of the equal-price SwingHigh case: two eligible
    SwingLows share an identical price (1.0950) at different confirmation
    indices -> the more recent one (index 9) governs.
    """
    series = (
        CandleSeriesBuilder()
        .candle(open=1.1020, high=1.1025, low=1.1015, close=1.1020)  # 0 — filler
        .candle(open=1.1040, high=1.1050, low=1.1035, close=1.1045)  # 1 — swing high
        .candle(open=1.1025, high=1.1030, low=1.1010, close=1.1015)  # 2 — filler
        .candle(open=1.1020, high=1.1025, low=1.1010, close=1.1015)  # 3 — filler
        .candle(open=1.1030, high=1.1060, low=1.1020, close=1.1040)  # 4 — rejection
        .candle(open=1.1035, high=1.1045, low=1.1025, close=1.1030)  # 5 — filler
        .candle(open=1.1025, high=1.1030, low=1.0950, close=1.0990)  # 6 — older SwingLow, price=1.0950
        .candle(open=1.0990, high=1.1000, low=1.0960, close=1.0980)  # 7 — filler
        .candle(open=1.0980, high=1.0990, low=1.0970, close=1.0975)  # 8 — filler
        .candle(open=1.0975, high=1.0985, low=1.0950, close=1.0965)  # 9 — newer SwingLow, SAME price=1.0950
        .candle(open=1.0965, high=1.0980, low=1.0955, close=1.0970)  # 10 — filler
        .candle(open=1.0970, high=1.0975, low=1.0935, close=1.0940)  # 11 — break
        .build()
    )

    events = detect_order_flow_events(series)

    assert len(events) == 1
    event = events[0]
    assert event.break_reference.index == 9
    assert event.break_reference.price == 1.0950


def test_wrong_side_swing_is_not_eligible_as_break_reference():
    """REQ-OF-02.2: an OLD SwingHigh (index 1, price 1.0900) sits on the
    WRONG side of the rejection reference (a SwingLow confirmed later at a
    HIGHER price, 1.0950) — the market rallied hard since that old high, so
    it is priced below the very low being rejected. It remains the only
    known SwingHigh for several candles whose closes trivially exceed its
    price (proving the guardrail excludes it entirely, not merely "not yet
    crossed") — no event fires until a genuine correct-side SwingHigh
    (index 12, price 1.1050) is confirmed and then broken.
    """
    series = (
        CandleSeriesBuilder()
        .candle(open=1.0875, high=1.0880, low=1.0865, close=1.0875)  # 0 — filler
        .candle(open=1.0880, high=1.0900, low=1.0870, close=1.0890)  # 1 — OLD SwingHigh, price=1.0900 (wrong side)
        .candle(open=1.0890, high=1.0895, low=1.0880, close=1.0888)  # 2 — filler
        .candle(open=1.0888, high=1.0920, low=1.0885, close=1.0915)  # 3 — filler, rallying
        .candle(open=1.0930, high=1.0965, low=1.0960, close=1.0962)  # 4 — filler
        .candle(open=1.0962, high=1.0970, low=1.0950, close=1.0955)  # 5 — SwingLow (rejection reference), price=1.0950
        .candle(open=1.0958, high=1.0966, low=1.0954, close=1.0962)  # 6 — filler
        .candle(open=1.0962, high=1.0972, low=1.0958, close=1.0968)  # 7 — filler
        .candle(open=1.0968, high=1.0978, low=1.0940, close=1.0972)  # 8 — rejection: wick<1.0950, close back above
        .candle(open=1.0972, high=1.0986, low=1.0968, close=1.0980)  # 9 — close trivially > wrong-side high (1.0900) -> still no event
        .candle(open=1.0980, high=1.0994, low=1.0976, close=1.0988)  # 10 — filler
        .candle(open=1.0988, high=1.1006, low=1.0984, close=1.0996)  # 11 — filler
        .candle(open=1.0996, high=1.1050, low=1.0990, close=1.1020)  # 12 — genuine correct-side SwingHigh, price=1.1050
        .candle(open=1.1020, high=1.1040, low=1.1010, close=1.1030)  # 13 — filler
        .candle(open=1.1030, high=1.1070, low=1.1025, close=1.1060)  # 14 — break -> event
        .build()
    )

    events = detect_order_flow_events(series)

    assert len(events) == 1
    event = events[0]
    assert event.direction == "bullish"
    assert event.rejection_index == 8
    assert event.break_reference.index == 12
    assert event.confirmation_index == 14


def test_new_bullish_rejection_replaces_pending_without_touching_bearish():
    """REQ-OF-04.1 (same-direction replacement) + REQ-OF-04.2 (cross-direction
    coexistence): a bullish candidate is created from an early SwingLow (L1,
    index 1), then a SECOND bullish rejection (a different SwingLow, L2,
    index 6) occurs before any break -> REPLACES the pending candidate. The
    eventual bullish event must reference L2, never L1. Independently, a
    bearish candidate (rejecting a SwingHigh, index 10) is created and
    resolves on its own break, untouched by the bullish replacement.
    """
    series = (
        CandleSeriesBuilder()
        .candle(open=1.0980, high=1.0985, low=1.0975, close=1.0980)  # 0 — filler
        .candle(open=1.0960, high=1.0965, low=1.0950, close=1.0955)  # 1 — L1 swing low, price=1.0950
        .candle(open=1.0975, high=1.0990, low=1.0970, close=1.0985)  # 2 — filler
        .candle(open=1.0980, high=1.0990, low=1.0975, close=1.0985)  # 3 — filler
        .candle(open=1.0970, high=1.0980, low=1.0940, close=1.0960)  # 4 — rejection1 (bullish, uses L1)
        .candle(open=1.0965, high=1.0975, low=1.0955, close=1.0970)  # 5 — filler
        .candle(open=1.0960, high=1.0965, low=1.0930, close=1.0945)  # 6 — L2 swing low, price=1.0930
        .candle(open=1.0940, high=1.0950, low=1.0935, close=1.0945)  # 7 — filler
        .candle(open=1.0945, high=1.0955, low=1.0920, close=1.0950)  # 8 — rejection2 (bullish, uses L2) -> REPLACES
        .candle(open=1.0950, high=1.0965, low=1.0945, close=1.0960)  # 9 — filler
        .candle(open=1.0960, high=1.1200, low=1.0955, close=1.1100)  # 10 — swing HIGH, price=1.1200 (bearish rejection ref)
        .candle(open=1.1100, high=1.1150, low=1.1080, close=1.1120)  # 11 — filler
        .candle(open=1.1120, high=1.1210, low=1.1060, close=1.1080)  # 12 — bearish rejection: wick>1.1200, close back below
        .candle(open=1.1080, high=1.1085, low=1.1040, close=1.1050)  # 13 — filler
        .candle(open=1.1050, high=1.1090, low=1.1045, close=1.1070)  # 14 — swing high, price=1.1090 (bullish break ref)
        .candle(open=1.1070, high=1.1080, low=1.1020, close=1.1030)  # 15 — bearish break (crosses artifact low@13)
        .candle(open=1.1030, high=1.1100, low=1.1020, close=1.1095)  # 16 — bullish break: close>1.1090
        .build()
    )

    events = detect_order_flow_events(series)

    assert len(events) == 2
    by_direction = {e.direction: e for e in events}

    bullish = by_direction["bullish"]
    assert bullish.rejection_reference.index == 6  # L2, NOT L1 (index 1)
    assert bullish.rejection_reference.price == 1.0930
    assert bullish.rejection_index == 8
    assert bullish.confirmation_index == 16

    bearish = by_direction["bearish"]
    assert bearish.rejection_reference.index == 10  # untouched by the bullish replacement
    assert bearish.rejection_index == 12


def test_outside_bar_creates_both_direction_rejections_with_no_tie_break():
    """REQ-OF-08: a single candle (an outside bar — its wick crosses BOTH a
    confirmed SwingLow downward and a confirmed SwingHigh upward, closing
    back between them) qualifies as a new rejection for BOTH directions
    simultaneously. Under REQ-OF-04's independence, both are accepted with
    no arbitration — both eventual events share the same `rejection_index`
    (the outside-bar candle itself).
    """
    series = (
        CandleSeriesBuilder()
        .candle(open=1.0980, high=1.0985, low=1.0975, close=1.0980)  # 0 — filler
        .candle(open=1.0960, high=1.0965, low=1.0950, close=1.0955)  # 1 — L swing low, price=1.0950
        .candle(open=1.0975, high=1.0990, low=1.0970, close=1.0985)  # 2 — filler
        .candle(open=1.0990, high=1.1200, low=1.0980, close=1.1010)  # 3 — H swing high, price=1.1200
        .candle(open=1.1010, high=1.1020, low=1.1000, close=1.1015)  # 4 — filler
        .candle(open=1.1015, high=1.1210, low=1.0930, close=1.1050)  # 5 — OUTSIDE BAR: wick<L, wick>H, close between -> both rejections
        .candle(open=1.1050, high=1.1060, low=1.1040, close=1.1055)  # 6 — filler
        .candle(open=1.1055, high=1.1100, low=1.1045, close=1.1080)  # 7 — bullish break reference, price=1.1100
        .candle(open=1.1080, high=1.1090, low=1.1060, close=1.1070)  # 8 — filler
        .candle(open=1.1070, high=1.1160, low=1.1050, close=1.1150)  # 9 — bullish break: close>1.1100 (<=1.1200, no bearish invalidation)
        .candle(open=1.1150, high=1.1155, low=1.1050, close=1.1060)  # 10 — filler decline
        .candle(open=1.1060, high=1.1070, low=1.0850, close=1.0900)  # 11 — bearish break: crosses down through an available low
        .build()
    )

    events = detect_order_flow_events(series)

    assert len(events) == 2
    by_direction = {e.direction: e for e in events}
    assert by_direction["bullish"].rejection_index == 5
    assert by_direction["bearish"].rejection_index == 5
    assert by_direction["bullish"].rejection_reference.kind == "low"
    assert by_direction["bearish"].rejection_reference.kind == "high"


def test_bullish_candidate_invalidated_by_close_back_through_rejection_reference():
    """REQ-OF-04.3: a pending bullish candidate is discarded (no event) if a
    later candle's close crosses back below its own rejection_reference in
    the original direction — even though a confirmed SwingHigh later gets
    decisively broken by close.
    """
    series = (
        CandleSeriesBuilder()
        .candle(open=1.0980, high=1.0985, low=1.0975, close=1.0980)  # 0 — filler
        .candle(open=1.0960, high=1.0965, low=1.0950, close=1.0955)  # 1 — swing low, price=1.0950
        .candle(open=1.0975, high=1.0990, low=1.0970, close=1.0985)  # 2 — filler
        .candle(open=1.0980, high=1.0990, low=1.0975, close=1.0985)  # 3 — filler
        .candle(open=1.0970, high=1.0980, low=1.0940, close=1.0960)  # 4 — rejection
        .candle(open=1.0955, high=1.0958, low=1.0930, close=1.0935)  # 5 — INVALIDATION: close<1.0950
        .candle(open=1.0940, high=1.0965, low=1.0935, close=1.0960)  # 6 — filler
        .candle(open=1.0960, high=1.1050, low=1.0955, close=1.1010)  # 7 — swing high, price=1.1050
        .candle(open=1.1010, high=1.1020, low=1.1000, close=1.1015)  # 8 — filler
        .candle(open=1.1015, high=1.1070, low=1.1010, close=1.1060)  # 9 — would-be break, but candidate already discarded
        .build()
    )

    events = detect_order_flow_events(series)

    assert events == []


def test_bearish_candidate_invalidated_by_close_back_through_rejection_reference():
    """Bearish mirror of the structural-invalidation test above."""
    series = (
        CandleSeriesBuilder()
        .candle(open=1.1020, high=1.1025, low=1.1015, close=1.1020)  # 0 — filler
        .candle(open=1.1040, high=1.1050, low=1.1035, close=1.1045)  # 1 — swing high, price=1.1050
        .candle(open=1.1025, high=1.1030, low=1.1010, close=1.1015)  # 2 — filler
        .candle(open=1.1020, high=1.1025, low=1.1010, close=1.1015)  # 3 — filler
        .candle(open=1.1030, high=1.1060, low=1.1020, close=1.1040)  # 4 — rejection
        .candle(open=1.1045, high=1.1070, low=1.1042, close=1.1065)  # 5 — INVALIDATION: close>1.1050
        .candle(open=1.1060, high=1.1065, low=1.1035, close=1.1040)  # 6 — filler
        .candle(open=1.1040, high=1.1045, low=1.0950, close=1.0990)  # 7 — swing low, price=1.0950
        .candle(open=1.0990, high=1.1000, low=1.0980, close=1.0985)  # 8 — filler
        .candle(open=1.0985, high=1.0990, low=1.0930, close=1.0940)  # 9 — would-be break, but candidate already discarded
        .build()
    )

    events = detect_order_flow_events(series)

    assert events == []


def test_pending_candidate_survives_arbitrarily_long_separation_then_consumes():
    """REQ-OF-04.4: with no invalidation and no break, a pending candidate
    survives indefinitely — no arbitrary time window — proven here with 40
    flat filler candles between rejection and break. Once the break fires,
    EXACTLY one event is emitted and the candidate is consumed: a
    subsequent candle closing back through the (now former)
    rejection_reference produces no further effect.
    """
    builder = (
        CandleSeriesBuilder()
        .candle(open=1.0980, high=1.0985, low=1.0975, close=1.0980)  # 0 — filler
        .candle(open=1.0960, high=1.0965, low=1.0950, close=1.0955)  # 1 — swing low, price=1.0950
        .candle(open=1.0975, high=1.0990, low=1.0970, close=1.0985)  # 2 — filler
        .candle(open=1.0980, high=1.0990, low=1.0975, close=1.0985)  # 3 — filler
        .candle(open=1.0970, high=1.0980, low=1.0940, close=1.0960)  # 4 — rejection
    )
    for _ in range(40):  # 5..44 — flat filler, no invalidation, no break
        builder.candle(open=1.0970, high=1.0975, low=1.0965, close=1.0970)
    series = (
        builder
        .candle(open=1.0970, high=1.1050, low=1.0965, close=1.1010)  # 45 — swing high, price=1.1050
        .candle(open=1.1010, high=1.1020, low=1.1000, close=1.1015)  # 46 — filler
        .candle(open=1.1015, high=1.1070, low=1.1010, close=1.1060)  # 47 — break -> event, candidate consumed
        .candle(open=1.1060, high=1.1065, low=1.0900, close=1.0910)  # 48 — closes far below the FORMER rejection_reference: no candidate left, no effect
        .build()
    )

    events = detect_order_flow_events(series)

    assert len(events) == 1
    event = events[0]
    assert event.rejection_index == 4
    assert event.confirmation_index == 47


def test_same_swing_point_reused_by_a_later_independent_rejection():
    """REQ-OF-04.5: a SwingPoint already consumed by a past event MAY
    participate in a NEW, independent rejection at a later, distinct
    rejection_index — this is a fresh rejection, not a reuse of the prior
    one. The same SwingLow (index 1) is rejected twice here: once
    consumed by an event at rejection_index=4, then rejected again at
    rejection_index=10, producing a second, independent event.
    """
    series = (
        CandleSeriesBuilder()
        .candle(open=1.0980, high=1.0985, low=1.0975, close=1.0980)  # 0 — filler
        .candle(open=1.0960, high=1.0965, low=1.0950, close=1.0955)  # 1 — swing low, price=1.0950
        .candle(open=1.0975, high=1.0990, low=1.0970, close=1.0985)  # 2 — filler
        .candle(open=1.0980, high=1.0990, low=1.0940, close=1.0985)  # 3 — filler (low tied with candle 4)
        .candle(open=1.0970, high=1.0980, low=1.0940, close=1.0960)  # 4 — rejection1 (uses swing low @1)
        .candle(open=1.0965, high=1.0975, low=1.0955, close=1.0970)  # 5 — filler
        .candle(open=1.0975, high=1.1050, low=1.0970, close=1.1010)  # 6 — swing high H1, price=1.1050
        .candle(open=1.1010, high=1.1020, low=1.1000, close=1.1015)  # 7 — filler
        .candle(open=1.1015, high=1.1070, low=1.1010, close=1.1060)  # 8 — break1 -> event1, candidate consumed
        .candle(open=1.1060, high=1.1065, low=1.1055, close=1.1060)  # 9 — filler
        .candle(open=1.1040, high=1.1045, low=1.0940, close=1.0960)  # 10 — rejection2: SAME swing low @1, rejected AGAIN
        .candle(open=1.0965, high=1.0975, low=1.0958, close=1.0970)  # 11 — filler
        .candle(open=1.0975, high=1.1100, low=1.0970, close=1.1050)  # 12 — swing high H2, price=1.1100
        .candle(open=1.1050, high=1.1060, low=1.1040, close=1.1055)  # 13 — filler
        .candle(open=1.1055, high=1.1120, low=1.1050, close=1.1110)  # 14 — break2 -> event2, independent
        .build()
    )

    events = detect_order_flow_events(series)

    assert len(events) == 2
    assert events[0].rejection_reference.index == 1
    assert events[1].rejection_reference.index == 1
    assert events[0].rejection_index == 4
    assert events[1].rejection_index == 10
    assert events[0].confirmation_index == 8
    assert events[1].confirmation_index == 14


def test_same_candle_resolves_existing_candidate_before_creating_a_new_one():
    """REQ-OF-07: on candle c, the EXISTING pending candidate (A, rejecting
    SwingLow @1) must be resolved BEFORE c is evaluated for a new rejection.
    Candle c both (a) breaks A's break_reference (SwingHigh @6) and (b)
    independently qualifies as a fresh rejection against a more recent
    SwingLow (@8) for the SAME direction. Resolving A first correctly
    emits A's event; if the new rejection were processed first, A would be
    replaced before ever being tested, and the emitted event would
    (incorrectly) carry the new candidate's identity instead.
    """
    series = (
        CandleSeriesBuilder()
        .candle(open=1.0980, high=1.0985, low=1.0975, close=1.0980)  # 0 — filler
        .candle(open=1.0960, high=1.0965, low=1.0950, close=1.0955)  # 1 — swing low A, price=1.0950
        .candle(open=1.0975, high=1.0990, low=1.0970, close=1.0985)  # 2 — filler
        .candle(open=1.0980, high=1.0990, low=1.0975, close=1.0985)  # 3 — filler
        .candle(open=1.0970, high=1.0980, low=1.0940, close=1.0960)  # 4 — rejection (uses A) -> pending
        .candle(open=1.0965, high=1.0975, low=1.0955, close=1.0970)  # 5 — filler
        .candle(open=1.0975, high=1.1050, low=1.0970, close=1.1010)  # 6 — swing high, price=1.1050 (A's break reference)
        .candle(open=1.1010, high=1.1020, low=1.1005, close=1.1015)  # 7 — filler
        .candle(open=1.1015, high=1.1020, low=1.1000, close=1.1010)  # 8 — swing low, price=1.1000 (new rejection candidate)
        .candle(open=1.1010, high=1.1020, low=1.1005, close=1.1015)  # 9 — filler
        .candle(open=1.1015, high=1.1070, low=1.0990, close=1.1060)  # 10 — resolves A (close>1.1050) AND qualifies as a new rejection (wick<1.1000, close>1.1000)
        .build()
    )

    events = detect_order_flow_events(series)

    assert len(events) == 1
    event = events[0]
    assert event.rejection_reference.index == 1  # candidate A, NOT the newly-created candidate
    assert event.rejection_index == 4
    assert event.confirmation_index == 10


def test_timeframe_and_instrument_labels_never_affect_detection():
    """REQ-OF-06: `detect_order_flow_events` never branches on `.timeframe`
    or `.instrument` — the SAME OHLC data produces the SAME events
    regardless of what those labels say.
    """
    from dataclasses import replace

    series = (
        CandleSeriesBuilder()
        .candle(open=1.0980, high=1.0985, low=1.0975, close=1.0980)  # 0 — filler
        .candle(open=1.0960, high=1.0965, low=1.0950, close=1.0955)  # 1 — swing low
        .candle(open=1.0975, high=1.0990, low=1.0970, close=1.0985)  # 2 — filler
        .candle(open=1.0980, high=1.0990, low=1.0975, close=1.0985)  # 3 — filler
        .candle(open=1.0970, high=1.0980, low=1.0940, close=1.0960)  # 4 — rejection
        .candle(open=1.0965, high=1.0975, low=1.0955, close=1.0970)  # 5 — filler
        .candle(open=1.0975, high=1.1050, low=1.0970, close=1.1010)  # 6 — swing high
        .candle(open=1.1010, high=1.1020, low=1.1000, close=1.1015)  # 7 — filler
        .candle(open=1.1015, high=1.1070, low=1.1010, close=1.1060)  # 8 — break -> event
        .build()
    )
    relabeled = replace(series, timeframe="4H", instrument="XAUUSD")

    assert detect_order_flow_events(series) == detect_order_flow_events(relabeled)
    assert len(detect_order_flow_events(series)) == 1


def test_bearish_order_flow_event_mirrors_bullish():
    """REQ-OF-01: bearish mirror of the fundamental case — reject above a
    confirmed SwingHigh (wick above, close back below), then a later
    candle's close breaks a confirmed SwingLow.

    Swing high @1 (price 1.1050). Candle 4 rejects it (wick to 1.1060,
    close back to 1.1040). Swing low @6 (price 1.0950). Candle 8 closes at
    1.0940, breaking it -> bearish event.
    """
    series = (
        CandleSeriesBuilder()
        .candle(open=1.1020, high=1.1025, low=1.1015, close=1.1020)  # 0 — filler
        .candle(open=1.1040, high=1.1050, low=1.1035, close=1.1045)  # 1 — swing high
        .candle(open=1.1025, high=1.1030, low=1.1010, close=1.1015)  # 2 — filler
        .candle(open=1.1020, high=1.1025, low=1.1010, close=1.1015)  # 3 — filler
        .candle(open=1.1030, high=1.1060, low=1.1020, close=1.1040)  # 4 — rejection: wick>1.1050, close back below
        .candle(open=1.1035, high=1.1045, low=1.1025, close=1.1030)  # 5 — filler
        .candle(open=1.1025, high=1.1030, low=1.0950, close=1.0990)  # 6 — swing low
        .candle(open=1.0990, high=1.1000, low=1.0980, close=1.0985)  # 7 — filler
        .candle(open=1.0985, high=1.0990, low=1.0930, close=1.0940)  # 8 — break: close < 1.0950
        .build()
    )

    events = detect_order_flow_events(series)

    assert len(events) == 1
    event = events[0]
    assert event.direction == "bearish"
    assert event.rejection_reference.index == 1
    assert event.rejection_reference.kind == "high"
    assert event.break_reference.index == 6
    assert event.break_reference.kind == "low"
    assert event.rejection_index == 4
    assert event.confirmation_index == 8


@given(series=_ohlc_series())
@settings(max_examples=200)
def test_correct_side_guard_and_self_confirmation_are_structural_invariants(series):
    """REQ-OF-07.1/07.2, tested as direct invariants over every event any
    random series can produce (not guessed edge cases):

    REQ-OF-07.1 (proof-backed): break_reference always sits strictly on the
    correct side of rejection_reference (REQ-OF-02's own guard) — this is
    exactly what makes "a single close both breaks and invalidates" a
    mathematical impossibility, not merely an untested case.

    REQ-OF-07.2 (proof-backed): neither rejection_reference nor
    break_reference is ever "used" (rejected against, or broken) by its own
    confirming candle — a SwingPoint at index i is confirmed by candle i+1,
    and `swing.py`'s fractal definition makes that candle structurally
    incapable of crossing the swing's own price.
    """
    for event in detect_order_flow_events(series):
        if event.direction == "bullish":
            assert event.break_reference.price > event.rejection_reference.price
        else:
            assert event.break_reference.price < event.rejection_reference.price

        assert event.rejection_index != event.rejection_reference.index + 1
        assert event.confirmation_index != event.break_reference.index + 1


@given(series=_ohlc_series())
@settings(max_examples=2000)
def test_opposite_direction_events_never_share_a_confirmation_index(series):
    """REQ-OF-09 (corrected post-implementation): a bullish and a bearish
    event sharing the same confirmation_index is PROVEN impossible, not
    merely untested. Proof: a shared break at candle F requires
    break_reference_bullish.price < break_reference_bearish.price (both
    breaks land strictly inside that gap); but both references were
    confirmed strictly before F (REQ-OF-07), so both were also required to
    stay unbroken through F-1, which forces the OPPOSITE inequality
    (break_reference_bearish.price <= close(F-1) <= break_reference_bullish.price).
    Contradiction -- the case cannot occur for any input. This is the
    persisted invariant test the spec's REQ-OF-09.1 requires in place of a
    constructed positive example (none exists)."""
    events = detect_order_flow_events(series)
    by_confirmation_index: dict[int, set[str]] = {}
    for event in events:
        by_confirmation_index.setdefault(event.confirmation_index, set()).add(event.direction)
    for directions in by_confirmation_index.values():
        assert directions != {"bullish", "bearish"}


def _mirror_series(series: OHLCSeries, pivot: float = 2.2) -> OHLCSeries:
    """Price mirror around `pivot` (price -> pivot - price), swapping each
    candle's high/low — turns any bullish structure into its exact bearish
    mirror (and vice versa) while preserving every strict inequality
    `detect_swings`/`detect_order_flow_events` rely on, since a decreasing
    affine transform reverses `<`/`>` consistently.
    """
    mirrored = tuple(
        Candle(
            timestamp=c.timestamp,
            open=pivot - c.open,
            high=pivot - c.low,
            low=pivot - c.high,
            close=pivot - c.close,
        )
        for c in series.candles
    )
    return OHLCSeries(candles=mirrored, instrument=series.instrument, timeframe=series.timeframe)


@given(series=_ohlc_series())
@settings(max_examples=100)
def test_bullish_bearish_symmetry_under_price_mirroring(series):
    """Bullish/bearish symmetry (final TDD item): mirroring a series' prices
    around a pivot (price -> pivot - price, swapping high/low) turns every
    bullish event into a bearish one at the SAME indices with the SAME
    structural identity, and vice versa — the algorithm treats both
    directions as true structural mirrors of one shared implementation
    (`_select_reference`/`_breaks` are direction-agnostic; only the
    per-direction wiring in `detect_order_flow_events` differs), so this
    holds without any special-casing.
    """
    events = detect_order_flow_events(series)
    mirrored_events = detect_order_flow_events(_mirror_series(series))

    def _mirror_event_key(e: OrderFlowEvent):
        opposite = "bearish" if e.direction == "bullish" else "bullish"
        return (
            opposite,
            e.rejection_reference.index,
            e.break_reference.index,
            e.rejection_index,
            e.confirmation_index,
        )

    def _event_key(e: OrderFlowEvent):
        return (
            e.direction,
            e.rejection_reference.index,
            e.break_reference.index,
            e.rejection_index,
            e.confirmation_index,
        )

    assert {_mirror_event_key(e) for e in events} == {_event_key(e) for e in mirrored_events}
