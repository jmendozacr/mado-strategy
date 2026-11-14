from core.candle import Candle, OHLCSeries
from core.config import Model1Config
from core.key_level import KeyLevel
from core.results import DetectionStatus
from entries.breaker_block import BreakerBlock, detect_breaker_blocks, to_key_levels
from entries.model1 import detect_model1_signals

from tests.fixtures.synthetic import (
    CandleSeriesBuilder,
    model1_confirmed_setup,
    model1_invalidated_setup,
    model1_pending_setup,
)


def breaker_block_retest_and_recovery_setup() -> OHLCSeries:
    """Same anchor/confirm/invalidate as `model1_invalidated_setup` (indices
    0-3: anchor purges CRT High @1, confirms @2, closes beyond the
    protected extreme 1.1035 @3 -> INVALIDATED, zone = anchor's body
    [1.1010, 1.1015]). Two candles appended: index 4 TOUCHES the zone
    (wick overlap) but closes above it (no recovery yet); index 5 CLOSES
    inside the zone -> recovery, one candle after the mere touch, so
    `retest_index` (4) and `recovery_index` (5) land on different candles.
    """
    return (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1020, low=1.0980, close=1.1010)  # 0 — range: H=1.1020 L=1.0980
        .candle(open=1.1010, high=1.1035, low=1.1005, close=1.1015)  # 1 — anchor, purges High
        .candle(open=1.1000, high=1.1005, low=1.0990, close=1.0995)  # 2 — confirms (wick entry @1.1005)
        .candle(open=1.0995, high=1.1040, low=1.0990, close=1.1038)  # 3 — closes beyond 1.1035 -> INVALIDATED
        .candle(open=1.1018, high=1.1025, low=1.1012, close=1.1020)  # 4 — touches zone (low<=1.1015), closes above it
        .candle(open=1.1018, high=1.1020, low=1.1008, close=1.1012)  # 5 — closes inside [1.1010,1.1015] -> recovery
        .build()
    )


def _invalidated_signal(series: OHLCSeries):
    signals = detect_model1_signals(series)
    invalidated = [s for s in signals if s.status == DetectionStatus.INVALIDATED]
    assert len(invalidated) == 1, f"expected exactly one INVALIDATED signal, got {invalidated}"
    return invalidated[0]


def test_an_invalidated_model1_becomes_a_breaker_block():
    series = model1_invalidated_setup()
    signal = _invalidated_signal(series)
    assert signal.confirmation_index == 3  # the breach candle, per entries/model1.py:150

    blocks = detect_breaker_blocks(series.candles, [signal])
    assert len(blocks) == 1
    block = blocks[0]
    assert block.anchor_index == signal.anchor_index == 1
    assert block.activation_index == 3
    assert block.direction == "bullish"  # flip of the trapped bearish Model-1
    assert block.top == 1.1015 and block.bottom == 1.1010  # anchor's own body [open, close]
    assert block.swept_level == signal.purge_target
    assert block.source_signal_id == signal.signal_id
    assert block.retest_index is None  # series ends at the activation candle
    assert block.recovery_index is None


def test_confirmed_and_pending_model1_signals_produce_no_breaker_block():
    confirmed_signals = detect_model1_signals(model1_confirmed_setup())
    pending_signals = detect_model1_signals(model1_pending_setup())
    assert detect_breaker_blocks(model1_confirmed_setup().candles, confirmed_signals) == []
    assert detect_breaker_blocks(model1_pending_setup().candles, pending_signals) == []


def test_breaker_block_separates_retest_touch_from_close_recovery():
    series = breaker_block_retest_and_recovery_setup()
    signal = _invalidated_signal(series)

    block = detect_breaker_blocks(series.candles, [signal])[0]
    assert block.retest_index == 4  # first wick overlap
    assert block.recovery_index == 5  # first CLOSE inside the zone, one candle later


def test_breaker_block_respects_max_retest_lookback():
    series = breaker_block_retest_and_recovery_setup()
    signal = _invalidated_signal(series)

    narrow = detect_breaker_blocks(series.candles, [signal], Model1Config(max_retest_lookback=0))[0]
    assert narrow.retest_index is None
    assert narrow.recovery_index is None


def test_to_key_levels_maps_activation_and_retest():
    block = BreakerBlock(
        anchor_index=1, activation_index=3, direction="bullish",
        top=1.1015, bottom=1.1010, swept_level=1.1020,
        retest_index=5, source_signal_id="x", recovery_index=None,
    )
    assert to_key_levels([block]) == [
        KeyLevel(kind="breaker_block", top=1.1015, bottom=1.1010, origin_index=3, expiry_index=5)
    ]


def test_to_key_levels_expiry_is_none_without_a_retest():
    block = BreakerBlock(
        anchor_index=1, activation_index=3, direction="bullish",
        top=1.1015, bottom=1.1010, swept_level=1.1020,
        retest_index=None, source_signal_id="x",
    )
    assert to_key_levels([block])[0].expiry_index is None
