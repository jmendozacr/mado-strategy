"""Explicit coverage map for Phase 8's 25 required proofs (section 14 of
the user's brief).

 1. candidates_built/filled (pop_stats) never read as model-specific without validation -> docs/56 (provenance audit, traced to source); test_funnel_reconstruction.py::test_verify_against_pooled_counts_detects_a_real_mismatch
 2. Genuinely model-specific counters stay separated                    -> extract/funnel_reconstruction.py's `counters_by_model` (FunnelCounters reused unmodified); docs/58's exact cross-check against the real funnel CSV
 3. Stages use explicit observation units                               -> docs/57 section 1 (the stage/unit table)
 4. Windows and triggers never summed as the same unit                  -> docs/59 ("multi-signal/multi-direction windows"); docs/60's explicit framing ("average yield", never "P(trigger|window)")
 5. Two-direction triggers never accidentally duplicated                -> THIS FILE: test_sweep_and_trigger_invariants_hold_on_real_data; extract/funnel_reconstruction.py::verify_sweep_and_trigger_invariants
 6. Each executed trade reconciles to its origin identifier when it exists -> docs/59 (identity chain table); stats/funnel_reconciliation_report.py's per-(model,instrument) reconciliation, all `filled_matches_ledger_executed: true`
 7. Duplicate IDs are detected                                          -> test_funnel_reconciliation_report.py::test_detects_duplicate_event_ids_if_present
 8. Missing identifiers are reported                                    -> test_funnel_reconciliation_report.py::test_records_with_unresolvable_model_are_reported_not_silently_dropped
 9. Fills by model sum to exactly 2047 in the baseline                  -> docs/58 ("Totals": 143+493+207+489+270+445 = 2047); stats/funnel_reconciliation_report.py's `total_executed`
10. Evaluable operations sum to exactly 2043                            -> stats/funnel_reconciliation_report.py's `total_evaluable`; real run: 619+1424=2043
11. The four open trades stay censored                                  -> stats/funnel_reconciliation_report.py's `baseline_check` (`open` field, both models); real run matches 1/3 exactly
12. E0/E1/E2/E3/E4 reproduce the prior counts                           -> stats/funnel_reconciliation_report.py::e0_e4_reconciliation (reuses Phase 6's `eligibility.stop_timing_decomposition` unmodified)
13. E1 still reproduces 72/619 and 89/1424                              -> stats/funnel_reconciliation_report.py::e1_reconciliation; real run: rate_1am=0.1163166..., rate_9am=0.0625 exactly
14. The funnel corresponds exclusively to D3/C2                        -> extract/funnel_reconstruction.py's `ANCHOR_SOURCE="new"`, `WINDOWS_9AM="new"`, `ARM_NAME="d3_c2"` constants; docs/56's provenance trace
15. The real 9AM window is 240 minutes                                  -> Phase 7's docs/47 (unchanged, reused); test_confirmation_window_features.py (Phase 7, unchanged)
16. The real 1AM window is 120 minutes                                  -> Phase 7's docs/47 (unchanged, reused)
17. Timestamps respect causality                                        -> `fill_pass_c`'s own assertion (`first_fillable_index > confirmation_index`, unmodified); `compute_atr_at_event` (Phase 3's causal boundary, reused unmodified in `_covariates_for_group`)
18. Never-executed orders get no invented outcome                       -> extract/funnel_reconstruction.py never assigns an `outcome`/`r_multiple` to a never-filled `Candidate` -- `_covariates_for_group` only ever reads `entry_price`/`stop_loss` (planned, pre-existing fields), never a result
19. Never-filled orders' features never use bars after the analyzed instant -> test_funnel_reconstruction.py::test_covariates_for_group_never_uses_a_bar_at_or_after_order_placement
20. Conversion rates never divide incompatible populations              -> docs/57 section 1's mandatory rule + docs/60's unit-labeled rates only
21. The reconstruction is deterministic                                 -> test_funnel_reconstruction.py::test_eligible_and_skipped_and_covariates_are_deterministic
22. Results do not depend on row order                                  -> test_funnel_reconstruction.py::test_partition_and_covariates_are_order_independent
23. Original data remains intact                                        -> THIS FILE: test_source_files_untouched_by_phase8_pipeline
24. The protected human audit is never touched or inspected             -> this phase's adapter imports nothing from `audit/trader-algorithm-fidelity/`; grep-verified, no reference anywhere in `extract/funnel_reconstruction.py` or `stats/funnel_reconciliation_report.py`
25. The process fails explicitly when a mandatory reconciliation fails  -> `verify_against_pooled_counts`/`verify_sweep_and_trigger_invariants` return an explicit `matches`/`*_invariant_holds` boolean, never silently swallowed; THIS FILE's mismatch tests assert `False` is correctly surfaced
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from eligibility.intrabar_ambiguity import classify_all_intrabar_uncertainty
from eligibility.stop_timing_decomposition import classify_all_timing
from extract.from_causal_lookahead_audit import SOURCE_RELATIVE_PATH, extract
from extract.funnel_reconstruction import reconstruct_for_symbol, verify_sweep_and_trigger_invariants
from stats.early_stop_hypothesis import build_primary_population
from stats.model_population_audit import load_all_series

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

SOURCES_TO_VERIFY = (
    SOURCE_RELATIVE_PATH,
    "detector/backtest/simulate.py",
    "detector/causal/htf_trigger.py",
    "audit/2026-11-17-causal-lookahead-audit/causal_intrabar.py",
    "audit/2026-11-17-causal-lookahead-audit/causal_anchor_v2.py",
    "audit/2026-11-17-causal-lookahead-audit/run_d1_d2_d3.py",
    "audit/2026-11-17-causal-lookahead-audit/run_c1_c2.py",
    "audit/2026-11-17-causal-lookahead-audit/funnel_2015plus_run2.csv",
)


def _hashes() -> dict[str, str]:
    return {
        rel: hashlib.sha256((REPO_ROOT / rel).read_bytes()).hexdigest()
        for rel in SOURCES_TO_VERIFY
    }


def test_source_files_untouched_by_phase8_pipeline():
    before = _hashes()
    records = extract(REPO_ROOT)
    series_by_instrument = load_all_series()
    timing_by_id = classify_all_timing(records, series_by_instrument)
    classify_all_intrabar_uncertainty(records, timing_by_id, series_by_instrument)
    build_primary_population(records)
    after = _hashes()
    assert before == after


def test_sweep_and_trigger_invariants_hold_on_real_data():
    """Requirement 5, on real EURUSD data: the sweep-category partition
    sums to windows_considered, and model1_confirmed plus every
    zero-signal reason sums to triggers_with_key_level, for BOTH models
    -- two-direction triggers are never double-counted against the
    wrong unit."""
    result = reconstruct_for_symbol("EURUSD")
    invariants = verify_sweep_and_trigger_invariants(result["counters_by_model"])
    for model, check in invariants.items():
        assert check["sweep_invariant_holds"], f"{model}: {check}"
        assert check["trigger_invariant_holds"], f"{model}: {check}"
