from raza_h4fvg_stats.report import net_r_per_qualifying_setup, outcome_funnel


def test_outcome_funnel_counts_qualifying_setups_correctly():
    sessions = {
        ("EURUSD", "2020-01-01"): {"outcome": "NO_DAILY_BIAS"},
        ("EURUSD", "2020-01-02"): {"outcome": "EXPIRED"},
        ("EURUSD", "2020-01-03"): {"outcome": "ENTERED", "r_multiple": 2.0},
    }
    result = outcome_funnel(sessions)
    assert result["n_total_sessions"] == 3
    assert result["n_qualifying_h4_setup"] == 2  # EXPIRED + ENTERED
    assert result["n_entered"] == 1


def test_net_r_per_qualifying_setup_uses_zero_for_non_entered():
    sessions = {
        ("EURUSD", "2020-01-01"): {"outcome": "NO_DAILY_BIAS"},  # excluded, not qualifying
        ("EURUSD", "2020-01-02"): {"outcome": "EXPIRED"},  # qualifying, R=0
        ("EURUSD", "2020-01-03"): {"outcome": "ENTERED", "r_multiple": 3.0},
        ("EURUSD", "2020-01-04"): {"outcome": "DISCARD_TARGET_BEFORE_ENTRY"},  # qualifying, R=0
    }
    result = net_r_per_qualifying_setup(sessions)
    assert result["n_qualifying"] == 3
    assert result["n_entered_with_r"] == 1
    assert result["total_net_r"] == 3.0
    assert abs(result["mean_net_r_per_qualifying_setup"] - 1.0) < 1e-9
