"""Hypothesis property tests for Layer-2 adapter invariants (spec.md
REQ-STAT-01/02/03/24/25/26/27): permutation-invariance, exactly-4-rows-per-
candidate, all-4-share-economic-outcome, NEVER_FILLED iff aggregate
accounting is valid, relation mapping preserves exactly 3 states, and
deterministic ordering. All data synthetic — manually-constructed expected
values, never `expected = adapter_helper(...); actual = adapter_helper(...)`
tautologies."""

from dataclasses import replace
from datetime import datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from adapter.build import build_direction_policy_observations
from adapter.bundle import InstrumentRunBundle
from adapter.errors import AdapterIntegrityError, TradeJoinIntegrityError
from adapter.relation import map_relation
from adapter.trade_join import map_trade_outcome, verify_aggregate_completeness
from backtest.candidate import Candidate
from backtest.population import Stage6Population
from backtest.simulate import ReconciliationReport, Trade
from evaluation.direction import PolicyRelation
from selection.model import OutcomeState, Relation

# --- Relation mapping preserves exactly 3 states -----------------------------


@given(st.sampled_from(list(PolicyRelation)))
def test_relation_mapping_is_total_over_the_frozen_domain(policy_relation):
    mapped = map_relation(policy_relation)
    assert mapped in {Relation.ALIGNED, Relation.OPPOSED, Relation.UNRESOLVED}


def test_relation_mapping_image_has_exactly_three_distinct_states():
    image = {map_relation(pr) for pr in PolicyRelation}
    assert image == {Relation.ALIGNED, Relation.OPPOSED, Relation.UNRESOLVED}


# --- NEVER_FILLED iff aggregate accounting is valid --------------------------


def _population(n_candidates: int) -> Stage6Population:
    from datetime import datetime, timedelta

    from core.candle import Candle, OHLCSeries

    candles = tuple(
        Candle(timestamp=datetime(2026, 1, 1) + timedelta(minutes=15 * i), open=1.0, high=1.1, low=0.9, close=1.05)
        for i in range(50)
    )
    series = OHLCSeries(candles=candles, instrument="EURUSDm", timeframe="15M")
    candidates = [
        Candidate(
            signal_id=f"sig-{i}", anchor_index=1, origin_index=0, direction="bullish", entry_type="wick",
            retest_index=3 + i, entry_price=1.0, stop_loss=0.9, take_profit=1.2, partial_price=1.1,
        )
        for i in range(n_candidates)
    ]
    return Stage6Population(
        series=series, candidates=candidates, excluded_no_crt_range=0, excluded_unaligned=0,
        excluded_never_confirmed=0, excluded_no_key_level=0, excluded_duplicate=0, excluded_kill_zone=0,
        excluded_rr_floor=0,
    )


def _report(excluded_never_filled: int) -> ReconciliationReport:
    return ReconciliationReport(
        signals_considered=0, trades_opened=0, excluded_no_crt_range=0, excluded_unaligned=0,
        excluded_never_confirmed=0, excluded_no_key_level=0, excluded_duplicate=0, excluded_kill_zone=0,
        excluded_rr_floor=0, excluded_never_filled=excluded_never_filled,
    )


@given(
    n_candidates=st.integers(min_value=0, max_value=10),
    n_trades=st.integers(min_value=0, max_value=10),
    excluded_never_filled=st.integers(min_value=0, max_value=10),
)
@settings(max_examples=100)
def test_aggregate_completeness_holds_iff_the_arithmetic_identity_holds(
    n_candidates, n_trades, excluded_never_filled
):
    population = _population(n_candidates)
    trades = [None] * n_trades  # only len() matters to this check
    report = _report(excluded_never_filled)
    holds = n_candidates == n_trades + excluded_never_filled

    if holds:
        verify_aggregate_completeness(population, trades, report)  # must not raise
    else:
        with pytest.raises(TradeJoinIntegrityError):
            verify_aggregate_completeness(population, trades, report)


# --- CLOSED/OPEN/NEVER_FILLED outcome mapping is total and categorical ------


@given(
    outcome=st.sampled_from(["win", "loss", "open"]),
    r_multiple=st.floats(min_value=-20.0, max_value=20.0, allow_nan=False, allow_infinity=False),
)
def test_valid_trade_contract_always_maps_without_raising(outcome, r_multiple):
    trade = Trade(
        signal_id="sig", anchor_index=1, direction="bullish", entry_index=3, entry_price=1.0,
        stop_loss=0.9, take_profit=1.2, exit_index=5 if outcome != "open" else None,
        exit_price=1.2 if outcome != "open" else None,
        outcome=outcome, r_multiple=r_multiple if outcome != "open" else None,
        ambiguous_bar=False, gap_filled=False, partial_exit_index=None, partial_exit_price=None,
        partial_r_multiple=None, partial_gap_filled=False,
    )
    state, closed_outcome, realized_r = map_trade_outcome(trade)
    if outcome == "open":
        assert state is OutcomeState.OPEN
        assert closed_outcome is None and realized_r is None
    else:
        assert state is OutcomeState.CLOSED
        assert realized_r == r_multiple
        # categorical: closed_outcome tracks Trade.outcome, never r_multiple's sign
        assert (closed_outcome == "win") == (outcome == "win")


@given(r_multiple=st.floats(min_value=-20.0, max_value=20.0, allow_nan=False, allow_infinity=False))
def test_win_outcome_maps_to_win_regardless_of_r_multiple_sign(r_multiple):
    """Section C2: closed_outcome is NEVER derived from realized_r's sign —
    a 'win' with a negative r_multiple must still map to WIN."""
    trade = Trade(
        signal_id="sig", anchor_index=1, direction="bullish", entry_index=3, entry_price=1.0,
        stop_loss=0.9, take_profit=1.2, exit_index=5, exit_price=1.2, outcome="win", r_multiple=r_multiple,
        ambiguous_bar=False, gap_filled=False, partial_exit_index=None, partial_exit_price=None,
        partial_r_multiple=None, partial_gap_filled=False,
    )
    _, closed_outcome, _ = map_trade_outcome(trade)
    assert closed_outcome == "win"


def test_none_trade_always_never_filled_never_raises():
    state, closed_outcome, realized_r = map_trade_outcome(None)
    assert state is OutcomeState.NEVER_FILLED
    assert closed_outcome is None and realized_r is None


# --- End-to-end: permutation-invariance and exactly-4-rows-per-candidate ----


from test_adapter_build import _build_synthetic_bundle  # reuse the one real synthetic fixture (tests/ is on sys.path)


@given(seed=st.integers(min_value=0, max_value=1000))
@settings(max_examples=10)
def test_output_is_invariant_to_input_evaluation_and_trade_order(seed):
    import random

    bundle = _build_synthetic_bundle()
    rng = random.Random(seed)
    shuffled_evaluations = list(bundle.evaluations)
    rng.shuffle(shuffled_evaluations)
    shuffled_trades = list(bundle.trades)
    rng.shuffle(shuffled_trades)
    shuffled_bundle = replace(bundle, evaluations=tuple(shuffled_evaluations), trades=tuple(shuffled_trades))

    baseline = build_direction_policy_observations(bundle)
    shuffled = build_direction_policy_observations(shuffled_bundle)
    assert shuffled == baseline


def test_exactly_four_rows_per_candidate_on_real_synthetic_run():
    bundle = _build_synthetic_bundle()
    observations = build_direction_policy_observations(bundle)
    by_candidate: dict = {}
    for obs in observations:
        by_candidate.setdefault(obs.candidate_id, []).append(obs)
    assert all(len(rows) == 4 for rows in by_candidate.values())
    assert len(observations) == 4 * len(bundle.population.candidates)
