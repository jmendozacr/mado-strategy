from extract.event_identity_reconciliation import compare_identities, detect_duplicate_signal_ids


def _row(signal_id, pair="EURUSD", model="1am", direction="bullish", entry_index=10, entry_price=1.10):
    return {
        "signal_id": signal_id, "pair": pair, "model": model, "direction": direction,
        "entry_index": entry_index, "entry_price": entry_price,
    }


def test_compare_identities_fully_matched_when_identical():
    recon = {"a": _row("sid-a"), "b": _row("sid-b")}
    ledger = {"a": _row("sid-a"), "b": _row("sid-b")}
    result = compare_identities(recon, ledger)
    assert result["fully_matched"] is True
    assert result["only_in_ledger"] == []
    assert result["only_in_reconstruction"] == []
    assert result["field_mismatches"] == []


def test_compare_identities_detects_only_in_ledger():
    recon = {"a": _row("sid-a")}
    ledger = {"a": _row("sid-a"), "b": _row("sid-b")}
    result = compare_identities(recon, ledger)
    assert result["only_in_ledger"] == ["b"]
    assert result["fully_matched"] is False


def test_compare_identities_detects_only_in_reconstruction():
    recon = {"a": _row("sid-a"), "c": _row("sid-c")}
    ledger = {"a": _row("sid-a")}
    result = compare_identities(recon, ledger)
    assert result["only_in_reconstruction"] == ["c"]
    assert result["fully_matched"] is False


def test_compare_identities_detects_a_field_mismatch():
    recon = {"a": _row("sid-a", model="1am")}
    ledger = {"a": _row("sid-a", model="9am")}
    result = compare_identities(recon, ledger)
    assert result["field_mismatches"] == [{"stable_id": "a", "fields": ["model"]}]
    assert result["fully_matched"] is False


def test_compare_identities_detects_an_entry_price_mismatch_beyond_tolerance():
    recon = {"a": _row("sid-a", entry_price=1.10001)}
    ledger = {"a": _row("sid-a", entry_price=1.10)}
    result = compare_identities(recon, ledger)
    assert result["field_mismatches"] == [{"stable_id": "a", "fields": ["entry_price"]}]


def test_compare_identities_tolerates_float_noise_in_entry_price():
    recon = {"a": _row("sid-a", entry_price=1.10 + 1e-12)}
    ledger = {"a": _row("sid-a", entry_price=1.10)}
    result = compare_identities(recon, ledger)
    assert result["fully_matched"] is True


def test_detect_duplicate_signal_ids_finds_a_real_duplicate():
    ledger = {"a": _row("sid-x"), "b": _row("sid-y"), "c": _row("sid-x")}
    assert detect_duplicate_signal_ids(ledger) == ["sid-x"]


def test_detect_duplicate_signal_ids_empty_when_unique():
    ledger = {"a": _row("sid-x"), "b": _row("sid-y")}
    assert detect_duplicate_signal_ids(ledger) == []
