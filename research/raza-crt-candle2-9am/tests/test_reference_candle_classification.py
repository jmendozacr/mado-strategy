import sys
from datetime import date, datetime, timedelta
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = LAB_ROOT.parent.parent
AUDIT_ROOT = REPO_ROOT / "audit" / "2026-11-17-causal-lookahead-audit"
for _path in (AUDIT_ROOT,):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import causal_intrabar as ci  # noqa: E402
from core.candle import Candle  # noqa: E402

from raza_extract.reference_candle_classification import classify_one

M15 = timedelta(minutes=15)


def _bucket(open_ts, closes, base=1.1000):
    """16 M15 candles spanning 4h; `closes` gives each candle's own
    (high, low, close) deltas from `base` so tests can place the
    final close and the running high/low precisely."""
    candles = []
    for i in range(16):
        h, l, c = closes[i] if i < len(closes) else (0.0, 0.0, 0.0)
        o = c  # open doesn't matter for this classification; close/high/low do
        candles.append(Candle(open_ts + i * M15, open=base + o, high=base + h, low=base + l, close=base + c))
    return tuple(candles)


def _ts(y, m, d, hour_ny):
    return ci.ny_anchored_open_utc(date(y, m, d), hour_ny)


def _full_series(reference_bucket, current_bucket):
    return reference_bucket + current_bucket


def test_inside_strict_close_classifies_inside_after_a_high_sweep():
    ref_open = _ts(2024, 6, 10, 5)  # a mid-year date, no DST edge
    cur_open = _ts(2024, 6, 10, 9)
    # reference: flat range [1.0990, 1.1010] (deltas -0.0010..+0.0010)
    reference = _bucket(ref_open, [(0.0010, -0.0010, 0.0) for _ in range(16)])
    # current: sweeps the high (delta +0.0020 > ref high +0.0010), closes back inside (delta +0.0005)
    deltas = [(0.0005, -0.0005, 0.0)] * 15 + [(0.0020, -0.0005, 0.0005)]
    current = _bucket(cur_open, deltas)
    m15 = _full_series(reference, current)
    timestamps = [c.timestamp for c in m15]

    result = classify_one("EURUSD", "bearish", "sid", cur_open, timestamps, m15)
    assert result.close_position == "INSIDE"
    assert result.sweep_side == "HIGH_ONLY"
    assert result.raza_direction == "bearish"


def test_outside_close_after_a_low_sweep():
    ref_open = _ts(2024, 6, 10, 5)
    cur_open = _ts(2024, 6, 10, 9)
    reference = _bucket(ref_open, [(0.0010, -0.0010, 0.0) for _ in range(16)])
    # sweeps the low (delta -0.0020 < ref low -0.0010), closes BELOW the range (delta -0.0015)
    deltas = [(0.0005, -0.0005, 0.0)] * 15 + [(0.0, -0.0020, -0.0015)]
    current = _bucket(cur_open, deltas)
    m15 = _full_series(reference, current)
    timestamps = [c.timestamp for c in m15]

    result = classify_one("EURUSD", "bullish", "sid", cur_open, timestamps, m15)
    assert result.close_position == "OUTSIDE"
    assert result.sweep_side == "LOW_ONLY"
    assert result.raza_direction == "bullish"


def test_exact_boundary_close_within_tolerance():
    ref_open = _ts(2024, 6, 10, 5)
    cur_open = _ts(2024, 6, 10, 9)
    reference = _bucket(ref_open, [(0.0010, -0.0010, 0.0) for _ in range(16)])
    # closes exactly at the reference high (0.0010)
    deltas = [(0.0005, -0.0005, 0.0)] * 15 + [(0.0015, -0.0005, 0.0010)]
    current = _bucket(cur_open, deltas)
    m15 = _full_series(reference, current)
    timestamps = [c.timestamp for c in m15]

    result = classify_one("EURUSD", "bearish", "sid", cur_open, timestamps, m15)
    assert result.close_position == "EXACT_BOUNDARY"


def test_double_sweep_is_ambiguous_per_raza_page_2():
    ref_open = _ts(2024, 6, 10, 5)
    cur_open = _ts(2024, 6, 10, 9)
    reference = _bucket(ref_open, [(0.0010, -0.0010, 0.0) for _ in range(16)])
    # sweeps BOTH sides across the 16 bars, closes inside
    deltas = [(0.0005, -0.0005, 0.0)] * 7 + [(0.0020, -0.0005, 0.0010)] + [(0.0005, -0.0025, -0.0010)] + [(0.0005, -0.0005, 0.0)] * 6
    current = _bucket(cur_open, deltas)
    m15 = _full_series(reference, current)
    timestamps = [c.timestamp for c in m15]

    result = classify_one("EURUSD", "bearish", "sid", cur_open, timestamps, m15)
    assert result.sweep_side == "BOTH"
    assert result.raza_direction == "DOUBLE_SWEEP_AMBIGUOUS"


def test_missing_reference_bucket_is_reported_not_silently_dropped():
    cur_open = _ts(2024, 6, 10, 9)
    reference_incomplete = tuple()  # no reference candles at all -> completeness check fails
    current = _bucket(cur_open, [(0.0005, -0.0005, 0.0) for _ in range(16)])
    m15 = reference_incomplete + current
    timestamps = [c.timestamp for c in m15]

    result = classify_one("EURUSD", "bearish", "sid", cur_open, timestamps, m15)
    assert result.close_position == "MISSING_OR_INCOMPLETE"
    assert result.sweep_side == "MISSING_OR_INCOMPLETE"
    assert result.raza_direction == "MISSING_OR_INCOMPLETE"


def test_missing_current_bucket_is_reported_not_silently_dropped():
    ref_open = _ts(2024, 6, 10, 5)
    cur_open = _ts(2024, 6, 10, 9)
    reference = _bucket(ref_open, [(0.0010, -0.0010, 0.0) for _ in range(16)])
    m15 = reference  # current bucket entirely absent
    timestamps = [c.timestamp for c in m15]

    result = classify_one("EURUSD", "bearish", "sid", cur_open, timestamps, m15)
    assert result.close_position == "MISSING_OR_INCOMPLETE"


def test_build_funnel_for_symbol_on_a_tight_real_data_range_has_consistent_stage_subsets():
    """Real-data smoke test (tight range, fast): every stage's own
    signal/trade set must be a SUBSET of the stage before it -- never a
    trade appearing without having first been a confirmed, candidate,
    filled signal. Also checks the trigger's own credited side stays
    swept by the complete candle (an analytic claim from the protocol,
    verified empirically here, not assumed)."""
    from datetime import datetime as _dt

    from raza_extract.reference_candle_classification import build_funnel_for_symbol
    result = build_funnel_for_symbol("EURUSD", start_date=_dt(2015, 1, 1), end_date=_dt(2015, 3, 1))

    assert result["n_triggers"] > 0
    assert result["candidate_sids"] <= result["confirmed_sids"]
    assert result["filled_sids"] <= result["candidate_sids"]
    assert set(result["executed_by_sid"].keys()) == result["filled_sids"]

    for sid in result["confirmed_sids"]:
        c = result["classifications"][sid]
        if c.sweep_side == "MISSING_OR_INCOMPLETE":
            continue
        # The credited side (the trigger's OWN baseline direction) must
        # remain swept by the complete current candle: "bearish" credits
        # on a high sweep, "bullish" on a low sweep.
        if c.direction == "bearish":
            assert c.sweep_side in ("HIGH_ONLY", "BOTH"), (sid, c)
        else:
            assert c.sweep_side in ("LOW_ONLY", "BOTH"), (sid, c)
