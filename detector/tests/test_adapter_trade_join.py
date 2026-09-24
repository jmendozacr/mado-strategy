"""Groups E/F/G/H/I/J (spec.md Section A/D/B/C2, REQ-STAT-24/25/04): the
TradeJoinKey functional-dependency proof, aggregate Trade completeness before
trusting NEVER_FILLED, and the CLOSED/OPEN/NEVER_FILLED outcome mapping —
including deliberately-corrupted synthetic Trade contract violations."""

import math

import pytest

from adapter.errors import TradeJoinIntegrityError, TradeOutcomeContractError
from adapter.trade_join import (
    TradeJoinKey,
    map_trade_outcome,
    prove_functional_join,
    trade_join_key,
    verify_aggregate_completeness,
)
from backtest.candidate import Candidate
from backtest.population import Stage6Population
from backtest.simulate import ReconciliationReport, Trade
from selection.model import CandidateIdentity, ClosedTradeOutcome, OutcomeState


def _identity(signal_id: str = "sig-1", retest_index: int = 3, instrument: str = "EURUSDm") -> CandidateIdentity:
    return CandidateIdentity(instrument=instrument, timeframe="15M", signal_id=signal_id, retest_index=retest_index)


def _trade(signal_id: str = "sig-1", outcome: str = "win", r_multiple: float | None = 1.5) -> Trade:
    return Trade(
        signal_id=signal_id, anchor_index=1, direction="bullish", entry_index=3, entry_price=1.0,
        stop_loss=0.9, take_profit=1.3, exit_index=5 if outcome != "open" else None,
        exit_price=1.3 if outcome != "open" else None, outcome=outcome, r_multiple=r_multiple,
        ambiguous_bar=False, gap_filled=False, partial_exit_index=None, partial_exit_price=None,
        partial_r_multiple=None, partial_gap_filled=False,
    )


def _report(excluded_never_filled: int = 0) -> ReconciliationReport:
    return ReconciliationReport(
        signals_considered=0, trades_opened=0, excluded_no_crt_range=0, excluded_unaligned=0,
        excluded_never_confirmed=0, excluded_no_key_level=0, excluded_duplicate=0, excluded_kill_zone=0,
        excluded_rr_floor=0, excluded_never_filled=excluded_never_filled,
    )


def _candidate(retest_index: int = 3, signal_id: str = "sig-1") -> Candidate:
    return Candidate(
        signal_id=signal_id, anchor_index=1, origin_index=0, direction="bullish", entry_type="wick",
        retest_index=retest_index, entry_price=1.0, stop_loss=0.9, take_profit=1.3, partial_price=1.15,
    )


def _population(candidates) -> Stage6Population:
    from datetime import datetime, timedelta
    from core.candle import Candle, OHLCSeries

    candles = tuple(
        Candle(timestamp=datetime(2026, 1, 1) + timedelta(minutes=15 * i), open=1.0, high=1.1, low=0.9, close=1.05)
        for i in range(10)
    )
    series = OHLCSeries(candles=candles, instrument="EURUSDm", timeframe="15M")
    return Stage6Population(
        series=series, candidates=list(candidates), excluded_no_crt_range=0, excluded_unaligned=0,
        excluded_never_confirmed=0, excluded_no_key_level=0, excluded_duplicate=0, excluded_kill_zone=0,
        excluded_rr_floor=0,
    )


# --- Group E: TradeJoinKey functional-dependency proof -----------------------


def test_trade_join_key_is_reduction_of_candidate_identity():
    identity = _identity()
    assert trade_join_key(identity) == TradeJoinKey(instrument="EURUSDm", signal_id="sig-1")


def test_proves_both_functions_when_run_is_clean():
    identities = [_identity(signal_id="a"), _identity(signal_id="b")]
    trades = [_trade(signal_id="a"), _trade(signal_id="b")]
    key_to_identity, key_to_trade = prove_functional_join(identities, trades, "EURUSDm")
    assert len(key_to_identity) == 2
    assert len(key_to_trade) == 2


def test_two_candidates_collapsing_to_same_key_fails_closed():
    """Two distinct CandidateIdentity (different retest_index) reducing to
    the same TradeJoinKey — TradeJoinKey -> CandidateIdentity is not a
    function."""
    identities = [_identity(signal_id="a", retest_index=3), _identity(signal_id="a", retest_index=7)]
    with pytest.raises(TradeJoinIntegrityError):
        prove_functional_join(identities, [], "EURUSDm")


def test_duplicate_trade_for_same_key_fails_closed():
    identities = [_identity(signal_id="a")]
    trades = [_trade(signal_id="a"), _trade(signal_id="a")]
    with pytest.raises(TradeJoinIntegrityError):
        prove_functional_join(identities, trades, "EURUSDm")


def test_orphan_trade_with_no_matching_candidate_fails_closed():
    identities = [_identity(signal_id="a")]
    trades = [_trade(signal_id="orphan-signal")]
    with pytest.raises(TradeJoinIntegrityError):
        prove_functional_join(identities, trades, "EURUSDm")


# --- Group F: aggregate completeness before NEVER_FILLED --------------------


def test_aggregate_completeness_holds():
    population = _population([_candidate(signal_id="a"), _candidate(signal_id="b")])
    trades = [_trade(signal_id="a")]
    report = _report(excluded_never_filled=1)
    verify_aggregate_completeness(population, trades, report)  # must not raise


def test_broken_accounting_fails_closed_never_becomes_never_filled():
    population = _population([_candidate(signal_id="a"), _candidate(signal_id="b")])
    trades = [_trade(signal_id="a")]
    report = _report(excluded_never_filled=0)  # 2 != 1 + 0
    with pytest.raises(TradeJoinIntegrityError):
        verify_aggregate_completeness(population, trades, report)


# --- Group G: NEVER_FILLED ----------------------------------------------------


def test_no_trade_maps_to_never_filled():
    state, closed_outcome, realized_r = map_trade_outcome(None)
    assert state is OutcomeState.NEVER_FILLED
    assert closed_outcome is None
    assert realized_r is None


# --- Group H: CLOSED WIN/LOSS --------------------------------------------------


def test_win_trade_maps_to_closed_win():
    state, closed_outcome, realized_r = map_trade_outcome(_trade(outcome="win", r_multiple=2.0))
    assert state is OutcomeState.CLOSED
    assert closed_outcome is ClosedTradeOutcome.WIN
    assert realized_r == 2.0


def test_loss_trade_maps_to_closed_loss():
    state, closed_outcome, realized_r = map_trade_outcome(_trade(outcome="loss", r_multiple=-1.0))
    assert state is OutcomeState.CLOSED
    assert closed_outcome is ClosedTradeOutcome.LOSS
    assert realized_r == -1.0


def test_closed_outcome_never_derived_from_r_multiple_sign():
    """A 'win' with a NEGATIVE r_multiple must still map to WIN — categorical,
    never inferred from sign (spec.md Section C2)."""
    state, closed_outcome, realized_r = map_trade_outcome(_trade(outcome="win", r_multiple=-0.3))
    assert closed_outcome is ClosedTradeOutcome.WIN
    assert realized_r == -0.3


# --- Group I: OPEN -------------------------------------------------------------


def test_open_trade_maps_to_open_with_no_fields():
    state, closed_outcome, realized_r = map_trade_outcome(_trade(outcome="open", r_multiple=None))
    assert state is OutcomeState.OPEN
    assert closed_outcome is None
    assert realized_r is None


# --- Group J: Trade contract corruption ---------------------------------------


def test_win_with_none_r_multiple_fails_closed():
    with pytest.raises(TradeOutcomeContractError):
        map_trade_outcome(_trade(outcome="win", r_multiple=None))


def test_loss_with_none_r_multiple_fails_closed():
    with pytest.raises(TradeOutcomeContractError):
        map_trade_outcome(_trade(outcome="loss", r_multiple=None))


def test_open_with_finite_r_multiple_fails_closed():
    with pytest.raises(TradeOutcomeContractError):
        map_trade_outcome(_trade(outcome="open", r_multiple=0.0))


def test_unexpected_outcome_string_fails_closed():
    with pytest.raises(TradeOutcomeContractError):
        map_trade_outcome(_trade(outcome="cancelled", r_multiple=None))


def test_non_finite_closed_r_multiple_fails_closed():
    with pytest.raises(TradeOutcomeContractError):
        map_trade_outcome(_trade(outcome="win", r_multiple=math.nan))
    with pytest.raises(TradeOutcomeContractError):
        map_trade_outcome(_trade(outcome="loss", r_multiple=math.inf))


# --- Group K: explicit zero-risk geometry validation (REQ-STAT-35, V4) ------
# entry_price/stop_loss both finite AND abs(entry_price - stop_loss) > 0,
# applied to every Trade regardless of outcome (WIN, LOSS, AND OPEN alike).


def _trade_with_geometry(outcome: str, entry_price: float, stop_loss: float) -> Trade:
    return Trade(
        signal_id="sig-1", anchor_index=1, direction="bullish", entry_index=3, entry_price=entry_price,
        stop_loss=stop_loss, take_profit=1.3, exit_index=5 if outcome != "open" else None,
        exit_price=1.3 if outcome != "open" else None, outcome=outcome,
        r_multiple=1.5 if outcome != "open" else None,
        ambiguous_bar=False, gap_filled=False, partial_exit_index=None, partial_exit_price=None,
        partial_r_multiple=None, partial_gap_filled=False,
    )


@pytest.mark.parametrize("outcome", ["win", "loss", "open"])
def test_zero_risk_entry_equals_stop_fails_closed_for_every_outcome(outcome):
    with pytest.raises(TradeOutcomeContractError):
        map_trade_outcome(_trade_with_geometry(outcome, entry_price=100.0, stop_loss=100.0))


@pytest.mark.parametrize("outcome", ["win", "loss", "open"])
def test_distinct_finite_entry_and_stop_is_valid_for_every_outcome(outcome):
    map_trade_outcome(_trade_with_geometry(outcome, entry_price=1.0, stop_loss=0.9))  # must not raise


@pytest.mark.parametrize("outcome", ["win", "loss", "open"])
def test_non_finite_entry_price_fails_closed(outcome):
    with pytest.raises(TradeOutcomeContractError):
        map_trade_outcome(_trade_with_geometry(outcome, entry_price=math.nan, stop_loss=0.9))


@pytest.mark.parametrize("outcome", ["win", "loss", "open"])
def test_non_finite_stop_loss_fails_closed(outcome):
    with pytest.raises(TradeOutcomeContractError):
        map_trade_outcome(_trade_with_geometry(outcome, entry_price=1.0, stop_loss=math.inf))


def test_zero_risk_check_does_not_recompute_or_repair_realized_r():
    """Integrity-only: a valid-geometry Trade's r_multiple passes through
    unchanged — the check never adjusts entry_price/stop_loss/r_multiple."""
    _, _, realized_r = map_trade_outcome(_trade_with_geometry("win", entry_price=1.0, stop_loss=0.9))
    assert realized_r == 1.5
