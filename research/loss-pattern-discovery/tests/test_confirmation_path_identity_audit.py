from types import SimpleNamespace

from extract.confirmation_path_identity_audit import reconcile_with_ledger


def _record(event_id, instrument, outcome_name="WIN"):
    return SimpleNamespace(
        identification=SimpleNamespace(event_id=event_id, instrument=instrument),
        operation=SimpleNamespace(outcome=SimpleNamespace(name=outcome_name)),
    )


def _path(symbol, model="1am", invalidations=0):
    return {"symbol": symbol, "model": model, "internal_invalidation_count": invalidations}


def test_fully_reconciled_when_every_ledger_record_has_a_matching_path():
    ledger = [_record("EURUSD|d3_c2|1am|t1|bullish", "EURUSD"), _record("USDCAD|d3_c2|9am|t2|bearish", "USDCAD")]
    paths = {"EURUSD|d3_c2|1am|t1|bullish": _path("EURUSD"), "USDCAD|d3_c2|9am|t2|bearish": _path("USDCAD", "9am")}
    result = reconcile_with_ledger(paths, ledger)
    assert result["fully_reconciled"] is True
    assert result["n_matched"] == 2
    assert result["n_missing_path"] == 0


def test_missing_path_is_reported_not_silently_dropped():
    ledger = [_record("EURUSD|d3_c2|1am|t1|bullish", "EURUSD")]
    result = reconcile_with_ledger({}, ledger)
    assert result["fully_reconciled"] is False
    assert result["missing_path_sids"] == ["EURUSD|d3_c2|1am|t1|bullish"]


def test_cross_instrument_mismatch_is_detected():
    sid = "EURUSD|d3_c2|1am|t1|bullish"
    ledger = [_record(sid, "EURUSD")]
    paths = {sid: _path("USDCAD")}  # a path claiming the wrong instrument
    result = reconcile_with_ledger(paths, ledger)
    assert result["n_cross_instrument_mismatch"] == 1
    assert result["fully_reconciled"] is False


def test_duplicate_event_ids_are_detected():
    sid = "EURUSD|d3_c2|1am|t1|bullish"
    ledger = [_record(sid, "EURUSD"), _record(sid, "EURUSD")]
    paths = {sid: _path("EURUSD")}
    result = reconcile_with_ledger(paths, ledger)
    assert result["duplicate_event_ids"] == [sid]
    assert result["fully_reconciled"] is False


def test_open_trades_keep_their_identity_and_are_still_matched():
    sid = "EURUSD|d3_c2|1am|t1|bullish"
    ledger = [_record(sid, "EURUSD", outcome_name="OPEN")]
    paths = {sid: _path("EURUSD")}
    result = reconcile_with_ledger(paths, ledger)
    assert result["n_open_trades_matched"] == 1
    assert result["open_trade_sids"] == [sid]
    assert result["fully_reconciled"] is True
