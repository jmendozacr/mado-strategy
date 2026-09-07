import statistics

from research.bootstrap import BOOTSTRAP_VERSION, DEFAULT_N_RESAMPLES, DEFAULT_SEED, bootstrap_ci


def _mean_delta(a: list[float], b: list[float]) -> float:
    return statistics.mean(a) - statistics.mean(b)


def test_bootstrap_ci_is_deterministic_given_a_fixed_seed():
    group_a = [1, 0, 1, 1, 0, 1, 0, 0, 1, 1]
    group_b = [0, 0, 1, 0, 0, 1, 0, 0, 0, 1]

    first = bootstrap_ci(group_a, group_b, _mean_delta, seed=42)
    second = bootstrap_ci(group_a, group_b, _mean_delta, seed=42)

    assert first == second


def test_bootstrap_ci_straddles_zero_for_identical_samples():
    """group_a and group_b drawn from the SAME underlying sample -> the
    true delta is 0, so a well-formed 90% CI must contain it."""
    sample = [1, 0, 1, 1, 0, 1, 0, 0, 1, 1, 0, 1, 1, 0, 0, 1, 0, 1, 1, 0]

    low, high = bootstrap_ci(sample, sample, _mean_delta, seed=DEFAULT_SEED)

    assert low <= 0.0 <= high


def test_bootstrap_ci_bounds_are_ordered():
    group_a = [2.0, -1.0, 3.0, 0.5, -0.5, 1.5, 2.5, -2.0, 0.0, 1.0]
    group_b = [-1.0, -1.5, 0.0, 0.5, 1.0, -0.5, 0.0, 1.0, -1.0, 0.5]

    low, high = bootstrap_ci(group_a, group_b, _mean_delta, seed=7)

    assert low <= high


def test_bootstrap_ci_uses_a_local_rng_not_global_random_state():
    """Reproducibility must not depend on what ran (or didn't) beforehand --
    perturbing the GLOBAL `random` module's state must not change the
    result for a fixed `seed`."""
    import random

    group_a = [1, 0, 1, 1, 0, 1, 0, 0, 1, 1]
    group_b = [0, 0, 1, 0, 0, 1, 0, 0, 0, 1]

    random.seed(12345)
    random.random()
    first = bootstrap_ci(group_a, group_b, _mean_delta, seed=99)

    random.seed(999)
    for _ in range(50):
        random.random()
    second = bootstrap_ci(group_a, group_b, _mean_delta, seed=99)

    assert first == second


def test_bootstrap_ci_respects_n_resamples_and_ci_parameters():
    group_a = [1, 0, 1, 1, 0, 1, 0, 0, 1, 1]
    group_b = [0, 0, 1, 0, 0, 1, 0, 0, 0, 1]

    narrow = bootstrap_ci(group_a, group_b, _mean_delta, n_resamples=500, ci=0.5, seed=1)
    wide = bootstrap_ci(group_a, group_b, _mean_delta, n_resamples=500, ci=0.99, seed=1)

    assert (wide[1] - wide[0]) >= (narrow[1] - narrow[0])


def test_bootstrap_version_and_defaults_are_documented_constants():
    assert BOOTSTRAP_VERSION == "percentage_bootstrap_v1"
    assert DEFAULT_N_RESAMPLES == 2000
    assert isinstance(DEFAULT_SEED, int)
