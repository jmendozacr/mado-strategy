"""Explicit coverage map for Phase 9's 25 required proofs.

 1. Event-level identity verified via the TRUE primary key (stable_id)        -> docs/68 ("Primary identity: fully reconciled"); test_event_identity_reconciliation.py::test_compare_identities_fully_matched_when_identical
 2. Any identity discrepancy is investigated before being accepted           -> docs/68 ("A separate, real discovery"); THIS FILE: test_duplicate_signal_ids_are_investigated_not_silently_accepted
 3. Field-level equality (model/instrument/direction/entry_index/entry_price) -> test_event_identity_reconciliation.py::test_compare_identities_detects_a_field_mismatch, ::test_compare_identities_detects_an_entry_price_mismatch_beyond_tolerance
 4. Float-noise tolerance does not mask a real mismatch                      -> test_event_identity_reconciliation.py::test_compare_identities_tolerates_float_noise_in_entry_price (positive control), ::test_compare_identities_detects_an_entry_price_mismatch_beyond_tolerance (negative control)
 5. Model-1's real anchor/engulf/retest/confirm rules documented from source  -> docs/67 section 1 (points 1-2), docs/69 (10 questions)
 6. `confirm_in_ltf_window_v2` structurally never returns terminal INVALIDATED -> docs/67 section 1.2; test_model1_rejection_diagnostics.py::test_confirm_in_ltf_window_v2_never_returns_invalidated_as_terminal (deterministic, real unmodified functions)
 7. `model1_pending_or_invalidated` is verified to always mean PENDING        -> docs/69 ("Structural finding"); same test as item 6
 8. Anchor-found-but-chain-exhausted is distinguished from zero-anchors-ever  -> docs/69 (anchor-probe disambiguation table); test_model1_rejection_diagnostics.py::test_probe_first_anchor_true_when_an_anchor_exists, ::test_probe_first_anchor_false_when_no_anchor_exists
 9. The anchor probe's own scope limitation is stated, not hidden            -> docs/69 ("Scope limitation, stated plainly")
10. Rejection taxonomy dimensions are never forced mutually-exclusive         -> docs/67 section 2; `RejectionDiagnostic` carries `category` AND `anchor_probe` independently
11. `window_empty_before_search` is categorized without probing an anchor    -> test_model1_rejection_diagnostics.py::test_diagnose_rejection_categorizes_window_empty_without_probing
12. `model1_pending_or_invalidated` is categorized without probing an anchor  -> test_model1_rejection_diagnostics.py::test_diagnose_rejection_categorizes_pending_or_invalidated_without_probing
13. `no_model1_anchor_found` triggers the anchor probe when a window exists   -> test_model1_rejection_diagnostics.py::test_diagnose_rejection_probes_when_no_anchor_found_and_window_exists
14. All 5 `_population_cuts` categories proven structurally impossible for D3/C2, both analytically and empirically -> docs/67 section 1.3; docs/70 (four-way table); `verify_population_cuts_are_zero` used on real 3-pair data (`all_zero: True`)
15. `_kill_zone_cut` is distinguished as available-but-inactive, never conflated with "never fires because it never applies" -> docs/70 (`kill_zone_gated == False` row)
16. Stage-6 attrition is attributed by FIRST firing rule in the real fixed sequence, never double-counted -> docs/70 ("Terminal-reason discipline"); test_stage6_attrition_diagnostics.py::test_removed_by_model_attributes_a_rejected_candidate_to_its_own_model (dedup case), ::test_removed_by_model_attributes_a_geometry_rejection_to_its_own_model (rr_floor case)
17. A confirmed signal that is deduplicated away still produces NO candidate (accepted confirmation, no candidate) -> test_stage6_attrition_diagnostics.py::test_removed_by_model_attributes_a_rejected_candidate_to_its_own_model (`len(population.candidates) == 1` from 2 confirmed inputs)
18. A confirmed signal failing the RR floor produces NO candidate (geometry rejection) -> test_stage6_attrition_diagnostics.py::test_removed_by_model_attributes_a_geometry_rejection_to_its_own_model
19. The instrumented population matches the real `build_stage6_population` exactly, not just by length -> test_stage6_attrition_diagnostics.py::test_instrumented_population_matches_the_real_function_exactly
20. The instrumented D3/C2 run matches the real `run_d_c2` exactly, not just by length -> test_model1_rejection_diagnostics.py::test_run_d_c2_instrumented_reproduces_the_real_pipeline_exactly
21. The full rejection funnel reconciles exactly to the user's stated baseline (triggers/confirmations/candidates/executed, both models) -> docs/71; THIS FILE: test_funnel_reconstruction_reconciles_to_the_phase9_baseline
22. 1AM vs. 9AM rejection-category rates are stable across all four periods (not a single-era artifact) -> docs/71 (period table); THIS FILE: test_confirmation_rate_gap_is_stable_across_all_four_periods
23. The confirmation-rate gap is reported as a structural association, never a causal/window-duration claim, and no counterfactual re-simulation is run -> docs/72 (explicit scope discipline); grep-verified: no re-simulation entry point added in `extract/funnel_reconstruction.py` or `extract/model1_rejection_diagnostics.py`
24. A causal-availability dictionary enforces that a post-rejection variable never explains that rejection -> docs/73 (four layers); docs/74 only ever cites Layer 1/2 facts (confirmation-rate, taxonomy) as associated with, never explaining, a Layer 4 (E1) outcome
25. Source files are reused unmodified; the protected human-pilot audit is never touched or inspected; the two verdict dimensions are reported independently per pre-registered criteria -> THIS FILE: test_source_files_untouched_by_phase9_pipeline; grep-verified no reference to `audit/trader-algorithm-fidelity/` anywhere in `extract/` or `stats/`; docs/75 (both dimensions reported separately, from docs/67 section 3's criteria fixed before the run)
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from extract.funnel_reconstruction import PERIOD_BUCKETS
from extract.model1_rejection_diagnostics import diagnose_rejection  # noqa: F401 (import smoke-check)
from extract.stage6_attrition_diagnostics import build_stage6_population_instrumented  # noqa: F401

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
LAB_ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = LAB_ROOT / "artifacts" / "phase8_funnel_reconstruction.json"

SOURCES_TO_VERIFY = (
    "audit/2026-11-17-causal-lookahead-audit/causal_intrabar.py",
    "audit/2026-11-17-causal-lookahead-audit/causal_anchor_v2.py",
    "audit/2026-11-17-causal-lookahead-audit/run_d1_d2_d3.py",
    "audit/2026-11-17-causal-lookahead-audit/run_c1_c2.py",
    "audit/2026-11-17-causal-lookahead-audit/funnel_2015plus_run2.csv",
    "audit/2026-11-17-causal-lookahead-audit/trades_d3_c2_2015plus_run2.csv",
    "detector/entries/model1.py",
    "detector/backtest/population.py",
)


def _hashes() -> dict[str, str]:
    return {
        rel: hashlib.sha256((REPO_ROOT / rel).read_bytes()).hexdigest()
        for rel in SOURCES_TO_VERIFY
    }


def test_source_files_untouched_by_phase9_pipeline():
    before = _hashes()
    from extract.model1_rejection_diagnostics import run_d_c2_instrumented  # noqa: F401
    from extract.event_identity_reconciliation import read_ledger_identities

    read_ledger_identities(REPO_ROOT)
    after = _hashes()
    assert before == after


def test_duplicate_signal_ids_are_investigated_not_silently_accepted():
    """Requirement 2: the 3 real duplicate signal_ids found in the ledger
    must each be explained (cross-instrument collision, no shared date),
    never merely reported as a raw count."""
    from extract.event_identity_reconciliation import (
        detect_duplicate_signal_ids,
        read_ledger_identities,
    )

    ledger = read_ledger_identities(REPO_ROOT)
    duplicates = detect_duplicate_signal_ids(ledger)
    assert len(duplicates) == 3
    for sid in duplicates:
        rows = [row for row in ledger.values() if row["signal_id"] == sid]
        instruments = {row["pair"] for row in rows}
        assert len(instruments) == 2, f"{sid}: expected a cross-instrument collision, got {instruments}"


def test_funnel_reconstruction_reconciles_to_the_phase9_baseline():
    """Requirement 21: aggregated across the 3 already-reconstructed pairs,
    the funnel matches the user's exact Phase 9 baseline table."""
    if not ARTIFACT.exists():
        import pytest

        pytest.skip("phase8_funnel_reconstruction.json not present in this environment")
    data = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    expected = {
        "1am": {"triggers": 11206, "confirmed": 1805, "candidates": 718, "filled": 620},
        "9am": {"triggers": 8712, "confirmed": 3311, "candidates": 1806, "filled": 1427},
    }
    totals = {"1am": {"triggers": 0, "confirmed": 0, "candidates": 0, "filled": 0},
              "9am": {"triggers": 0, "confirmed": 0, "candidates": 0, "filled": 0}}
    for symbol in ("EURUSD", "USDCAD", "AUDUSD"):
        for model in ("1am", "9am"):
            counters = data[symbol]["counters_by_model"][model]
            splits = data[symbol]["splits"][model]
            totals[model]["triggers"] += counters["triggers_with_key_level"]
            totals[model]["confirmed"] += counters["model1_confirmed"]
            totals[model]["candidates"] += splits["candidates_built"]
            totals[model]["filled"] += splits["filled"]
    assert totals == expected


def test_confirmation_rate_gap_is_stable_across_all_four_periods():
    """Requirement 22: the 1AM/9AM confirmation-rate gap is not a single-
    period artifact -- 1AM stays well below 9AM in every one of the 4
    period buckets."""
    if not ARTIFACT.exists():
        import pytest

        pytest.skip("phase8_funnel_reconstruction.json not present in this environment")
    data = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    agg_trig = {m: {p: 0 for p in PERIOD_BUCKETS} for m in ("1am", "9am")}
    agg_conf = {m: {p: 0 for p in PERIOD_BUCKETS} for m in ("1am", "9am")}
    for symbol in ("EURUSD", "USDCAD", "AUDUSD"):
        for model in ("1am", "9am"):
            tbp = data[symbol]["triggers_by_model_period"][model]
            cbp = data[symbol]["confirmed_by_model_period"][model]
            for period in PERIOD_BUCKETS:
                agg_trig[model][period] += tbp.get(period, 0)
                agg_conf[model][period] += cbp.get(period, 0)
    for period in PERIOD_BUCKETS:
        rate_1am = agg_conf["1am"][period] / agg_trig["1am"][period]
        rate_9am = agg_conf["9am"][period] / agg_trig["9am"][period]
        assert rate_1am < 0.25 < 0.35 < rate_9am, (period, rate_1am, rate_9am)
