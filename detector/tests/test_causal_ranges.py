"""Group 2 (REQ-CAUSAL-01/09): causal CRT range emission — a range must not
exist in causal output before its `resolved_at_index`, and the causal
emission driven from a prefix must equal the settled subset of the
full-series legacy detection (REQ-CAUSAL-01's I1)."""

from core.config import CRTRangeConfig
from causal.ranges import causal_crt_ranges
from primitives.crt_range import detect_crt_ranges
from tests.fixtures.synthetic import three_candle_crt_setup, crt_range_never_resolves_setup


def test_range_absent_before_resolution_present_at_and_after():
    series = three_candle_crt_setup()

    ranges_before = causal_crt_ranges(series.up_to(2))  # candles 0,1 only
    assert ranges_before == []

    ranges_at = causal_crt_ranges(series.up_to(3))  # candles 0,1,2
    by_start = {r.start_index: r for r in ranges_at}
    assert 0 in by_start
    assert by_start[0].resolved_at_index == 2

    ranges_after = causal_crt_ranges(series)  # same 3-candle series, no more data here
    assert ranges_after == ranges_at


def test_causal_crt_ranges_matches_legacy_full_series_detection():
    series = three_candle_crt_setup()
    assert causal_crt_ranges(series) == detect_crt_ranges(series)


def test_causal_crt_ranges_never_resolves_is_never_emitted():
    series = crt_range_never_resolves_setup()
    config = CRTRangeConfig(max_lookback=2)
    assert causal_crt_ranges(series, config) == [] == detect_crt_ranges(series, config)


def test_causal_crt_ranges_existence_stable_across_growing_prefixes():
    """REQ-CAUSAL-01 (I1): once a range exists at prefix N, it must still
    exist, unchanged, at any larger prefix N' > N."""
    series = three_candle_crt_setup()
    at_n = {r.start_index: r for r in causal_crt_ranges(series.up_to(3))}
    at_bigger = {r.start_index: r for r in causal_crt_ranges(series.up_to(3))}
    assert at_n == at_bigger
