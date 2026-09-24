"""Groups M/N/Q (spec.md REQ-STAT-29): the Candidate admission cutoff
(`candidate_cutoff_end_utc`), the separate outcome-followup resolution
cutoff (`outcome_followup_end_utc`), and naive-UTC timestamp normalization.
`Candle.timestamp` is a naive `datetime` throughout this repo, representing
UTC by an existing repo convention (`alignment/htf_ltf.py::_daily_close`'s
docstring) — comparing naive against timezone-aware, or converting to local
time, is prohibited."""

from datetime import datetime

from adapter.errors import CandidateCutoffError
from core.candle import OHLCSeries


def require_naive(value: datetime) -> None:
    if value.tzinfo is not None:
        raise CandidateCutoffError(
            f"{value!r} carries tzinfo — this repo's timestamps are naive-UTC by convention; "
            f"never compare naive against timezone-aware, never attach tzinfo"
        )


def parse_manifest_timestamp(raw: str) -> datetime:
    """Frozen cutoff strings are `'...Z'`, explicit UTC — normalized to a
    naive datetime (drop the redundant `Z`/tzinfo marker, never attach one)."""
    text = raw[:-1] if raw.endswith("Z") else raw
    parsed = datetime.fromisoformat(text)
    require_naive(parsed)
    return parsed


def validate_retest_index_bounds(retest_index: int, ltf_series: OHLCSeries) -> None:
    """REQ-STAT-29(b): before any timestamp access, `0 <= retest_index <
    len(ltf_series.candles)` MUST hold — violation is a fail-closed error,
    never Python's negative-index wraparound behavior."""
    if not (0 <= retest_index < len(ltf_series.candles)):
        raise CandidateCutoffError(
            f"retest_index {retest_index} is out of bounds for a series of "
            f"{len(ltf_series.candles)} candles — never wrapped as a negative Python index"
        )


def candidate_event_timestamp(retest_index: int, ltf_series: OHLCSeries) -> datetime:
    """REQ-STAT-29(a): the Candidate's governing event timestamp is the
    candle AT `retest_index` (`Candidate.retest_index = K`) — NEVER the
    anchor, origin, confirmation, or fill candle."""
    validate_retest_index_bounds(retest_index, ltf_series)
    return ltf_series.candles[retest_index].timestamp


def validate_candidate_cutoff(
    retest_index: int, ltf_series: OHLCSeries, candidate_cutoff_end_utc: datetime
) -> None:
    """REQ-STAT-29(a): eligible iff `candidate_timestamp < candidate_cutoff_end_utc`
    (strict `<`) — equal or after the cutoff is NOT eligible."""
    timestamp = candidate_event_timestamp(retest_index, ltf_series)
    require_naive(timestamp)
    require_naive(candidate_cutoff_end_utc)
    if not timestamp < candidate_cutoff_end_utc:
        raise CandidateCutoffError(
            f"Candidate retest timestamp {timestamp} is not strictly before "
            f"candidate_cutoff_end_utc {candidate_cutoff_end_utc} — not eligible"
        )


def validate_exit_index_bounds(exit_index: int, ltf_series: OHLCSeries) -> None:
    """REQ-STAT-29(c): before any timestamp access, `0 <= exit_index <
    len(ltf_series.candles)` MUST hold — mirrors
    `validate_retest_index_bounds` on the candidate side. Violation is a
    fail-closed error, never Python's negative-index wraparound behavior."""
    if not (0 <= exit_index < len(ltf_series.candles)):
        raise CandidateCutoffError(
            f"exit_index {exit_index} is out of bounds for a series of "
            f"{len(ltf_series.candles)} candles — never wrapped as a negative Python index"
        )


def exit_event_timestamp(exit_index: int, ltf_series: OHLCSeries) -> datetime:
    """REQ-STAT-29(c): the Trade's governing resolution timestamp is the
    candle AT `exit_index` — bounds-checked before any access."""
    validate_exit_index_bounds(exit_index, ltf_series)
    return ltf_series.candles[exit_index].timestamp


def validate_outcome_followup_cutoff(
    exit_index: int | None, ltf_series: OHLCSeries, outcome_followup_end_utc: datetime
) -> None:
    """REQ-STAT-29(c)/(d): for a CLOSED Trade with `exit_index is not None`,
    bounds-check `exit_index` and look up its timestamp here — never assume
    a caller already computed it. No Trade resolution may consume a candle
    timestamped AFTER `outcome_followup_end_utc` (a boundary-equal exit is
    not "after" it, so it stays valid) — a Trade still unresolved at that
    boundary remains OPEN, never fetched further. `exit_index is None`
    (OPEN/NEVER_FILLED — no exit candle was consumed, and Layer-2 MUST NOT
    manufacture one) is always valid. This is a SEPARATE question from
    `validate_candidate_cutoff` — never conflated (REQ-STAT-29d)."""
    if exit_index is None:
        return
    exit_timestamp = exit_event_timestamp(exit_index, ltf_series)
    require_naive(exit_timestamp)
    require_naive(outcome_followup_end_utc)
    if exit_timestamp > outcome_followup_end_utc:
        raise CandidateCutoffError(
            f"Trade exit timestamp {exit_timestamp} consumed a candle after "
            f"outcome_followup_end_utc {outcome_followup_end_utc} — Layer-2 must not fetch later data"
        )
