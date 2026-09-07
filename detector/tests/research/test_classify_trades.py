import os

import pytest

from research.classify_trades import ClassifiedTrade, _resolve_population_base, classify_trades
from research.reconcile_prevalence import compute_prevalence

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_PAIRS_DIR = os.path.join(_REPO_ROOT, "pairs")

# Same bounded, REAL-data tail slice as test_reconcile_prevalence.py's
# `_build_small_real_slice` -- kept as a separate copy rather than a shared
# import so each test module stays independently readable; both slices are
# built from the same source CSVs/tail sizes and are therefore identical in
# content.
_TAIL_LINES = {"M15": 4000, "H4": 600, "D1": 150}
_SOURCE_CSV = {
    "M15": os.path.join(_PAIRS_DIR, "M15", "EURUSDm_M15_202207260000_202609042045.csv"),
    "H4": os.path.join(_PAIRS_DIR, "H4", "EURUSDm_H4_202001020000_202609042000.csv"),
    "D1": os.path.join(_PAIRS_DIR, "D1", "EURUSDm_Daily_202001020000_202609040000.csv"),
}


def _build_small_real_slice(tmp_path) -> str:
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


def test_classify_trades_buckets_are_always_a_through_d(tmp_path):
    pairs_dir = _build_small_real_slice(tmp_path)

    result = classify_trades(pairs_dir, population="checkpoint_1_oos", instruments=("EURUSDm",))

    assert result, "expected at least one classified trade in this real slice"
    assert all(ct.bucket in ("A", "B", "C", "D") for ct in result)
    assert all(ct.instrument == "EURUSDm" for ct in result)


def test_classify_trades_outcome_and_r_multiple_are_consistent(tmp_path):
    pairs_dir = _build_small_real_slice(tmp_path)

    result = classify_trades(pairs_dir, population="checkpoint_1_oos", instruments=("EURUSDm",))

    for ct in result:
        assert ct.outcome in ("win", "loss", "open")
        assert (ct.r_multiple is None) == (ct.outcome == "open")


def test_classify_trades_signal_ids_are_unique(tmp_path):
    """One row per trade -- a signal_id must never repeat within one
    instrument's classified population (mirrors `_reconcile_instrument`'s
    own duplicate-signal_id assertion)."""
    pairs_dir = _build_small_real_slice(tmp_path)

    result = classify_trades(pairs_dir, population="checkpoint_1_oos", instruments=("EURUSDm",))

    signal_ids = [ct.signal_id for ct in result]
    assert len(signal_ids) == len(set(signal_ids))


def test_classify_trades_bucket_counts_match_compute_prevalence(tmp_path):
    """The refactor must not change a single classification decision --
    aggregating `classify_trades`' flat list by bucket must reproduce
    `compute_prevalence`'s own `BucketCounts.a/b/c/d` exactly, for the same
    population/config."""
    pairs_dir = _build_small_real_slice(tmp_path)

    classified = classify_trades(pairs_dir, population="checkpoint_1_oos", instruments=("EURUSDm",))
    report = compute_prevalence(
        pairs_dir, population="checkpoint_1_oos", instruments=("EURUSDm",), enforce_sanity=False
    )
    buckets = report.per_instrument["EURUSDm"].buckets

    counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    for ct in classified:
        counts[ct.bucket] += 1

    assert counts == {"A": buckets.a, "B": buckets.b, "C": buckets.c, "D": buckets.d}
    assert len(classified) == buckets.total_classified


def test_classify_trades_is_deterministic_across_repeated_runs(tmp_path):
    pairs_dir = _build_small_real_slice(tmp_path)

    first = classify_trades(pairs_dir, population="checkpoint_1_oos", instruments=("EURUSDm",))
    second = classify_trades(pairs_dir, population="checkpoint_1_oos", instruments=("EURUSDm",))

    assert first == second


def test_resolve_population_base_active_full_uses_pairs_dir_directly_no_anchor_filter():
    base, anchor_window = _resolve_population_base("/some/pairs", "active_full")
    assert base == "/some/pairs"
    assert anchor_window is None


def test_classify_trades_active_full_has_at_least_as_many_trades_as_checkpoint_1_oos(tmp_path):
    """`"active_full"` reads the same active directory as
    `"checkpoint_1_oos"` but applies no anchor-window filter -- its
    classified population must be a superset (>=) of the anchored one."""
    pairs_dir = _build_small_real_slice(tmp_path)

    full = classify_trades(pairs_dir, population="active_full", instruments=("EURUSDm",))
    anchored = classify_trades(pairs_dir, population="checkpoint_1_oos", instruments=("EURUSDm",))

    assert len(full) >= len(anchored)


def test_classified_trade_is_a_frozen_dataclass_with_expected_fields():
    ct = ClassifiedTrade(instrument="EURUSDm", signal_id="s1", bucket="A", outcome="win", r_multiple=2.0)
    assert ct.instrument == "EURUSDm"
    assert ct.signal_id == "s1"
    assert ct.bucket == "A"
    assert ct.outcome == "win"
    assert ct.r_multiple == 2.0
    with pytest.raises(Exception):
        ct.bucket = "B"  # frozen
