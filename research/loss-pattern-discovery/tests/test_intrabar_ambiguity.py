import datetime as dt

from core.candle import Candle, OHLCSeries

from eligibility.intrabar_ambiguity import classify_all_intrabar_uncertainty, classify_intrabar_uncertainty
from eligibility.stop_timing_decomposition import TimingCategory, TimingClassification
from schema.events import (
    EventRecord,
    ExitReasonBasis,
    FeaturesAtStop,
    FeaturesPreEntry,
    Identification,
    Outcome,
    OriginalOperation,
)


def _series(candles) -> OHLCSeries:
    return OHLCSeries(candles=tuple(candles), instrument="EURUSD", timeframe="M15")


def _record(
    event_id, entry_ts, exit_ts, direction="bullish", entry_price=1.10, stop_loss=1.09,
    ambiguous_bar=False, gap_filled=False,
):
    identification = Identification(
        event_id=event_id, source_path="x", source_version="x", instrument="EURUSD",
        session_label="9am", config_id="d3_c2", original_direction=direction,
    )
    operation = OriginalOperation(
        entry_price=entry_price, stop_loss=stop_loss, take_profit=1.13, risk_price=abs(entry_price - stop_loss),
        activation_ts=entry_ts - dt.timedelta(minutes=30), order_placed_ts=entry_ts,
        entry_ts=entry_ts, exit_ts=exit_ts, exit_price=stop_loss, outcome=Outcome.LOSS, r_multiple=-1.01,
        exit_reason="stop_loss", exit_reason_basis=ExitReasonBasis.INFERRED_BINARY,
        ambiguous_bar=ambiguous_bar, gap_filled=gap_filled, has_partial_exit=False,
    )
    features_pre_entry = FeaturesPreEntry(
        feeder_ref_available_ts=None, activation_instant_ts=operation.activation_ts,
        model1_available_ts=None, order_placed_ts=entry_ts, time_from_activation_to_order_s=1800.0,
        planned_risk_price=operation.risk_price, planned_reward_price=0.03, planned_rr=2.0,
    )
    features_at_stop = FeaturesAtStop(
        exit_ts=exit_ts, exit_price=stop_loss, outcome=Outcome.LOSS, r_multiple=-1.01,
        speed_to_stop_s=(exit_ts - entry_ts).total_seconds(), ambiguous_bar=ambiguous_bar, gap_filled=gap_filled,
    )
    return EventRecord(identification, operation, features_pre_entry, features_at_stop)


def _e0_timing(event_id):
    return TimingClassification(event_id, TimingCategory.SAME_BAR_SL, 0)


def _e1_timing(event_id):
    return TimingClassification(event_id, TimingCategory.NEXT_BAR_SL, 1)


def test_bullish_same_bar_sequence_verifiable_when_open_above_entry():
    ts = dt.datetime(2026, 1, 1, 10, 0)
    record = _record("e0-1", ts, ts, direction="bullish", entry_price=1.10, stop_loss=1.09)
    series = _series([Candle(ts, open=1.105, high=1.105, low=1.08, close=1.08)])
    result = classify_intrabar_uncertainty(record, _e0_timing("e0-1"), series)
    assert result.engine_conservative_same_bar is True
    assert result.sequence_verifiable is True
    assert "entry preceded the stop touch" in result.can_affirm[0]


def test_bullish_same_bar_not_verifiable_when_open_below_entry():
    ts = dt.datetime(2026, 1, 1, 10, 0)
    record = _record("e0-2", ts, ts, direction="bullish", entry_price=1.10, stop_loss=1.09)
    series = _series([Candle(ts, open=1.095, high=1.10, low=1.08, close=1.09)])
    result = classify_intrabar_uncertainty(record, _e0_timing("e0-2"), series)
    assert result.sequence_verifiable is False
    assert result.can_affirm == ()
    assert "whether entry preceded or followed" in result.cannot_affirm[0]


def test_bearish_same_bar_sequence_verifiable_when_open_below_entry():
    ts = dt.datetime(2026, 1, 1, 10, 0)
    record = _record("e0-3", ts, ts, direction="bearish", entry_price=1.09, stop_loss=1.10)
    series = _series([Candle(ts, open=1.085, high=1.11, low=1.085, close=1.10)])
    result = classify_intrabar_uncertainty(record, _e0_timing("e0-3"), series)
    assert result.sequence_verifiable is True


def test_bearish_same_bar_not_verifiable_when_open_above_entry():
    ts = dt.datetime(2026, 1, 1, 10, 0)
    record = _record("e0-4", ts, ts, direction="bearish", entry_price=1.09, stop_loss=1.10)
    series = _series([Candle(ts, open=1.095, high=1.10, low=1.08, close=1.09)])
    result = classify_intrabar_uncertainty(record, _e0_timing("e0-4"), series)
    assert result.sequence_verifiable is False


def test_non_same_bar_event_never_gets_a_same_bar_verdict():
    # E1 (next-bar): entry already closed on a prior bar -- no entry-vs-stop
    # ambiguity to resolve, and this module must never invent one.
    entry_ts = dt.datetime(2026, 1, 1, 10, 0)
    exit_ts = entry_ts + dt.timedelta(minutes=15)
    record = _record("e1-1", entry_ts, exit_ts, gap_filled=True)
    series = _series([Candle(exit_ts, open=1.088, high=1.088, low=1.08, close=1.08)])
    result = classify_intrabar_uncertainty(record, _e1_timing("e1-1"), series)
    assert result.engine_conservative_same_bar is False
    assert result.sequence_verifiable is None
    assert result.gap_affected is True  # read straight from the ledger's own flag


def test_same_bar_event_never_reports_gap_affected_regardless_of_flag():
    # _fill_candle_immediate_loss hardcodes gap_filled=False -- a gap-through
    # fill candle is exempted upstream and never reaches E0 at all. Even if
    # the ledger somehow carried gap_filled=True here, this module must not
    # surface it as gap_affected for an E0 event.
    ts = dt.datetime(2026, 1, 1, 10, 0)
    record = _record("e0-5", ts, ts, gap_filled=True)
    series = _series([Candle(ts, open=1.105, high=1.105, low=1.08, close=1.08)])
    result = classify_intrabar_uncertainty(record, _e0_timing("e0-5"), series)
    assert result.gap_affected is False


def test_ambiguous_bar_flag_never_treated_as_a_resolved_same_bar_sequence():
    # same_bar_multi_level_ambiguity events are already routed to OTHER_EXIT
    # upstream (stop_eligibility) -- this test proves that even if one
    # reached this function directly, it would stay ambiguous, never be
    # read as evidence of a verified sequence.
    ts = dt.datetime(2026, 1, 1, 10, 0)
    record = _record("amb-1", ts, ts, ambiguous_bar=True)
    timing = TimingClassification("amb-1", TimingCategory.OTHER_EXIT, None)
    series = _series([Candle(ts, open=1.105, high=1.14, low=1.08, close=1.09)])
    result = classify_intrabar_uncertainty(record, timing, series)
    assert result.same_bar_multi_level_ambiguity is True
    assert result.engine_conservative_same_bar is False
    assert result.sequence_verifiable is None


def test_insufficient_evidence_when_entry_ts_not_in_series():
    ts = dt.datetime(2026, 1, 1, 10, 0)
    other_ts = ts + dt.timedelta(days=5)
    record = _record("e0-6", ts, ts)
    series = _series([Candle(other_ts, open=1.10, high=1.10, low=1.09, close=1.09)])
    result = classify_intrabar_uncertainty(record, _e0_timing("e0-6"), series)
    assert result.insufficient_evidence is True
    assert result.sequence_verifiable is None


def test_classification_never_consults_a_later_candle():
    ts = dt.datetime(2026, 1, 1, 10, 0)
    record = _record("e0-7", ts, ts, direction="bullish", entry_price=1.10, stop_loss=1.09)
    series_without_future = _series([Candle(ts, open=1.105, high=1.105, low=1.08, close=1.08)])
    series_with_wild_future = _series([
        Candle(ts, open=1.105, high=1.105, low=1.08, close=1.08),
        Candle(ts + dt.timedelta(minutes=15), open=100.0, high=200.0, low=0.0001, close=50.0),
    ])
    r1 = classify_intrabar_uncertainty(record, _e0_timing("e0-7"), series_without_future)
    r2 = classify_intrabar_uncertainty(record, _e0_timing("e0-7"), series_with_wild_future)
    assert r1.sequence_verifiable == r2.sequence_verifiable
    assert r1.evidence == r2.evidence


def test_deterministic():
    ts = dt.datetime(2026, 1, 1, 10, 0)
    record = _record("det-1", ts, ts)
    series = _series([Candle(ts, open=1.105, high=1.105, low=1.08, close=1.08)])
    timing = _e0_timing("det-1")
    assert classify_intrabar_uncertainty(record, timing, series) == classify_intrabar_uncertainty(record, timing, series)


def test_classify_all_intrabar_uncertainty_maps_each_event_independently():
    ts = dt.datetime(2026, 1, 1, 10, 0)
    r1 = _record("multi-1", ts, ts, direction="bullish", entry_price=1.10, stop_loss=1.09)
    r2 = _record("multi-2", ts, ts, direction="bullish", entry_price=1.10, stop_loss=1.09)
    series = _series([Candle(ts, open=1.095, high=1.10, low=1.08, close=1.09)])
    timing_by_id = {"multi-1": _e0_timing("multi-1"), "multi-2": _e0_timing("multi-2")}
    series_by_instrument = {"EURUSD": series}
    result = classify_all_intrabar_uncertainty([r1, r2], timing_by_id, series_by_instrument)
    assert set(result.keys()) == {"multi-1", "multi-2"}
    assert result["multi-1"].sequence_verifiable is False
