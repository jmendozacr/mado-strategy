"""Backtest metrics — win rate, aggregate R, population-reconciliation
invariant/precedence (REQ-39, 40.1, 40.3, 49) — plus the trades.csv row-
ordering contract (design/interfaces: sorted by (entry_index, signal_id),
independent of emission order).
"""

import random
from datetime import datetime

from fixtures.synthetic import CandleSeriesBuilder

from alignment.htf_ltf import AlignedSignal
from core.config import DetectorConfig
from core.key_level import KeyLevel
from core.results import DetectionStatus
from entries.model1 import Model1Signal
from primitives.crt_range import CRTRange

from backtest.metrics import compute_metrics
from backtest.simulate import ReconciliationReport, Trade, simulate

_HTF_CONTEXT = CRTRange(
    model="2-candle", high=1.1050, low=1.0950, start_index=0, end_index=1,
    resolution="true_break", resolved_at_index=1,
)

# See test_backtest_simulate.py's _KEY_LEVEL for the rationale (design §8.1).
_KEY_LEVEL = KeyLevel(kind="fvg", top=1.1050, bottom=1.0950, origin_index=0, expiry_index=None)

_ZERO_RECONCILIATION = ReconciliationReport(
    signals_considered=0, trades_opened=0, excluded_no_crt_range=0, excluded_unaligned=0,
    excluded_never_confirmed=0, excluded_no_key_level=0, excluded_duplicate=0, excluded_kill_zone=0,
    excluded_rr_floor=0, excluded_never_filled=0,
)


def _trade(signal_id: str, entry_index: int, outcome: str, r_multiple: float | None = None) -> Trade:
    return Trade(
        signal_id=signal_id, anchor_index=0, direction="bullish", entry_index=entry_index,
        entry_price=1.1000, stop_loss=1.0990, take_profit=1.1020,
        exit_index=None if outcome == "open" else entry_index + 1,
        exit_price=None if outcome == "open" else 1.1010,
        outcome=outcome, r_multiple=r_multiple, ambiguous_bar=False, gap_filled=False,
        partial_exit_index=None, partial_exit_price=None, partial_r_multiple=None, partial_gap_filled=False,
    )


def _signal(
    anchor_index, direction, entry_type, retest_index,
    status=DetectionStatus.CONFIRMED, confirmation_type="purge_engulf", origin_index=0,
):
    return Model1Signal(
        anchor_index=anchor_index, direction=direction, purge_target=0.0,
        confirmation_type=confirmation_type, entry_type=entry_type, entry_price=0.0,
        retest_index=retest_index, status=status,
        confirmation_index=retest_index if retest_index is not None else anchor_index,
        origin_index=origin_index,
    )


def _aligned(signal, htf_context=_HTF_CONTEXT, aligned="aligned", key_level=_KEY_LEVEL):
    return AlignedSignal(ltf_signal=signal, htf_context=htf_context, aligned=aligned, key_level=key_level)


def test_win_rate_is_none_never_zero_when_no_trades_have_closed():
    """REQ-39.1: zero closed trades -> win_rate is None/n/a, never 0.0."""
    metrics = compute_metrics([_trade("a", 0, "open")], _ZERO_RECONCILIATION, DetectorConfig().backtest, "enabled")

    assert metrics.win_rate is None


def test_win_rate_over_five_closed_trades():
    """REQ-39.2: 3 wins + 2 losses (5 closed) -> win_rate = 0.6."""
    trades = [
        _trade("w1", 0, "win", 2.0), _trade("w2", 1, "win", 1.5), _trade("w3", 2, "win", 0.5),
        _trade("l1", 3, "loss", -1.0), _trade("l2", 4, "loss", -1.0),
    ]

    metrics = compute_metrics(trades, _ZERO_RECONCILIATION, DetectorConfig().backtest, "enabled")

    assert metrics.win_rate == 0.6


def test_average_and_total_r_over_closed_trades():
    """REQ-49.1: closed r_multiples +2, +2, -1 -> average_r_multiple=1.0,
    total_r=3.0."""
    trades = [_trade("a", 0, "win", 2.0), _trade("b", 1, "win", 2.0), _trade("c", 2, "loss", -1.0)]

    metrics = compute_metrics(trades, _ZERO_RECONCILIATION, DetectorConfig().backtest, "enabled")

    assert metrics.average_r_multiple == 1.0
    assert metrics.total_r == 3.0


def test_average_and_total_r_are_none_never_zero_when_no_trades_have_closed():
    """REQ-49.2: zero closed trades -> both average_r_multiple and total_r
    are None/n/a, never 0.0."""
    metrics = compute_metrics([_trade("a", 0, "open")], _ZERO_RECONCILIATION, DetectorConfig().backtest, "enabled")

    assert metrics.average_r_multiple is None
    assert metrics.total_r is None


def test_metrics_denominators_exclude_opens_in_a_mixed_population():
    """REQ-49/49.4: win_rate, average_r_multiple and total_r are computed
    over CLOSED trades only, and open_trades counts exactly the open ones
    — pinned on a population that mixes both, unlike every other metrics
    test here (all-closed or all-open), which cannot distinguish a
    denominator that wrongly includes/excludes opens."""
    trades = [
        _trade("w1", 0, "win", 2.0), _trade("w2", 1, "win", 1.5), _trade("w3", 2, "win", 0.5),
        _trade("l1", 3, "loss", -1.0), _trade("l2", 4, "loss", -1.0),
        _trade("o1", 5, "open"), _trade("o2", 6, "open"), _trade("o3", 7, "open"), _trade("o4", 8, "open"),
    ]

    metrics = compute_metrics(trades, _ZERO_RECONCILIATION, DetectorConfig().backtest, "enabled")

    assert metrics.win_rate == 0.6
    assert metrics.closed_trades == 5
    assert metrics.open_trades == 4
    assert metrics.average_r_multiple == 0.4
    assert metrics.total_r == 2.0


def test_reconciliation_buckets_plus_trades_opened_sum_to_signals_considered():
    """REQ-40.1: for a real simulate() run mixing distinct bucket outcomes
    (no_crt_range, unaligned, no_key_level, and a trade), trades_opened +
    every one of the 8 exclusion buckets sums EXACTLY to
    signals_considered."""
    series = (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1010, low=1.0990, close=1.1005)  # 0 — anchor
        .candle(open=1.1005, high=1.1010, low=1.1000, close=1.1005)  # 1 — filler
        .candle(open=1.1002, high=1.1008, low=1.1001, close=1.1004)  # 2 — retest, no touch
        .candle(open=1.1003, high=1.1006, low=1.1001, close=1.1002)  # 3 — no touch
        .candle(open=1.1020, high=1.1025, low=1.0995, close=1.1010)  # 4 — fills
        .candle(open=1.1000, high=1.1010, low=1.0995, close=1.1002)  # 5 — SL/TP untouched
        .build()
    )
    opens_a_trade = _signal(anchor_index=0, direction="bullish", entry_type="body", retest_index=2, origin_index=0)
    no_crt_range = _signal(
        anchor_index=0, direction="bullish", entry_type="body", retest_index=2,
        confirmation_type="fvg_fill", origin_index=1,
    )
    unaligned = _signal(anchor_index=0, direction="bullish", entry_type="body", retest_index=2, origin_index=2)
    no_key_level = _signal(anchor_index=0, direction="bullish", entry_type="body", retest_index=2, origin_index=3)

    population = [
        _aligned(opens_a_trade),
        _aligned(no_crt_range),
        _aligned(unaligned, htf_context=None, aligned="unaligned"),
        _aligned(no_key_level, key_level=None),
    ]
    trades, report = simulate(population, series, DetectorConfig())

    bucket_sum = report.trades_opened + sum([
        report.excluded_no_crt_range, report.excluded_unaligned, report.excluded_never_confirmed,
        report.excluded_no_key_level, report.excluded_duplicate, report.excluded_kill_zone,
        report.excluded_rr_floor, report.excluded_never_filled,
    ])
    assert bucket_sum == report.signals_considered == 4
    assert report.trades_opened == 1
    assert report.excluded_no_crt_range == 1
    assert report.excluded_unaligned == 1
    assert report.excluded_no_key_level == 1


def test_unaligned_and_outside_kill_zone_lands_in_excluded_unaligned_not_kill_zone():
    """REQ-40.3: a signal that is BOTH unaligned AND anchored outside the
    kill zone lands in excluded_unaligned (stage 2), never excluded_kill_zone
    (stage 5) -- the earliest matching stage wins."""
    series = (
        CandleSeriesBuilder(start=datetime(2026, 1, 1, 10, 30))  # 10:30 UTC -> 05:30 NY, outside the default kill zone
        .candle(open=1.1000, high=1.1010, low=1.0990, close=1.1005)  # 0 — anchor, outside the kill zone
        .candle(open=1.1005, high=1.1010, low=1.1000, close=1.1005)  # 1 — filler
        .candle(open=1.1002, high=1.1008, low=1.1001, close=1.1004)  # 2 — retest
        .build()
    )
    signal = _signal(anchor_index=0, direction="bullish", entry_type="body", retest_index=2)

    trades, report = simulate([_aligned(signal, htf_context=None, aligned="unaligned")], series, DetectorConfig())

    assert trades == []
    assert report.excluded_unaligned == 1
    assert report.excluded_kill_zone == 0


def test_trades_are_ordered_by_entry_index_then_signal_id_independent_of_emission_order():
    """design/interfaces row-ordering contract: trades.csv rows (the
    simulate() output feeding write_trades_csv) are sorted by the total key
    (entry_index, signal_id) ascending, independent of the order candidates
    were fed in -- entry_index is the fill index, signal_id is injective so
    the tie-break makes the order total."""
    series = (
        CandleSeriesBuilder()
        .candle(open=1.1000, high=1.1010, low=1.0995, close=1.1005)  # 0 — anchor A (body entry=1.1000)
        .candle(open=1.1000, high=1.1010, low=1.0995, close=1.1005)  # 1 — anchor B (body entry=1.1000)
        .candle(open=1.1002, high=1.1010, low=1.0995, close=1.1005)  # 2 — anchor C (body entry=1.1002); its range also
        # touches A's/B's entry_price (1.1000) -> all three fill HERE, at the same entry_index -> a genuine tie.
        .build()
    )
    signals = [_signal(anchor_index=i, direction="bullish", entry_type="body", retest_index=2, origin_index=i) for i in range(3)]
    aligned = [_aligned(s) for s in signals]
    random.Random(7).shuffle(aligned)

    trades, _ = simulate(aligned, series, DetectorConfig())

    ordering_keys = [(t.entry_index, t.signal_id) for t in trades]
    assert ordering_keys == sorted(ordering_keys)
    assert len({t.entry_index for t in trades}) == 1  # confirms this is a genuine tie, not a vacuous pass
    assert len(trades) == 3
