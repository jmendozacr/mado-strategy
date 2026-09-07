"""Percentage bootstrap confidence intervals — RESEARCH TOOLING.

Formalizes, as a versioned function, the bootstrap method every prior
ablation this session used informally: resample each group independently
WITH replacement, compute a statistic on each resampled pair, and take the
percentile interval of the resulting distribution. This module gives that
method a name (`BOOTSTRAP_VERSION`), a fixed default seed, and a test
suite, so a reported CI is reproducible exactly, not just "roughly the same
shape" — a gap the prior, ad hoc ablations never closed.

Leaf module: no imports beyond the standard library, so it carries none of
the `.importlinter` leaf-package concerns `order_block.py`/`displacement.py`
document.
"""

import random
from typing import Callable

BOOTSTRAP_VERSION = "percentage_bootstrap_v1"
DEFAULT_N_RESAMPLES = 2000
# Arbitrary-but-documented: today's date (2026-09-06) as an int, not chosen
# to produce any particular result.
DEFAULT_SEED = 20260906


def bootstrap_ci(
    group_a: list[float],
    group_b: list[float],
    statistic_fn: Callable[[list[float], list[float]], float],
    n_resamples: int = DEFAULT_N_RESAMPLES,
    ci: float = 0.90,
    seed: int = DEFAULT_SEED,
) -> tuple[float, float]:
    """Percentage bootstrap for `statistic_fn(a, b)` (e.g. a delta of win
    rates or mean Rs between two independent samples). Resamples EACH group
    independently WITH replacement, `n_resamples` times, computes
    `statistic_fn` on each resampled pair, returns the `(low, high)`
    percentile interval at the given confidence level. Deterministic given
    `seed` (uses a local `random.Random` instance, never the global RNG
    state, so this is reproducible regardless of call order or what else
    ran before it).
    """
    rng = random.Random(seed)
    n_a, n_b = len(group_a), len(group_b)

    stats = []
    for _ in range(n_resamples):
        resampled_a = [group_a[rng.randrange(n_a)] for _ in range(n_a)]
        resampled_b = [group_b[rng.randrange(n_b)] for _ in range(n_b)]
        stats.append(statistic_fn(resampled_a, resampled_b))

    stats.sort()
    tail = (1.0 - ci) / 2.0
    low_index = round(tail * (n_resamples - 1))
    high_index = round((1.0 - tail) * (n_resamples - 1))
    return stats[low_index], stats[high_index]
