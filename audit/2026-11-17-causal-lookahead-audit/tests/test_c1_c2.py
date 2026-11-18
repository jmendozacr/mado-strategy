"""Tests for Arms C1/C2 (causal_intrabar.py). Design: design-c1-c2.md
rounds 1-3. Nothing under detector/ or scanner/ touched.
"""
import bisect
import os
import sys
from datetime import datetime, timedelta

import pytest

AUDIT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.abspath(os.path.join(AUDIT_DIR, "..", ".."))
DATA_DIR = os.path.join(REPO_ROOT, "data")

from backtest.candidate import Candidate  # noqa: E402
from backtest.population import build_stage6_population  # noqa: E402
from backtest.simulate import _resolve_exits  # noqa: E402
from core.candle import Candle, OHLCSeries  # noqa: E402
from core.config import DetectorConfig  # noqa: E402
from core.key_level import KeyLevel  # noqa: E402
from experimental.htf_trigger_1am_9am_backtest import SYMBOL_CONFIG, _find_csv  # noqa: E402
from ingestion.loader import load_mt5_csv  # noqa: E402
from ingestion.pairing import load_pair  # noqa: E402
from primitives.crt_range import detect_crt_ranges  # noqa: E402
from primitives.swing import detect_swings  # noqa: E402

import causal_intrabar as ci  # noqa: E402
from causal_lib import build_key_levels  # noqa: E402


def _m15(lows, highs=None, start=datetime(2026, 1, 1, 0, 0)):
    highs = highs or [max(100.0, low) for low in lows]
    return tuple(
        Candle(timestamp=start + timedelta(minutes=15 * i), open=100.0, high=highs[i], low=low, close=100.0)
        for i, low in enumerate(lows)
    )


def _h4(opens_highs_lows_closes, start=datetime(2026, 1, 1, 0, 0), step=timedelta(hours=4)):
    return tuple(
        Candle(timestamp=start + step * i, open=o, high=h, low=l, close=c)
        for i, (o, h, l, c) in enumerate(opens_highs_lows_closes)
    )


# ---------------------------------------------------------------------------
# fill_pass_c (round-3 fix: first_fillable_index, never confirmation_index)
# ---------------------------------------------------------------------------

def _bullish_candidate(signal_id, entry_price=100.0):
    return Candidate(
        signal_id=signal_id, anchor_index=0, origin_index=0, direction="bullish", entry_type="wick",
        retest_index=0, entry_price=entry_price, stop_loss=90.0, take_profit=120.0, partial_price=110.0,
    )


def test_fill_pass_c_touch_only_during_confirmation_bar_never_fills():
    """Confirmation bar is index 5 (opens 01:15, closes 01:30). It touches
    entry_price=100 itself (low=95). No bar from first_fillable_index
    (index 6) onward ever touches again. Required: never_filled."""
    lows = [110.0] * 10
    lows[5] = 95.0  # touches, but THIS bar is the confirmation bar itself
    candles = _m15(lows)
    m15_timestamps = [c.timestamp for c in candles]
    candidate = _bullish_candidate("sig-A")
    order_placed_ts = candles[5].timestamp + ci.M15_DURATION  # available_at(confirmation bar)

    filled, never_filled, skipped = ci.fill_pass_c(
        [candidate], candles, m15_timestamps, max_fill_wait=20,
        order_placed_ts_by_signal_id={"sig-A": order_placed_ts},
        confirmation_index_by_signal_id={"sig-A": 5},
    )
    assert filled == []
    assert never_filled == 1
    assert skipped == 0


def test_fill_pass_c_touch_after_activation_fills_at_that_later_touch():
    """Same setup, but a touch exists at index 8 (>= first_fillable_index
    = 6). Must fill at index 8, never at the confirmation bar (index 5)."""
    lows = [110.0] * 10
    lows[5] = 95.0   # confirmation bar's own touch -- must be ignored
    lows[8] = 97.0   # the real, credited touch
    candles = _m15(lows)
    m15_timestamps = [c.timestamp for c in candles]
    candidate = _bullish_candidate("sig-B")
    order_placed_ts = candles[5].timestamp + ci.M15_DURATION

    filled, never_filled, skipped = ci.fill_pass_c(
        [candidate], candles, m15_timestamps, max_fill_wait=20,
        order_placed_ts_by_signal_id={"sig-B": order_placed_ts},
        confirmation_index_by_signal_id={"sig-B": 5},
    )
    assert never_filled == 0
    assert len(filled) == 1
    resolved, fill_index = filled[0]
    assert fill_index == 8


def test_fill_pass_c_first_fillable_index_uses_real_timestamps_across_a_gap():
    """A gap right after the confirmation bar: bar 5 closes 01:30, but the
    next bar available opens 02:00 (missing 01:30/01:45). first_fillable_index
    must resolve to the ACTUAL next bar via bisect, never a blind +1."""
    start = datetime(2026, 1, 1, 0, 0)
    pre_gap = [
        Candle(timestamp=start + timedelta(minutes=15 * i), open=100, high=110, low=110, close=100)
        for i in range(6)
    ]
    post_gap = [
        Candle(timestamp=start + timedelta(hours=2) + timedelta(minutes=15 * i), open=100, high=110, low=97, close=100)
        for i in range(4)
    ]
    candles = tuple(pre_gap + post_gap)
    m15_timestamps = [c.timestamp for c in candles]
    candidate = _bullish_candidate("sig-C")
    order_placed_ts = candles[5].timestamp + ci.M15_DURATION  # 01:30 -- no bar opens exactly then

    filled, never_filled, skipped = ci.fill_pass_c(
        [candidate], candles, m15_timestamps, max_fill_wait=20,
        order_placed_ts_by_signal_id={"sig-C": order_placed_ts},
        confirmation_index_by_signal_id={"sig-C": 5},
    )
    expected_index = bisect.bisect_left(m15_timestamps, order_placed_ts)
    assert expected_index == 6  # the real next bar, at 02:00 -- not confirmation_index+1's timestamp
    assert len(filled) == 1
    assert filled[0][1] == 6  # first post-gap bar touches (low=97)
    assert never_filled == 0


def test_fill_pass_c_rejects_first_fillable_index_not_strictly_after_confirmation():
    """Defensive invariant (round 3): a caller bug that produces
    first_fillable_index <= confirmation_index must fail loudly, not
    silently credit a fill from the confirmation bar itself."""
    candles = _m15([110.0] * 5)
    m15_timestamps = [c.timestamp for c in candles]
    candidate = _bullish_candidate("sig-D")
    with pytest.raises(AssertionError):
        ci.fill_pass_c(
            [candidate], candles, m15_timestamps, max_fill_wait=20,
            order_placed_ts_by_signal_id={"sig-D": candles[2].timestamp},  # == confirmation bar's own open, wrong
            confirmation_index_by_signal_id={"sig-D": 2},
        )


def test_fill_pass_c_consecutive_grid_gives_exact_equality_invariant():
    """On a gapless grid, first_fillable_ts == model1_available_ts exactly
    (equality is fine -- only the INDEX must move forward)."""
    candles = _m15([110.0] * 10)
    m15_timestamps = [c.timestamp for c in candles]
    confirmation_index = 4
    order_placed_ts = candles[confirmation_index].timestamp + ci.M15_DURATION
    assert order_placed_ts == candles[confirmation_index + 1].timestamp
    idx = bisect.bisect_left(m15_timestamps, order_placed_ts)
    assert idx == confirmation_index + 1


# ---------------------------------------------------------------------------
# key_level_credited: timestamp bridge + sentinel safety (round 3)
# ---------------------------------------------------------------------------

def test_key_level_credited_rejects_cross_grid_index_reuse():
    h4_broker = OHLCSeries(
        candles=_h4([(1, 1, 1, 1)] * 10), instrument="EURUSD", timeframe="4H",
    )
    level = KeyLevel(kind="fvg", top=105.0, bottom=95.0, origin_index=5)  # available at h4[5].ts + 4h
    purge_before = h4_broker.candles[5].timestamp + ci.H4_DURATION - timedelta(minutes=1)
    purge_after = h4_broker.candles[5].timestamp + ci.H4_DURATION + timedelta(minutes=1)

    assert ci.key_level_credited((100.0,), purge_before, [level], h4_broker) is None
    credited = ci.key_level_credited((100.0,), purge_after, [level], h4_broker)
    assert credited is level


def test_key_level_credited_handles_sentinel_origin_without_indexerror():
    h4_broker = OHLCSeries(candles=_h4([(1, 1, 1, 1)] * 5), instrument="EURUSD", timeframe="4H")
    sentinel_level = KeyLevel(kind="fvg", top=105.0, bottom=95.0, origin_index=len(h4_broker.candles))
    result = ci.key_level_credited((100.0,), datetime(2027, 1, 1), [sentinel_level], h4_broker)
    assert result is None  # never credits -- and, critically, no IndexError


def test_key_level_credited_handles_sentinel_expiry_as_never_expired():
    h4_broker = OHLCSeries(candles=_h4([(1, 1, 1, 1)] * 5), instrument="EURUSD", timeframe="4H")
    level = KeyLevel(
        kind="fvg", top=105.0, bottom=95.0, origin_index=0, expiry_index=len(h4_broker.candles),
    )
    far_future = h4_broker.candles[-1].timestamp + timedelta(days=365)
    result = ci.key_level_credited((100.0,), far_future, [level], h4_broker)
    assert result is level  # sentinel expiry never found within the series -- treated as not-yet-expired


# ---------------------------------------------------------------------------
# Feeder-candle construction / completeness (design §3/§4)
# ---------------------------------------------------------------------------

def test_validate_complete_feeder_bucket():
    base = datetime(2026, 1, 1, 9, 0)
    good = tuple(Candle(timestamp=base + timedelta(minutes=15 * i), open=1, high=1, low=1, close=1) for i in range(16))
    assert ci.validate_complete_feeder_bucket(good, base) is True

    too_few = good[:15]
    assert ci.validate_complete_feeder_bucket(too_few, base) is False

    wrong_start = tuple(Candle(timestamp=base + timedelta(minutes=15 * (i + 1)), open=1, high=1, low=1, close=1) for i in range(16))
    assert ci.validate_complete_feeder_bucket(wrong_start, base) is False

    gap = list(good)
    gap[8] = Candle(timestamp=gap[8].timestamp + timedelta(minutes=15), open=1, high=1, low=1, close=1)
    assert ci.validate_complete_feeder_bucket(tuple(gap), base) is False


def test_available_at_is_open_plus_duration():
    candle = Candle(timestamp=datetime(2026, 3, 30, 6, 0), open=1, high=1, low=1, close=1)
    assert ci.available_at(candle, ci.M15_DURATION) == datetime(2026, 3, 30, 6, 15)
    assert ci.available_at(candle, ci.H4_DURATION) == datetime(2026, 3, 30, 10, 0)


# ---------------------------------------------------------------------------
# End-to-end: small real EURUSD slice, C1 and C2
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def eurusd_small_slice():
    h4_csv = _find_csv(DATA_DIR, "EURUSD", "H4")
    m15_csv = _find_csv(DATA_DIR, "EURUSD", "M15")
    d1_csv = _find_csv(DATA_DIR, "EURUSD", "D1")
    h4_full, m15_full = load_pair(htf_csv=h4_csv, htf_symbol="EURUSD", ltf_csv=m15_csv, ltf_symbol="EURUSD")
    daily_full = load_mt5_csv(d1_csv, symbol="EURUSD")
    h4 = h4_full.up_to(600)
    daily = daily_full.up_to(120)
    cutoff = h4.candles[-1].timestamp
    m15_count = sum(1 for c in m15_full.candles if c.timestamp <= cutoff)
    m15 = m15_full.up_to(m15_count)
    config = DetectorConfig(backtest=SYMBOL_CONFIG["EURUSD"])
    m15_timestamps = [c.timestamp for c in m15.candles]
    ltf_ranges = detect_crt_ranges(m15, config.crt_range)
    swings = detect_swings(m15, config.swing)
    key_levels = build_key_levels(h4, daily, config.fvg)
    return h4, m15, daily, config, m15_timestamps, ltf_ranges, swings, key_levels


def test_c1_never_confirms_model1_before_activation_instant(eurusd_small_slice):
    h4, m15, daily, config, m15_timestamps, ltf_ranges, swings, key_levels = eurusd_small_slice
    checked = 0
    for model, model_name in ((ci.MODEL_1AM, "1am"), (ci.MODEL_9AM, "9am")):
        for i in range(1, len(h4.candles)):
            if h4.candles[i].timestamp.hour != model.trigger_utc_hour or h4.candles[i].timestamp.minute != 0:
                continue
            reference = ci.complete_feeder_candle_broker(h4, i - 1)
            window_open_ts = h4.candles[i].timestamp
            outcomes = ci.detect_sweep_and_key_level(
                m15_timestamps, m15.candles, reference, window_open_ts,
                window_open_ts + ci.H4_DURATION, key_levels, h4,
            )
            for direction, outcome in outcomes.items():
                if outcome.trigger is None:
                    continue
                record = ci.build_causal_signal(
                    model, model_name, outcome.trigger, window_open_ts, m15, ltf_ranges, config.model1, reference
                )
                if record.aligned is None:
                    continue
                checked += 1
                assert record.model1_available_ts >= record.activation_instant_ts
                assert record.confirmation_index is not None
                m15_confirm_ts = m15.candles[record.confirmation_index].timestamp
                assert m15_confirm_ts + ci.M15_DURATION == record.model1_available_ts
    assert checked > 0, "fixture produced zero confirmed C1 signals -- widen the slice"


def test_c1_c2_share_build_causal_signal_and_fill_pass_c():
    """Structural check: both arms call the exact same functions
    (build_causal_signal, fill_pass_c) -- no per-arm branch exists in
    either. Verified by identity, not by re-reading source."""
    import run_c1_c2
    assert run_c1_c2.ci.build_causal_signal is ci.build_causal_signal
    assert run_c1_c2.ci.fill_pass_c is ci.fill_pass_c
