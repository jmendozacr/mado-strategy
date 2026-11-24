from stats.bootstrap import (
    block_bootstrap_ci,
    block_bootstrap_paired_diff_ci,
    median,
    proportion_true,
    quantiles,
)


def test_block_bootstrap_ci_is_deterministic_for_a_fixed_seed():
    values = [(float(i), ("EURUSD", 2021, i % 10)) for i in range(100)]
    a = block_bootstrap_ci(values, statistic=median, seed=1, n_resamples=200)
    b = block_bootstrap_ci(values, statistic=median, seed=1, n_resamples=200)
    assert a == b


def test_block_bootstrap_ci_contains_point_estimate_region():
    values = [(float(i % 5), ("EURUSD", 2021, i % 20)) for i in range(200)]
    result = block_bootstrap_ci(values, statistic=median, seed=2, n_resamples=500)
    assert result["ci_low"] <= result["point_estimate"] <= result["ci_high"]


def test_paired_diff_is_near_zero_for_identical_groups():
    paired = [(1.0, 1.0, ("EURUSD", 2021, i % 10)) for i in range(100)]
    result = block_bootstrap_paired_diff_ci(paired, statistic=median, seed=3, n_resamples=300)
    assert result["point_estimate"] == 0.0
    assert result["ci_low"] <= 0.0 <= result["ci_high"]


def test_paired_diff_detects_a_real_shift():
    paired = [(2.0, 1.0, ("EURUSD", 2021, i % 10)) for i in range(100)]
    result = block_bootstrap_paired_diff_ci(paired, statistic=median, seed=4, n_resamples=300)
    assert result["point_estimate"] == 1.0
    assert result["ci_low"] > 0.0  # a constant +1 shift should not cross zero


def test_empty_input_returns_none_not_a_crash():
    result = block_bootstrap_ci([], statistic=median)
    assert result["point_estimate"] is None
    assert result["n"] == 0


def test_proportion_true_and_quantiles_basic_sanity():
    flags = [1.0, 1.0, 0.0, 0.0]
    assert proportion_true(flags) == 0.5
    q = quantiles([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    assert q[0.5] in (5, 6)
