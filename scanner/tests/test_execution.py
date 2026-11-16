"""TDD for execution.py -- written FIRST. Both functions are pure/MT5-
independent (symbol trade specs and account balance are plain numbers
passed in, never fetched here) so they're fully testable without a live
terminal -- odd/tasks/scanner-auto-execution.md S3/S4.
"""
from execution import calculate_lot_size, partial_close_volume, partial_price_reached, pending_order_type


def test_basic_lot_size_matches_hand_computed_value():
    # $10,000 balance, 1% risk = $100. Stop distance 0.0020 (20 pips on a
    # 5-decimal quote). EURUSD-like specs: tick_size=0.00001, tick_value=$1
    # per tick per standard lot (i.e. $10/pip/lot, the same economics this
    # session already verified by hand for EURUSD/AUDUSD).
    lot = calculate_lot_size(
        balance=10000.0, risk_pct=1.0, entry_price=1.1000, stop_loss=1.0980,
        tick_value=1.0, tick_size=0.00001, volume_min=0.01, volume_max=100.0, volume_step=0.01,
    )
    # risk_amount=$100, stop_distance=0.0020=200 ticks, risk_per_lot=200*$1=$200/lot
    # raw_lots = 100/200 = 0.5 -- already on the 0.01 step, no rounding needed.
    assert lot == 0.5


def test_rounds_down_to_volume_step_never_up():
    # Craft a stop distance that produces a raw lot size strictly between
    # two 0.01 steps -- must floor, never round to the nearer step (that
    # could silently risk MORE than the target %).
    lot = calculate_lot_size(
        balance=10000.0, risk_pct=1.0, entry_price=1.1000, stop_loss=1.0985,  # 150 ticks
        tick_value=1.0, tick_size=0.00001, volume_min=0.01, volume_max=100.0, volume_step=0.01,
    )
    # risk_per_lot = 150, raw_lots = 100/150 = 0.6666... -> floor to 0.66, not 0.67.
    assert lot == 0.66


def test_below_volume_min_skips_the_trade_instead_of_forcing_minimum():
    """Forcing volume_min when the real target is smaller would silently
    risk more than intended -- S3 says skip, never force."""
    lot = calculate_lot_size(
        balance=100.0, risk_pct=1.0, entry_price=1.1000, stop_loss=1.0980,
        tick_value=1.0, tick_size=0.00001, volume_min=0.01, volume_max=100.0, volume_step=0.01,
    )
    # risk_amount=$1, risk_per_lot=$200, raw_lots=0.005 -- below volume_min.
    assert lot is None


def test_clamped_to_volume_max():
    lot = calculate_lot_size(
        balance=100_000_000.0, risk_pct=50.0, entry_price=1.1000, stop_loss=1.0999,  # 10 ticks
        tick_value=1.0, tick_size=0.00001, volume_min=0.01, volume_max=100.0, volume_step=0.01,
    )
    assert lot == 100.0


def test_zero_stop_distance_returns_none_rather_than_dividing_by_zero():
    lot = calculate_lot_size(
        balance=10000.0, risk_pct=1.0, entry_price=1.1000, stop_loss=1.1000,
        tick_value=1.0, tick_size=0.00001, volume_min=0.01, volume_max=100.0, volume_step=0.01,
    )
    assert lot is None


def test_bullish_entry_below_current_price_is_buy_limit():
    assert pending_order_type("bullish", entry_price=1.0980, current_price=1.1000) == "BUY_LIMIT"


def test_bullish_entry_above_current_price_is_buy_stop():
    assert pending_order_type("bullish", entry_price=1.1020, current_price=1.1000) == "BUY_STOP"


def test_bearish_entry_above_current_price_is_sell_limit():
    assert pending_order_type("bearish", entry_price=1.1020, current_price=1.1000) == "SELL_LIMIT"


def test_bearish_entry_below_current_price_is_sell_stop():
    assert pending_order_type("bearish", entry_price=1.0980, current_price=1.1000) == "SELL_STOP"


def test_partial_close_volume_splits_evenly_at_50_percent():
    assert partial_close_volume(
        volume=0.5, partial_fraction=0.5, volume_step=0.01, volume_min=0.01,
    ) == 0.25


def test_partial_close_volume_floors_to_step_never_rounds_up():
    """Same floor-never-round-up convention as calculate_lot_size -- an
    uneven split must never close MORE than the configured fraction."""
    assert partial_close_volume(
        volume=0.07, partial_fraction=0.5, volume_step=0.01, volume_min=0.01,
    ) == 0.03  # raw partial 0.035 -> floors to 0.03, remainder 0.04 stays >= volume_min


def test_partial_close_volume_none_when_the_remainder_would_be_sub_minimum():
    """A 0.01-lot position has no room to split -- closing ANY part of it
    would leave a remainder below volume_min (or, floored, a zero-size
    partial) -- skip the partial entirely rather than close the whole
    position or leave an invalid remainder."""
    assert partial_close_volume(
        volume=0.01, partial_fraction=0.5, volume_step=0.01, volume_min=0.01,
    ) is None


def test_partial_close_volume_none_when_partial_itself_rounds_to_zero():
    assert partial_close_volume(
        volume=0.015, partial_fraction=0.3, volume_step=0.01, volume_min=0.01,
    ) is None  # raw partial 0.0045 -> floors to 0.00


def test_partial_price_reached_bullish_at_or_above_the_level():
    assert partial_price_reached("bullish", partial_price=1.1050, current_price=1.1050) is True
    assert partial_price_reached("bullish", partial_price=1.1050, current_price=1.1060) is True
    assert partial_price_reached("bullish", partial_price=1.1050, current_price=1.1040) is False


def test_partial_price_reached_bearish_at_or_below_the_level():
    assert partial_price_reached("bearish", partial_price=1.0950, current_price=1.0950) is True
    assert partial_price_reached("bearish", partial_price=1.0950, current_price=1.0940) is True
    assert partial_price_reached("bearish", partial_price=1.0950, current_price=1.0960) is False
