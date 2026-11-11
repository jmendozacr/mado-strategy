"""odd/tasks/model1-causal-retry-chain.md T4 (S2-S4): chained-anchor
Model-1 retry. Scenarios verified programmatically before being pinned
here (see the task log), each one hand-built so there is exactly one way
to read what happens, not inferred from a larger synthetic fixture.
"""

from datetime import datetime, timedelta

from causal.retry_chain import chained_purge_engulf_signal
from core.candle import Candle, OHLCSeries
from core.config import Model1Config
from core.results import DetectionStatus
from primitives.crt_range import CRTRange

_BASE = datetime(2026, 1, 1, 10, 0)


def _candle(o, h, l, c, i):
    return Candle(timestamp=_BASE + timedelta(hours=i), open=o, high=h, low=l, close=c)


def test_invalidated_anchor_chains_to_the_breaching_candle_and_confirms():
    """S2: anchor1 (index1, bearish, purges High=1.1025) invalidates at
    candle2 (close 1.1030 > anchor1's protected extreme 1.1025) -- instead
    of stopping there, candle2 itself becomes the new anchor and tracking
    continues: candle3 confirms it (close below its body), candle4 retests,
    candle5 closes beyond the retest's own open -> the real-world
    confirming event. The HTF range H-A would attribute to the breach
    candle's timestamp resolves "false_break" (the level is never truly
    broken), so nothing stops the chain early.
    """
    candles = (
        _candle(1.1000, 1.1020, 1.0980, 1.1010, 0),  # 0 -- range
        _candle(1.1010, 1.1025, 1.1005, 1.1015, 1),  # 1 -- anchor1, purges High(1.1025)
        _candle(1.1015, 1.1035, 1.1010, 1.1030, 2),  # 2 -- breaches anchor1.high(1.1025) -> INVALIDATED; becomes anchor2
        _candle(1.1010, 1.1012, 1.0950, 1.0960, 3),  # 3 -- anchor2 confirms (close < body_low 1.1015)
        _candle(1.0965, 1.1020, 1.0955, 1.0970, 4),  # 4 -- retest (wick overlaps anchor2's body)
        _candle(1.0900, 1.0905, 1.0700, 1.0800, 5),  # 5 -- closes beyond retest_open(1.0965) -> confirms
    )
    ltf_range = CRTRange(
        model="2-candle", high=1.1020, low=1.0980,
        start_index=0, end_index=1, resolution="false_break", resolved_at_index=1,
    )
    htf_candles = (
        _candle(1.1000, 1.1020, 1.0980, 1.1010, 0),  # 0 -- HTF range bounds
        _candle(1.1010, 1.1030, 1.1000, 1.1000, 1),  # 1 -- pokes high(1.1030), closes at midpoint(1.1000) -> false_break
    )
    htf_series = OHLCSeries(candles=htf_candles, instrument="EURUSD", timeframe="1H")
    htf_ranges = [
        CRTRange(model="2-candle", high=1.1020, low=1.0980, start_index=0, end_index=1, resolution="false_break", resolved_at_index=1),
    ]

    result = chained_purge_engulf_signal(
        candles, 1, "bearish", ltf_range, Model1Config(), origin_index=0, htf_series=htf_series, htf_ranges=htf_ranges,
    )

    assert result.anchor_index == 2  # re-anchored to the breaching candle, not stuck on anchor1
    assert result.retest_index == 4
    # Causally settled as of its own retest_index (candle4) -- the actual
    # confirming close happens at candle5, strictly after the retest, so a
    # causally-correct observer as of candle4 could only see PENDING. This
    # mirrors `causal.signals.causal_purge_engulf_signals`'s own settling
    # behavior, reused here rather than re-derived.
    assert result.status == DetectionStatus.PENDING


def test_chain_stops_once_the_relevant_htf_range_truly_breaks():
    """S3: anchor1 invalidates at candle2 (t=12:00). H-A attributes HTF
    range [1.0980, 1.1020] to that moment, resolved "true_break" at HTF
    index1, closing at 12:00 -- already known by the 12:00 breach -- so the
    chain stops there instead of re-anchoring to candle2. The signal
    returned is anchor1's own INVALIDATED result, unmodified."""
    candles = (
        _candle(1.1000, 1.1020, 1.0980, 1.1010, 0),  # 0 -- range
        _candle(1.1010, 1.1025, 1.1005, 1.1015, 1),  # 1 -- anchor1, purges High(1.1025)
        _candle(1.1015, 1.1035, 1.1010, 1.1030, 2),  # 2 -- breaches anchor1.high -> INVALIDATED @ t=12:00
        _candle(1.1010, 1.1012, 1.0950, 1.0960, 3),  # 3 -- would confirm a retry; must never be reached
    )
    ltf_range = CRTRange(
        model="2-candle", high=1.1020, low=1.0980,
        start_index=0, end_index=1, resolution="false_break", resolved_at_index=1,
    )
    htf_candles = (
        _candle(1.1000, 1.1020, 1.0980, 1.1010, 0),  # 0 -- HTF range bounds
        _candle(1.1010, 1.1030, 1.0960, 1.0970, 1),  # 1 -- purges high(1.1030), closes below low(1.0970<1.0980) -> true_break, closes 12:00
    )
    htf_series = OHLCSeries(candles=htf_candles, instrument="EURUSD", timeframe="1H")
    htf_ranges = [
        CRTRange(model="2-candle", high=1.1020, low=1.0980, start_index=0, end_index=1, resolution="true_break", resolved_at_index=1),
    ]

    result = chained_purge_engulf_signal(
        candles, 1, "bearish", ltf_range, Model1Config(), origin_index=0, htf_series=htf_series, htf_ranges=htf_ranges,
    )

    assert result.anchor_index == 1  # never re-anchored
    assert result.status == DetectionStatus.INVALIDATED
    assert result.confirmation_index == 2


def test_chain_mirrors_direction_for_bullish_low_side():
    """S4: mirror of the retry case for bullish (purges Low, protected
    extreme is the anchor's own low, confirmation close is above
    body_high). Here the retest and its own closing-beyond-open land on
    the SAME candle (unlike the bearish retry test above, where they're
    one candle apart) -- causal settling has nothing after retest_index
    left to discount, so CONFIRMED stands as-is. No HTF range competes for
    this moment at all (`htf_ranges=[]`), which must never stop the chain
    (absence of evidence is not evidence of a break)."""
    candles = (
        _candle(1.1020, 1.1040, 1.1000, 1.1010, 0),  # 0 -- range
        _candle(1.1010, 1.1015, 0.9995, 1.1005, 1),  # 1 -- anchor1, purges Low(1.1000)
        _candle(1.1005, 1.1010, 0.9980, 0.9990, 2),  # 2 -- breaches anchor1.low -> INVALIDATED; becomes anchor2
        _candle(1.0990, 1.1050, 1.0985, 1.1040, 3),  # 3 -- anchor2 confirms (close > body_high)
        _candle(1.1030, 1.1045, 1.0990, 1.1035, 4),  # 4 -- retest (wick overlaps anchor2's body)
        _candle(1.1100, 1.1200, 1.1095, 1.1180, 5),  # 5 -- closes beyond retest_open -> confirms
    )
    ltf_range = CRTRange(
        model="2-candle", high=1.1040, low=1.1000,
        start_index=0, end_index=1, resolution="false_break", resolved_at_index=1,
    )
    htf_series = OHLCSeries(candles=(_candle(1.1020, 1.1040, 1.1000, 1.1010, 0),), instrument="EURUSD", timeframe="1H")

    result = chained_purge_engulf_signal(
        candles, 1, "bullish", ltf_range, Model1Config(), origin_index=0, htf_series=htf_series, htf_ranges=[],
    )

    assert result.anchor_index == 2
    assert result.retest_index == 4
    assert result.status == DetectionStatus.CONFIRMED
    assert result.confirmation_index == 4


def test_anchor_that_confirms_without_ever_invalidating_is_unaffected():
    """Baseline: when the first anchor confirms cleanly (the common case,
    no chain needed), behavior is unchanged from a plain
    `causal_purge_engulf_signals`-style single-anchor call -- including its
    causal settling: this fixture's real confirming close lands one candle
    after its own retest (candle4, not candle3), so settling as of
    retest_index=3 correctly reports PENDING, same as it would for the
    non-chained causal path on this exact signal. No invalidation ever
    happens, so the HTF stop-check is never even consulted (`htf_ranges=[]`
    is enough)."""
    candles = (
        _candle(1.1000, 1.1020, 1.0980, 1.1010, 0),  # 0 -- range
        _candle(1.1010, 1.1035, 1.1000, 1.1015, 1),  # 1 -- anchor, purges High
        _candle(1.1000, 1.1005, 1.0950, 1.0960, 2),  # 2 -- confirms
        _candle(1.0960, 1.1012, 1.0955, 1.0965, 3),  # 3 -- retest
        _candle(1.0965, 1.0968, 1.0900, 1.0910, 4),  # 4 -- expansion -> confirms
    )
    ltf_range = CRTRange(
        model="2-candle", high=1.1020, low=1.0980,
        start_index=0, end_index=1, resolution="false_break", resolved_at_index=1,
    )
    htf_series = OHLCSeries(candles=(_candle(1.1000, 1.1020, 1.0980, 1.1010, 0),), instrument="EURUSD", timeframe="1H")

    result = chained_purge_engulf_signal(
        candles, 1, "bearish", ltf_range, Model1Config(), origin_index=0, htf_series=htf_series, htf_ranges=[],
    )

    assert result.anchor_index == 1
    assert result.retest_index == 3
    assert result.status == DetectionStatus.PENDING
