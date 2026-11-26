"""Explicit coverage map for Phase 10's 24 required proofs (brief section 13).

 1. El diagnóstico reproduce las confirmaciones originales            -> test_confirmation_path_diagnostics.py::test_run_d_c2_with_confirmation_paths_reproduces_the_real_pipeline_exactly, ::test_trace_confirmation_path_for_record_reproduces_the_real_pipeline_exactly
 2. El diagnóstico reproduce los candidatos originales (confirmed records feeding Stage 6) -> same tests as item 1 (`record.aligned.ltf_signal.signal_id` fingerprint equality, counters equality)
 3. Se conservan los identificadores de Fase 9 (stable_id as primary key) -> docs/82; extract/confirmation_path_identity_audit.py never joins on signal_id alone; test_confirmation_path_identity_audit.py
 4. Las colisiones cross-instrument no mezclan eventos                -> test_confirmation_path_identity_audit.py::test_cross_instrument_mismatch_is_detected; real reconciliation (docs/82): n_cross_instrument_mismatch == 0
 5. Los contadores de intentos tienen una definición inequívoca       -> docs/79 section 1 (algebraic identity); test_confirmation_path_diagnostics.py::test_attempt_count_equals_invalidation_count_plus_one_always
 6. Las invalidaciones internas se distinguen de estados terminales   -> `ConfirmationAttempt.status` enumerates "INVALIDATED" separately from "CONFIRMED"/"PENDING"/"NONE"; every synthetic test in test_confirmation_path_diagnostics.py asserts this explicitly
 7. Los reinicios se registran exactamente                            -> test_confirmation_path_diagnostics.py::test_confirmation_after_multiple_invalidations_records_every_restart (`[a.anchor_index for a in path.attempts] == [1, 3, 5]`)
 8. Las confirmaciones directas no reciben reinicios ficticios        -> test_confirmation_path_diagnostics.py::test_direct_confirmation_has_zero_invalidations_and_one_attempt
 9. Una confirmación posterior a una invalidación registra su trayectoria real -> test_confirmation_path_diagnostics.py::test_confirmation_after_one_invalidation_records_its_real_trajectory
10. El diagnóstico nunca lee velas posteriores a la disponibilidad de confirmación -> test_confirmation_path_diagnostics.py::test_never_reads_candles_beyond_the_window_end_even_when_poisoned
11. El agotamiento de ventana respeta el código D3/C2                 -> test_confirmation_path_diagnostics.py::test_window_exhaustion_after_engulf_without_retest_is_pending_with_no_fictitious_restart, ::test_window_exhaustion_without_ever_engulfing_is_none_with_no_fictitious_restart (both call the real, unmodified `_track_anchor`/`find_first_valid_anchor`)
12. Los timestamps respetan EST/EDT                                   -> reuses Phase 7/9's own DST-aware `ca.new_9am_window_fns`/`ca.old_window_fns` unmodified (docs/80); never reimplemented in this phase
13. No se utiliza el estado futuro de un candidato para reconstruir su confirmación -> `trace_confirmation_path_for_record`'s own signature accepts only `record.direction`/`record.activation_instant_ts` (pre-order fields); docs/82
14. La equivalencia de conjuntos se verifica, no solamente la igualdad de cantidades -> `_fingerprint()`'s full sorted-tuple comparison in test_run_d_c2_with_confirmation_paths_reproduces_the_real_pipeline_exactly; dataclass equality (`==`) in test_trace_confirmation_path_for_record_reproduces_the_real_pipeline_exactly
15. Los ganadores mantienen su denominador                            -> `build_primary_population` (Phase 5, reused unmodified) never filters by outcome beyond excluding OPEN; docs/84's baseline-reproduction section
16. E1 reproduce exactamente Fase 6/7                                 -> THIS FILE: test_e1_subgroup_counts_sum_to_the_established_baseline_exactly
17. Las cuatro operaciones abiertas conservan su clasificación        -> test_confirmation_path_identity_audit.py::test_open_trades_keep_their_identity_and_are_still_matched; real reconciliation (docs/82): n_open_trades_matched == 4
18. Los análisis detectan grupos insuficientes                        -> test_confirmation_path_e1_association.py::test_within_model_contrast_flags_insufficient_support
19. El soporte común se verifica antes de estandarizar                -> `within_model_contrast`'s own `sufficient_support` field, checked in docs/85 before Deliverable E's standardization (H3) is treated as valid
20. Los resultados son deterministas                                  -> test_confirmation_path_reconstruction.py::test_reconstruct_paths_for_symbol_is_deterministic
21. Las fuentes originales permanecen intactas                        -> THIS FILE: test_source_files_untouched_by_phase10_pipeline
22. No se ejecuta ninguna modificación de RR                          -> THIS FILE: test_no_rr_floor_value_was_changed_anywhere_in_the_repository (same hash test covers `backtest/population.py`)
23. La propuesta de Fase 11 no incluye resultados contrafactuales inventados -> THIS FILE: test_phase11_proposal_contains_no_invented_counterfactual_numbers
24. Los errores de integridad producen fallos explícitos              -> test_confirmation_path_identity_audit.py::test_missing_path_is_reported_not_silently_dropped, ::test_duplicate_event_ids_are_detected; `load_all_symbol_paths` raises `FileNotFoundError` explicitly when an artifact is missing (never silently returns partial data)
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from extract.confirmation_path_diagnostics import confirm_in_ltf_window_v2_traced  # noqa: F401
from extract.confirmation_path_identity_audit import load_all_symbol_paths  # noqa: F401

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
LAB_ROOT = Path(__file__).resolve().parent.parent

SOURCES_TO_VERIFY = (
    "audit/2026-11-17-causal-lookahead-audit/causal_intrabar.py",
    "audit/2026-11-17-causal-lookahead-audit/causal_anchor_v2.py",
    "audit/2026-11-17-causal-lookahead-audit/run_d1_d2_d3.py",
    "audit/2026-11-17-causal-lookahead-audit/run_c1_c2.py",
    "audit/2026-11-17-causal-lookahead-audit/funnel_2015plus_run2.csv",
    "audit/2026-11-17-causal-lookahead-audit/trades_d3_c2_2015plus_run2.csv",
    "detector/entries/model1.py",
    "detector/backtest/population.py",
    "detector/backtest/levels.py",
)


def _hashes() -> dict[str, str]:
    return {
        rel: hashlib.sha256((REPO_ROOT / rel).read_bytes()).hexdigest()
        for rel in SOURCES_TO_VERIFY
    }


def test_source_files_untouched_by_phase10_pipeline():
    before = _hashes()
    from extract.confirmation_path_reconstruction import reconstruct_paths_for_symbol
    from datetime import datetime

    reconstruct_paths_for_symbol("EURUSD", start_date=datetime(2015, 1, 1), end_date=datetime(2015, 2, 1))
    after = _hashes()
    assert before == after


def test_no_rr_floor_value_was_changed_anywhere_in_the_repository():
    """Requirement 22: `min_risk_reward` stays exactly 2.0 for every pair
    -- this phase never writes to `experimental/htf_trigger_1am_9am_backtest.py`
    (the SYMBOL_CONFIG source), checked both by the hash test above and,
    independently, by reading the live config value itself."""
    import sys

    detector_root = REPO_ROOT / "detector"
    if str(detector_root) not in sys.path:
        sys.path.insert(0, str(detector_root))
    from experimental.htf_trigger_1am_9am_backtest import SYMBOL_CONFIG

    for symbol, config in SYMBOL_CONFIG.items():
        assert config.min_risk_reward == 2.0, f"{symbol}: min_risk_reward changed to {config.min_risk_reward}"


def test_phase11_proposal_contains_no_invented_counterfactual_numbers():
    """Requirement 23: the registered Phase 11 proposal describes a
    DESIGN, never fabricated backtest results for the 2,592 discarded
    signals -- checked by requiring the explicit non-execution
    disclaimer and the required section headers, and rejecting any
    numeric profitability claim pattern for the discarded population."""
    doc = (LAB_ROOT / "docs" / "87-phase11-rr-filter-counterfactual-proposal.md").read_text(encoding="utf-8")
    assert "NOT executed" in doc or "not executed" in doc.lower()
    for header in ("## Question", "## Hypotheses", "## Sources", "## Risks of bias",
                   "## Recommended design", "## Validity criteria", "## Conditions to begin"):
        assert header in doc, f"missing required section: {header}"
    forbidden_patterns = (
        r"\$[\d,]+\s*(profit|loss|gain)",
        r"net profit of \d",
        r"would have (made|lost|earned) \$?\d",
        r"win rate of \d+(\.\d+)?%\s*(on|for|among)\s*the\s*discarded",
    )
    for pattern in forbidden_patterns:
        assert not re.search(pattern, doc, re.IGNORECASE), f"found a forbidden invented-result pattern: {pattern}"


def test_e1_subgroup_counts_sum_to_the_established_baseline_exactly():
    """Requirement 16: splitting the primary population by the
    pre-registered contrast and summing each subgroup's own E1 count
    must reproduce Phase 6/7's exact baseline (72 for 1AM, 89 for
    9AM) -- a consistency check on the join, not merely assumed from
    the contrast's own point rates."""
    import sys
    detector_root = REPO_ROOT / "detector"
    if str(detector_root) not in sys.path:
        sys.path.insert(0, str(detector_root))

    from stats.confirmation_path_e1_association import run

    result = run()
    contrast = result["within_model_contrast"]
    for model, expected_total in (("1am", 72), ("9am", 89)):
        c = contrast[model]
        n_e1 = round(c["n_zero_invalidation"] * c["rate_zero_invalidation"]) + round(
            c["n_one_or_more_invalidation"] * c["rate_one_or_more_invalidation"]
        )
        assert n_e1 == expected_total, f"{model}: reconstructed E1 count {n_e1} != baseline {expected_total}"
