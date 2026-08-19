from fixtures.synthetic import (
    crt_range_false_break_setup,
    crt_range_never_resolves_setup,
    crt_range_resolves_on_last_candle_setup,
    multi_inside_crt_setup,
    multi_outside_crt_setup,
    three_candle_crt_setup,
    two_candle_crt_setup,
)

from core.config import CRTRangeConfig
from primitives.crt_range import detect_crt_ranges


def test_detects_3_candle_crt_with_true_break_resolution():
    """REQ-11.1, grounded charter-1 [00:16:11]: Vela2 purges the High and
    closes back inside; Vela3 fully expands beyond the Low. Correct
    High/Low + true_break resolution, classified as 3-candle.
    """
    series = three_candle_crt_setup()

    ranges = detect_crt_ranges(series)

    crt_range = next(r for r in ranges if r.start_index == 0)
    assert crt_range.high == series.candles[0].high
    assert crt_range.low == series.candles[0].low
    assert crt_range.model == "3-candle"
    assert crt_range.resolution == "true_break"
    assert crt_range.resolved_at_index == 2


def test_detects_2_candle_crt_not_3():
    """REQ-12.1, grounded charter-1 [00:16:53]: Vela2 both purges the High
    and, within the same candle, closes beyond the Low -> flagged 2-candle,
    not 3.
    """
    series = two_candle_crt_setup()

    ranges = detect_crt_ranges(series)

    crt_range = next(r for r in ranges if r.start_index == 0)
    assert crt_range.model == "2-candle"
    assert crt_range.resolution == "true_break"
    assert crt_range.resolved_at_index == 1


def test_detects_multi_inside_crt_as_one_detection():
    """REQ-13.1, grounded charter-1 [00:18:12]: candles 2-3 stay trapped
    inside the range; candle 4 finally purges the High; candle 5 expands
    beyond the Low -> one Inside-Bar (multi-inside) detection for the
    range-establishing candle, not N false ranges.
    """
    series = multi_inside_crt_setup()

    ranges = detect_crt_ranges(series)

    matches = [r for r in ranges if r.start_index == 0]
    assert len(matches) == 1
    crt_range = matches[0]
    assert crt_range.model == "multi-inside"
    assert crt_range.resolution == "true_break"
    assert crt_range.resolved_at_index == 4


def test_detects_multi_outside_crt_when_expansion_takes_multiple_candles():
    """Charter-1 [00:11:06] Outside Bar CRT: Vela2 purges the High (like
    the 3-candle model) but expansion does not complete at Vela3 — it
    takes an additional candle to finally close beyond the Low ->
    multi-outside, not 3-candle.
    """
    series = multi_outside_crt_setup()

    ranges = detect_crt_ranges(series)

    crt_range = next(r for r in ranges if r.start_index == 0)
    assert crt_range.model == "multi-outside"
    assert crt_range.resolution == "true_break"
    assert crt_range.resolved_at_index == 3


def test_detects_false_break_resolution():
    """False break / Turtle Soup: Vela2 pokes the Low, closes back inside;
    a subsequent candle's close reverses back through the range reaching
    at least the opposite side's midpoint without fully breaking the High.
    """
    series = crt_range_false_break_setup()

    ranges = detect_crt_ranges(series)

    crt_range = next(r for r in ranges if r.start_index == 0)
    assert crt_range.resolution == "false_break"
    assert crt_range.resolved_at_index == 2


def test_never_resolves_within_lookback_is_not_emitted():
    """REQ-14.1: price stays inside the range for the whole lookback
    window -> no range flagged at all for that start index.
    """
    series = crt_range_never_resolves_setup()

    ranges = detect_crt_ranges(series, config=CRTRangeConfig(max_lookback=2))

    assert ranges == []


def test_resolves_exactly_on_last_lookback_candle():
    """Boundary check: a candle at exactly `i + max_lookback` must still
    resolve the range (inclusive boundary), not be excluded by an
    off-by-one error.
    """
    series = crt_range_resolves_on_last_candle_setup()

    ranges = detect_crt_ranges(series, config=CRTRangeConfig(max_lookback=2))

    crt_range = next(r for r in ranges if r.start_index == 0)
    assert crt_range.resolution == "true_break"
    assert crt_range.resolved_at_index == 2


def test_max_lookback_is_read_from_config_not_hardcoded():
    """REQ-25: max_lookback is sourced from CRTRangeConfig, not hardcoded —
    a smaller configured lookback excludes a range the default (20) would
    have allowed to resolve.
    """
    series = crt_range_resolves_on_last_candle_setup()

    ranges = detect_crt_ranges(series, config=CRTRangeConfig(max_lookback=1))

    assert not any(r.start_index == 0 for r in ranges)
