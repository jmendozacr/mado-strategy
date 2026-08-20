from core.candle import OHLCSeries
from core.pairing_table import PairingError, validate_pairing
from ingestion.loader import load_mt5_csv


def load_pair(
    htf_csv: str, htf_symbol: str, ltf_csv: str, ltf_symbol: str
) -> tuple[OHLCSeries, OHLCSeries]:
    """Load an HTF+LTF CSV pair for the SAME instrument (REQ-03), rejecting
    a mismatched-instrument pairing (REQ-27) or an unlisted timeframe
    pairing (REQ-04, via core.pairing_table).
    """
    if htf_symbol != ltf_symbol:
        raise PairingError(
            f"mismatched instrument pairing: htf_symbol={htf_symbol} "
            f"ltf_symbol={ltf_symbol}"
        )

    htf_series = load_mt5_csv(htf_csv, symbol=htf_symbol)
    ltf_series = load_mt5_csv(ltf_csv, symbol=ltf_symbol)

    validate_pairing(htf_series.timeframe, ltf_series.timeframe)

    return htf_series, ltf_series
