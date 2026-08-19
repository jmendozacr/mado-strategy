"""Hypothesis harness for the no-lookahead structural contract (REQ-07,
ADR-03): detect(series.up_to(n)) must equal full-series detection,
truncated to indices in the settled zone (index <= n - k - 1).

Swing's k=1, so the settled zone is index <= n - 2 (swings need both
neighbours, so a truncated series of length n can never surface an index
beyond n - 2 anyway — the property test locks this in as a regression
guard against a future change accidentally introducing lookahead).
"""

from datetime import datetime, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from core.candle import Candle, OHLCSeries
from primitives.swing import detect_swings

_SWING_K = 1


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
def ohlc_series(draw, min_size=3, max_size=30):
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    candles = tuple(_ohlc_candle(draw, i) for i in range(size))
    return OHLCSeries(candles=candles, instrument="EURUSD", timeframe="1H")


@given(series=ohlc_series())
@settings(max_examples=100)
def test_swing_detection_has_no_lookahead(series: OHLCSeries):
    full_swings = detect_swings(series)

    for n in range(3, len(series.candles) + 1):
        truncated_swings = detect_swings(series.up_to(n))
        settled_boundary = n - _SWING_K - 1  # indices <= this are settled

        settled_full_swings = [s for s in full_swings if s.index <= settled_boundary]

        assert truncated_swings == settled_full_swings
