"""Package skeleton, error types, progress enum.

Structural assertions that the runner package exists, progress events
carry no statistical value, and error types are distinct."""

import importlib
import inspect

import pytest


def test_runner_package_importable():
    import runner

    assert hasattr(runner, "__name__")


def test_error_types_are_distinct_exceptions():
    from runner.errors import (
        AuthorizationError,
        PerformanceQualificationError,
        ReproducibilityError,
    )

    assert issubclass(AuthorizationError, Exception)
    assert issubclass(ReproducibilityError, Exception)
    assert issubclass(PerformanceQualificationError, Exception)
    assert AuthorizationError is not ReproducibilityError
    assert AuthorizationError is not PerformanceQualificationError


def test_progress_enum_members_exist():
    from runner.progress import ProgressEvent

    expected = {
        "PREFLIGHT_PASSED",
        "INSTRUMENT_DATASET_VALIDATED",
        "INSTRUMENT_BUNDLE_VALIDATED",
        "ALL_INSTRUMENTS_VALIDATED",
        "STATISTICS_COMPLETE",
        "PUBLISHED",
    }
    actual = {e.name for e in ProgressEvent}
    assert actual == expected


def test_progress_enum_no_statistical_fields():
    """Progress events must carry no statistical value.
    Verify no member name or value contains statistical terms."""
    from runner.progress import ProgressEvent

    forbidden_terms = [
        "realized_r", "closed_outcome", "mean_r", "wr", "est_b",
        "ci_lower", "ci_upper", "instrument_delta", "nomination",
        "candidate_count", "trade_count",
    ]
    for event in ProgressEvent:
        for term in forbidden_terms:
            assert term not in event.name.lower(), f"{event.name} contains forbidden term {term}"
            assert term not in str(event.value).lower(), f"{event.value} contains forbidden term {term}"


def test_progress_event_is_str_enum():
    from enum import StrEnum

    from runner.progress import ProgressEvent

    assert issubclass(ProgressEvent, StrEnum)
