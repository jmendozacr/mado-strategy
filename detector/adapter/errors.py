"""Layer-2 error taxonomy (spec.md Section M, REQ-STAT-20/24/25/26/27/28/29/30).

One base type plus one concrete type per fail-closed category Section M's
canonical `data_quality_fail_closed` table assigns to Layer-2, so a caller
can catch narrowly (a specific join defect) or broadly (`AdapterIntegrityError`,
"any Layer-2 integrity failure") without ever needing a bare `Exception`.
"""


class AdapterIntegrityError(Exception):
    """Base type for every Layer-2 fail-closed condition. Never raised
    directly — always one of the concrete categories below."""


class CandidateReconciliationError(AdapterIntegrityError):
    """REQ-STAT-26: a Candidate's DirectionEvaluation rows are not exactly
    4, one per `FROZEN_POLICY_IDS` member, with identical
    `(instrument, timeframe, signal_id, retest_index)` across all 4 — or an
    evaluation row cannot be reconciled against any Candidate at all
    (Section C's join-integrity table, condition 1 / REQ-STAT-01/02)."""


class RelationMappingError(CandidateReconciliationError):
    """REQ-STAT-27: `evaluation.direction.PolicyRelation` carries a value
    outside the explicit, exhaustive ALIGNED/OPPOSED/UNRESOLVED mapping."""


class TradeJoinIntegrityError(AdapterIntegrityError):
    """REQ-STAT-24 / Section M #1: `TradeJoinKey -> CandidateIdentity` or
    `TradeJoinKey -> Trade` is not a function within one instrument's run."""


class TradeOutcomeContractError(AdapterIntegrityError):
    """Section M #2/#3/#7: a `Trade`'s outcome/r_multiple shape violates its
    own frozen contract (win/loss without a finite r_multiple, open with a
    non-None r_multiple, an unexpected outcome string, a non-finite CLOSED
    r_multiple, or a structurally impossible zero-risk R)."""


class ClusterReconstructionError(AdapterIntegrityError):
    """REQ-STAT-28: the `signal_id -> htf_context` lookup (via a full-series
    `tag_alignment()` re-run) failed to resolve, or resolved inconsistently,
    for a signal_id Layer-2 needed to cluster."""


class CandidateCutoffError(AdapterIntegrityError):
    """REQ-STAT-29: a Candidate's `retest_index` is out of the LTF series'
    bounds, or its governing timestamp violates the frozen candidate-cutoff
    or outcome-followup-cutoff boundary."""


class DatasetIntegrityError(AdapterIntegrityError):
    """Section M #4/#5/#6/#12: duplicate candles/timestamps/keys, missing
    files/candles, boundary gaps affecting prefix/setup/outcome, or
    incomplete-session dropping, detected during dataset/manifest
    validation."""


class FrozenArtifactMismatchError(AdapterIntegrityError):
    """Section M #8 / REQ-STAT-19/31/32: a dataset or protocol file's SHA-256
    does not match the manifest's declared hash, or a protected path does
    not match the recorded execution-baseline commit."""
