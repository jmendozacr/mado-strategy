from composite.mss import MSSEvent
from primitives.swing import SwingPoint
from experimental.swing_structural_break_check import summarize, swing_confirmed_by_mss


def _swing(index=5, kind="high", price=1.10):
    return SwingPoint(index=index, kind=kind, price=price)


def _mss(broken_swing, index=10, direction="bearish"):
    return MSSEvent(index=index, direction=direction, broken_swing=broken_swing)


class TestSwingConfirmedByMss:
    def test_true_when_this_exact_swing_was_broken(self) -> None:
        swing = _swing()
        assert swing_confirmed_by_mss(swing, [_mss(swing)]) is True

    def test_false_when_never_broken(self) -> None:
        assert swing_confirmed_by_mss(_swing(), []) is False

    def test_false_when_a_different_swing_was_broken(self) -> None:
        swing = _swing(index=5, kind="high", price=1.10)
        other = _swing(index=7, kind="low", price=1.05)
        assert swing_confirmed_by_mss(swing, [_mss(other)]) is False

    def test_false_when_same_index_and_price_but_different_kind(self) -> None:
        """Structural dataclass equality is exact across all three fields
        -- a high and a low sharing index/price (an outside candle) are
        NOT the same swing."""
        swing = _swing(index=5, kind="high", price=1.10)
        other = _swing(index=5, kind="low", price=1.10)
        assert swing_confirmed_by_mss(swing, [_mss(other)]) is False

    def test_window_none_is_unbounded_default(self) -> None:
        """Matches the first (uninformative) pass: a break arbitrarily far
        in the future still counts when no window is given."""
        swing = _swing(index=5)
        far_break = _mss(swing, index=100_000)
        assert swing_confirmed_by_mss(swing, [far_break]) is True

    def test_window_excludes_a_break_beyond_it(self) -> None:
        swing = _swing(index=5)
        late_break = _mss(swing, index=5 + 21)  # 21 candles later
        assert swing_confirmed_by_mss(swing, [late_break], window=20) is False

    def test_window_includes_a_break_at_the_boundary_inclusive(self) -> None:
        swing = _swing(index=5)
        boundary_break = _mss(swing, index=5 + 20)  # exactly 20 candles later
        assert swing_confirmed_by_mss(swing, [boundary_break], window=20) is True

    def test_window_includes_a_break_well_within_it(self) -> None:
        swing = _swing(index=5)
        near_break = _mss(swing, index=8)
        assert swing_confirmed_by_mss(swing, [near_break], window=20) is True


class TestSummarize:
    def test_counts_and_fraction(self) -> None:
        confirmed = _swing(index=1)
        unconfirmed = _swing(index=2)
        result = summarize([confirmed, unconfirmed], [_mss(confirmed)])
        assert result == {"total_swings": 2, "swings_confirmed_by_mss": 1, "fraction": 0.5}

    def test_empty_population_reports_zero(self) -> None:
        assert summarize([], []) == {"total_swings": 0, "swings_confirmed_by_mss": 0, "fraction": 0.0}

    def test_window_passes_through(self) -> None:
        near = _swing(index=1)
        far = _swing(index=2)
        events = [_mss(near, index=5), _mss(far, index=100)]
        result = summarize([near, far], events, window=20)
        assert result == {"total_swings": 2, "swings_confirmed_by_mss": 1, "fraction": 0.5}
