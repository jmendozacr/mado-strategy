"""Explicit coverage map for Phase 5's 15 required proofs (section 13 of
the user's brief).

 1. A win is never classified as SL                                 -> test_early_stop_hypothesis.py::test_is_confirmed_stop_excludes_wins_and_ambiguous
 2. An open trade is never considered a loss                        -> test_early_stop_hypothesis.py::test_build_primary_population_excludes_open_only
 3. A partial exit never silently becomes SL                        -> test_early_stop_hypothesis.py::test_partial_exit_win_not_flagged_as_confirmed_stop
 4. The early endpoint distinguishes same bar / next bar / later     -> test_trade_timing.py::test_same_bar_is_duration_zero, ::test_next_bar_is_duration_one, ::test_two_bars_later_is_not_same_or_next
 5. M15 timestamps respect open/close/availability                   -> test_trade_timing.py (exact bisect match) + Phase 3/4's existing causal boundary tests, unchanged
 6. Gaps never produce an artificially short duration                -> test_trade_timing.py::test_weekend_gap_does_not_shrink_bar_count_duration
 7. The primary comparison uses ALL eligible operations, not just losses -> test_early_stop_hypothesis.py::test_build_primary_population_excludes_open_only (includes the win)
 8. Controls/strata never depend on post-entry information           -> features/pre_entry_features.py's own Phase-4 causality tests (unchanged, reused); risk_atr strata are built solely from `PreEntryFeatures.risk_atr`
 9. risk_atr is computed exclusively from pre-entry data              -> test_pre_entry_features.py::test_future_candle_does_not_affect_pre_entry_feature (Phase 4, unchanged, still passing)
10. A matching/standardization without common support is never forced -> test_early_stop_hypothesis.py::test_standardized_gap_excludes_unsupported_strata_and_is_deterministic
11. Excluded operations and reasons are reported                     -> test_early_stop_hypothesis.py::test_common_support_flags_insufficient_strata_and_reports_share
12. Results are deterministic                                        -> test_early_stop_hypothesis.py::test_unadjusted_gap_is_deterministic_and_matches_point_estimate, ::test_standardized_gap_excludes_unsupported_strata_and_is_deterministic
13. The path-integrity label is never used as an independent predictor of its own duration -> test_early_stop_hypothesis.py::test_duration_explains_integrity_zero_mismatches_by_construction
14. Censoring is never confused with competing events                -> test_early_stop_hypothesis.py::test_build_primary_population_excludes_open_only (OPEN excluded entirely, not given a duration-based competing-event label)
15. No original source file is modified                              -> THIS FILE: test_source_files_untouched_by_phase5_pipeline
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from extract.from_causal_lookahead_audit import SOURCE_RELATIVE_PATH, extract
from eligibility.stop_eligibility import classify_all
from stats.early_stop_hypothesis import build_primary_population

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def test_source_files_untouched_by_phase5_pipeline():
    source_path = REPO_ROOT / SOURCE_RELATIVE_PATH
    before = hashlib.sha256(source_path.read_bytes()).hexdigest()
    records = extract(REPO_ROOT)
    classify_all(records)
    build_primary_population(records)
    after = hashlib.sha256(source_path.read_bytes()).hexdigest()
    assert before == after
