"""Groups M/N/Q (spec.md REQ-STAT-29): the Candidate admission cutoff, the
separate outcome-followup resolution cutoff, and naive-UTC timestamp
normalization for the 'Z'-suffixed manifest strings."""

from datetime import datetime, timedelta

import pytest

from adapter.cutoff import (
    candidate_event_timestamp,
    exit_event_timestamp,
    parse_manifest_timestamp,
    require_naive,
    validate_candidate_cutoff,
    validate_exit_index_bounds,
    validate_outcome_followup_cutoff,
    validate_retest_index_bounds,
)
from adapter.errors import CandidateCutoffError
from core.candle import Candle, OHLCSeries


def _series(size: int = 10) -> OHLCSeries:
    candles = tuple(
        Candle(
            timestamp=datetime(2026, 1, 1) + timedelta(minutes=15 * i),
            open=1.0, high=1.1, low=0.9, close=1.05,
        )
        for i in range(size)
    )
    return OHLCSeries(candles=candles, instrument="EURUSDm", timeframe="15M")


# --- Group M(b): retest_index bounds -----------------------------------------


def test_retest_index_within_bounds_passes():
    validate_retest_index_bounds(3, _series())  # must not raise


def test_negative_retest_index_fails_closed_never_wraparound():
    with pytest.raises(CandidateCutoffError):
        validate_retest_index_bounds(-1, _series())


def test_retest_index_at_or_past_length_fails_closed():
    series = _series(size=10)
    with pytest.raises(CandidateCutoffError):
        validate_retest_index_bounds(10, _series(size=10))
    with pytest.raises(CandidateCutoffError):
        validate_retest_index_bounds(999, series)


def test_candidate_event_timestamp_is_the_retest_candle_never_anchor():
    series = _series()
    assert candidate_event_timestamp(3, series) == series.candles[3].timestamp
    assert candidate_event_timestamp(3, series) != series.candles[1].timestamp


# --- Group M(a): candidate cutoff, strict < ----------------------------------


def test_candidate_strictly_before_cutoff_is_eligible():
    series = _series()
    cutoff = series.candles[5].timestamp
    validate_candidate_cutoff(3, series, cutoff)  # must not raise


def test_candidate_at_cutoff_boundary_is_not_eligible():
    series = _series()
    cutoff = series.candles[5].timestamp  # equal, not strictly before
    with pytest.raises(CandidateCutoffError):
        validate_candidate_cutoff(5, series, cutoff)


def test_candidate_after_cutoff_is_not_eligible():
    series = _series()
    cutoff = series.candles[5].timestamp
    with pytest.raises(CandidateCutoffError):
        validate_candidate_cutoff(7, series, cutoff)


# --- Group N: outcome followup cutoff, separate from candidate cutoff -------
# REQ-STAT-29(c), V4: `validate_outcome_followup_cutoff` now owns the
# exit_index bounds-check + timestamp lookup itself (mirrors the candidate
# side) — callers pass `exit_index` + the LTF series, never a pre-computed
# timestamp.


def test_no_exit_index_never_checked_open_never_filled():
    validate_outcome_followup_cutoff(None, _series(), datetime(2026, 1, 1))  # must not raise


def test_exit_before_followup_cutoff_is_valid():
    series = _series()
    followup_cutoff = series.candles[7].timestamp
    validate_outcome_followup_cutoff(5, series, followup_cutoff)


def test_exit_exactly_at_followup_cutoff_is_valid_boundary_inclusive():
    series = _series()
    boundary_index = 5
    boundary = series.candles[boundary_index].timestamp
    validate_outcome_followup_cutoff(boundary_index, series, boundary)  # "after" is forbidden, not "at"


def test_exit_after_followup_cutoff_fails_closed():
    series = _series()
    followup_cutoff = series.candles[5].timestamp
    with pytest.raises(CandidateCutoffError):
        validate_outcome_followup_cutoff(7, series, followup_cutoff)


def test_candidate_cutoff_and_outcome_followup_cutoff_are_independent():
    """Regression: a Candidate admitted before the candidate cutoff may
    legitimately have its Trade resolve after the candidate cutoff but
    before the (later) outcome-followup cutoff — the two questions must
    never be conflated (spec.md REQ-STAT-29d)."""
    series = _series(size=20)
    candidate_cutoff = series.candles[5].timestamp
    outcome_followup_cutoff = series.candles[15].timestamp

    validate_candidate_cutoff(3, series, candidate_cutoff)  # admitted

    # exit at index 10: after candidate cutoff, before followup cutoff — still valid
    validate_outcome_followup_cutoff(10, series, outcome_followup_cutoff)


# --- Group N(bounds): exit_index bounds-check mirrors retest_index's --------


def test_exit_index_within_bounds_passes():
    validate_exit_index_bounds(3, _series())  # must not raise


def test_negative_exit_index_fails_closed_never_wraparound():
    with pytest.raises(CandidateCutoffError):
        validate_exit_index_bounds(-1, _series())


def test_exit_index_at_or_past_length_fails_closed():
    series = _series(size=10)
    with pytest.raises(CandidateCutoffError):
        validate_exit_index_bounds(10, series)
    with pytest.raises(CandidateCutoffError):
        validate_exit_index_bounds(999, series)


def test_exit_event_timestamp_is_the_exit_candle():
    series = _series()
    assert exit_event_timestamp(5, series) == series.candles[5].timestamp


def test_negative_exit_index_fails_closed_via_followup_cutoff_never_wraparound():
    with pytest.raises(CandidateCutoffError):
        validate_outcome_followup_cutoff(-1, _series(), datetime(2026, 1, 1))


def test_exit_index_at_series_length_fails_closed_via_followup_cutoff():
    series = _series(size=10)
    with pytest.raises(CandidateCutoffError):
        validate_outcome_followup_cutoff(10, series, datetime(2026, 1, 1))


# --- Group Q: naive-UTC timestamp normalization ------------------------------


def test_z_suffixed_manifest_timestamp_normalizes_to_naive():
    parsed = parse_manifest_timestamp("2026-01-01T00:00:00Z")
    assert parsed == datetime(2026, 1, 1, 0, 0, 0)
    assert parsed.tzinfo is None


def test_require_naive_rejects_timezone_aware_datetime():
    from datetime import timezone

    aware = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(CandidateCutoffError):
        require_naive(aware)


def test_require_naive_accepts_naive_datetime():
    require_naive(datetime(2026, 1, 1))  # must not raise


def test_candidate_cutoff_rejects_aware_cutoff_value():
    """Comparing naive against timezone-aware, or converting to local time,
    is prohibited (spec.md REQ-STAT-29)."""
    from datetime import timezone

    series = _series()
    aware_cutoff = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(CandidateCutoffError):
        validate_candidate_cutoff(3, series, aware_cutoff)
