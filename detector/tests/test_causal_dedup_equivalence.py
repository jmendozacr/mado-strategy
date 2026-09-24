"""Finding #3 (human review, iteration 2): `causal.signals`' own survivor
selection (`min(admissible, key=lambda pair: pair[0].start_index)`) has
never been independently tested for equivalence against legacy
`backtest.population._dedup`'s `min(group, key=origin_index)` rule -- the
original implementation brief required exactly this proof when a parallel
helper is created instead of reusing `_dedup` directly.

Scope: REQ-CAUSAL-11 already proves that, for a fixed `(anchor_index,
direction)` within one `causal_purge_engulf_signals` call, `_track_anchor`
is a pure function of `(candles, anchor_index, direction, config)` alone --
so every competitor sharing `(anchor_index, direction)` necessarily also
shares `entry_type`/`entry_price`/`retest_index`, differing only in
`origin_index`/`purge_target` (which encode which source range produced
it). This test's fixtures hold that invariant fixed (as the real pipeline
always does) and vary only `origin_index` across competitors -- proving
the two `min(origin_index)` rules agree is then a proof about the survivor
rule itself, not an artefact of engineering the fixture to dodge
`_dedup`'s finer `(anchor_index, direction, entry_price, entry_type)` key.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from backtest.candidate import Candidate
from backtest.population import _dedup
from core.config import Model1Config
from core.results import DetectionStatus
from entries.model1 import Model1Signal
from primitives.crt_range import CRTRange

_SHARED = dict(
    anchor_index=5,
    direction="bearish",
    purge_target=1.1000,
    confirmation_type="purge_engulf",
    entry_type="wick",
    entry_price=1.0950,
    retest_index=8,
    status=DetectionStatus.CONFIRMED,
    confirmation_index=8,
)


def _pair(origin_index: int) -> tuple[CRTRange, Model1Signal]:
    source_range = CRTRange(
        model="2-candle", high=1.2, low=1.1, start_index=origin_index, end_index=origin_index + 1,
        resolution="true_break", resolved_at_index=origin_index + 1,
    )
    signal = Model1Signal(origin_index=origin_index, **_SHARED)
    return source_range, signal


def _candidate(origin_index: int) -> Candidate:
    signal = Model1Signal(origin_index=origin_index, **_SHARED)
    return Candidate(
        signal_id=signal.signal_id,
        anchor_index=signal.anchor_index,
        origin_index=signal.origin_index,
        direction=signal.direction,
        entry_type=signal.entry_type,
        retest_index=signal.retest_index,
        entry_price=signal.entry_price,
        stop_loss=0.9000,
        take_profit=1.1500,
        partial_price=1.0225,
    )


def _causal_survivor(origin_indices: list[int]) -> Model1Signal:
    pairs = [_pair(i) for i in origin_indices]
    _, winner = min(pairs, key=lambda pair: pair[0].start_index)
    return winner


def _legacy_survivor(origin_indices: list[int]) -> Candidate:
    candidates = [_candidate(i) for i in origin_indices]
    survivors, excluded = _dedup(candidates)
    assert len(survivors) == 1  # fixture guarantee: all share _dedup's own grouping key
    assert excluded == len(origin_indices) - 1
    return survivors[0]


def _assert_equivalent(causal_winner: Model1Signal, legacy_winner: Candidate) -> None:
    assert causal_winner.origin_index == legacy_winner.origin_index
    assert causal_winner.signal_id == legacy_winner.signal_id
    assert causal_winner.anchor_index == legacy_winner.anchor_index
    assert causal_winner.direction == legacy_winner.direction
    assert causal_winner.entry_type == legacy_winner.entry_type
    assert causal_winner.entry_price == legacy_winner.entry_price
    assert causal_winner.retest_index == legacy_winner.retest_index


def test_deterministic_three_way_competition_agrees_with_legacy_dedup():
    origin_indices = [7, 2, 5]
    causal_winner = _causal_survivor(origin_indices)
    legacy_winner = _legacy_survivor(origin_indices)
    assert causal_winner.origin_index == 2  # sanity: lowest wins
    _assert_equivalent(causal_winner, legacy_winner)


def test_deterministic_two_way_tie_break_boundary_agrees_with_legacy_dedup():
    origin_indices = [0, 1]
    _assert_equivalent(_causal_survivor(origin_indices), _legacy_survivor(origin_indices))


def test_single_competitor_trivially_agrees_with_legacy_dedup():
    origin_indices = [3]
    _assert_equivalent(_causal_survivor(origin_indices), _legacy_survivor(origin_indices))


@given(
    origin_indices=st.lists(
        st.integers(min_value=0, max_value=200), min_size=1, max_size=12, unique=True
    )
)
@settings(max_examples=100)
def test_causal_survivor_selection_agrees_with_legacy_dedup_property(origin_indices):
    causal_winner = _causal_survivor(origin_indices)
    legacy_winner = _legacy_survivor(origin_indices)
    assert causal_winner.origin_index == min(origin_indices)
    _assert_equivalent(causal_winner, legacy_winner)
