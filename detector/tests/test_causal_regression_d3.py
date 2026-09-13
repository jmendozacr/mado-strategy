"""D3 regression (spec.md Section A, leakage channels B3/B4 — "Stage6-level
phantom events and economic mutation"): an identical `(retest_index,
anchor_index, direction)` key can get a DIFFERENT `take_profit` purely from
candles appended after the shared event, because legacy `_purge_index_map`
lets a later-detected, lower-`start_index` HTF range silently steal the
purge-candle slot from the range that was already mapped there.

Reuses the exact fixture verified in `test_causal_htf.py` (legacy
`_purge_index_map` flips from start_index=4 to start_index=3 once a 7th HTF
candle is appended) — this test carries that flip through to the actual
`take_profit` economic field, and proves the causal H-A path is immune."""

from datetime import datetime, timedelta

from alignment.htf_ltf import _purge_index_map
from backtest.levels import take_profit
from causal.htf import select_htf_context
from core.candle import Candle, OHLCSeries
from core.pairing_table import TIMEFRAME_DURATIONS
from primitives.crt_range import detect_crt_ranges

_HTF_SPECS = [
    (1.1006, 1.1035, 1.0997, 1.1000),  # 0
    (1.1008, 1.1032, 1.0991, 1.0998),  # 1
    (1.0992, 1.1005, 1.0944, 1.0973),  # 2
    (1.0972, 1.1032, 1.0963, 1.1009),  # 3 -- only resolves once candle 6 exists
    (1.1013, 1.1021, 1.0992, 1.1016),  # 4 -- resolves true_break @5
    (1.0996, 1.1018, 1.0959, 1.0986),  # 5 -- shared purge candle for both ranges
    (1.1004, 1.1015, 1.0985, 1.1014),  # 6 -- future candle
]
_HTF_DURATION = TIMEFRAME_DURATIONS["4H"]
_DIRECTION = "bearish"  # take_profit = htf_context.low for bearish


def _htf_series(n: int) -> OHLCSeries:
    start = datetime(2026, 1, 1, 0, 0)
    candles = tuple(
        Candle(timestamp=start + _HTF_DURATION * i, open=o, high=h, low=l, close=c)
        for i, (o, h, l, c) in enumerate(_HTF_SPECS[:n])
    )
    return OHLCSeries(candles=candles, instrument="EURUSD", timeframe="4H")


def test_legacy_take_profit_mutates_from_a_future_htf_candle():
    """Historical evidence only (REQ-CAUSAL-21) — reproduces B3/B4 on the
    real, current, unmodified `alignment.htf_ltf._purge_index_map`."""
    series6, series7 = _htf_series(6), _htf_series(7)
    map6 = _purge_index_map(series6.candles, detect_crt_ranges(series6))
    map7 = _purge_index_map(series7.candles, detect_crt_ranges(series7))

    tp_at_6 = take_profit(map6[5], _DIRECTION)
    tp_at_7 = take_profit(map7[5], _DIRECTION)

    assert map6[5].start_index == 4
    assert map7[5].start_index == 3
    assert tp_at_6 != tp_at_7  # B3/B4: the mutation, reproduced


def test_causal_take_profit_stable_across_the_same_future_candle():
    """Fix: H-A selects by event-time closure, not by which ranges happen
    to be present in the input — the same event time `t` yields the same
    `take_profit` whether or not the future candle is appended."""
    series6, series7 = _htf_series(6), _htf_series(7)
    t = series6.candles[5].timestamp + _HTF_DURATION  # fixed LTF event time

    context_at_6 = select_htf_context(series6, detect_crt_ranges(series6), t)
    context_at_7 = select_htf_context(series7, detect_crt_ranges(series7), t)

    assert context_at_6.start_index == context_at_7.start_index == 4
    assert take_profit(context_at_6, _DIRECTION) == take_profit(context_at_7, _DIRECTION)
