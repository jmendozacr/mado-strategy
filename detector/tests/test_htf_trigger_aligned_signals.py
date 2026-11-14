"""odd/tasks/scanner-1am-9am-diversified.md T1: the production end-to-end
wiring from HTF+LTF series + a pre-built key_levels list to a list of
(AlignedSignal, model_name) pairs -- the exact composition this session's
scratchpad reconstructed for the backtest, now given a tested home so the
live scanner (and anything else) can reuse it instead of re-deriving it.
"""
from datetime import datetime, timedelta

from alignment.htf_ltf import AlignedSignal
from causal.htf_trigger import MODEL_1AM, MODEL_9AM, confirmation_window_utc, find_1am_9am_aligned_signals
from core.candle import Candle, OHLCSeries
from core.config import CRTRangeConfig, Model1Config
from core.key_level import KeyLevel

_DAY = datetime(2026, 1, 5)  # a Monday, arbitrary -- same fixture day as test_htf_trigger.py
_ZONE = KeyLevel(kind="fvg", top=1.1040, bottom=1.1030, origin_index=0, expiry_index=None)


def _htf_candle(hour, o, h, l, c):
    return Candle(timestamp=_DAY + timedelta(hours=hour), open=o, high=h, low=l, close=c)


def _m15(ts, o, h, l, c):
    return Candle(timestamp=ts, open=o, high=h, low=l, close=c)


def _confirming_ltf_series(window_start):
    """Same confirmation shape as test_htf_trigger_confirmation.py's own
    `test_clean_confirmation_inside_the_window`, anchored at the REAL
    computed window start instead of an arbitrary timestamp -- the anchor
    purges the range's high (bearish), confirms, retests, then expands."""
    candles = (
        _m15(window_start - timedelta(minutes=15), 1.1000, 1.1020, 1.0980, 1.1010),  # range
        _m15(window_start, 1.1010, 1.1035, 1.1000, 1.1015),  # anchor, purges High
        _m15(window_start + timedelta(minutes=15), 1.1000, 1.1005, 1.0950, 1.0960),  # confirms
        _m15(window_start + timedelta(minutes=30), 1.0960, 1.1012, 1.0955, 1.0965),  # retest
        _m15(window_start + timedelta(minutes=45), 1.0965, 1.0968, 1.0900, 1.0910),  # expansion -> confirms
    )
    return OHLCSeries(candles=candles, instrument="EURUSDm", timeframe="15M")


def test_end_to_end_bearish_9am_trigger_confirms_and_tags_model():
    htf_candles = (
        _htf_candle(8, 1.1000, 1.1020, 1.0980, 1.1010),  # 08:00 UTC -- previous candle
        _htf_candle(12, 1.1010, 1.1035, 1.1000, 1.1005),  # 12:00 UTC -- 9AM trigger, sweeps+rejects
    )
    w_start, _w_end = confirmation_window_utc(htf_candles[1], MODEL_9AM)
    ltf_series = _confirming_ltf_series(w_start)

    results = find_1am_9am_aligned_signals(
        htf_candles, ltf_series, key_levels=[_ZONE],
        crt_config=CRTRangeConfig(), model1_config=Model1Config(),
    )

    assert len(results) == 1
    aligned, model_name = results[0]
    assert isinstance(aligned, AlignedSignal)
    assert model_name == "9am"
    assert aligned.aligned == "aligned"
    assert aligned.key_level == _ZONE
    assert aligned.key_level_reaction == "reject_close_inside"
    assert aligned.ltf_signal.direction == "bearish"
    assert aligned.htf_context.high == 1.1020
    assert aligned.htf_context.low == 1.0980


def test_no_credited_key_level_means_no_signal():
    htf_candles = (
        _htf_candle(8, 1.1000, 1.1020, 1.0980, 1.1010),
        _htf_candle(12, 1.1010, 1.1035, 1.1000, 1.1005),
    )
    w_start, _w_end = confirmation_window_utc(htf_candles[1], MODEL_9AM)
    ltf_series = _confirming_ltf_series(w_start)

    results = find_1am_9am_aligned_signals(
        htf_candles, ltf_series, key_levels=[],  # no registered zone at all
        crt_config=CRTRangeConfig(), model1_config=Model1Config(),
    )
    assert results == []


def test_confirmation_outside_the_models_own_window_is_not_counted():
    htf_candles = (
        _htf_candle(8, 1.1000, 1.1020, 1.0980, 1.1010),
        _htf_candle(12, 1.1010, 1.1035, 1.1000, 1.1005),
    )
    w_start, _w_end = confirmation_window_utc(htf_candles[1], MODEL_9AM)
    # Shift the whole confirming sequence to start 3 hours AFTER the real
    # window -- ltf_window_indices must find nothing, so no signal.
    ltf_series = _confirming_ltf_series(w_start + timedelta(hours=3))

    results = find_1am_9am_aligned_signals(
        htf_candles, ltf_series, key_levels=[_ZONE],
        crt_config=CRTRangeConfig(), model1_config=Model1Config(),
    )
    assert results == []


def test_models_parameter_lets_a_caller_scope_to_a_single_model():
    """The live scanner (and this test suite) only ever wants MODEL_1AM +
    MODEL_9AM (MODEL_5AM was tested and declined this session) -- but the
    function itself stays generically parameterized over any FeederModel
    sequence, never hardcoding which ones to run."""
    htf_candles = (
        _htf_candle(8, 1.1000, 1.1020, 1.0980, 1.1010),
        _htf_candle(12, 1.1010, 1.1035, 1.1000, 1.1005),  # this IS the 9am-hour candle
    )
    w_start, _w_end = confirmation_window_utc(htf_candles[1], MODEL_9AM)
    ltf_series = _confirming_ltf_series(w_start)

    only_1am = find_1am_9am_aligned_signals(
        htf_candles, ltf_series, key_levels=[_ZONE],
        crt_config=CRTRangeConfig(), model1_config=Model1Config(), models=(MODEL_1AM,),
    )
    assert only_1am == []  # the trigger candle is at the 9am hour, not 1am -- excluded when scoped to 1am only

    both = find_1am_9am_aligned_signals(
        htf_candles, ltf_series, key_levels=[_ZONE],
        crt_config=CRTRangeConfig(), model1_config=Model1Config(), models=(MODEL_1AM, MODEL_9AM),
    )
    assert len(both) == 1
    assert both[0][1] == "9am"
