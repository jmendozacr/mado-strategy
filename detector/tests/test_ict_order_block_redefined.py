from datetime import datetime, timedelta

from composite.ict_order_block import ICTOrderBlock, detect_order_blocks, to_key_levels
from composite.mss import MSSEvent
from core.candle import Candle
from primitives.swing import SwingPoint


def _candle(i, o, c, h=None, l=None):
    return Candle(
        timestamp=datetime(2026, 1, 1) + timedelta(hours=4 * i),
        open=o, close=c,
        high=h if h is not None else max(o, c) + 0.0001,
        low=l if l is not None else min(o, c) - 0.0001,
    )


def _flat(n, base=1.10, body=0.0005):
    candles = []
    price = base
    for i in range(n):
        candles.append(_candle(i, price, price + body))
        price += body
    return candles


def _swing_event(index, direction="bullish"):
    return MSSEvent(
        index=index, direction=direction,
        broken_swing=SwingPoint(index=0, kind="low" if direction == "bullish" else "high", price=1.10),
    )


class TestDetectOrderBlocks:
    def test_happy_path_produces_one_active_block(self) -> None:
        break_index = 20
        candles = _flat(break_index - 1)
        candles.append(_candle(break_index - 1, 1.1100, 1.1090))  # the bearish anchor
        candles.append(_candle(break_index, 1.1095, 1.1250, h=1.1260, l=1.1085))  # break + displacement in one candle
        series = type("S", (), {"candles": tuple(candles)})()

        blocks = detect_order_blocks(series, mss_events=[_swing_event(break_index, "bullish")])

        assert len(blocks) == 1
        block = blocks[0]
        assert block.anchor_index == break_index - 1
        assert block.break_index == break_index
        assert block.confirmation_index == break_index
        assert block.direction == "bullish"
        assert block.top == candles[break_index - 1].high
        assert block.bottom == candles[break_index - 1].low
        assert block.status == "active"
        assert block.mitigation_index is None
        assert block.invalidation_index is None

    def test_no_block_when_displacement_never_confirms(self) -> None:
        candles = _flat(20)
        break_index = 20
        candles.append(_candle(break_index - 1, 1.1100, 1.1090))
        candles.append(_candle(break_index, 1.1095, 1.1096))  # tiny move, no displacement
        series = type("S", (), {"candles": tuple(candles)})()

        blocks = detect_order_blocks(series, mss_events=[_swing_event(break_index, "bullish")])
        assert blocks == []

    def test_no_block_when_no_anchor_within_lookback(self) -> None:
        candles = _flat(30, body=0.0005)  # every candle bullish -- no bearish anchor anywhere
        break_index = 29
        candles[break_index] = _candle(break_index, 1.1095, 1.1250, h=1.1260, l=1.1085)
        series = type("S", (), {"candles": tuple(candles)})()

        blocks = detect_order_blocks(series, mss_events=[_swing_event(break_index, "bullish")])
        assert blocks == []

    def test_mitigation_touch_without_invalidation(self) -> None:
        break_index = 20
        candles = _flat(break_index - 1)
        candles.append(_candle(break_index - 1, 1.1100, 1.1090))
        candles.append(_candle(break_index, 1.1095, 1.1250, h=1.1260, l=1.1085))
        # touches back into the zone [1.1090-ish bottom, top] but closes back above bottom
        candles.append(_candle(break_index + 1, 1.1200, 1.1210, h=1.1215, l=1.1091))
        series = type("S", (), {"candles": tuple(candles)})()

        blocks = detect_order_blocks(series, mss_events=[_swing_event(break_index, "bullish")])
        assert blocks[0].status == "mitigated"
        assert blocks[0].mitigation_index == break_index + 1
        assert blocks[0].invalidation_index is None

    def test_invalidation_closes_beyond_the_zone(self) -> None:
        break_index = 20
        candles = _flat(break_index - 1)
        candles.append(_candle(break_index - 1, 1.1100, 1.1090))
        candles.append(_candle(break_index, 1.1095, 1.1250, h=1.1260, l=1.1085))
        candles.append(_candle(break_index + 1, 1.1150, 1.1050))  # closes below bottom (1.1090)
        series = type("S", (), {"candles": tuple(candles)})()

        blocks = detect_order_blocks(series, mss_events=[_swing_event(break_index, "bullish")])
        assert blocks[0].status == "invalidated"
        assert blocks[0].invalidation_index == break_index + 1

    def test_close_exactly_on_the_zone_edge_does_not_invalidate(self) -> None:
        """The zone is inclusive of its own edges (mirrors the crediting
        convention elsewhere in this codebase): a close landing exactly ON
        `bottom` has not closed BEYOND it."""
        break_index = 20
        candles = _flat(break_index - 1)
        candles.append(_candle(break_index - 1, 1.1100, 1.1090, l=1.1080))  # bottom = 1.1080 exactly
        candles.append(_candle(break_index, 1.1095, 1.1250, h=1.1260, l=1.1085))
        candles.append(_candle(break_index + 1, 1.1150, 1.1080))  # closes exactly on bottom
        series = type("S", (), {"candles": tuple(candles)})()

        blocks = detect_order_blocks(series, mss_events=[_swing_event(break_index, "bullish")])
        assert blocks[0].status != "invalidated"
        assert blocks[0].invalidation_index is None

    def test_two_mss_events_can_each_produce_their_own_block(self) -> None:
        break_1 = 20
        candles = _flat(break_1 - 1)
        candles.append(_candle(break_1 - 1, 1.1100, 1.1090))
        candles.append(_candle(break_1, 1.1095, 1.1250, h=1.1260, l=1.1085))
        break_2 = break_1 + 10
        candles += _flat(break_2 - 1 - len(candles), base=1.1250)
        candles.append(_candle(break_2 - 1, 1.1350, 1.1340))
        candles.append(_candle(break_2, 1.1345, 1.1500, h=1.1510, l=1.1335))
        series = type("S", (), {"candles": tuple(candles)})()

        blocks = detect_order_blocks(
            series, mss_events=[_swing_event(break_1, "bullish"), _swing_event(break_2, "bullish")]
        )
        assert {b.break_index for b in blocks} == {break_1, break_2}


class TestToKeyLevels:
    def test_origin_is_confirmation_not_anchor_expiry_is_invalidation(self) -> None:
        block = ICTOrderBlock(
            anchor_index=3, break_index=5, confirmation_index=5, direction="bullish",
            top=1.12, bottom=1.11, status="invalidated", mitigation_index=6, invalidation_index=7,
        )
        levels = to_key_levels([block])
        assert len(levels) == 1
        level = levels[0]
        assert level.kind == "ict_order_block"
        assert level.top == 1.12 and level.bottom == 1.11
        assert level.origin_index == 5  # confirmation_index, NEVER the anchor's own index
        assert level.expiry_index == 7  # invalidation_index, mitigation does not expire the level

    def test_active_block_has_no_expiry(self) -> None:
        block = ICTOrderBlock(
            anchor_index=3, break_index=5, confirmation_index=5, direction="bullish",
            top=1.12, bottom=1.11, status="active",
        )
        assert to_key_levels([block])[0].expiry_index is None
