"""Block bootstrap utilities for dependent (near-in-time) observations.

Events close together in time, or sharing a market episode, are not
independent draws; a naive i.i.d. bootstrap would understate uncertainty.
This module resamples at the BLOCK level, where a block is one
`(instrument, iso_calendar_week)` group -- a single, fixed choice declared
here BEFORE any Phase-2 result was inspected, not tuned per metric.

Determinism: every resample goes through an explicit `random.Random(seed)`
instance, never the global `random` module.
"""
from __future__ import annotations

import random
from collections import defaultdict
from datetime import datetime
from typing import Callable

BLOCK_UNIT = "instrument_iso_calendar_week"
DEFAULT_SEED = 20261124
DEFAULT_RESAMPLES = 2000
DEFAULT_CI = 0.90


def block_key(instrument: str, ts: datetime) -> tuple[str, int, int]:
    iso = ts.isocalendar()
    return (instrument, iso[0], iso[1])


def _percentile_ci(resampled_stats: list[float], ci: float) -> tuple[float, float]:
    resampled_stats = sorted(resampled_stats)
    n = len(resampled_stats)
    alpha = (1 - ci) / 2
    lo_idx = max(int(alpha * n), 0)
    hi_idx = min(int((1 - alpha) * n), n - 1)
    return resampled_stats[lo_idx], resampled_stats[hi_idx]


def block_bootstrap_ci(
    values_with_blocks: list[tuple[float, tuple]],
    statistic: Callable[[list[float]], float],
    n_resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_SEED,
    ci: float = DEFAULT_CI,
) -> dict:
    """Resample whole blocks with replacement; recompute `statistic` over the
    pooled resampled values each time; report the percentile CI."""
    blocks: dict[tuple, list[float]] = defaultdict(list)
    for value, block in values_with_blocks:
        blocks[block].append(value)
    block_list = list(blocks.values())
    n_total = sum(len(vs) for vs in block_list)
    if not block_list:
        return {
            "n": 0, "n_blocks": 0, "point_estimate": None,
            "ci_low": None, "ci_high": None, "n_resamples": n_resamples, "ci_level": ci,
        }

    rng = random.Random(seed)
    point_estimate = statistic([v for vs in block_list for v in vs])
    resampled_stats = []
    for _ in range(n_resamples):
        chosen = [block_list[rng.randrange(len(block_list))] for _ in range(len(block_list))]
        pooled = [v for vs in chosen for v in vs]
        resampled_stats.append(statistic(pooled))
    ci_low, ci_high = _percentile_ci(resampled_stats, ci)
    return {
        "n": n_total, "n_blocks": len(block_list), "point_estimate": point_estimate,
        "ci_low": ci_low, "ci_high": ci_high, "n_resamples": n_resamples, "ci_level": ci,
    }


def block_bootstrap_paired_diff_ci(
    paired_values_with_blocks: list[tuple[float, float, tuple]],
    statistic: Callable[[list[float]], float],
    n_resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_SEED,
    ci: float = DEFAULT_CI,
) -> dict:
    """Each entry is (sl_value, matched_control_value, block) for one real
    event / matched control pair. Resamples whole blocks of PAIRS together
    (preserving the 1:1 match), then reports `statistic(sl) - statistic(control)`
    over each resample, as a percentile CI on the difference."""
    blocks: dict[tuple, list[tuple[float, float]]] = defaultdict(list)
    for sl_value, control_value, block in paired_values_with_blocks:
        blocks[block].append((sl_value, control_value))
    block_list = list(blocks.values())
    n_total = sum(len(pairs) for pairs in block_list)
    if not block_list:
        return {
            "n": 0, "n_blocks": 0, "point_estimate": None,
            "ci_low": None, "ci_high": None, "n_resamples": n_resamples, "ci_level": ci,
        }

    rng = random.Random(seed)

    def _diff(pairs: list[tuple[float, float]]) -> float:
        return statistic([p[0] for p in pairs]) - statistic([p[1] for p in pairs])

    point_estimate = _diff([pair for block in block_list for pair in block])
    resampled_diffs = []
    for _ in range(n_resamples):
        chosen = [block_list[rng.randrange(len(block_list))] for _ in range(len(block_list))]
        pooled = [pair for block in chosen for pair in block]
        resampled_diffs.append(_diff(pooled))
    ci_low, ci_high = _percentile_ci(resampled_diffs, ci)
    return {
        "n": n_total, "n_blocks": len(block_list), "point_estimate": point_estimate,
        "ci_low": ci_low, "ci_high": ci_high, "n_resamples": n_resamples, "ci_level": ci,
    }


def median(values: list[float]) -> float:
    if not values:
        return float("nan")
    values = sorted(values)
    n = len(values)
    mid = n // 2
    return values[mid] if n % 2 else (values[mid - 1] + values[mid]) / 2


def proportion_true(values: list[float]) -> float:
    """`values` are 0.0/1.0 indicators; `statistic` callables must take a
    flat list, so boolean flags are converted to floats before pooling."""
    if not values:
        return float("nan")
    return sum(values) / len(values)


def quantiles(values: list[float], qs: tuple[float, ...] = (0.1, 0.25, 0.5, 0.75, 0.9)) -> dict[float, float]:
    if not values:
        return {q: float("nan") for q in qs}
    ordered = sorted(values)
    n = len(ordered)
    result = {}
    for q in qs:
        idx = min(int(q * n), n - 1)
        result[q] = ordered[idx]
    return result
