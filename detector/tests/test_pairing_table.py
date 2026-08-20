import pytest

from core.pairing_table import PairingError, validate_pairing


def test_daily_htf_with_1h_ltf_passes():
    """REQ-04.1: Daily CRT pairs with 1-Hour Model-1 per charter-2's table."""
    validate_pairing(htf_timeframe="D", ltf_timeframe="1H")


def test_daily_htf_with_5m_ltf_is_rejected_citing_expected_1h():
    """REQ-04.2: Daily+5M is not a listed pairing -> rejected, citing the
    expected 1H.
    """
    with pytest.raises(PairingError, match="1H"):
        validate_pairing(htf_timeframe="D", ltf_timeframe="5M")


def test_all_five_charter2_pairings_pass():
    """Charter-2 [00:14:37]'s full 5-row table: Monthly->Daily,
    Weekly->4H, Daily->1H, 4H->15M, 1H->5M.
    """
    for htf_timeframe, ltf_timeframe in [
        ("MN", "D"),
        ("W", "4H"),
        ("D", "1H"),
        ("4H", "15M"),
        ("1H", "5M"),
    ]:
        validate_pairing(htf_timeframe=htf_timeframe, ltf_timeframe=ltf_timeframe)


def test_unsupported_htf_timeframe_is_rejected():
    with pytest.raises(PairingError, match="15M"):
        validate_pairing(htf_timeframe="15M", ltf_timeframe="5M")
