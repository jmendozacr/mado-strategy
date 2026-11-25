"""Explicit coverage map for Phase 6's 18 required proofs (section 11 of
the user's brief).

 1. E0+E1 reproduces Phase 5's endpoint                         -> test_stop_timing_decomposition.py::test_gap_decomposition_sum_of_parts_matches_combined_gap, ::test_decomposition_identity_e0_plus_e1_equals_combined_rate
 2. Same-bar and next-bar are never mixed                       -> test_stop_timing_decomposition.py::test_same_bar_confirmed_stop_is_e0, ::test_next_bar_confirmed_stop_is_e1; test_sensitivity_scenarios.py::test_s1_counts_only_next_bar_not_same_bar
 3. Entry/SL order within one bar is never arbitrarily invented -> test_intrabar_ambiguity.py::test_bullish_same_bar_not_verifiable_when_open_below_entry, ::test_bearish_same_bar_not_verifiable_when_open_above_entry
 4. An ambiguous sequence stays ambiguous                       -> test_intrabar_ambiguity.py::test_ambiguous_bar_flag_never_treated_as_a_resolved_same_bar_sequence
 5. The original engine's own results are never modified        -> THIS FILE: test_source_files_untouched_by_phase6_pipeline
 6. Price opening beyond the SL gets the correct treatment      -> docs/37 section 1 (Q7); test_intrabar_ambiguity.py::test_same_bar_event_never_reports_gap_affected_regardless_of_flag
 7. Gaps never silently become ordinary fills                   -> test_intrabar_ambiguity.py::test_non_same_bar_event_never_gets_a_same_bar_verdict (gap_affected surfaced explicitly)
 8. An SL/TP tie is identified                                  -> test_stop_timing_decomposition.py::test_ambiguous_bar_loss_never_promoted_to_a_stop_category
 9. ambiguous_bar is never treated as a verified sequence       -> test_intrabar_ambiguity.py::test_ambiguous_bar_flag_never_treated_as_a_resolved_same_bar_sequence
10. Classification never depends on future prices               -> test_intrabar_ambiguity.py::test_classification_never_consults_a_later_candle
11. Timestamps respect M15 opening semantics                    -> docs/37 section 0/1 (Q10, citing run_c1_c2.py::fmt_idx_ts); common/trade_timing.py (Phase 5, unchanged, reused)
12. The audit never uses a later bar to decide the current bar  -> test_intrabar_ambiguity.py::test_classification_never_consults_a_later_candle
13. Winning trades stay in the right denominator                -> test_stop_timing_decomposition.py::test_win_is_other_exit_never_a_stop_category, ::test_decomposition_table_denominators_are_consistent_across_categories
14. Open/censored trades keep their classification              -> test_stop_timing_decomposition.py::test_open_is_censored_with_no_duration
15. The sensitivity-scenario analysis is deterministic          -> test_sensitivity_scenarios.py::test_scenarios_are_deterministic
16. Statistical controls use the same criteria for both models  -> test_sensitivity_scenarios.py::test_s2_upper_bound_equals_s0_exactly (same `unadjusted_gap` machinery, same SEED/CI, for both models)
17. Original sources remain intact                              -> THIS FILE: test_source_files_untouched_by_phase6_pipeline
18. Removing ambiguous events is never presented as unbiased for the whole population -> test_sensitivity_scenarios.py::test_s3_excludes_the_not_verifiable_e0_event_and_reports_it; docs/40-phase6-sensitivity-analysis.md
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from eligibility.intrabar_ambiguity import classify_all_intrabar_uncertainty
from eligibility.stop_timing_decomposition import classify_all_timing
from extract.from_causal_lookahead_audit import SOURCE_RELATIVE_PATH, extract
from stats.early_stop_hypothesis import build_primary_population
from stats.model_population_audit import load_all_series

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

SOURCES_TO_VERIFY = (
    SOURCE_RELATIVE_PATH,
    "detector/backtest/simulate.py",
    "audit/2026-11-17-causal-lookahead-audit/causal_intrabar.py",
    "audit/2026-11-17-causal-lookahead-audit/run_c1_c2.py",
)


def _hashes() -> dict[str, str]:
    return {
        rel: hashlib.sha256((REPO_ROOT / rel).read_bytes()).hexdigest()
        for rel in SOURCES_TO_VERIFY
    }


def test_source_files_untouched_by_phase6_pipeline():
    before = _hashes()
    records = extract(REPO_ROOT)
    series_by_instrument = load_all_series()
    timing_by_id = classify_all_timing(records, series_by_instrument)
    classify_all_intrabar_uncertainty(records, timing_by_id, series_by_instrument)
    build_primary_population(records)
    after = _hashes()
    assert before == after
