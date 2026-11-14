"""odd/tasks/model1-causal-retry-chain.md T5: wiring the chain into
`causal.signals.causal_purge_engulf_signals` via its new optional
`htf_series`/`htf_ranges` parameters. Tests the actual delegation this
function now does, distinct from `test_causal_retry_chain.py` (which
tests `chained_purge_engulf_signal` directly, one layer below)."""

from datetime import datetime, timedelta

from causal.signals import causal_purge_engulf_signals
from core.candle import Candle, OHLCSeries
from core.config import Model1Config
from core.results import DetectionStatus
from primitives.crt_range import CRTRange

_BASE = datetime(2026, 1, 1, 10, 0)


def _candle(o, h, l, c, i):
    return Candle(timestamp=_BASE + timedelta(hours=i), open=o, high=h, low=l, close=c)


_LTF_CANDLES = (
    _candle(1.1000, 1.1020, 1.0980, 1.1010, 0),  # 0 -- range
    _candle(1.1010, 1.1025, 1.1005, 1.1015, 1),  # 1 -- anchor1, purges High(1.1025)
    _candle(1.1015, 1.1035, 1.1010, 1.1030, 2),  # 2 -- breaches anchor1.high -> INVALIDATED; becomes anchor2
    _candle(1.1010, 1.1012, 1.0950, 1.0960, 3),  # 3 -- anchor2 confirms
    _candle(1.0965, 1.1020, 1.0955, 1.0970, 4),  # 4 -- retest
    _candle(1.0900, 1.0905, 1.0700, 1.0800, 5),  # 5 -- confirms (strictly after retest)
)
_LTF_RANGE = CRTRange(
    model="2-candle", high=1.1020, low=1.0980,
    start_index=0, end_index=1, resolution="false_break", resolved_at_index=1,
)
_HTF_CANDLES = (
    _candle(1.1000, 1.1020, 1.0980, 1.1010, 0),
    _candle(1.1010, 1.1030, 1.1000, 1.1000, 1),  # pokes high, closes at midpoint -> false_break
    _candle(1.1000, 1.1005, 1.0995, 1.1002, 2),
)
_HTF_RANGE = CRTRange(
    model="3-candle", high=1.1020, low=1.0980,
    start_index=0, end_index=2, resolution="false_break", resolved_at_index=2,
)


def test_without_htf_series_behavior_is_unchanged():
    """`htf_series=None` (the default) must reproduce this function's
    exact pre-T5 output -- the single invalidated anchor, no retry."""
    ltf_series = OHLCSeries(candles=_LTF_CANDLES, instrument="EURUSD", timeframe="1H")

    signals = causal_purge_engulf_signals(ltf_series, [_LTF_RANGE], Model1Config())

    assert len(signals) == 1
    assert signals[0].anchor_index == 1
    assert signals[0].status == DetectionStatus.INVALIDATED


def test_with_htf_series_the_winning_invalidated_signal_is_chained():
    """Passing `htf_series`/`htf_ranges` (the production wiring
    `causal.generate.generate_causal_aligned_signals` now uses) makes the
    SAME winning signal retry instead of settling as INVALIDATED --
    re-anchored to the breaching candle, same as
    `chained_purge_engulf_signal` produces directly."""
    ltf_series = OHLCSeries(candles=_LTF_CANDLES, instrument="EURUSD", timeframe="1H")
    htf_series = OHLCSeries(candles=_HTF_CANDLES, instrument="EURUSD", timeframe="1H")

    signals = causal_purge_engulf_signals(
        ltf_series, [_LTF_RANGE], Model1Config(), htf_series=htf_series, htf_ranges=[_HTF_RANGE],
    )

    assert len(signals) == 1
    assert signals[0].anchor_index == 2
    assert signals[0].retest_index == 4
    assert signals[0].status == DetectionStatus.PENDING
