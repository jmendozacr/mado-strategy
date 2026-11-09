from composite.mss import MSSEvent
from primitives.fvg import FVG
from primitives.swing import SwingPoint
from experimental.fvg_structural_break_check import fvg_followed_by_real_break, summarize


def _fvg(direction, end_index=5, fill_index=None, start_index=4, top=1.1, bottom=1.09):
    return FVG(
        start_index=start_index, end_index=end_index, top=top, bottom=bottom,
        direction=direction, fill_status="filled" if fill_index is not None else "open",
        fill_index=fill_index,
    )


def _mss(index, direction):
    return MSSEvent(index=index, direction=direction, broken_swing=SwingPoint(index=0, kind="high", price=1.1))


class TestFvgFollowedByRealBreak:
    def test_true_when_same_direction_mss_occurs_after_formation_and_before_fill(self) -> None:
        fvg = _fvg("bullish", end_index=5, fill_index=20)
        assert fvg_followed_by_real_break(fvg, [_mss(10, "bullish")]) is True

    def test_false_when_no_mss_event(self) -> None:
        fvg = _fvg("bullish", end_index=5, fill_index=20)
        assert fvg_followed_by_real_break(fvg, []) is False

    def test_false_when_direction_does_not_match(self) -> None:
        fvg = _fvg("bullish", end_index=5, fill_index=20)
        assert fvg_followed_by_real_break(fvg, [_mss(10, "bearish")]) is False

    def test_false_when_mss_occurs_before_formation(self) -> None:
        fvg = _fvg("bullish", end_index=5, fill_index=20)
        assert fvg_followed_by_real_break(fvg, [_mss(3, "bullish")]) is False

    def test_false_when_mss_occurs_strictly_after_fill(self) -> None:
        fvg = _fvg("bullish", end_index=5, fill_index=10)
        assert fvg_followed_by_real_break(fvg, [_mss(11, "bullish")]) is False

    def test_true_at_the_fill_index_itself_right_closed(self) -> None:
        fvg = _fvg("bullish", end_index=5, fill_index=10)
        assert fvg_followed_by_real_break(fvg, [_mss(10, "bullish")]) is True

    def test_open_fvg_has_no_upper_bound(self) -> None:
        fvg = _fvg("bullish", end_index=5, fill_index=None)
        assert fvg_followed_by_real_break(fvg, [_mss(10_000, "bullish")]) is True


class TestSummarize:
    def test_counts_and_fraction(self) -> None:
        fvgs = [
            _fvg("bullish", end_index=5, fill_index=20),  # followed
            _fvg("bearish", end_index=5, fill_index=20),  # not followed
        ]
        result = summarize(fvgs, [_mss(10, "bullish")])
        assert result["total_fvgs"] == 2
        assert result["fvgs_followed_by_real_break"] == 1
        assert result["fraction"] == 0.5

    def test_empty_population_reports_zero(self) -> None:
        assert summarize([], []) == {"total_fvgs": 0, "fvgs_followed_by_real_break": 0, "fraction": 0.0}
