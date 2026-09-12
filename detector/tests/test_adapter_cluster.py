"""Group L (spec.md Section K/REQ-STAT-07/28): cluster reconstruction via a
full-series-only `tag_alignment()` re-run, joined by signal_id. Section K's
code audit proves `signal_id -> htf_context` a function by construction —
these tests still guard the fail-closed boundary Layer-2 owns: absent
signal_id, an inconsistent reconstruction, and never truncating the series."""

from datetime import datetime, timedelta

import pytest

from adapter.cluster import build_cluster_map, lookup_context_cluster, reconstruct_context_clusters
from adapter.errors import ClusterReconstructionError
from alignment.htf_ltf import AlignedSignal
from core.candle import Candle, OHLCSeries
from core.config import DetectorConfig
from core.results import DetectionStatus
from entries.model1 import Model1Signal
from primitives.crt_range import CRTRange


def _signal(origin_index: int, anchor_index: int) -> Model1Signal:
    return Model1Signal(
        anchor_index=anchor_index, direction="bullish", purge_target=1.0,
        confirmation_type="purge_engulf", entry_type="wick", entry_price=1.0,
        retest_index=anchor_index + 2, status=DetectionStatus.CONFIRMED,
        confirmation_index=anchor_index + 1, origin_index=origin_index,
    )


def _crt_range(start_index: int, end_index: int, resolved_at_index: int) -> CRTRange:
    return CRTRange(
        model="2-candle", high=1.2, low=0.8, start_index=start_index, end_index=end_index,
        resolution="true_break", resolved_at_index=resolved_at_index,
    )


def _tagged(signal: Model1Signal, htf_context: CRTRange | None, aligned: str = "aligned") -> AlignedSignal:
    return AlignedSignal(ltf_signal=signal, htf_context=htf_context, aligned=aligned)


# --- build_cluster_map: the pure join, no I/O ---------------------------------


def test_cluster_id_shape_is_instrument_start_end_resolved():
    signal = _signal(0, 1)
    htf_context = _crt_range(2, 9, 8)
    mapping = build_cluster_map("EURUSDm", [_tagged(signal, htf_context)])
    assert mapping[signal.signal_id] == ("EURUSDm", 2, 9, 8)


def test_unaligned_signal_has_no_cluster_entry():
    signal = _signal(0, 1)
    mapping = build_cluster_map("EURUSDm", [_tagged(signal, None, aligned="unaligned")])
    assert signal.signal_id not in mapping


def test_duplicate_signal_id_with_inconsistent_htf_context_fails_closed():
    """A deliberately-corrupted synthetic input: the same signal_id
    reconstructing to two different htf_context values — never possible per
    Section K's proof, but Layer-2 must still guard the boundary."""
    signal = _signal(0, 1)
    tagged_a = _tagged(signal, _crt_range(2, 9, 8))
    tagged_b = _tagged(signal, _crt_range(3, 10, 9))  # same signal_id, different context
    with pytest.raises(ClusterReconstructionError):
        build_cluster_map("EURUSDm", [tagged_a, tagged_b])


def test_absent_signal_id_lookup_fails_closed():
    mapping = build_cluster_map("EURUSDm", [])
    with pytest.raises(ClusterReconstructionError):
        lookup_context_cluster(mapping, "no-such-signal")


def test_missing_htf_context_means_absent_from_map_and_lookup_fails_closed():
    signal = _signal(0, 1)
    mapping = build_cluster_map("EURUSDm", [_tagged(signal, None, aligned="unaligned")])
    with pytest.raises(ClusterReconstructionError):
        lookup_context_cluster(mapping, signal.signal_id)


# --- reconstruct_context_clusters: the full-series-only wrapper --------------


def _series(instrument: str, timeframe: str, size: int) -> OHLCSeries:
    candles = tuple(
        Candle(
            timestamp=datetime(2026, 1, 1) + timedelta(minutes=15 * i) if timeframe == "15M"
            else datetime(2026, 1, 1) + timedelta(hours=4 * i),
            open=1.0, high=1.1, low=0.9, close=1.05,
        )
        for i in range(size)
    )
    return OHLCSeries(candles=candles, instrument=instrument, timeframe=timeframe)


def test_reconstruct_delegates_to_tag_alignment_on_full_series():
    htf_series = _series("EURUSDm", "4H", 5)
    ltf_series = _series("EURUSDm", "15M", 5)
    # Featureless synthetic candles produce no detected signals — this
    # confirms the wrapper runs tag_alignment end-to-end without raising,
    # not that any particular signal is found.
    mapping = reconstruct_context_clusters("EURUSDm", htf_series, ltf_series, DetectorConfig())
    assert mapping == {}


def test_cluster_module_never_truncates_the_series():
    """REQ-STAT-28: Layer-2 MUST NOT call `tag_alignment()` incrementally or
    on a truncated series. Structural guard: the module must never slice a
    series (`.up_to(` / `.candles[`) before handing it to `tag_alignment`."""
    import inspect

    import adapter.cluster as cluster_module

    source = inspect.getsource(cluster_module)
    assert ".up_to(" not in source
    assert ".candles[" not in source
