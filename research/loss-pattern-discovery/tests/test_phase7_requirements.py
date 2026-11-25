"""Explicit coverage map for Phase 7's 20 required proofs (section 13 of
the user's brief).

 1. S2's bounds are correct, with uncertainty in BOTH models            -> test_sensitivity_scenarios.py::test_s2_difference_bounds_use_cross_model_pairing_not_same_scenario_pairing
 2. The E1 endpoint reproduces Phase 6                                  -> test_e1_timing_association.py::test_model_0_matches_hand_computed_e1_rate; real data: docs/50 Model 0 = 11.63%/6.25%, matching docs/38 exactly
 3. Each window's start and end are correct                             -> test_confirmation_window_features.py::test_1am_window_boundaries_are_02_to_04_ny, ::test_9am_window_boundaries_are_09_to_13_ny_not_09_to_1030
 4. Temporal-position calculation respects M15 timestamps               -> test_confirmation_window_features.py::test_elapsed_and_relative_position_respect_window_duration
 5. A confirmation is never available before its own bar closes         -> test_confirmation_window_features.py::test_confirmation_available_at_is_bar_open_plus_15_minutes
 6. Order placement never precedes confirmation availability            -> test_confirmation_window_features.py::test_order_placement_never_precedes_confirmation_availability + real-data invariant test
 7. Fill never occurs before the first eligible instant                 -> test_confirmation_window_features.py::test_fill_never_precedes_order_placement_in_well_formed_data + real-data invariant (order_to_fill_minutes >= 0 for all 2043)
 8. EST/EDT computed via the real timezone, never a fixed offset        -> test_confirmation_window_features.py::test_est_edt_transition_is_handled_by_real_zoneinfo_not_a_fixed_offset
 9. Models keep their own, different window durations                  -> test_confirmation_window_features.py's 1AM (120min) vs. 9AM (240min) tests
10. Common support is checked BEFORE adjusting                          -> test_e1_timing_association.py::test_model_1_risk_standardized_has_common_support_and_standardized_gap, ::test_model_2_timing_standardized_never_uses_order_to_fill_minutes; real data: docs/50 Model 2a's 50.3% unsupported share, reported, not silently adjusted past
11. No post-entry variable is used as a pre-entry predictor             -> docs/48's field-integrity table (order_to_fill_minutes explicitly excluded from the predictor set); test_e1_timing_association.py::test_model_2_timing_standardized_never_uses_order_to_fill_minutes
12. E0 and E1 stay separate                                             -> stats/e1_timing_association.py's `_e1_flags` uses `TimingCategory.NEXT_BAR_SL` exclusively, never `SAME_BAR_SL` (Phase 6's own E0/E1 separation, unchanged)
13. Winning trades are included in the correct denominator              -> test_e1_timing_association.py::test_model_0_matches_hand_computed_e1_rate (fixture denominator includes wins)
14. Open trades are never classified as losses                          -> `stats.early_stop_hypothesis.build_primary_population` (Phase 5, unchanged, reused) + its own existing tests
15. Signals without verifiable timestamps get no invented values        -> test_confirmation_window_features.py::test_missing_model1_available_ts_is_reported_not_invented, ::test_unknown_origin_model_is_reported_not_invented
16. Adjustments never silently extrapolate past common support          -> `stats.early_stop_hypothesis.standardized_gap` (Phase 5, unchanged, reused) excludes unsupported strata entirely; docs/50's own explicit discussion of Model 2a's 50.3% unsupported share
17. The methodology is deterministic                                    -> test_confirmation_window_features.py::test_deterministic; test_e1_timing_association.py::test_models_are_deterministic; test_sensitivity_scenarios.py (Phase 6, unchanged)
18. Historical reports are never overwritten                            -> docs/40 preserved verbatim; docs/41 gets a correction BANNER, not a rewrite (docs/46, docs/47)
19. Results are reproducible with identical data/config                 -> every stats/*.py script here is a deterministic function of the unchanged source CSV plus a fixed seed (same SEED/N_RESAMPLES as Phase 5/6)
20. Original sources are never modified                                 -> THIS FILE: test_source_files_untouched_by_phase7_pipeline
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from eligibility.intrabar_ambiguity import classify_all_intrabar_uncertainty
from eligibility.stop_timing_decomposition import classify_all_timing
from extract.from_causal_lookahead_audit import SOURCE_RELATIVE_PATH, extract
from features.confirmation_window_features import compute_all_confirmation_window_features
from stats.early_stop_hypothesis import build_primary_population
from stats.model_population_audit import load_all_series
from stats.temporal_feature_dataset import build_temporal_feature_dataset

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

SOURCES_TO_VERIFY = (
    SOURCE_RELATIVE_PATH,
    "detector/backtest/simulate.py",
    "detector/causal/htf_trigger.py",
    "audit/2026-11-17-causal-lookahead-audit/causal_intrabar.py",
    "audit/2026-11-17-causal-lookahead-audit/causal_anchor_v2.py",
    "audit/2026-11-17-causal-lookahead-audit/run_d1_d2_d3.py",
)


def _hashes() -> dict[str, str]:
    return {
        rel: hashlib.sha256((REPO_ROOT / rel).read_bytes()).hexdigest()
        for rel in SOURCES_TO_VERIFY
    }


def test_source_files_untouched_by_phase7_pipeline():
    before = _hashes()
    records = extract(REPO_ROOT)
    series_by_instrument = load_all_series()
    timing_by_id = classify_all_timing(records, series_by_instrument)
    classify_all_intrabar_uncertainty(records, timing_by_id, series_by_instrument)
    primary = build_primary_population(records)
    compute_all_confirmation_window_features(primary)
    build_temporal_feature_dataset(primary, series_by_instrument)
    after = _hashes()
    assert before == after
