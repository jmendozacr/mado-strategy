"""`context_cluster_id` derivation from caller-supplied `AlignedSignal.htf_context`.
Signals with null htf_context are omitted from the map; conflicting non-null
contexts for the same signal_id raise during map construction. Lookup raises for
any signal_id absent from the map, including those omitted due to null htf_context."""

import pytest

from adapter.cluster import build_cluster_map, lookup_context_cluster
from adapter.errors import ClusterReconstructionError
from alignment.htf_ltf import AlignedSignal
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


def test_adapter_cluster_does_not_reference_tag_alignment():
    """AST guard: cluster.py must not import or attribute-reference tag_alignment."""
    import ast
    import importlib.util
    import pathlib

    spec = importlib.util.find_spec("adapter.cluster")
    source = pathlib.Path(spec.origin).read_text()
    tree = ast.parse(source)
    imported = [
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    ]
    attributes = [
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
    ]
    assert "tag_alignment" not in imported
    assert "tag_alignment" not in attributes
