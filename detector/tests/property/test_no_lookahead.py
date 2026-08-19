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
from primitives.crt_range import detect_crt_ranges
from primitives.fvg import detect_fvgs
from primitives.swing import detect_swings

_SWING_K = 1
_FVG_K = 3
_CRT_RANGE_K = 20


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


@given(series=ohlc_series())
@settings(max_examples=100)
def test_fvg_detection_has_no_lookahead(series: OHLCSeries):
    """FVG's k=3 bounds formation identity (start_index/end_index/top/
    bottom/direction) — settled once candles i, i+1, i+2 are visible.
    fill_status is NOT k-bounded the same way: "cumulative price action
    after formation" can fill a gap arbitrarily far beyond formation, so it
    is monotonic (open -> filled, never filled -> open) rather than final
    within a fixed settling window. The property checks (a) full equality
    of formation-identity fields for settled gaps, and (b) fill_status
    monotonicity: a truncated view reporting "filled" must also report
    "filled" in the full series (that observation can't be undone by more
    data); "open" in a truncated view may still resolve "filled" later.
    """
    full_fvgs = detect_fvgs(series)
    full_by_start = {f.start_index: f for f in full_fvgs}

    for n in range(3, len(series.candles) + 1):
        truncated_fvgs = detect_fvgs(series.up_to(n))
        settled_boundary = n - _FVG_K - 1

        settled_truncated = [f for f in truncated_fvgs if f.start_index <= settled_boundary]

        settled_full_start_indices = {
            f.start_index for f in full_fvgs if f.start_index <= settled_boundary
        }
        assert {f.start_index for f in settled_truncated} == settled_full_start_indices

        for truncated_fvg in settled_truncated:
            full_fvg = full_by_start[truncated_fvg.start_index]
            assert truncated_fvg.end_index == full_fvg.end_index
            assert truncated_fvg.top == full_fvg.top
            assert truncated_fvg.bottom == full_fvg.bottom
            assert truncated_fvg.direction == full_fvg.direction
            if truncated_fvg.fill_status == "filled":
                assert full_fvg.fill_status == "filled"


@given(series=ohlc_series(max_size=45))
@settings(max_examples=100)
def test_crt_range_detection_has_no_lookahead(series: OHLCSeries):
    """CRT range's k=max_lookback=20 bounds the ENTIRE outcome (emitted or
    not, and every field) per start_index — unlike FVG's fill_status, a
    range's resolution always completes (or doesn't) within a bounded
    lookback, so settled entries need full equality, not monotonicity.
    """
    full_ranges = detect_crt_ranges(series)
    full_by_start = {r.start_index: r for r in full_ranges}

    for n in range(3, len(series.candles) + 1):
        truncated_ranges = detect_crt_ranges(series.up_to(n))
        settled_boundary = n - _CRT_RANGE_K - 1

        settled_truncated_starts = {
            r.start_index for r in truncated_ranges if r.start_index <= settled_boundary
        }
        settled_full_starts = {
            r.start_index for r in full_ranges if r.start_index <= settled_boundary
        }
        assert settled_truncated_starts == settled_full_starts

        truncated_by_start = {r.start_index: r for r in truncated_ranges}
        for start in settled_truncated_starts:
            assert truncated_by_start[start] == full_by_start[start]
