"""Group 3 (REQ-CAUSAL-07): LTF R-strict admission — a CRT range `R` may
produce/compete for a signal at event index `K` iff
`R.resolved_at_index <= K - 1`. Four explicit boundary cases."""

import pytest

from causal.signals import r_strict_admissible
from primitives.crt_range import CRTRange


def _range_resolving_at(index: int) -> CRTRange:
    return CRTRange(
        model="2-candle", high=1.2, low=1.1, start_index=0, end_index=index,
        resolution="true_break", resolved_at_index=index,
    )


K = 10


@pytest.mark.parametrize(
    "resolved_at_index, expected",
    [
        (K - 2, True),   # resolves well before K -> eligible
        (K - 1, True),   # resolves exactly one candle before K -> eligible (R-strict boundary)
        (K, False),      # resolves ON K -> ineligible (R-strict, not R-loose)
        (K + 1, False),  # resolves after K -> ineligible
    ],
)
def test_r_strict_boundary(resolved_at_index, expected):
    source_range = _range_resolving_at(resolved_at_index)
    assert r_strict_admissible(source_range, retest_index=K) is expected


def test_r_strict_vacuously_admissible_when_no_retest_event():
    """A signal that never retests (`retest_index is None`) has no K to
    test R-strict against — it can never become a Candidate downstream
    (REQ-CAUSAL-04 governs its exclusion, not this predicate)."""
    source_range = _range_resolving_at(999)
    assert r_strict_admissible(source_range, retest_index=None) is True
