import pytest

from composite.ote import DISCOUNT_PREMIUM_SPLIT, impulse_leg, in_ote_zone, ote_zone
from primitives.swing import SwingPoint


def _high(index, price):
    return SwingPoint(index=index, price=price, kind="high")


def _low(index, price):
    return SwingPoint(index=index, price=price, kind="low")


class TestImpulseLeg:
    def test_bullish_returns_low_then_high_charter_order(self) -> None:
        swings = [_low(2, 1.10), _high(5, 1.20)]
        result = impulse_leg(swings, before_index=10, direction="bullish")
        assert result == (1.10, 1.20)

    def test_bearish_returns_high_then_low_charter_order(self) -> None:
        swings = [_high(2, 1.20), _low(5, 1.10)]
        result = impulse_leg(swings, before_index=10, direction="bearish")
        assert result == (1.20, 1.10)

    def test_uses_the_most_recent_swing_of_each_kind(self) -> None:
        swings = [_low(1, 1.05), _high(3, 1.15), _low(6, 1.10), _high(8, 1.25)]
        result = impulse_leg(swings, before_index=10, direction="bullish")
        assert result == (1.10, 1.25)

    def test_none_when_a_swing_kind_is_missing(self) -> None:
        swings = [_low(2, 1.10)]
        assert impulse_leg(swings, before_index=10, direction="bullish") is None

    def test_none_when_no_swings_precede_the_cutoff(self) -> None:
        swings = [_low(20, 1.10), _high(25, 1.20)]
        assert impulse_leg(swings, before_index=10, direction="bullish") is None

    def test_respects_the_cutoff_strictly_no_lookahead(self) -> None:
        """A swing AT or after before_index must not be used -- it was not
        yet knowable at that point in the series."""
        swings = [_low(5, 1.10), _high(10, 1.20)]
        result = impulse_leg(swings, before_index=10, direction="bullish")
        assert result is None  # the high at index 10 is not < before_index


class TestOteZone:
    def test_bullish_zone_is_the_retracement_band_below_the_high(self) -> None:
        # low=1.00, high=1.10, span=0.10. 60% retracement from high = 1.04,
        # 75% retracement from high = 0.925... wait use round numbers:
        zone = ote_zone(1.00, 1.10, band=(0.60, 0.75))
        # 60% level = 1.10 - 0.10*0.60 = 1.04; 75% level = 1.10 - 0.10*0.75 = 1.025
        assert zone == (1.025, 1.04)

    def test_bearish_zone_mirrors_correctly(self) -> None:
        # impulse_start=1.10 (high), impulse_end=1.00 (low), span=-0.10
        zone = ote_zone(1.10, 1.00, band=(0.60, 0.75))
        # 60% level = 1.00 - (-0.10)*0.60 = 1.06; 75% level = 1.00 - (-0.10)*0.75 = 1.075
        assert zone == pytest.approx((1.06, 1.075))


class TestDiscountPremiumSplit:
    def test_bullish_discount_is_the_lower_half_toward_the_origin_low(self) -> None:
        zone = ote_zone(1.00, 1.10, band=DISCOUNT_PREMIUM_SPLIT)
        assert zone == pytest.approx((1.00, 1.05))

    def test_bearish_premium_is_the_upper_half_toward_the_origin_high(self) -> None:
        zone = ote_zone(1.10, 1.00, band=DISCOUNT_PREMIUM_SPLIT)
        assert zone == pytest.approx((1.05, 1.10))


class TestInOteZone:
    def test_price_inside_the_band_is_true(self) -> None:
        assert in_ote_zone(1.03, zone=(1.025, 1.04)) is True

    def test_price_outside_the_band_is_false(self) -> None:
        assert in_ote_zone(1.05, zone=(1.025, 1.04)) is False

    def test_inclusive_edges(self) -> None:
        assert in_ote_zone(1.025, zone=(1.025, 1.04)) is True
        assert in_ote_zone(1.04, zone=(1.025, 1.04)) is True

    def test_overlaps_a_key_level_zone_not_just_a_point(self) -> None:
        """A credited KeyLevel is itself a [bottom, top] zone, not a single
        price -- overlap (not containment) is the right test, consistent
        with how confluence crediting itself works."""
        from composite.ote import ote_overlaps_zone
        assert ote_overlaps_zone(level_bottom=1.03, level_top=1.05, ote=(1.025, 1.04)) is True
        assert ote_overlaps_zone(level_bottom=1.05, level_top=1.06, ote=(1.025, 1.04)) is False
