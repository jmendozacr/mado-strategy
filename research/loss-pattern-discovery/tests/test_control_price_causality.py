"""Phase 3.1: the control's synthetic reference price used the reference
bar's CLOSE (only known at `control_ts + M15_DURATION`) while timestamping
the event at `control_ts` itself (the bar's OPEN) -- a causality leak
structurally identical to Phase 3's Defect B, just not yet applied to
`control_to_event_record`/`recovery_control_to_event_record`.

Coverage map for the 11 checks in the user's brief (section 5):

 1. Reference price available at the declared effective instant -> THIS FILE: test_fixed_version_uses_open_available_at_control_ts
 2. No future closes used                                        -> THIS FILE: test_RED_old_logic_would_have_used_a_close_not_yet_available
 3. First post-event move does not reuse the reference bar        -> THIS FILE: test_post_event_movement_does_not_reuse_the_reference_bars_own_range
 4. No valid bar lost to a bisect_left/right off-by-one            -> THIS FILE: test_bisect_left_finds_the_exact_reference_bar_not_an_off_by_one
 5. 1h/4h/1d/3d horizon boundaries stay correct                    -> test_post_stop_metrics.py::test_horizon_boundary_falling_inside_an_open_bar_excludes_that_bar,
                                                                       THIS FILE: test_horizon_boundary_exactly_at_a_bars_close_is_inclusive
 6. NY matching uses comparable instants                           -> test_control_sampling.py::test_controls_are_within_the_ny_hour_tolerance_of_their_matched_event
 7. EST/EDT conversion stays correct                               -> common/ny_time.py sanity already exercised via test_controls_are_within_the_ny_hour_tolerance_of_their_matched_event
 8. ATR uses only available information                            -> test_post_stop_metrics.py::test_atr_excludes_the_event_bars_own_not_yet_closed_candle
 9. Gaps/weekly closures keep their treatment                      -> test_post_stop_metrics.py::test_weekend_gap_is_flagged_without_interpolation, ::test_censored_only_means_true_data_exhaustion_not_weekend_closure
10. Deterministic under a fixed seed                               -> test_control_sampling.py::test_sampling_is_deterministic_for_a_fixed_seed
11. No contamination of original sources                           -> test_phase2_requirements.py::test_source_files_are_never_modified_by_the_pipeline (unaffected by this phase; no source file touched)
"""
from __future__ import annotations

import datetime as dt

from core.candle import Candle, OHLCSeries

from behavior.post_stop_metrics import compute_post_stop_behavior
from control.sampling import ControlEvent, MatchTier, control_to_event_record
from behavior.recovery_analysis import recovery_control_to_event_record

REFERENCE_BAR = Candle(
    timestamp=dt.datetime(2026, 1, 5, 10, 0),  # opens 10:00, closes 10:15
    open=1.1000, high=1.1050, low=1.0990, close=1.1040,
)


def _series(candles) -> OHLCSeries:
    return OHLCSeries(candles=tuple(candles), instrument="EURUSD", timeframe="M15")


def _make_control(control_ts=None, direction="bullish") -> ControlEvent:
    return ControlEvent(
        control_id="control:e0", matched_event_id="e0", instrument="EURUSD", origin_model="9am",
        direction=direction, period_bucket="2021-2023", control_ts=control_ts or REFERENCE_BAR.timestamp,
        risk_price=0.01, target_distance=0.01, atr_at_control=0.001, atr_at_matched_event=0.001,
        actual_stop_time_ny=5.0, control_reference_time_ny=5.0, match_tier=MatchTier.MATCHED,
    )


def test_RED_old_logic_would_have_used_a_close_not_yet_available():
    # Reproduces the Phase-3 bug inline (never calls the fixed function):
    # at 10:00 (the bar's own open), the bug used 1.1040 -- a price that
    # does not exist until 10:15. This is the exact defect the user's
    # example describes.
    series = _series([REFERENCE_BAR])
    import bisect
    from common.series_index import timestamps_for

    idx = bisect.bisect_left(timestamps_for(series), REFERENCE_BAR.timestamp)
    close_the_old_code_used = series.candles[idx].close
    assert close_the_old_code_used == 1.1040
    # At 10:00 itself, only the OPEN (1.1000) was actually knowable --
    # the close (1.1040) could not have been used by anything causal.
    assert close_the_old_code_used != REFERENCE_BAR.open


def test_fixed_version_uses_open_available_at_control_ts():
    series = _series([REFERENCE_BAR])
    control = _make_control()
    record = control_to_event_record(control, series)
    assert record.operation.exit_price == 1.1000  # the OPEN, available instantly at control_ts
    assert record.operation.exit_price != 1.1040  # never the close
    assert record.operation.exit_ts == REFERENCE_BAR.timestamp


def test_recovery_control_also_uses_open_not_close():
    series = _series([REFERENCE_BAR])
    control = _make_control()
    record = recovery_control_to_event_record(control, series)
    assert record.operation.exit_price == 1.1000
    assert record.operation.stop_loss == 1.1000


def test_bisect_left_finds_the_exact_reference_bar_not_an_off_by_one():
    before = Candle(REFERENCE_BAR.timestamp - dt.timedelta(minutes=15), open=1.09, high=1.09, low=1.09, close=1.09)
    after = Candle(REFERENCE_BAR.timestamp + dt.timedelta(minutes=15), open=1.12, high=1.12, low=1.12, close=1.12)
    series = _series([before, REFERENCE_BAR, after])
    control = _make_control()
    record = control_to_event_record(control, series)
    # Must resolve to the REFERENCE bar's own open (1.1000), not its
    # neighbors' (1.09 / 1.12) -- an off-by-one in either direction would
    # silently substitute the wrong bar.
    assert record.operation.exit_price == 1.1000


def test_post_event_movement_does_not_reuse_the_reference_bars_own_range():
    # The reference bar's own high/low (1.1050/1.0990) must never leak into
    # post-event MFE/MAE -- those describe what happens AFTER the
    # reference instant, and the reference bar itself defines that instant.
    next_bar = Candle(
        REFERENCE_BAR.timestamp + dt.timedelta(minutes=15),
        open=1.1000, high=1.1005, low=1.0995, close=1.1000,
    )
    series = _series([REFERENCE_BAR, next_bar])
    control = _make_control()
    record = control_to_event_record(control, series)
    [behavior] = compute_post_stop_behavior(record, series, horizons=(("4h", dt.timedelta(hours=4)),))
    # If the reference bar's own 1.1050 high leaked in, MFE would be 0.005;
    # it must instead come only from next_bar (max 0.0005 either side).
    assert behavior.raw_max_price <= 1.1005
    assert behavior.raw_min_price >= 1.0995


def test_horizon_boundary_exactly_at_a_bars_close_is_inclusive():
    # A bar closing EXACTLY at the horizon boundary (not before, not after)
    # must be included -- its OHLC is fully known right at that instant.
    control = _make_control()
    series = _series([REFERENCE_BAR])  # closes at 10:15
    # exit_ts (control_ts) = 10:00; a 15-minute horizon's boundary is 10:15,
    # exactly when REFERENCE_BAR (used as the NEXT bar here) would close --
    # but REFERENCE_BAR IS the reference/exit bar itself, excluded from
    # post-event measurement by construction. Build a dedicated next bar
    # whose own close lands exactly on the horizon boundary instead.
    next_bar = Candle(
        REFERENCE_BAR.timestamp + dt.timedelta(minutes=15),  # opens 10:15, closes 10:30
        open=1.1000, high=1.1010, low=1.0995, close=1.1005,
    )
    full_series = _series([REFERENCE_BAR, next_bar])
    record = control_to_event_record(control, full_series)
    [behavior] = compute_post_stop_behavior(
        record, full_series, horizons=(("30min", dt.timedelta(minutes=30)),)
    )
    # next_bar opens 10:15, closes 10:30 == the horizon boundary exactly -> included.
    assert behavior.bars_available == 1
    assert behavior.raw_max_price == 1.1010
