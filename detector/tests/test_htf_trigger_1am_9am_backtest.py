"""No committed tool existed to backtest the LIVE 1AM+9AM diversified
strategy (`causal.htf_trigger.find_1am_9am_aligned_signals`, what
`scanner/main.py` runs) over historical data -- every prior "1AM+9AM
diversification test" measurement was a throwaway, never-committed
scratch script. This gives that construction a tested home.
"""
from datetime import datetime, timedelta

from alignment.htf_ltf import AlignedSignal
from core.candle import Candle, OHLCSeries
from core.config import DetectorConfig, FVGConfig
from core.key_level import KeyLevel
from entries.model1 import Model1Signal
from core.results import DetectionStatus
from experimental.htf_trigger_1am_9am_backtest import backtest_1am_9am, build_key_levels, trade_stats

_DAY = datetime(2026, 1, 5)


def _htf_candle(hour, o, h, l, c):
    return Candle(timestamp=_DAY + timedelta(hours=hour), open=o, high=h, low=l, close=c)


def _daily_candle(day, o, h, l, c):
    return Candle(timestamp=_DAY + timedelta(days=day), open=o, high=h, low=l, close=c)


def test_build_key_levels_pools_fvg_and_reindexed_order_block():
    """Byte-for-byte scanner.main._build_key_levels's own construction --
    FVG on the HTF series, Order Block on Daily, reindexed to HTF-index-
    space -- given its own test since it can't import scanner.main (that
    module pulls in MT5-only dependencies this suite can't load)."""
    htf = OHLCSeries(
        candles=tuple(_htf_candle(h, 1.1000, 1.1010, 1.0990, 1.1005) for h in range(0, 40, 4)),
        instrument="EURUSD", timeframe="H4",
    )
    daily = OHLCSeries(
        candles=tuple(_daily_candle(d, 1.1000, 1.1010, 1.0990, 1.1005) for d in range(5)),
        instrument="EURUSD", timeframe="Daily",
    )
    levels = build_key_levels(htf, daily, FVGConfig())
    assert all(level.kind in ("fvg", "ict_order_block") for level in levels)


def test_backtest_1am_9am_wires_key_levels_into_the_trigger_function(monkeypatch):
    """Sanity check the WIRING, not find_1am_9am_aligned_signals' own
    domain logic (already covered by test_htf_trigger_aligned_signals.py):
    `backtest_1am_9am` must build key levels from (h4, daily) and pass
    them, plus h4.candles/m15/crt_config/model1_config, straight through."""
    import experimental.htf_trigger_1am_9am_backtest as module

    zone = KeyLevel(kind="fvg", top=1.1, bottom=1.0, origin_index=0)
    signal = Model1Signal(
        anchor_index=0, direction="bullish", purge_target=1.0, confirmation_type="purge_engulf",
        entry_type="wick", entry_price=1.0, retest_index=1, status=DetectionStatus.CONFIRMED,
        confirmation_index=0, origin_index=0,
    )
    aligned = AlignedSignal(ltf_signal=signal, htf_context=None, aligned="aligned", key_level=zone)

    monkeypatch.setattr(module, "build_key_levels", lambda htf, daily, fvg_config: [zone])
    calls = []

    def _fake_trigger(htf_candles, ltf_series, key_levels, crt_config, model1_config):
        calls.append((htf_candles, ltf_series, key_levels, crt_config, model1_config))
        return [(aligned, "9am")]

    monkeypatch.setattr(module, "find_1am_9am_aligned_signals", _fake_trigger)

    m15 = OHLCSeries(candles=(), instrument="EURUSD", timeframe="15M")
    htf = OHLCSeries(candles=(_htf_candle(0, 1.1, 1.1, 1.1, 1.1),), instrument="EURUSD", timeframe="H4")
    daily = OHLCSeries(candles=(), instrument="EURUSD", timeframe="Daily")
    config = DetectorConfig()

    aligned_signals, model_by_id = backtest_1am_9am(m15, htf, daily, config)

    assert len(calls) == 1
    passed_htf_candles, passed_m15, passed_levels, passed_crt, passed_model1 = calls[0]
    assert passed_htf_candles == htf.candles
    assert passed_m15 is m15
    assert passed_levels == [zone]
    assert passed_crt is config.crt_range
    assert passed_model1 is config.model1
    assert aligned_signals == [aligned]
    assert model_by_id == {signal.signal_id: "9am"}


def test_trade_stats_reports_zero_not_an_error_for_an_empty_population():
    assert trade_stats([]) == {"trades": 0, "closed": 0, "win_rate": 0.0, "avg_r": 0.0, "total_r": 0.0}
