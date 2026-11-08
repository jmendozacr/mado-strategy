from composite.mss import MSSEvent
from primitives.ict_order_block import ICTOrderBlock
from primitives.swing import SwingPoint
from experimental.order_block_structural_break_check import (
    ob_followed_by_real_break,
    summarize,
)


def _ob(direction, confirmation_index=5, invalidation_index=None, candle_index=4, top=1.1, bottom=1.09):
    return ICTOrderBlock(
        candle_index=candle_index, confirmation_index=confirmation_index, direction=direction,
        top=top, bottom=bottom, status="invalidated" if invalidation_index is not None else "open",
        invalidation_index=invalidation_index,
    )


def _mss(index, direction):
    return MSSEvent(index=index, direction=direction, broken_swing=SwingPoint(index=0, kind="high", price=1.1))


class TestObFollowedByRealBreak:
    def test_true_when_same_direction_mss_occurs_after_confirmation_and_before_invalidation(self) -> None:
        ob = _ob("bullish", confirmation_index=5, invalidation_index=20)
        events = [_mss(10, "bullish")]
        assert ob_followed_by_real_break(ob, events) is True

    def test_false_when_no_mss_event_in_range(self) -> None:
        ob = _ob("bullish", confirmation_index=5, invalidation_index=20)
        assert ob_followed_by_real_break(ob, []) is False

    def test_false_when_mss_direction_does_not_match(self) -> None:
        ob = _ob("bullish", confirmation_index=5, invalidation_index=20)
        events = [_mss(10, "bearish")]
        assert ob_followed_by_real_break(ob, events) is False

    def test_false_when_mss_occurs_before_confirmation_index(self) -> None:
        """An MSS that happened BEFORE this OB even formed cannot be the
        break this OB precedes -- it would be crediting a cause after its
        effect."""
        ob = _ob("bullish", confirmation_index=5, invalidation_index=20)
        events = [_mss(3, "bullish")]
        assert ob_followed_by_real_break(ob, events) is False

    def test_false_when_mss_occurs_strictly_after_invalidation(self) -> None:
        """Once the zone is invalidated it is no longer a live Key Level
        (mirrors KeyLevel.expiry_index semantics), so a later break is not
        credited to it."""
        ob = _ob("bullish", confirmation_index=5, invalidation_index=10)
        events = [_mss(11, "bullish")]
        assert ob_followed_by_real_break(ob, events) is False

    def test_true_at_the_invalidation_index_itself_right_closed(self) -> None:
        ob = _ob("bullish", confirmation_index=5, invalidation_index=10)
        events = [_mss(10, "bullish")]
        assert ob_followed_by_real_break(ob, events) is True

    def test_open_ob_has_no_upper_bound(self) -> None:
        ob = _ob("bullish", confirmation_index=5, invalidation_index=None)
        events = [_mss(10_000, "bullish")]
        assert ob_followed_by_real_break(ob, events) is True


class TestSummarize:
    def test_counts_and_fraction(self) -> None:
        obs = [
            _ob("bullish", confirmation_index=5, invalidation_index=20),  # followed
            _ob("bearish", confirmation_index=5, invalidation_index=20),  # not followed
        ]
        events = [_mss(10, "bullish")]

        result = summarize(obs, events)

        assert result["total_obs"] == 2
        assert result["obs_followed_by_real_break"] == 1
        assert result["fraction"] == 0.5

    def test_empty_population_reports_zero_not_an_error(self) -> None:
        result = summarize([], [])
        assert result == {"total_obs": 0, "obs_followed_by_real_break": 0, "fraction": 0.0}
