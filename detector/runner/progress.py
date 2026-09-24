"""Closed enum of progress events.

No member carries any statistical value: no realized_r, closed_outcome,
relation distribution, MeanR, WR, EST-B, CI, instrument delta, nomination,
candidate count, trade count, or any per-policy figure."""

from enum import StrEnum


class ProgressEvent(StrEnum):
    PREFLIGHT_PASSED = "PREFLIGHT_PASSED"
    INSTRUMENT_DATASET_VALIDATED = "INSTRUMENT_DATASET_VALIDATED"
    INSTRUMENT_BUNDLE_VALIDATED = "INSTRUMENT_BUNDLE_VALIDATED"
    ALL_INSTRUMENTS_VALIDATED = "ALL_INSTRUMENTS_VALIDATED"
    STATISTICS_COMPLETE = "STATISTICS_COMPLETE"
    PUBLISHED = "PUBLISHED"
