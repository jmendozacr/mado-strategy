import itertools
import os

import pytest

from research.reconcile_prevalence import (
    BucketCounts,
    PrevalenceSanityError,
    _aggregate,
    _dominant_bucket_fraction,
    compute_prevalence,
)

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_PAIRS_DIR = os.path.join(_REPO_ROOT, "pairs")

# A small, bounded, REAL-data slice per tier (~2 months, EURUSDm only) --
# M15's range (2026-07-09..2026-09-04) sits fully inside H4's
# (2026-04-23..2026-09-04) and D1's (2026-03-15..2026-09-04), giving
# `detect_order_blocks`/`detect_displacements` real prior Daily structure to
# work with, and includes the checkpoint anchor window
# (2026-08-20..2026-09-04) so `population="checkpoint_1_oos"` has something
# to filter to. Kept small (a few thousand rows, not the multi-year series)
# so the test stays fast -- this is real data, just bounded.
_TAIL_LINES = {"M15": 4000, "H4": 600, "D1": 150}
_SOURCE_CSV = {
    "M15": os.path.join(_PAIRS_DIR, "M15", "EURUSDm_M15_202207260000_202609042045.csv"),
    "H4": os.path.join(_PAIRS_DIR, "H4", "EURUSDm_H4_202001020000_202609042000.csv"),
    "D1": os.path.join(_PAIRS_DIR, "D1", "EURUSDm_Daily_202001020000_202609040000.csv"),
}


def _build_small_real_slice(tmp_path) -> str:
    """Writes a bounded tail slice of the real, current (non-discovery)
    EURUSDm CSVs into a temp directory shaped like `compute_prevalence`'s
    `population="checkpoint_1_oos"` layout. Skipped (not fabricated) if the
    real source CSVs are unavailable in this environment."""
    for tier, path in _SOURCE_CSV.items():
        if not os.path.isfile(path):
            pytest.skip(f"real data fixture missing: {path}")

    pairs_dir = tmp_path / "pairs"
    for tier, n_lines in _TAIL_LINES.items():
        with open(_SOURCE_CSV[tier], encoding="utf-8") as f:
            lines = f.readlines()
        header, tail = lines[0], lines[-n_lines:]

        tier_dir = pairs_dir / tier
        tier_dir.mkdir(parents=True, exist_ok=True)
        (tier_dir / f"EURUSDm_{tier}_slice.csv").write_text(header + "".join(tail), encoding="utf-8")

    return str(pairs_dir)


# ---------------------------------------------------------------------------
# _aggregate: reconciliation invariants
# ---------------------------------------------------------------------------

_MIXED_OUTCOMES = [
    "A", "A", "B", "C", "D", "D", "D",
    "excluded_no_active_ob", "excluded_no_displacement_event", "excluded_no_htf_purge_index",
]


def test_aggregate_sums_to_total_classified_exactly():
    buckets = _aggregate(_MIXED_OUTCOMES)
    assert buckets.a + buckets.b + buckets.c + buckets.d == buckets.total_classified
    assert buckets == BucketCounts(
        a=2, b=1, c=1, d=3,
        excluded_no_active_ob=1, excluded_no_displacement_event=1, excluded_no_htf_purge_index=1,
    )


def test_aggregate_is_input_ordering_independent():
    """Shuffling the order outcomes are processed in doesn't change the
    final counts -- aggregation is a sum over a set."""
    expected = _aggregate(_MIXED_OUTCOMES)
    for permutation in itertools.permutations(_MIXED_OUTCOMES):
        assert _aggregate(list(permutation)) == expected


def test_dominant_bucket_fraction_flags_the_known_bug_shape():
    """100% bucket A, as the prior buggy attempt reported -- must read as
    a dominant fraction of 1.0, the exact shape the sanity guardrail
    watches for."""
    buckets = BucketCounts(a=1000, b=0, c=0, d=0, excluded_no_active_ob=0, excluded_no_displacement_event=0, excluded_no_htf_purge_index=0)
    assert _dominant_bucket_fraction(buckets) == 1.0


def test_dominant_bucket_fraction_zero_when_nothing_classified():
    assert _dominant_bucket_fraction(BucketCounts(0, 0, 0, 0, 0, 0, 0)) == 0.0


# ---------------------------------------------------------------------------
# compute_prevalence: exercised against a small, bounded, REAL data slice
# ---------------------------------------------------------------------------


def test_compute_prevalence_on_real_slice_satisfies_reconciliation_invariants(tmp_path):
    pairs_dir = _build_small_real_slice(tmp_path)

    report = compute_prevalence(
        pairs_dir, population="checkpoint_1_oos", instruments=("EURUSDm",), enforce_sanity=False
    )

    rec = report.per_instrument["EURUSDm"]
    b = rec.buckets
    assert b.a + b.b + b.c + b.d == b.total_classified
    accounted = b.total_classified + b.excluded_no_active_ob + b.excluded_no_displacement_event + b.excluded_no_htf_purge_index
    assert accounted == rec.trades_opened
    assert report.pooled == b  # single instrument -> pooled equals that instrument's own buckets
    assert rec.raw_signals >= rec.aligned_signals >= rec.trades_opened >= 0


def test_compute_prevalence_is_deterministic_across_repeated_runs(tmp_path):
    pairs_dir = _build_small_real_slice(tmp_path)

    first = compute_prevalence(
        pairs_dir, population="checkpoint_1_oos", instruments=("EURUSDm",), enforce_sanity=False
    )
    second = compute_prevalence(
        pairs_dir, population="checkpoint_1_oos", instruments=("EURUSDm",), enforce_sanity=False
    )

    assert first == second


def test_compute_prevalence_raises_prevalence_sanity_error_when_enforced_on_a_too_small_slice(tmp_path):
    """The pooled reference range for checkpoint_1_oos (59-60) is
    calibrated against all 3 real instruments summed -- a single-instrument
    slice's pooled total legitimately falls below even the 3x-padded floor,
    which is exactly what `enforce_sanity=True` (the default a real run
    uses) must catch and refuse to report."""
    pairs_dir = _build_small_real_slice(tmp_path)

    with pytest.raises(PrevalenceSanityError):
        compute_prevalence(pairs_dir, population="checkpoint_1_oos", instruments=("EURUSDm",))
