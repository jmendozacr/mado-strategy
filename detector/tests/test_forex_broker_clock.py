"""Tests for alignment.forex_broker_clock — REQ-73 (session identity via bisect,
not CRTRange.start_index) and ForexCRTSignal construction."""

from datetime import datetime, timedelta

from alignment.htf_ltf import AlignedSignal
from core.candle import Candle, OHLCSeries
from core.forex_crt_context import ForexCRTContext, ForexCRTSignal
from core.results import DetectionStatus
from entries.model1 import Model1Signal
from primitives.crt_range import CRTRange

from alignment.forex_broker_clock import detect_forex_crt_signals, find_asia_range_index


def _candle(ts: datetime, o=1.1, h=1.102, l=1.098, c=1.101) -> Candle:
    return Candle(timestamp=ts, open=o, high=h, low=l, close=c)


def _model1(anchor_index: int, direction="bearish") -> Model1Signal:
    return Model1Signal(
        anchor_index=anchor_index,
        direction=direction,
        purge_target=1.1,
        confirmation_type="purge_engulf",
        entry_type="wick",
        entry_price=1.1,
        retest_index=None,
        status=DetectionStatus.CONFIRMED,
        confirmation_index=anchor_index + 1,
        origin_index=anchor_index - 1,
    )


def _crt_range(start_index: int) -> CRTRange:
    return CRTRange(
        model="2-candle",
        high=1.102,
        low=1.098,
        start_index=start_index,
        end_index=start_index + 1,
        resolution="true_break",
        resolved_at_index=start_index + 1,
    )


# --- REQ-73.1: aligned signal in execution window with 01:00 enclosing H4 -> ForexCRTSignal ---

def _htf_series_with_london_session():
    """H4 candles spanning an overnight session: 17:00 Sep 15, 21:00 Sep 15,
    01:00 Sep 16, 05:00 Sep 16 — chronologically sorted."""
    htf_candles = (
        _candle(datetime(2026, 9, 15, 17, 0)),
        _candle(datetime(2026, 9, 15, 21, 0)),
        _candle(datetime(2026, 9, 16, 1, 0)),
        _candle(datetime(2026, 9, 16, 5, 0)),
    )
    return OHLCSeries(candles=htf_candles, instrument="EURUSD", timeframe="H4")


def test_aligned_signal_in_execution_window_emits_forex_crt_signal():
    """An M15 anchor at 02:15 enclosed by the 01:00 H4 candle -> qualifies."""
    htf_series = _htf_series_with_london_session()

    ltf_candles = tuple(
        _candle(datetime(2026, 9, 16, 2, m))
        for m in [0, 15, 30, 45]
    )
    ltf_series = OHLCSeries(candles=ltf_candles, instrument="EURUSD", timeframe="M15")

    signal = AlignedSignal(
        ltf_signal=_model1(anchor_index=1),
        htf_context=_crt_range(start_index=2),
        aligned="aligned",
    )

    result = detect_forex_crt_signals([signal], htf_series, ltf_series)

    assert len(result) == 1
    assert result[0].aligned_signal is signal
    assert result[0].forex_context.enclosing_h4_index == 2  # the 01:00 candle
    assert result[0].priority is False  # 02:15 is not in 03:00-04:00


def test_priority_subwindow_flag():
    """An M15 anchor at 03:15 -> priority=True."""
    htf_series = _htf_series_with_london_session()

    ltf_candles = tuple(
        _candle(datetime(2026, 9, 16, 3, m))
        for m in [0, 15, 30, 45]
    )
    ltf_series = OHLCSeries(candles=ltf_candles, instrument="EURUSD", timeframe="M15")

    signal = AlignedSignal(
        ltf_signal=_model1(anchor_index=1),
        htf_context=_crt_range(start_index=2),
        aligned="aligned",
    )

    result = detect_forex_crt_signals([signal], htf_series, ltf_series)

    assert len(result) == 1
    assert result[0].priority is True


# --- REQ-73.3: unaligned signals are excluded ---

def test_unaligned_signal_excluded():
    htf_series = _htf_series_with_london_session()

    ltf_candles = tuple(
        _candle(datetime(2026, 9, 16, 2, m))
        for m in [0, 15, 30, 45]
    )
    ltf_series = OHLCSeries(candles=ltf_candles, instrument="EURUSD", timeframe="M15")

    signal = AlignedSignal(
        ltf_signal=_model1(anchor_index=1),
        htf_context=None,
        aligned="unaligned",
    )

    result = detect_forex_crt_signals([signal], htf_series, ltf_series)

    assert result == []


# --- REQ-73.5: signal outside execution window excluded ---

def test_signal_outside_execution_window_excluded():
    """An M15 anchor at 05:15 — outside 02:00-04:00 window."""
    htf_candles = tuple(
        _candle(datetime(2026, 9, 16, h, 0))
        for h in [1, 5, 9, 13]
    )
    htf_series = OHLCSeries(candles=htf_candles, instrument="EURUSD", timeframe="H4")

    ltf_candles = tuple(
        _candle(datetime(2026, 9, 16, 5, m))
        for m in [0, 15, 30, 45]
    )
    ltf_series = OHLCSeries(candles=ltf_candles, instrument="EURUSD", timeframe="M15")

    signal = AlignedSignal(
        ltf_signal=_model1(anchor_index=1),
        htf_context=_crt_range(start_index=1),
        aligned="aligned",
    )

    result = detect_forex_crt_signals([signal], htf_series, ltf_series)

    assert result == []


# --- REQ-73.7: session identity via bisect, NOT CRTRange.start_index ---

def test_session_identity_via_bisect_not_start_index():
    """CRTRange.start_index points to the 17:00 H4 candle (generic sliding
    window origin), but the M15 anchor at 02:15 is temporally enclosed by the
    01:00 H4 candle. The function must use bisect to find the enclosing H4,
    NOT CRTRange.start_index."""
    htf_series = _htf_series_with_london_session()

    ltf_candles = tuple(
        _candle(datetime(2026, 9, 16, 2, m))
        for m in [0, 15, 30, 45]
    )
    ltf_series = OHLCSeries(candles=ltf_candles, instrument="EURUSD", timeframe="M15")

    # start_index=0 points to 17:00 — NOT the session-identity candle
    signal = AlignedSignal(
        ltf_signal=_model1(anchor_index=1),
        htf_context=_crt_range(start_index=0),
        aligned="aligned",
    )

    result = detect_forex_crt_signals([signal], htf_series, ltf_series)

    assert len(result) == 1
    # Enclosing H4 is index 2 (01:00), NOT index 0 (17:00 = start_index)
    assert result[0].forex_context.enclosing_h4_index == 2


# --- REQ-71.2/71.3: Asia range lookup ---

def test_find_asia_range_index_found():
    htf_series = _htf_series_with_london_session()

    idx = find_asia_range_index(datetime(2026, 9, 16, 1, 0), htf_series)
    assert idx == 1  # the 21:00 candle


def test_find_asia_range_index_not_found():
    htf_candles = tuple(
        _candle(datetime(2026, 9, 16, h, 0))
        for h in [1, 5, 9, 13]
    )
    htf_series = OHLCSeries(candles=htf_candles, instrument="EURUSD", timeframe="H4")

    idx = find_asia_range_index(datetime(2026, 9, 16, 1, 0), htf_series)
    assert idx is None


# --- ForexCRTContext Asia range fields ---

def test_forex_context_includes_asia_range_fields():
    asia_candle = Candle(
        timestamp=datetime(2026, 9, 15, 21, 0),
        open=1.1000, high=1.1040, low=1.0960, close=1.1010,
    )
    htf_candles = (
        _candle(datetime(2026, 9, 15, 17, 0)),
        asia_candle,
        _candle(datetime(2026, 9, 16, 1, 0)),
        _candle(datetime(2026, 9, 16, 5, 0)),
    )
    htf_series = OHLCSeries(candles=htf_candles, instrument="EURUSD", timeframe="H4")

    ltf_candles = tuple(
        _candle(datetime(2026, 9, 16, 2, m))
        for m in [0, 15, 30, 45]
    )
    ltf_series = OHLCSeries(candles=ltf_candles, instrument="EURUSD", timeframe="M15")

    signal = AlignedSignal(
        ltf_signal=_model1(anchor_index=1),
        htf_context=_crt_range(start_index=2),
        aligned="aligned",
    )

    result = detect_forex_crt_signals([signal], htf_series, ltf_series)

    assert len(result) == 1
    ctx = result[0].forex_context
    assert ctx.asia_range_h4_index == 1
    assert ctx.asia_range_high == 1.1040
    assert ctx.asia_range_low == 1.0960
    assert ctx.asia_range_midpoint == (1.1040 + 1.0960) / 2


def test_forex_context_asia_range_none_when_missing():
    """Series starts after the 21:00 candle — Asia range fields are None."""
    htf_candles = (
        _candle(datetime(2026, 9, 16, 1, 0)),
        _candle(datetime(2026, 9, 16, 5, 0)),
        _candle(datetime(2026, 9, 16, 9, 0)),
        _candle(datetime(2026, 9, 16, 13, 0)),
    )
    htf_series = OHLCSeries(candles=htf_candles, instrument="EURUSD", timeframe="H4")

    ltf_candles = tuple(
        _candle(datetime(2026, 9, 16, 2, m))
        for m in [0, 15, 30, 45]
    )
    ltf_series = OHLCSeries(candles=ltf_candles, instrument="EURUSD", timeframe="M15")

    signal = AlignedSignal(
        ltf_signal=_model1(anchor_index=1),
        htf_context=_crt_range(start_index=0),
        aligned="aligned",
    )

    result = detect_forex_crt_signals([signal], htf_series, ltf_series)

    assert len(result) == 1
    ctx = result[0].forex_context
    assert ctx.asia_range_h4_index is None
    assert ctx.asia_range_high is None
    assert ctx.asia_range_low is None
    assert ctx.asia_range_midpoint is None


# --- REQ-77: nine_pm_metrics attachment ---

def _htf_with_prior_and_asia(prior_high=1.110, prior_low=1.090):
    """H4 series: 17:00 (prior to Asia), 21:00 (Asia/9PM), 01:00 (London)."""
    return OHLCSeries(
        candles=(
            Candle(timestamp=datetime(2026, 9, 15, 17, 0),
                   open=1.100, high=prior_high, low=prior_low, close=1.105),
            Candle(timestamp=datetime(2026, 9, 15, 21, 0),
                   open=1.105, high=1.108, low=1.102, close=1.107),
            Candle(timestamp=datetime(2026, 9, 16, 1, 0),
                   open=1.107, high=1.112, low=1.098, close=1.101),
            Candle(timestamp=datetime(2026, 9, 16, 5, 0),
                   open=1.101, high=1.115, low=1.095, close=1.110),
        ),
        instrument="EURUSD",
        timeframe="H4",
    )


def _ltf_at_02h15():
    return OHLCSeries(
        candles=tuple(_candle(datetime(2026, 9, 16, 2, m)) for m in [0, 15, 30, 45]),
        instrument="EURUSD",
        timeframe="M15",
    )


def test_nine_pm_metrics_populated_when_prior_exists():
    """REQ-77.1: 9PM candle at index 1 with predecessor at index 0 -> nine_pm_metrics not None."""
    htf_series = _htf_with_prior_and_asia()
    ltf_series = _ltf_at_02h15()
    signal = AlignedSignal(
        ltf_signal=_model1(anchor_index=1),
        htf_context=_crt_range(start_index=2),
        aligned="aligned",
    )

    result = detect_forex_crt_signals([signal], htf_series, ltf_series)

    assert len(result) == 1
    assert result[0].nine_pm_metrics is not None


def test_nine_pm_metrics_none_when_asia_absent():
    """REQ-77.2: No 21:00 candle in series -> nine_pm_metrics is None."""
    htf_candles = (
        Candle(timestamp=datetime(2026, 9, 16, 1, 0),
               open=1.100, high=1.112, low=1.098, close=1.101),
        Candle(timestamp=datetime(2026, 9, 16, 5, 0),
               open=1.101, high=1.115, low=1.095, close=1.110),
        Candle(timestamp=datetime(2026, 9, 16, 9, 0),
               open=1.110, high=1.120, low=1.100, close=1.115),
        Candle(timestamp=datetime(2026, 9, 16, 13, 0),
               open=1.115, high=1.125, low=1.105, close=1.118),
    )
    htf_series = OHLCSeries(candles=htf_candles, instrument="EURUSD", timeframe="H4")
    ltf_series = _ltf_at_02h15()
    signal = AlignedSignal(
        ltf_signal=_model1(anchor_index=1),
        htf_context=_crt_range(start_index=0),
        aligned="aligned",
    )

    result = detect_forex_crt_signals([signal], htf_series, ltf_series)

    assert len(result) == 1
    assert result[0].nine_pm_metrics is None


def test_nine_pm_metrics_none_when_asia_at_index_zero():
    """REQ-77.3: 9PM candle is the first in the series (index 0) -> no prior -> None."""
    htf_candles = (
        Candle(timestamp=datetime(2026, 9, 15, 21, 0),
               open=1.100, high=1.110, low=1.090, close=1.105),
        Candle(timestamp=datetime(2026, 9, 16, 1, 0),
               open=1.105, high=1.115, low=1.095, close=1.108),
        Candle(timestamp=datetime(2026, 9, 16, 5, 0),
               open=1.108, high=1.118, low=1.098, close=1.112),
        Candle(timestamp=datetime(2026, 9, 16, 9, 0),
               open=1.112, high=1.122, low=1.102, close=1.116),
    )
    htf_series = OHLCSeries(candles=htf_candles, instrument="EURUSD", timeframe="H4")
    ltf_series = _ltf_at_02h15()
    signal = AlignedSignal(
        ltf_signal=_model1(anchor_index=1),
        htf_context=_crt_range(start_index=1),
        aligned="aligned",
    )

    result = detect_forex_crt_signals([signal], htf_series, ltf_series)

    assert len(result) == 1
    assert result[0].nine_pm_metrics is None


def test_nine_pm_metrics_correct_values():
    """REQ-77.1 + REQ-76: verify metric values propagate correctly end-to-end."""
    # prior H4 (17:00): high=1.110, low=1.090
    # 9PM H4 (21:00): open=1.105, high=1.108, low=1.102, close=1.107
    # 9PM high (1.108) < prior high (1.110) and 9PM low (1.102) > prior low (1.090) -> inside bar
    htf_series = _htf_with_prior_and_asia(prior_high=1.110, prior_low=1.090)
    ltf_series = _ltf_at_02h15()
    signal = AlignedSignal(
        ltf_signal=_model1(anchor_index=1),
        htf_context=_crt_range(start_index=2),
        aligned="aligned",
    )

    result = detect_forex_crt_signals([signal], htf_series, ltf_series)

    m = result[0].nine_pm_metrics
    assert m is not None
    assert m.body_direction == "bullish"   # 1.107 > 1.105
    assert m.extends_prior_high is False   # 1.108 <= 1.110
    assert m.extends_prior_low is False    # 1.102 >= 1.090
    assert m.is_inside_bar is True
    assert m.prior_h4_index == 0
