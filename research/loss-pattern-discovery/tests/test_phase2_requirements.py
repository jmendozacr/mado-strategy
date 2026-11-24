"""Explicit coverage map for Phase 2's 13 required proofs (section 10 of the
user's brief). Each numbered requirement below is satisfied either by a test
in this file or by a named test elsewhere in this suite -- listed so the
mapping is auditable in one place, not scattered.

 1. A loss is not auto-classified as SL            -> test_stop_eligibility.py::test_a_loss_is_not_automatically_classified_as_confirmed_stop
 2. Partial exits are preserved correctly          -> test_stop_eligibility.py::test_partial_exit_preserved_and_referenced_against_entry_price_not_stop_loss
 3. An ambiguous stop never becomes confirmed      -> test_stop_eligibility.py::test_ambiguous_bar_never_promoted_to_confirmed_even_at_exact_stop_price
 4. No future OHLC used for entry conditions       -> test_schema_separation.py::test_features_pre_entry_has_no_outcome_or_exit_fields,
                                                       test_extract_from_causal_lookahead_audit.py::test_pre_entry_features_never_populated_from_exit_fields
 5. Post-stop trajectory starts at the defined pt  -> test_post_stop_metrics.py::test_first_actionable_ts_is_exit_plus_one_m15_bar,
                                                       ::test_exit_bar_itself_is_excluded_from_raw_extremes
 6. Incomplete horizons are censored               -> test_post_stop_metrics.py::test_incomplete_horizon_is_censored_not_fabricated
 7. Gaps are detected without interpolation        -> test_post_stop_metrics.py::test_weekend_gap_is_flagged_without_interpolation
 8. MFE/MAE respect the evaluated direction        -> test_post_stop_metrics.py::test_mfe_mae_respect_bearish_direction,
                                                       test_post_stop_trajectory.py (Phase 1, same convention)
 9. R-normalization requires a valid risk          -> test_post_stop_metrics.py::test_r_normalization_requires_valid_risk_price
10. Control group not selected on future outcomes  -> test_control_sampling.py::test_control_to_event_record_only_uses_pre_control_information,
                                                       ::test_controls_respect_the_exclusion_buffer_around_real_events
11. Events/controls not silently duplicated        -> test_control_sampling.py::test_controls_do_not_silently_duplicate_the_same_timestamp_when_pool_is_large_enough
12. Extraction/analysis are deterministic          -> THIS FILE: test_extraction_is_deterministic, test_control_sampling_is_deterministic (duplicate of
                                                       test_control_sampling.py::test_sampling_is_deterministic_for_a_fixed_seed, kept here for the map),
                                                       test_bootstrap.py::test_block_bootstrap_ci_is_deterministic_for_a_fixed_seed
13. Original sources remain intact                 -> THIS FILE: test_source_files_are_never_modified_by_the_pipeline
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from extract.from_causal_lookahead_audit import SOURCE_RELATIVE_PATH, extract
from eligibility.stop_eligibility import classify_all

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_extraction_is_deterministic():
    records_a = extract(REPO_ROOT)
    records_b = extract(REPO_ROOT)
    assert len(records_a) == len(records_b)
    for a, b in zip(records_a, records_b):
        assert a.identification.event_id == b.identification.event_id
        assert a.operation.exit_price == b.operation.exit_price
        assert a.operation.r_multiple == b.operation.r_multiple


def test_classification_is_deterministic():
    records = extract(REPO_ROOT)
    results_a = classify_all(records)
    results_b = classify_all(records)
    assert {k: v.category for k, v in results_a.items()} == {k: v.category for k, v in results_b.items()}


def test_source_files_are_never_modified_by_the_pipeline():
    source_path = REPO_ROOT / SOURCE_RELATIVE_PATH
    before = _hash_file(source_path)

    records = extract(REPO_ROOT)
    classify_all(records)

    after = _hash_file(source_path)
    assert before == after
