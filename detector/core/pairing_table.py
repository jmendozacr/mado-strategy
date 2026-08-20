from datetime import timedelta

TIMEFRAME_DURATIONS: dict[str, timedelta] = {
    "5M": timedelta(minutes=5),
    "15M": timedelta(minutes=15),
    "1H": timedelta(hours=1),
    "4H": timedelta(hours=4),
    "D": timedelta(days=1),
    "W": timedelta(days=7),
    "MN": timedelta(days=30),
}

PAIRING_TABLE: dict[str, str] = {
    "MN": "D",
    "W": "4H",
    "D": "1H",
    "4H": "15M",
    "1H": "5M",
}


class PairingError(Exception):
    pass


def validate_pairing(htf_timeframe: str, ltf_timeframe: str) -> None:
    """Charter-2 [00:14:37]'s 5-row HTF->LTF timeframe pairing table."""
    expected_ltf = PAIRING_TABLE.get(htf_timeframe)
    if expected_ltf is None:
        raise PairingError(
            f"unsupported HTF timeframe: {htf_timeframe} "
            f"(expected one of {', '.join(PAIRING_TABLE)})"
        )
    if ltf_timeframe != expected_ltf:
        raise PairingError(
            f"invalid HTF/LTF pairing: {htf_timeframe}+{ltf_timeframe} "
            f"(expected {htf_timeframe}+{expected_ltf})"
        )
