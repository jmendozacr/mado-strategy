"""Bug 1 differential regression: the single-pass sweep-line implementations
(fvg.py's fill-status resolution, mss.py's decisive-break resolution) must
resolve every instance identically to the per-instance forward scan they
replaced — pinned against independent reference implementations of the OLD
per-instance algorithms, run on a larger, overlap-heavy synthetic series
(hypothesis's default max_size in test_no_lookahead.py is far smaller than
what surfaced Bug 1 against real MT5 data).
"""

import random
from datetime import datetime, timedelta

from core.candle import Candle, OHLCSeries
from core.config import FVGConfig, MSSConfig
from composite.mss import detect_mss_events
from primitives.fvg import detect_fvgs
from primitives.swing import detect_swings

_SERIES_SIZE = 600


def _synthetic_series(size: int, seed: int) -> OHLCSeries:
    rng = random.Random(seed)
    candles = []
    price = 1.1000
    for i in range(size):
        open_ = price
        close = open_ + rng.uniform(-0.0015, 0.0015)
        high = max(open_, close) + rng.uniform(0.0, 0.0008)
        low = min(open_, close) - rng.uniform(0.0, 0.0008)
        candles.append(
            Candle(
                timestamp=datetime(2026, 1, 1) + timedelta(minutes=5 * i),
                open=open_, high=high, low=low, close=close,
            )
        )
        price = close
    return OHLCSeries(candles=tuple(candles), instrument="EURUSD", timeframe="5M")


def _reference_fill_status(candles, start_index, direction, top, bottom):
    """Independent reimplementation of the ORIGINAL per-FVG forward scan
    (pre-Bug-1-fix): a fresh linear scan restarting at start_index for every
    FVG, unlike the sweep-line's single shared pass.
    """
    for j in range(start_index, len(candles)):
        if direction == "bullish" and candles[j].low <= bottom:
            return "filled", j
        if direction == "bearish" and candles[j].high >= top:
            return "filled", j
    return "open", None


def test_sweep_fill_status_matches_reference_scan_on_large_overlapping_series():
    series = _synthetic_series(size=_SERIES_SIZE, seed=7)
    fvgs = detect_fvgs(series, config=FVGConfig(min_size_atr=0.0))

    assert len(fvgs) > 20  # sanity: fixture actually produces plenty of overlap

    for fvg in fvgs:
        expected_status, expected_index = _reference_fill_status(
            series.candles, fvg.start_index + 3, fvg.direction, fvg.top, fvg.bottom
        )
        assert fvg.fill_status == expected_status
        assert fvg.fill_index == expected_index


def _reference_decisive_break(candles, after_index, kind, price, threshold):
    for j in range(after_index + 1, len(candles)):
        close = candles[j].close
        if kind == "high" and close >= price + threshold:
            return j
        if kind == "low" and close <= price - threshold:
            return j
    return None


def test_sweep_decisive_break_matches_reference_scan_on_large_series():
    series = _synthetic_series(size=_SERIES_SIZE, seed=11)
    config = MSSConfig()
    swings = detect_swings(series)
    events = detect_mss_events(series, config=config)

    assert len(swings) > 20  # sanity: fixture actually produces plenty of swings

    events_by_key = {(e.broken_swing.index, e.direction): e for e in events}

    for broken_swing in swings:
        opposite_kind = "low" if broken_swing.kind == "high" else "high"
        candidates = [s for s in swings if s.kind == opposite_kind and s.index < broken_swing.index]
        if not candidates:
            continue
        opposite_swing = max(candidates, key=lambda s: s.index)
        distance = abs(broken_swing.price - opposite_swing.price)
        if distance <= 0:
            continue
        threshold = distance * config.decisive_close_ratio
        expected_index = _reference_decisive_break(
            series.candles, broken_swing.index, broken_swing.kind, broken_swing.price, threshold
        )
        direction = "bullish" if broken_swing.kind == "high" else "bearish"
        key = (broken_swing.index, direction)

        if expected_index is None:
            assert key not in events_by_key
        else:
            assert key in events_by_key
            assert events_by_key[key].index == expected_index
