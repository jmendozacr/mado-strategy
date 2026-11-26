from datetime import date, timedelta

from conftest import flat_bucket, ny_ts, override

from primitives.fvg import FVG
from raza_h4fvg.h4_setup import h4_decision, known_fvgs_at

H4_COUNT = 16


def _reference_and_current(session_date, reference_overrides=None, current_overrides=None, base=1.1000):
    reference_open = ny_ts(session_date.year, session_date.month, session_date.day, 5)
    current_open = ny_ts(session_date.year, session_date.month, session_date.day, 9)
    assert current_open - reference_open == timedelta(hours=4)

    reference = flat_bucket(reference_open, H4_COUNT, base=base, flat_delta=0.0005)
    current = flat_bucket(current_open, H4_COUNT, base=base, flat_delta=0.0005)
    for idx, kwargs in (reference_overrides or {}).items():
        override(reference, idx, **kwargs)
    for idx, kwargs in (current_overrides or {}).items():
        override(current, idx, **kwargs)
    return tuple(reference + current), current_open


def _early_h4_series_for_fvg(before_ts):
    """A tiny, separate H4-timeframe series (distinct resolution from
    the M15 reference/current buckets above) whose own last candle
    closes well before `before_ts` -- `known_fvgs_at` reads this
    series's own timestamps, never the M15 one."""
    from core.candle import Candle
    return (
        Candle(before_ts - timedelta(hours=16), open=1.0, high=1.0, low=1.0, close=1.0),
        Candle(before_ts - timedelta(hours=12), open=1.0, high=1.0, low=1.0, close=1.0),
        Candle(before_ts - timedelta(hours=8), open=1.0, high=1.0, low=1.0, close=1.0),
    )


def test_bullish_setup_qualifies_with_a_matching_bullish_gap():
    session_date = date(2024, 6, 10)
    candles, current_open = _reference_and_current(
        session_date,
        reference_overrides={0: dict(open=1.10, high=1.1010, low=1.0990, close=1.10)},
        current_overrides={
            5: dict(open=1.0995, high=1.1005, low=1.0970, close=1.0995),
            15: dict(open=1.0995, high=1.1000, low=1.0990, close=1.0995),
        },
    )
    timestamps = [c.timestamp for c in candles]
    h4_series = _early_h4_series_for_fvg(current_open)
    gap = FVG(start_index=0, end_index=2, top=1.0980, bottom=1.0960, direction="bullish", fill_status="open")
    fvgs_known = known_fvgs_at([gap], h4_series, ny_ts(session_date.year, session_date.month, session_date.day, 9))
    assert len(fvgs_known) == 1

    result = h4_decision(timestamps, candles, current_open, "bullish", fvgs_known)
    assert result.qualifies
    assert result.sweep_side == "LOW_ONLY"
    assert result.swept_extreme == 1.0970
    assert result.target_edge == 1.1010


def test_setup_rejected_when_no_gap_matches_direction():
    session_date = date(2024, 6, 10)
    candles, current_open = _reference_and_current(
        session_date,
        reference_overrides={0: dict(open=1.10, high=1.1010, low=1.0990, close=1.10)},
        current_overrides={
            5: dict(open=1.0995, high=1.1005, low=1.0970, close=1.0995),
            15: dict(open=1.0995, high=1.1000, low=1.0990, close=1.0995),
        },
    )
    timestamps = [c.timestamp for c in candles]
    h4_series = _early_h4_series_for_fvg(current_open)
    # A BEARISH gap exists, but the setup is bullish -- never matches.
    gap = FVG(start_index=0, end_index=2, top=1.1040, bottom=1.1020, direction="bearish", fill_status="open")
    fvgs_known = known_fvgs_at([gap], h4_series, ny_ts(session_date.year, session_date.month, session_date.day, 9))

    result = h4_decision(timestamps, candles, current_open, "bullish", fvgs_known)
    assert not result.qualifies
    assert result.reason == "NO_MATCHING_GAP"


def test_double_sweep_is_disqualified_even_with_a_matching_gap():
    session_date = date(2024, 6, 10)
    candles, current_open = _reference_and_current(
        session_date,
        reference_overrides={0: dict(open=1.10, high=1.1010, low=1.0990, close=1.10)},
        current_overrides={
            5: dict(open=1.0995, high=1.1030, low=1.0970, close=1.0995),  # both sides swept
            15: dict(open=1.0995, high=1.1000, low=1.0990, close=1.0995),
        },
    )
    timestamps = [c.timestamp for c in candles]
    h4_series = _early_h4_series_for_fvg(current_open)
    gap = FVG(start_index=0, end_index=2, top=1.0980, bottom=1.0960, direction="bullish", fill_status="open")
    fvgs_known = known_fvgs_at([gap], h4_series, ny_ts(session_date.year, session_date.month, session_date.day, 9))

    result = h4_decision(timestamps, candles, current_open, "bullish", fvgs_known)
    assert not result.qualifies
    assert result.reason == "DOUBLE_SWEEP"


def test_sweep_disagreeing_with_daily_bias_is_disqualified():
    session_date = date(2024, 6, 10)
    candles, current_open = _reference_and_current(
        session_date,
        reference_overrides={0: dict(open=1.10, high=1.1010, low=1.0990, close=1.10)},
        current_overrides={
            5: dict(open=1.1005, high=1.1030, low=1.0995, close=1.1005),  # HIGH sweep
            15: dict(open=1.1005, high=1.1008, low=1.1000, close=1.1005),
        },
    )
    timestamps = [c.timestamp for c in candles]
    h4_series = _early_h4_series_for_fvg(current_open)
    gap = FVG(start_index=0, end_index=2, top=1.0980, bottom=1.0960, direction="bullish", fill_status="open")
    fvgs_known = known_fvgs_at([gap], h4_series, ny_ts(session_date.year, session_date.month, session_date.day, 9))

    # Daily bias says bullish, but the H4 candle swept the HIGH -> disagreement.
    result = h4_decision(timestamps, candles, current_open, "bullish", fvgs_known)
    assert not result.qualifies
    assert result.reason == "DISAGREES_WITH_DAILY_BIAS"


def test_fvg_not_yet_known_at_0900_is_excluded():
    session_date = date(2024, 6, 10)
    nine_am = ny_ts(session_date.year, session_date.month, session_date.day, 9)
    from core.candle import Candle
    h4_series = (Candle(nine_am + timedelta(hours=1), open=1.0, high=1.0, low=1.0, close=1.0),)  # closes AFTER 09:00
    gap = FVG(start_index=0, end_index=0, top=1.0980, bottom=1.0960, direction="bullish", fill_status="open")
    fvgs_known = known_fvgs_at([gap], h4_series, nine_am)
    assert fvgs_known == []
