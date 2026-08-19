from datetime import datetime

from core.candle import Candle, OHLCSeries


def _candle(hour: int, price: float) -> Candle:
    return Candle(
        timestamp=datetime(2026, 1, 1, hour),
        open=price,
        high=price + 1,
        low=price - 1,
        close=price,
    )


def test_up_to_returns_candles_with_index_strictly_less_than_n():
    series = OHLCSeries(
        candles=(_candle(0, 1.0), _candle(1, 2.0), _candle(2, 3.0), _candle(3, 4.0)),
        instrument="EURUSD",
        timeframe="1H",
    )

    truncated = series.up_to(2)

    assert truncated.candles == (_candle(0, 1.0), _candle(1, 2.0))


def test_up_to_excludes_the_index_itself():
    series = OHLCSeries(
        candles=(_candle(0, 1.0), _candle(1, 2.0), _candle(2, 3.0), _candle(3, 4.0)),
        instrument="EURUSD",
        timeframe="1H",
    )

    truncated = series.up_to(3)

    assert truncated.candles == (_candle(0, 1.0), _candle(1, 2.0), _candle(2, 3.0))
    assert truncated.instrument == "EURUSD"
    assert truncated.timeframe == "1H"
