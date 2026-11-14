from datetime import datetime

from research.eurusd_recipe_validation.daily_risk import apply_daily_loss_stop
from research.eurusd_recipe_validation.trades import ClosedTrade


def _trade(signal_id, entry_hour, exit_hour, outcome, day=2):
    """Hours are NY-local-safe: the series uses UTC-naive bar stamps, and
    07:00-16:00 UTC all fall inside the same NY calendar date."""
    return ClosedTrade(
        signal_id=signal_id,
        direction="bullish",
        # Bar indices must stay monotonic ACROSS days, or the rule's own
        # (entry_index, signal_id) ordering would interleave the days.
        entry_index=day * 100 + entry_hour,
        exit_index=None if exit_hour is None else day * 100 + exit_hour,
        entry_time=datetime(2024, 1, day, entry_hour),
        exit_time=None if exit_hour is None else datetime(2024, 1, day, exit_hour),
        outcome=outcome,
        r_multiple=None if outcome == "open" else (1.0 if outcome == "win" else -1.0),
    )


def _ids(trades):
    return [t.signal_id for t in trades]


def test_empty_population_yields_nothing():
    assert apply_daily_loss_stop([]) == []


def test_a_single_loss_does_not_stop_the_day():
    trades = [_trade("a", 7, 8, "loss"), _trade("b", 9, 10, "win")]
    assert _ids(apply_daily_loss_stop(trades)) == ["a", "b"]


def test_trading_stops_after_the_second_closed_loss_of_the_day():
    trades = [
        _trade("a", 7, 8, "loss"),
        _trade("b", 9, 10, "loss"),
        _trade("c", 11, 12, "win"),
        _trade("d", 13, 14, "win"),
    ]
    assert _ids(apply_daily_loss_stop(trades)) == ["a", "b"]


def test_a_loss_still_open_at_the_new_entry_does_not_count_yet():
    # "b" is a loss but only closes at 14:00, after "c" enters at 11:00 --
    # a causal rule can only react to losses already realised.
    trades = [_trade("a", 7, 8, "loss"), _trade("b", 9, 14, "loss"), _trade("c", 11, 12, "win")]
    assert _ids(apply_daily_loss_stop(trades)) == ["a", "b", "c"]


def test_a_loss_closing_exactly_on_the_new_entry_bar_counts():
    trades = [_trade("a", 7, 8, "loss"), _trade("b", 9, 11, "loss"), _trade("c", 11, 12, "win")]
    assert _ids(apply_daily_loss_stop(trades)) == ["a", "b"]


def test_wins_never_contribute_to_the_daily_loss_count():
    trades = [
        _trade("a", 7, 8, "win"),
        _trade("b", 9, 10, "win"),
        _trade("c", 11, 12, "win"),
        _trade("d", 13, 14, "loss"),
    ]
    assert _ids(apply_daily_loss_stop(trades)) == ["a", "b", "c", "d"]


def test_an_unclosed_trade_never_contributes_to_the_daily_loss_count():
    trades = [
        _trade("a", 7, None, "open"),
        _trade("b", 8, None, "open"),
        _trade("c", 9, 10, "win"),
    ]
    assert _ids(apply_daily_loss_stop(trades)) == ["a", "b", "c"]


def test_the_count_resets_on_the_next_session_day():
    trades = [
        _trade("a", 7, 8, "loss", day=2),
        _trade("b", 9, 10, "loss", day=2),
        _trade("c", 11, 12, "win", day=2),
        _trade("d", 7, 8, "win", day=3),
    ]
    assert _ids(apply_daily_loss_stop(trades)) == ["a", "b", "d"]


def test_losses_from_trades_the_rule_already_rejected_are_not_counted():
    # "c" is rejected; its own (loss) outcome must not deepen the count that
    # already blocks the day, because the rule means it was never taken.
    trades = [
        _trade("a", 7, 8, "loss", day=2),
        _trade("b", 9, 10, "loss", day=2),
        _trade("c", 11, 12, "loss", day=2),
        _trade("d", 7, 8, "win", day=3),
    ]
    accepted = apply_daily_loss_stop(trades)
    assert _ids(accepted) == ["a", "b", "d"]


def test_a_higher_limit_admits_more_losses_before_stopping():
    trades = [
        _trade("a", 7, 8, "loss"),
        _trade("b", 9, 10, "loss"),
        _trade("c", 11, 12, "loss"),
        _trade("d", 13, 14, "win"),
    ]
    assert _ids(apply_daily_loss_stop(trades, max_losses_per_day=3)) == ["a", "b", "c"]


def test_unsorted_input_is_ordered_deterministically_before_gating():
    unsorted_trades = [
        _trade("c", 11, 12, "win"),
        _trade("a", 7, 8, "loss"),
        _trade("b", 9, 10, "loss"),
    ]
    assert _ids(apply_daily_loss_stop(unsorted_trades)) == ["a", "b"]
