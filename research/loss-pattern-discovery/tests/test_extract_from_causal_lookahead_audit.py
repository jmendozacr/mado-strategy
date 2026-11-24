from pathlib import Path

from extract.from_causal_lookahead_audit import SOURCE_RELATIVE_PATH, extract
from schema.events import ExitReasonBasis, Outcome

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def test_extract_returns_one_record_per_csv_row():
    records = extract(REPO_ROOT)
    source_path = REPO_ROOT / SOURCE_RELATIVE_PATH
    expected = sum(1 for _ in source_path.open(encoding="utf-8")) - 1  # minus header
    assert len(records) == expected
    assert expected > 2000  # sanity: this is the ~2047-row ledger, not an empty/truncated file


def test_first_known_record_matches_source_csv():
    records = extract(REPO_ROOT)
    first = records[0]
    assert first.identification.instrument == "EURUSD"
    assert first.identification.config_id == "d3_c2"
    assert first.identification.session_label == "9am"
    assert first.identification.original_direction == "bullish"
    assert first.operation.outcome is Outcome.LOSS
    assert first.operation.exit_reason == "stop_loss"
    assert first.operation.exit_reason_basis is ExitReasonBasis.INFERRED_BINARY
    assert first.operation.r_multiple < 0
    assert first.operation.entry_price == 1.18225


def test_pre_entry_features_never_populated_from_exit_fields():
    records = extract(REPO_ROOT)
    for record in records[:50]:
        pre = record.features_pre_entry
        if pre.order_placed_ts is not None and record.operation.exit_ts is not None:
            assert pre.order_placed_ts <= record.operation.exit_ts


def test_open_right_censored_rows_parse_without_fabricating_exit_data():
    records = extract(REPO_ROOT)
    open_records = [r for r in records if r.operation.outcome is Outcome.OPEN]
    assert open_records, "expected at least one still-open (right-censored) trade in this ledger"
    for record in open_records:
        assert record.operation.exit_ts is None
        assert record.operation.exit_price is None
        assert record.operation.r_multiple is None
        assert record.operation.exit_reason is None


def test_source_path_mismatch_raises_not_silently_substitutes():
    import pytest

    with pytest.raises(FileNotFoundError):
        extract(REPO_ROOT / "does-not-exist")
