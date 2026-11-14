from datetime import datetime, timedelta

import pytest

from alignment.htf_ltf import AlignedSignal
from core.candle import Candle, OHLCSeries
from core.key_level import KeyLevel
from entries.model1 import Model1Signal
from primitives.crt_range import CRTRange
from research.eurusd_recipe_validation.pipeline import (
    BASELINE,
    VARIANTS,
    _filter_zone_rejection,
    aggregate_stats,
)
from research.eurusd_recipe_validation.trades import (
    RECIPE_SESSION_END_HOUR,
    RECIPE_SESSION_START_HOUR,
    ClosedTrade,
)

_DAY_ZERO = datetime(2024, 1, 1, 12, 0)


def _trade(signal_id, day_offset, r_multiple, outcome=None):
    exit_time = _DAY_ZERO + timedelta(days=day_offset)
    return ClosedTrade(
        signal_id=signal_id, direction="bullish", entry_index=day_offset, exit_index=day_offset,
        entry_time=exit_time, exit_time=exit_time,
        outcome=outcome or ("win" if r_multiple > 0 else "loss"), r_multiple=r_multiple,
    )


def test_the_baseline_variant_trades_exactly_the_live_recipe_session():
    """The baseline row of the comparison IS the live recipe, so its
    session window must be the live scanner's -- which test_trades pins to
    `scanner/rules.py` itself."""
    assert (BASELINE.session_start_hour, BASELINE.session_end_hour) == (
        RECIPE_SESSION_START_HOUR, RECIPE_SESSION_END_HOUR
    )
    assert BASELINE.max_key_level_zone_pips is None
    assert BASELINE.min_risk_reward == 2.0  # the documented library default, REQ-35


def test_the_baseline_is_the_first_variant_so_every_comparison_is_against_it():
    assert VARIANTS[0] is BASELINE


def test_variant_keys_are_unique_so_data_files_cannot_overwrite_each_other():
    keys = [spec.key for spec in VARIANTS]
    assert len(keys) == len(set(keys))


def test_an_empty_population_produces_no_statistics_rather_than_zeros():
    stats = aggregate_stats(())
    assert (stats.trades, stats.closed, stats.total_r) == (0, 0, 0.0)
    assert stats.win_rate is None and stats.average_r is None and stats.calmar_ratio is None


def test_wins_losses_and_expectancy_are_counted_over_closed_trades_only():
    trades = (
        _trade("a", 0, 2.0),
        _trade("b", 1, -1.0),
        ClosedTrade("c", "bullish", 2, None, _DAY_ZERO, None, "open", None),
    )
    stats = aggregate_stats(trades)
    assert (stats.trades, stats.closed, stats.wins, stats.losses) == (3, 2, 1, 1)
    assert stats.win_rate == pytest.approx(0.5)
    assert stats.average_r == pytest.approx(0.5)
    assert stats.total_r == pytest.approx(1.0)


def test_max_drawdown_is_the_worst_peak_to_trough_run_in_r():
    # +5, -3, -1, +2 => peak 5, trough 1, worst give-back 4R.
    trades = (_trade("a", 0, 5.0), _trade("b", 1, -3.0), _trade("c", 2, -1.0), _trade("d", 3, 2.0))
    assert aggregate_stats(trades).max_drawdown_r == pytest.approx(4.0)


def test_the_reconstructed_calmar_is_annualised_r_over_peak_to_trough_r():
    # Exactly one year apart: total 4R, worst give-back 2R => 4/1/2 = 2.0.
    trades = (
        _trade("a", 0, 6.0),
        _trade("b", 100, -2.0),
        _trade("c", 365, 0.0, outcome="loss"),
    )
    stats = aggregate_stats(trades)
    assert stats.total_r == pytest.approx(4.0)
    assert stats.max_drawdown_r == pytest.approx(2.0)
    assert stats.calmar_ratio == pytest.approx(4.0 / (365 / 365.25) / 2.0)


def test_calmar_is_undefined_rather_than_infinite_when_there_was_no_drawdown():
    trades = (_trade("a", 0, 1.0), _trade("b", 365, 1.0))
    assert aggregate_stats(trades).calmar_ratio is None


def test_the_reported_close_window_spans_first_to_last_realised_trade():
    trades = (_trade("a", 3, 1.0), _trade("b", 0, 1.0), _trade("c", 10, 1.0))
    stats = aggregate_stats(trades)
    assert stats.first_close == _DAY_ZERO.date()
    assert stats.last_close == (_DAY_ZERO + timedelta(days=10)).date()


def test_lever_d_require_zone_rejection_is_registered_and_additive_only():
    """Candidate lever from the Key Level reaction redefinition probe
    (`experimental.key_level_reaction_redefinition`): require the purge
    candle to actually leave the credited zone, on top of the recipe's
    existing `reject_close_inside`-vs-CRT-range filter every variant
    already starts from."""
    keys = [spec.key for spec in VARIANTS]
    assert "lever_d_zone_reject" in keys
    assert len(keys) == len(set(keys))


def _htf_candle(i, o, h, l, c):
    return Candle(timestamp=_DAY_ZERO + timedelta(hours=4 * i), open=o, high=h, low=l, close=c)


def _crt_range(high, low, start, end):
    return CRTRange(
        model="2-candle", high=high, low=low, start_index=start, end_index=end,
        resolution="true_break", resolved_at_index=end,
    )


def _aligned_signal(crt_range, level, anchor_index=0):
    ltf_signal = Model1Signal(
        anchor_index=anchor_index, direction="bullish", purge_target=0.0,
        confirmation_type="purge_engulf", entry_type="wick", entry_price=0.0,
        retest_index=None, status="CONFIRMED", confirmation_index=0, origin_index=0,
    )
    return AlignedSignal(
        ltf_signal=ltf_signal, htf_context=crt_range, aligned="aligned",
        key_level=level, key_level_reaction="reject_close_inside",
    )


def test_filter_zone_rejection_drops_a_signal_that_never_left_the_credited_zone():
    """The exact gap the probe measured: close back inside the CRT range
    (today's `reject_close_inside`) while still sitting inside the Key
    Level zone -- not a genuine rejection."""
    crt_range = _crt_range(high=1.10, low=1.00, start=0, end=1)
    zone_dipping_in = KeyLevel(kind="ict_order_block", top=1.14, bottom=1.08, origin_index=0)
    purge = _htf_candle(1, 1.09, 1.13, 1.08, 1.095)  # close inside [1.00,1.10] AND inside [1.08,1.14]
    htf = OHLCSeries(
        candles=(_htf_candle(0, 1.05, 1.06, 1.04, 1.05), purge),
        instrument="EURUSDm", timeframe="H4",
    )
    signal = _aligned_signal(crt_range, zone_dipping_in)

    assert _filter_zone_rejection([signal], htf) == []


def test_filter_zone_rejection_keeps_a_genuine_rejection():
    crt_range = _crt_range(high=1.10, low=1.00, start=0, end=1)
    zone_above = KeyLevel(kind="fvg", top=1.14, bottom=1.12, origin_index=0)
    purge = _htf_candle(1, 1.09, 1.13, 1.08, 1.095)
    htf = OHLCSeries(
        candles=(_htf_candle(0, 1.05, 1.06, 1.04, 1.05), purge),
        instrument="EURUSDm", timeframe="H4",
    )
    signal = _aligned_signal(crt_range, zone_above)

    assert _filter_zone_rejection([signal], htf) == [signal]
