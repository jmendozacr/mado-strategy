import datetime as dt

from alignment.htf_ltf import AlignedSignal
from backtest.population import build_stage6_population
from core.candle import Candle, OHLCSeries
from core.config import BacktestConfig, DetectorConfig
from core.key_level import KeyLevel
from core.results import DetectionStatus
from entries.model1 import Model1Signal
from primitives.crt_range import CRTRange

from extract.stage6_attrition_diagnostics import (
    build_stage6_population_instrumented,
    verify_population_cuts_are_zero,
)

TS0 = dt.datetime(2026, 1, 1, 0, 0)


def _series(n=40):
    candles = tuple(
        Candle(TS0 + dt.timedelta(minutes=15 * i), open=1.10, high=1.101, low=1.099, close=1.10)
        for i in range(n)
    )
    return OHLCSeries(candles=candles, instrument="EURUSD", timeframe="M15")


def _htf_context():
    return CRTRange(model="2-candle", high=1.20, low=1.00, start_index=0, end_index=0,
                    resolution="false_break", resolved_at_index=0)


def _aligned_signal(anchor_index=5, direction="bullish", retest_index=6, origin_index=4):
    signal = Model1Signal(
        anchor_index=anchor_index, direction=direction, purge_target=1.09,
        confirmation_type="purge_engulf", entry_type="wick", entry_price=1.10,
        retest_index=retest_index, status=DetectionStatus.CONFIRMED,
        confirmation_index=anchor_index + 2, origin_index=origin_index,
    )
    key_level = KeyLevel(kind="fvg", top=1.12, bottom=1.08, origin_index=0, expiry_index=None)
    return AlignedSignal(ltf_signal=signal, htf_context=_htf_context(), aligned="aligned", key_level=key_level, key_level_reaction=None)


def _config(min_risk_reward=2.0, kill_zone_gated=False):
    backtest = BacktestConfig(
        trading_cost_price=0.0001, max_fill_wait=10, partial_fraction=0.0,
        min_risk_reward=min_risk_reward, kill_zone_gated=kill_zone_gated,
        min_stop_distance_price=0.0001, breakeven_after_partial=False,
    )
    return DetectorConfig(backtest=backtest)


def test_instrumented_population_matches_the_real_function_exactly():
    series = _series()
    config = _config()
    aligned = [_aligned_signal()]
    original = build_stage6_population(aligned, series, config)
    instrumented, _removed = build_stage6_population_instrumented(aligned, series, config)
    assert [c.signal_id for c in instrumented.candidates] == [c.signal_id for c in original.candidates]
    assert instrumented.excluded_duplicate == original.excluded_duplicate
    assert instrumented.excluded_kill_zone == original.excluded_kill_zone
    assert instrumented.excluded_rr_floor == original.excluded_rr_floor
    assert instrumented.excluded_no_crt_range == original.excluded_no_crt_range
    assert instrumented.excluded_unaligned == original.excluded_unaligned
    assert instrumented.excluded_never_confirmed == original.excluded_never_confirmed
    assert instrumented.excluded_no_key_level == original.excluded_no_key_level
    assert instrumented.excluded_confirmed_no_retest == original.excluded_confirmed_no_retest


def test_verify_population_cuts_are_zero_true_for_a_clean_d3_c2_style_population():
    series = _series()
    config = _config()
    aligned = [_aligned_signal()]
    population, _removed = build_stage6_population_instrumented(aligned, series, config)
    check = verify_population_cuts_are_zero(population)
    assert check["all_zero"] is True
    assert check["values"]["excluded_no_crt_range"] == 0


def test_removed_by_model_attributes_a_rejected_candidate_to_its_own_model():
    # Two DISTINCT anchors (different anchor_index/origin_index) so they
    # produce two different signal_ids -- one model's candidate survives,
    # the other's gets duplicated away by sharing the exact same
    # (anchor_index, direction, entry_price, entry_type) key as a
    # second copy of itself (the simplest reliable way to force a `_dedup`
    # removal without depending on exact RR geometry).
    series = _series()
    config = _config()
    survivor = _aligned_signal(anchor_index=5, origin_index=4)
    duplicate = _aligned_signal(anchor_index=5, origin_index=3)  # same anchor/direction/entry -> different signal_id, same dedup key
    model_by_sig = {
        survivor.ltf_signal.signal_id: "1am",
        duplicate.ltf_signal.signal_id: "9am",
    }
    population, removed = build_stage6_population_instrumented(
        [survivor, duplicate], series, config, model_by_sig=model_by_sig,
    )
    assert len(population.candidates) == 1  # _dedup keeps exactly one (lowest origin_index)
    assert population.excluded_duplicate == 1
    # The lower origin_index (3, from `duplicate`) survives per `_dedup`'s
    # own `min(..., key=lambda c: c.origin_index)` rule -- so the REMOVED
    # one is `survivor`, attributed to "1am".
    assert removed["duplicate"] == {"1am": 1}


def test_removed_by_model_attributes_a_geometry_rejection_to_its_own_model():
    # An unreachable RR floor (100.0) forces `_rr_floor_cut` to reject the
    # candidate regardless of its actual computed geometry -- the rule
    # being exercised, not a specific numeric RR value.
    series = _series()
    config = _config(min_risk_reward=100.0)
    aligned = [_aligned_signal()]
    model_by_sig = {aligned[0].ltf_signal.signal_id: "9am"}
    population, removed = build_stage6_population_instrumented(
        aligned, series, config, model_by_sig=model_by_sig,
    )
    assert len(population.candidates) == 0
    assert population.excluded_rr_floor == 1
    assert removed["rr_floor"] == {"9am": 1}


def test_removed_by_model_is_empty_when_nothing_is_removed():
    series = _series()
    config = _config()
    aligned = [_aligned_signal()]
    model_by_sig = {aligned[0].ltf_signal.signal_id: "1am"}
    population, removed = build_stage6_population_instrumented(
        aligned, series, config, model_by_sig=model_by_sig,
    )
    assert len(population.candidates) == 1
    assert removed == {"duplicate": {}, "kill_zone": {}, "rr_floor": {}}
