import hashlib
import math
from datetime import datetime, timezone

import pytest

from research.dukascopy_eurusd_gbpusd.adapter import (
    APPROVED_TIMEFRAMES,
    DUKASCOPY_M1_COLUMNS,
    GapStatus,
    InputIdentity,
    MinuteRow,
    OfflineDomain,
    PROVIDER_TO_STRATEGY,
    aggregate_ohlcv,
    classify_gap,
    parse_csv_bytes,
    parse_eet_timestamp,
    resolve_identity,
    validate_rows,
    verify_sha256,
)


def row(timestamp: str, volume: float = 1.0) -> MinuteRow:
    return MinuteRow(
        timestamp=timestamp,
        open=1.1,
        high=1.2,
        low=1.0,
        close=1.15,
        volume=volume,
    )


def test_parse_eet_uses_standard_offset() -> None:
    assert parse_eet_timestamp("2024.01.15 12:00:00") == datetime(
        2024, 1, 15, 10, 0, tzinfo=timezone.utc
    )


def test_parse_eet_uses_daylight_offset() -> None:
    assert parse_eet_timestamp("2024.07.15 12:00:00") == datetime(
        2024, 7, 15, 9, 0, tzinfo=timezone.utc
    )


def test_validate_rows_preserves_zero_volume_but_rejects_duplicates() -> None:
    rows = [row("2024.01.15 12:00:00", volume=0.0), row("2024.01.15 12:01:00")]
    assert validate_rows(rows) == rows

    with pytest.raises(ValueError, match="duplicate timestamp"):
        validate_rows(rows + [row("2024.01.15 12:01:00")])


def test_aggregate_uses_eet_session_boundary_and_preserves_ohlcv() -> None:
    # Three consecutive minutes fit inside one M15 bucket.
    rows = [
        row("2024.01.15 01:00:00"),
        row("2024.01.15 01:01:00", volume=2.0),
        row("2024.01.15 01:02:00"),
    ]
    bars = aggregate_ohlcv(rows, timeframe_minutes=15)
    assert len(bars) == 1
    assert bars[0].timestamp == parse_eet_timestamp("2024.01.15 01:00:00")
    assert bars[0].open == 1.1
    assert bars[0].high == 1.2
    assert bars[0].low == 1.0
    assert bars[0].close == 1.15
    assert bars[0].volume == 4.0


def test_unexplained_gap_is_fail_closed() -> None:
    previous = parse_eet_timestamp("2024.01.15 12:00:00")
    current = parse_eet_timestamp("2024.01.15 12:03:00")
    assert classify_gap(previous, current, offline_domains=()) is GapStatus.UNRESOLVED


def test_validate_rows_rejects_non_finite_price() -> None:
    for bad_value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError, match="non-finite"):
            validate_rows(
                [MinuteRow(timestamp="2024.01.15 12:00:00", open=bad_value, high=1.2, low=1.0, close=1.15, volume=1.0)]
            )


def test_validate_rows_rejects_non_finite_volume() -> None:
    with pytest.raises(ValueError, match="non-finite volume"):
        validate_rows(
            [MinuteRow(timestamp="2024.01.15 12:00:00", open=1.1, high=1.2, low=1.0, close=1.15, volume=math.nan)]
        )


def test_validate_rows_rejects_non_monotonic_timestamps() -> None:
    rows = [row("2024.01.15 12:02:00"), row("2024.01.15 12:01:00")]
    with pytest.raises(ValueError, match="non-monotonic timestamp"):
        validate_rows(rows)


def test_aggregate_rejects_unapproved_timeframe() -> None:
    with pytest.raises(ValueError, match="not in approved set"):
        aggregate_ohlcv([row("2024.01.15 12:00:00")], timeframe_minutes=5)


def test_aggregate_approved_timeframes_are_accepted() -> None:
    # Smoke-test each approved timeframe constant produces output without error.
    r = row("2024.01.15 12:00:00")
    for tf in sorted(APPROVED_TIMEFRAMES):
        bars = aggregate_ohlcv([r], timeframe_minutes=tf)
        assert len(bars) == 1


def test_d1_boundary_tracks_spring_dst_midnight() -> None:
    rows = [
        row("2024.03.30 23:59:00"),
        row("2024.03.31 00:00:00"),
    ]
    bars = aggregate_ohlcv(rows, timeframe_minutes=1440)
    assert [bar.timestamp for bar in bars] == [
        parse_eet_timestamp("2024.03.30 00:00:00"),
        parse_eet_timestamp("2024.03.31 00:00:00"),
    ]


def test_d1_boundary_tracks_fall_dst_midnight() -> None:
    rows = [
        row("2024.10.26 23:59:00"),
        row("2024.10.27 00:00:00"),
    ]
    bars = aggregate_ohlcv(rows, timeframe_minutes=1440)
    assert [bar.timestamp for bar in bars] == [
        parse_eet_timestamp("2024.10.26 00:00:00"),
        parse_eet_timestamp("2024.10.27 00:00:00"),
    ]


def test_h4_boundary_uses_local_wall_clock() -> None:
    rows = [row("2024.03.31 02:59:00"), row("2024.03.31 04:00:00")]
    bars = aggregate_ohlcv(rows, timeframe_minutes=240)
    assert [bar.timestamp for bar in bars] == [
        parse_eet_timestamp("2024.03.31 00:00:00"),
        parse_eet_timestamp("2024.03.31 04:00:00"),
    ]


def test_gap_explained_by_offline_domain() -> None:
    previous = parse_eet_timestamp("2024.01.15 12:00:00")
    current = parse_eet_timestamp("2024.01.15 14:00:00")
    domain = OfflineDomain(
        start=parse_eet_timestamp("2024.01.15 12:01:00"),
        end=parse_eet_timestamp("2024.01.15 14:00:00"),
    )
    assert classify_gap(previous, current, offline_domains=[domain]) is GapStatus.EXPLAINED


# ---------------------------------------------------------------------------
# Identity contract tests
# ---------------------------------------------------------------------------

def test_eurusd_maps_to_strategy_identity() -> None:
    identity = resolve_identity("EURUSD", "EET", "Bid", "/ext/eurusd.csv", "placeholder")
    assert identity.provider_instrument == "EURUSD"
    assert identity.strategy_instrument == "DUKASCOPY_EURUSD"


def test_gbpusd_maps_to_strategy_identity() -> None:
    identity = resolve_identity("GBPUSD", "EET", "Bid", "/ext/gbpusd.csv", "placeholder")
    assert identity.provider_instrument == "GBPUSD"
    assert identity.strategy_instrument == "DUKASCOPY_GBPUSD"


def test_identity_preserves_metadata_fields() -> None:
    identity = resolve_identity("EURUSD", "EET", "Bid", "/ext/eurusd.csv", "deadbeef")
    assert identity.source_path == "/ext/eurusd.csv"
    assert identity.source_sha256 == "deadbeef"
    assert identity.timezone_label == "EET"
    assert identity.offer_side == "Bid"


def test_unknown_instrument_rejected() -> None:
    with pytest.raises(ValueError, match="unknown provider_instrument"):
        resolve_identity("USDJPY", "EET", "Bid", "/ext/usdjpy.csv", "placeholder")


def test_wrong_offer_side_rejected() -> None:
    with pytest.raises(ValueError, match="offer_side"):
        resolve_identity("EURUSD", "EET", "Ask", "/ext/eurusd.csv", "placeholder")


def test_wrong_timezone_label_rejected() -> None:
    with pytest.raises(ValueError, match="timezone_label"):
        resolve_identity("EURUSD", "UTC", "Bid", "/ext/eurusd.csv", "placeholder")


def test_provider_to_strategy_covers_both_instruments() -> None:
    assert "EURUSD" in PROVIDER_TO_STRATEGY
    assert "GBPUSD" in PROVIDER_TO_STRATEGY
    assert PROVIDER_TO_STRATEGY["EURUSD"] == "DUKASCOPY_EURUSD"
    assert PROVIDER_TO_STRATEGY["GBPUSD"] == "DUKASCOPY_GBPUSD"


# ---------------------------------------------------------------------------
# SHA-256 tests
# ---------------------------------------------------------------------------

_SAMPLE_BYTES = b"hello dukascopy"
_SAMPLE_SHA256 = hashlib.sha256(_SAMPLE_BYTES).hexdigest()


def test_sha256_passes_on_correct_hash() -> None:
    verify_sha256(_SAMPLE_BYTES, _SAMPLE_SHA256)  # must not raise


def test_sha256_raises_on_wrong_hash() -> None:
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_sha256(_SAMPLE_BYTES, "0" * 64)


def test_sha256_is_deterministic() -> None:
    assert hashlib.sha256(_SAMPLE_BYTES).hexdigest() == _SAMPLE_SHA256


# ---------------------------------------------------------------------------
# CSV header and parsing tests
# ---------------------------------------------------------------------------

# Pre-built synthetic identities; source_sha256 is placeholder — verify_sha256
# is called separately and tested above.
_EURUSD_ID = resolve_identity("EURUSD", "EET", "Bid", "/ext/eurusd.csv", "placeholder")
_GBPUSD_ID = resolve_identity("GBPUSD", "EET", "Bid", "/ext/gbpusd.csv", "placeholder")

_EURUSD_ROW = b"2024.01.15 12:00:00,1.09525,1.09535,1.09490,1.09510,100.0"
_GBPUSD_ROW = b"2024.01.15 12:00:00,1.27000,1.27100,1.26900,1.27050,80.0"
# Exact bytes as produced by the real JForex CSV export (trailing space on "Volume ").
_HEADER = b"Time (EET),Open,High,Low,Close,Volume "


def test_valid_eurusd_csv_header_accepted() -> None:
    csv_bytes = _HEADER + b"\n" + _EURUSD_ROW + b"\n"
    rows = parse_csv_bytes(csv_bytes, _EURUSD_ID)
    assert len(rows) == 1


def test_valid_gbpusd_csv_header_accepted() -> None:
    csv_bytes = _HEADER + b"\n" + _GBPUSD_ROW + b"\n"
    rows = parse_csv_bytes(csv_bytes, _GBPUSD_ID)
    assert len(rows) == 1


def test_wrong_header_first_column_rejected() -> None:
    csv_bytes = b"Time,Open,High,Low,Close,Volume\n" + _EURUSD_ROW + b"\n"
    with pytest.raises(ValueError, match="unexpected CSV header"):
        parse_csv_bytes(csv_bytes, _EURUSD_ID)


def test_wrong_header_missing_column_rejected() -> None:
    csv_bytes = b"Timestamp,Open,High,Low,Close\n" + _EURUSD_ROW + b"\n"
    with pytest.raises(ValueError, match="unexpected CSV header"):
        parse_csv_bytes(csv_bytes, _EURUSD_ID)


def test_empty_csv_rejected() -> None:
    with pytest.raises(ValueError, match="empty CSV"):
        parse_csv_bytes(b"", _EURUSD_ID)


def test_parse_csv_produces_correct_minute_row() -> None:
    csv_bytes = _HEADER + b"\n" + _EURUSD_ROW + b"\n"
    rows = parse_csv_bytes(csv_bytes, _EURUSD_ID)
    assert rows[0] == MinuteRow(
        timestamp="2024.01.15 12:00:00",
        open=1.09525,
        high=1.09535,
        low=1.09490,
        close=1.09510,
        volume=100.0,
    )


def test_zero_volume_row_preserved_through_parse() -> None:
    zero_vol = b"2024.01.15 12:00:00,1.09525,1.09535,1.09490,1.09510,0.0"
    csv_bytes = _HEADER + b"\n" + zero_vol + b"\n"
    rows = parse_csv_bytes(csv_bytes, _EURUSD_ID)
    assert len(rows) == 1
    assert rows[0].volume == 0.0


def test_malformed_row_non_numeric_price_rejected() -> None:
    bad_row = b"2024.01.15 12:00:00,BADPRICE,1.09535,1.09490,1.09510,100.0"
    csv_bytes = _HEADER + b"\n" + bad_row + b"\n"
    with pytest.raises(ValueError, match="non-numeric field"):
        parse_csv_bytes(csv_bytes, _EURUSD_ID)


def test_malformed_row_wrong_column_count_rejected() -> None:
    short_row = b"2024.01.15 12:00:00,1.09525,1.09535"
    csv_bytes = _HEADER + b"\n" + short_row + b"\n"
    with pytest.raises(ValueError, match="expected .* columns"):
        parse_csv_bytes(csv_bytes, _EURUSD_ID)


def test_multiple_rows_parsed_in_order() -> None:
    row1 = b"2024.01.15 12:00:00,1.09525,1.09535,1.09490,1.09510,100.0"
    row2 = b"2024.01.15 12:01:00,1.09510,1.09540,1.09500,1.09530,120.0"
    csv_bytes = _HEADER + b"\n" + row1 + b"\n" + row2 + b"\n"
    rows = parse_csv_bytes(csv_bytes, _EURUSD_ID)
    assert len(rows) == 2
    assert rows[0].timestamp == "2024.01.15 12:00:00"
    assert rows[1].timestamp == "2024.01.15 12:01:00"


def test_blank_lines_skipped_silently() -> None:
    csv_bytes = _HEADER + b"\n\n" + _EURUSD_ROW + b"\n\n"
    rows = parse_csv_bytes(csv_bytes, _EURUSD_ID)
    assert len(rows) == 1


def test_dukascopy_m1_columns_constant_matches_header() -> None:
    # Confirm the constant matches the real JForex export (trailing space stripped at parse time).
    assert DUKASCOPY_M1_COLUMNS == ("Time (EET)", "Open", "High", "Low", "Close", "Volume")


def test_exact_jforex_header_with_trailing_volume_space_accepted() -> None:
    # The real export has "Volume " (trailing space); the parser must accept it.
    raw_header = b"Time (EET),Open,High,Low,Close,Volume "
    csv_bytes = raw_header + b"\n" + _EURUSD_ROW + b"\n"
    rows = parse_csv_bytes(csv_bytes, _EURUSD_ID)
    assert len(rows) == 1


def test_old_timestamp_header_rejected() -> None:
    # Prior synthetic header ("Timestamp,...") no longer matches the real export.
    csv_bytes = b"Timestamp,Open,High,Low,Close,Volume\n" + _EURUSD_ROW + b"\n"
    with pytest.raises(ValueError, match="unexpected CSV header"):
        parse_csv_bytes(csv_bytes, _EURUSD_ID)


# ---------------------------------------------------------------------------
# Parser-level validation rejection tests (validate_rows called by parser)
# ---------------------------------------------------------------------------

def test_parse_csv_rejects_non_finite_price() -> None:
    # "nan" and "inf" parse as valid floats but must be rejected by the parser.
    for bad in ("nan", "inf", "-inf"):
        bad_row = f"2024.01.15 12:00:00,{bad},1.09535,1.09490,1.09510,100.0".encode()
        csv_bytes = _HEADER + b"\n" + bad_row + b"\n"
        with pytest.raises(ValueError, match="non-finite"):
            parse_csv_bytes(csv_bytes, _EURUSD_ID)


def test_parse_csv_rejects_duplicate_timestamps() -> None:
    row1 = b"2024.01.15 12:00:00,1.09525,1.09535,1.09490,1.09510,100.0"
    csv_bytes = _HEADER + b"\n" + row1 + b"\n" + row1 + b"\n"
    with pytest.raises(ValueError, match="duplicate timestamp"):
        parse_csv_bytes(csv_bytes, _EURUSD_ID)


def test_parse_csv_rejects_non_monotonic_timestamps() -> None:
    row1 = b"2024.01.15 12:02:00,1.09525,1.09535,1.09490,1.09510,100.0"
    row2 = b"2024.01.15 12:01:00,1.09510,1.09540,1.09500,1.09530,120.0"
    csv_bytes = _HEADER + b"\n" + row1 + b"\n" + row2 + b"\n"
    with pytest.raises(ValueError, match="non-monotonic timestamp"):
        parse_csv_bytes(csv_bytes, _EURUSD_ID)


def test_parse_csv_rejects_malformed_timestamp() -> None:
    bad_row = b"2024/01/15 12:00:00,1.09525,1.09535,1.09490,1.09510,100.0"
    csv_bytes = _HEADER + b"\n" + bad_row + b"\n"
    with pytest.raises(ValueError):
        parse_csv_bytes(csv_bytes, _EURUSD_ID)
