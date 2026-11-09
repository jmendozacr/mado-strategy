from datetime import datetime, timedelta

from alignment.htf_ltf import AlignedSignal
from core.candle import Candle
from core.key_level import KeyLevel
from entries.model1 import Model1Signal
from experimental.ote_confluence_check import (
    OteRow,
    build_ote_rows,
    classify_ote,
    stats_for,
)
from primitives.crt_range import CRTRange
from primitives.swing import SwingPoint


def _candle(i, o, c, h=None, l=None):
    return Candle(
        timestamp=datetime(2026, 1, 1) + timedelta(hours=4 * i),
        open=o, close=c,
        high=h if h is not None else max(o, c) + 0.0001,
        low=l if l is not None else min(o, c) - 0.0001,
    )


def _range(high, low, start, end):
    return CRTRange(model="2-candle", high=high, low=low, start_index=start, end_index=end,
                     resolution="true_break", resolved_at_index=end)


def _signal(direction="bullish", anchor_index=0):
    return Model1Signal(
        anchor_index=anchor_index, direction=direction, purge_target=0.0,
        confirmation_type="purge_engulf", entry_type="wick", entry_price=0.0,
        retest_index=None, status="CONFIRMED", confirmation_index=0, origin_index=0,
    )


def _aligned(crt_range, level, direction="bullish"):
    return AlignedSignal(
        ltf_signal=_signal(direction=direction), htf_context=crt_range, aligned="aligned", key_level=level,
    )


class TestClassifyOte:
    def test_none_without_credited_key_level(self) -> None:
        crt_range = _range(1.10, 1.00, 0, 1)
        candles = (_candle(0, 1.05, 1.06), _candle(1, 1.05, 1.11))
        signal = _aligned(crt_range, level=None)
        assert classify_ote(signal, candles, swings=[], band=(0.60, 0.75)) is None

    def test_none_without_an_impulse_leg(self) -> None:
        crt_range = _range(1.10, 1.00, 0, 1)
        candles = (_candle(0, 1.05, 1.06), _candle(1, 1.05, 1.11))
        level = KeyLevel(kind="fvg", top=1.05, bottom=1.04, origin_index=0)
        signal = _aligned(crt_range, level)
        assert classify_ote(signal, candles, swings=[], band=(0.60, 0.75)) is None

    def test_true_when_level_overlaps_the_ote_band(self) -> None:
        crt_range = _range(1.10, 1.00, 0, 1)
        candles = (_candle(0, 1.05, 1.06), _candle(1, 1.05, 1.11))
        swings = [SwingPoint(index=0, kind="low", price=1.00), SwingPoint(index=0, kind="high", price=1.10)]
        # bullish leg (1.00, 1.10), band (0.60,0.75) -> zone (1.025, 1.04)
        level = KeyLevel(kind="fvg", top=1.035, bottom=1.030, origin_index=0)
        signal = _aligned(crt_range, level)
        assert classify_ote(signal, candles, swings=swings, band=(0.60, 0.75)) is True

    def test_false_when_level_outside_the_ote_band(self) -> None:
        crt_range = _range(1.10, 1.00, 0, 1)
        candles = (_candle(0, 1.05, 1.06), _candle(1, 1.05, 1.11))
        swings = [SwingPoint(index=0, kind="low", price=1.00), SwingPoint(index=0, kind="high", price=1.10)]
        level = KeyLevel(kind="fvg", top=1.09, bottom=1.08, origin_index=0)
        signal = _aligned(crt_range, level)
        assert classify_ote(signal, candles, swings=swings, band=(0.60, 0.75)) is False


class TestBuildAndStats:
    def test_build_rows_skips_unevaluable_signals(self) -> None:
        crt_range = _range(1.10, 1.00, 0, 1)
        candles = (_candle(0, 1.05, 1.06), _candle(1, 1.05, 1.11))
        signals = [_aligned(crt_range, level=None)]
        rows = build_ote_rows(signals, candles, swings=[], trades=[], band=(0.60, 0.75))
        assert rows == ()

    def test_stats_for_splits_by_in_ote(self) -> None:
        rows = (
            OteRow(signal_id="a", key_level_kind="fvg", in_ote=True, outcome="win", r_multiple=2.0),
            OteRow(signal_id="b", key_level_kind="fvg", in_ote=True, outcome="loss", r_multiple=-1.0),
            OteRow(signal_id="c", key_level_kind="fvg", in_ote=False, outcome="loss", r_multiple=-1.0),
        )
        in_zone = stats_for(rows, in_ote=True)
        out_zone = stats_for(rows, in_ote=False)
        assert in_zone["n"] == 2 and in_zone["win_rate"] == 0.5
        assert out_zone["n"] == 1 and out_zone["win_rate"] == 0.0
