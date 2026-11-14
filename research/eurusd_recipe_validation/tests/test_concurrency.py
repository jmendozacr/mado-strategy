from datetime import datetime

from research.eurusd_recipe_validation.concurrency import simulate_bounded_concurrency
from research.eurusd_recipe_validation.trades import ClosedTrade

_T0 = datetime(2024, 1, 1, 0, 0)


def _trade(signal_id, entry_index, exit_index, outcome="win", r_multiple=1.0):
    return ClosedTrade(
        signal_id=signal_id,
        direction="bullish",
        entry_index=entry_index,
        exit_index=exit_index,
        entry_time=_T0,
        exit_time=None if exit_index is None else _T0,
        outcome=outcome,
        r_multiple=r_multiple,
    )


def _ids(trades):
    return [t.signal_id for t in trades]


def test_empty_population_yields_nothing():
    assert simulate_bounded_concurrency([]) == []


def test_serial_trades_are_all_accepted():
    trades = [_trade("a", 0, 5), _trade("b", 10, 15), _trade("c", 20, 25)]
    assert _ids(simulate_bounded_concurrency(trades)) == ["a", "b", "c"]


def test_third_simultaneous_trade_is_rejected_at_the_two_r_cap():
    trades = [_trade("a", 0, 100), _trade("b", 1, 100), _trade("c", 2, 100)]
    assert _ids(simulate_bounded_concurrency(trades)) == ["a", "b"]


def test_a_rejected_trade_does_not_itself_occupy_a_slot():
    # "c" is rejected while a+b are open; "d" opens only after "a" has freed
    # its slot, so the cap must not have been consumed by the rejection.
    trades = [_trade("a", 0, 10), _trade("b", 1, 100), _trade("c", 2, 100), _trade("d", 20, 30)]
    assert _ids(simulate_bounded_concurrency(trades)) == ["a", "b", "d"]


def test_a_slot_frees_on_the_bar_the_prior_trade_exits():
    # RECONSTRUCTED tie convention: exit_index == entry_index frees the slot.
    trades = [_trade("a", 0, 5), _trade("b", 1, 100), _trade("c", 5, 50)]
    assert _ids(simulate_bounded_concurrency(trades)) == ["a", "b", "c"]


def test_a_slot_stays_occupied_one_bar_before_the_exit():
    trades = [_trade("a", 0, 5), _trade("b", 1, 100), _trade("c", 4, 50)]
    assert _ids(simulate_bounded_concurrency(trades)) == ["a", "b"]


def test_a_never_closed_trade_occupies_its_slot_permanently():
    # Both open trades hold the cap for the rest of the series, so a
    # candidate hundreds of bars later still finds no room.
    trades = [
        _trade("a", 0, None, outcome="open", r_multiple=None),
        _trade("b", 1, None, outcome="open", r_multiple=None),
        _trade("c", 500, 501),
    ]
    assert _ids(simulate_bounded_concurrency(trades)) == ["a", "b"]


def test_one_never_closed_trade_still_leaves_the_other_slot_usable():
    trades = [_trade("a", 0, None, outcome="open", r_multiple=None), _trade("b", 1, 2), _trade("c", 500, 501)]
    assert _ids(simulate_bounded_concurrency(trades)) == ["a", "b", "c"]


def test_cap_of_one_r_admits_only_strictly_serial_trades():
    trades = [_trade("a", 0, 10), _trade("b", 5, 15), _trade("c", 10, 20)]
    assert _ids(simulate_bounded_concurrency(trades, max_open_risk_r=1.0)) == ["a", "c"]


def test_unsorted_input_is_ordered_deterministically_before_gating():
    unsorted_trades = [_trade("c", 2, 100), _trade("a", 0, 100), _trade("b", 1, 100)]
    assert _ids(simulate_bounded_concurrency(unsorted_trades)) == ["a", "b"]


def test_entry_index_ties_break_on_signal_id():
    trades = [_trade("z", 0, 100), _trade("a", 0, 100), _trade("m", 0, 100)]
    assert _ids(simulate_bounded_concurrency(trades)) == ["a", "m"]


def test_a_fractional_risk_unit_admits_more_concurrent_trades():
    trades = [_trade("a", 0, 100), _trade("b", 1, 100), _trade("c", 2, 100), _trade("d", 3, 100)]
    accepted = simulate_bounded_concurrency(trades, max_open_risk_r=2.0, risk_per_trade_r=0.5)
    assert _ids(accepted) == ["a", "b", "c", "d"]
