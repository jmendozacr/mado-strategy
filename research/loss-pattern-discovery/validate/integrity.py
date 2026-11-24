"""Integrity, chronology and provenance validators for extracted EventRecords.

These do not fix anything -- a record that fails a check is reported, never
silently corrected or dropped, so selection bias from exclusion stays visible
(see docs/04-methodology-safeguards.md, "Evidence eligibility").
"""
from __future__ import annotations

from dataclasses import dataclass

from schema.events import EventRecord, Outcome


@dataclass(frozen=True)
class ValidationIssue:
    event_id: str
    check: str
    detail: str


def check_temporal_ordering(record: EventRecord) -> list[ValidationIssue]:
    """Defense-in-depth re-check of what the schema's field-group separation
    already enforces structurally: no stage may be timestamped after a later
    stage's own timestamp."""
    issues: list[ValidationIssue] = []
    op = record.operation
    stamps = [
        ("feeder_ref_available_ts", record.features_pre_entry.feeder_ref_available_ts),
        ("activation_instant_ts", record.features_pre_entry.activation_instant_ts),
        ("model1_available_ts", record.features_pre_entry.model1_available_ts),
        ("order_placed_ts", record.features_pre_entry.order_placed_ts),
        ("entry_ts", op.entry_ts),
        ("exit_ts", op.exit_ts),
    ]
    present = [(name, ts) for name, ts in stamps if ts is not None]
    for (name_a, ts_a), (name_b, ts_b) in zip(present, present[1:]):
        if ts_a > ts_b:
            issues.append(
                ValidationIssue(
                    event_id=record.identification.event_id,
                    check="temporal_ordering",
                    detail=f"{name_a}={ts_a} is after {name_b}={ts_b}",
                )
            )
    return issues


def check_price_side_consistency(record: EventRecord) -> list[ValidationIssue]:
    """The stop loss and take profit must sit on the side of entry_price that
    `original_direction` implies -- otherwise the row cannot be a causally
    coherent trade plan."""
    op = record.operation
    direction = record.identification.original_direction
    issues: list[ValidationIssue] = []
    if direction == "bullish":
        ok = op.stop_loss < op.entry_price < op.take_profit
    elif direction == "bearish":
        ok = op.take_profit < op.entry_price < op.stop_loss
    else:
        issues.append(
            ValidationIssue(
                event_id=record.identification.event_id,
                check="price_side_consistency",
                detail=f"unrecognized direction {direction!r}",
            )
        )
        return issues
    if not ok:
        issues.append(
            ValidationIssue(
                event_id=record.identification.event_id,
                check="price_side_consistency",
                detail=(
                    f"direction={direction} entry={op.entry_price} "
                    f"sl={op.stop_loss} tp={op.take_profit}"
                ),
            )
        )
    return issues


def check_outcome_r_sign(record: EventRecord) -> list[ValidationIssue]:
    """A loss should carry a non-positive R and a win a non-negative R. A
    violation does not necessarily mean the row is wrong (partial exits can
    blend signs) but it must be surfaced, never assumed away."""
    op = record.operation
    issues: list[ValidationIssue] = []
    if op.r_multiple is None:
        # Right-censored (still-open) trades have no r_multiple yet -- that
        # is expected, not a defect; nothing to check here.
        return issues
    if op.outcome is Outcome.LOSS and op.r_multiple > 0:
        issues.append(
            ValidationIssue(
                event_id=record.identification.event_id,
                check="outcome_r_sign",
                detail=f"outcome=loss but r_multiple={op.r_multiple}",
            )
        )
    if op.outcome is Outcome.WIN and op.r_multiple < 0:
        issues.append(
            ValidationIssue(
                event_id=record.identification.event_id,
                check="outcome_r_sign",
                detail=f"outcome=win but r_multiple={op.r_multiple}",
            )
        )
    return issues


def check_duplicate_ids(records: list[EventRecord]) -> list[ValidationIssue]:
    seen: dict[str, int] = {}
    issues: list[ValidationIssue] = []
    for record in records:
        event_id = record.identification.event_id
        seen[event_id] = seen.get(event_id, 0) + 1
    for event_id, count in seen.items():
        if count > 1:
            issues.append(
                ValidationIssue(
                    event_id=event_id,
                    check="duplicate_id",
                    detail=f"appears {count} times in the same source",
                )
            )
    return issues


def validate_all(records: list[EventRecord]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for record in records:
        issues.extend(check_temporal_ordering(record))
        issues.extend(check_price_side_consistency(record))
        issues.extend(check_outcome_r_sign(record))
    issues.extend(check_duplicate_ids(records))
    return issues
