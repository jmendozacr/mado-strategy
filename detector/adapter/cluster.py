"""Group L (spec.md Section K/REQ-STAT-07/28): `context_cluster_id`
reconstruction. Section K's code audit proves `signal_id -> htf_context` a
function by construction (`anchor_index` is embedded verbatim in `signal_id`
and `tag_alignment()`'s `htf_context` is a pure function of `anchor_index`
alone) — no provenance-preserving sidecar is needed. Layer-2 still owns the
fail-closed boundary: absent signal_id, an inconsistent reconstruction, and
never calling `tag_alignment()` incrementally or on a truncated series."""

from collections.abc import Sequence

from adapter.errors import ClusterReconstructionError
from alignment.htf_ltf import AlignedSignal, tag_alignment
from core.candle import OHLCSeries
from core.config import DetectorConfig

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


def reconstruct_context_clusters(
    instrument: str, htf_series: OHLCSeries, ltf_series: OHLCSeries, config: DetectorConfig
) -> dict[str, ContextClusterId]:
    """REQ-STAT-28: re-runs `tag_alignment()` on the COMPLETE, frozen series
    identical to the one that built the `Stage6Population` under evaluation
    — callers MUST pass the exact `htf_series`/`ltf_series` objects, never a
    truncated/incremental view."""
    tagged = tag_alignment(htf_series, ltf_series, config.crt_range, config.fvg, config.model1)
    return build_cluster_map(instrument, tagged)


def lookup_context_cluster(cluster_map: dict[str, ContextClusterId], signal_id: str) -> ContextClusterId:
    try:
        return cluster_map[signal_id]
    except KeyError:
        raise ClusterReconstructionError(
            f"signal_id {signal_id!r} absent from the full-series tag_alignment() reconstruction"
        ) from None
