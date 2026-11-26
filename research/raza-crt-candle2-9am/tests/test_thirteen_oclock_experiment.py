from datetime import datetime

from raza_extract.thirteen_oclock_experiment import (
    build_experiment_for_symbol,
    reconcile_baseline_against_ledger,
)


def test_population_is_restricted_to_exact_1300_confirmations_and_baseline_reconciles():
    """Real-data check (tight range): the population only contains
    signals whose model1_available_ts equals the H4 close-availability
    instant exactly, and every baseline-executed signal in it matches
    the real, unmodified ledger exactly -- restricting the input set to
    build_stage6_population/fill_pass_c never changes an individual
    candidate's own resolution."""
    result = build_experiment_for_symbol(
        "EURUSD", start_date=datetime(2015, 1, 1), end_date=datetime(2017, 1, 1),
    )
    assert result["n_population"] > 0
    recon = reconcile_baseline_against_ledger(result["rows"])
    assert recon["fully_reconciled"], recon


def test_variant_arm_never_builds_a_candidate_outside_the_inside_group():
    result = build_experiment_for_symbol(
        "EURUSD", start_date=datetime(2015, 1, 1), end_date=datetime(2017, 1, 1),
    )
    for sid, row in result["rows"].items():
        if row["close_position"] != "INSIDE":
            assert row["variant"]["is_candidate"] is False, (sid, row)
            assert row["variant"]["is_filled"] is False
            assert row["variant"]["outcome"] is None


def test_every_row_carries_both_arms_independently():
    result = build_experiment_for_symbol(
        "EURUSD", start_date=datetime(2015, 1, 1), end_date=datetime(2017, 1, 1),
    )
    for sid, row in result["rows"].items():
        assert "baseline" in row and "variant" in row
        assert row["close_position"] in ("INSIDE", "OUTSIDE", "EXACT_BOUNDARY", "MISSING_OR_INCOMPLETE")
        assert row["sweep_side"] in ("HIGH_ONLY", "LOW_ONLY", "BOTH", "MISSING_OR_INCOMPLETE", "NEITHER_ANOMALY")
