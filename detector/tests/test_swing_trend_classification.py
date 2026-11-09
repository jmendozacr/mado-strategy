from primitives.swing import ClassifiedSwing, SwingPoint, classify_trend


def _high(index, price):
    return SwingPoint(index=index, price=price, kind="high")


def _low(index, price):
    return SwingPoint(index=index, price=price, kind="low")


class TestClassifyTrend:
    def test_first_high_swing_is_unclassified(self) -> None:
        result = classify_trend([_high(1, 1.10)])
        assert result == [ClassifiedSwing(swing=_high(1, 1.10), label=None)]

    def test_first_low_swing_is_unclassified(self) -> None:
        result = classify_trend([_low(1, 1.00)])
        assert result == [ClassifiedSwing(swing=_low(1, 1.00), label=None)]

    def test_second_high_above_first_is_HH(self) -> None:
        swings = [_high(1, 1.10), _high(5, 1.15)]
        result = classify_trend(swings)
        assert result[1].label == "HH"

    def test_second_high_below_first_is_LH(self) -> None:
        swings = [_high(1, 1.10), _high(5, 1.05)]
        result = classify_trend(swings)
        assert result[1].label == "LH"

    def test_equal_high_price_is_LH_not_a_higher_high(self) -> None:
        swings = [_high(1, 1.10), _high(5, 1.10)]
        result = classify_trend(swings)
        assert result[1].label == "LH"

    def test_second_low_above_first_is_HL(self) -> None:
        swings = [_low(1, 1.00), _low(5, 1.05)]
        result = classify_trend(swings)
        assert result[1].label == "HL"

    def test_second_low_below_first_is_LL(self) -> None:
        swings = [_low(1, 1.00), _low(5, 0.95)]
        result = classify_trend(swings)
        assert result[1].label == "LL"

    def test_equal_low_price_is_HL_not_a_lower_low(self) -> None:
        swings = [_low(1, 1.00), _low(5, 1.00)]
        result = classify_trend(swings)
        assert result[1].label == "HL"

    def test_highs_and_lows_classify_independently_of_each_other(self) -> None:
        """A low swing never compares against a prior HIGH, and vice versa
        -- each kind tracks only its own most recent predecessor."""
        swings = [_high(1, 1.10), _low(3, 1.00), _high(5, 1.20), _low(7, 0.90)]
        result = classify_trend(swings)
        labels = {(c.swing.index, c.swing.kind): c.label for c in result}
        assert labels[(1, "high")] is None
        assert labels[(3, "low")] is None
        assert labels[(5, "high")] == "HH"  # vs index 1's 1.10
        assert labels[(7, "low")] == "LL"  # vs index 3's 1.00

    def test_order_preserved_and_length_matches_input(self) -> None:
        swings = [_high(1, 1.10), _low(3, 1.00), _high(5, 1.20)]
        result = classify_trend(swings)
        assert [c.swing for c in result] == swings

    def test_empty_input_returns_empty(self) -> None:
        assert classify_trend([]) == []
