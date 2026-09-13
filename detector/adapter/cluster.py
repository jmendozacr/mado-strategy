"""`context_cluster_id` derivation from caller-supplied `AlignedSignal.htf_context`.
`build_cluster_map` omits signals with null htf_context and raises on conflicting
non-null contexts for the same signal_id. `lookup_context_cluster` raises for any
signal_id absent from the map, including those omitted due to null htf_context."""

from collections.abc import Sequence

from adapter.errors import ClusterReconstructionError
from alignment.htf_ltf import AlignedSignal

ContextClusterId = tuple[str, int, int, int]


def build_cluster_map(instrument: str, tagged_signals: Sequence[AlignedSignal]) -> dict[str, ContextClusterId]:
    """The pure join (REQ-STAT-07): `context_cluster_id = (instrument,
    htf_context.start_index, htf_context.end_index,
    htf_context.resolved_at_index)`. An unaligned/no-context signal
    contributes no entry — it is never eligible for clustering."""
    mapping: dict[str, ContextClusterId] = {}
    for tagged in tagged_signals:
        if tagged.htf_context is None:
            continue
        signal_id = tagged.ltf_signal.signal_id
        cluster_id: ContextClusterId = (
            instrument,
            tagged.htf_context.start_index,
            tagged.htf_context.end_index,
            tagged.htf_context.resolved_at_index,
        )
        existing = mapping.get(signal_id)
        if existing is not None and existing != cluster_id:
            raise ClusterReconstructionError(
                f"signal_id {signal_id!r} reconstructs to inconsistent htf_context: "
                f"{existing} vs {cluster_id} — signal_id -> htf_context must be a function"
            )
        mapping[signal_id] = cluster_id
    return mapping


def lookup_context_cluster(cluster_map: dict[str, ContextClusterId], signal_id: str) -> ContextClusterId:
    try:
        return cluster_map[signal_id]
    except KeyError:
        raise ClusterReconstructionError(
            f"signal_id {signal_id!r} absent from the supplied aligned_signals — "
            f"every candidate must have an AlignedSignal with a non-null htf_context"
        ) from None
