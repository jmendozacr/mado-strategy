from datetime import datetime, timedelta

from core.candle import Candle, OHLCSeries
from experimental.order_block_redefinition_backtest import daily_key_levels, trade_stats


class _FakeTrade:
    def __init__(self, outcome, r_multiple):
        self.outcome = outcome
        self.r_multiple = r_multiple


def _candle(i, o, c, h=None, l=None):
    return Candle(
        timestamp=datetime(2026, 1, 1) + timedelta(days=i),
        open=o, close=c,
        high=h if h is not None else max(o, c) + 0.0001,
        low=l if l is not None else min(o, c) - 0.0001,
    )


def _series_with_a_bearish_engulfing_pair_and_a_real_bos() -> OHLCSeries:
    """20 flat candles, a bearish anchor, then one huge bullish candle that
    both (a) fully engulfs the anchor (satisfies the ARCHIVED 2-candle
    rule) and (b) is itself a decisive structural break + displacement
    (satisfies the REDEFINED chain) -- exercises both detectors from one
    fixture."""
    candles = []
    price = 1.10
    for i in range(20):
        candles.append(_candle(i, price, price + 0.0005))
        price += 0.0005
    candles.append(_candle(20, 1.1100, 1.1090))  # bearish anchor
    candles.append(_candle(21, 1.1095, 1.1300, h=1.1310, l=1.1085))  # engulfs + displaces
    return OHLCSeries(candles=tuple(candles), instrument="EURUSDm", timeframe="Daily")


class TestDailyKeyLevels:
    def test_archived_and_redefined_both_return_ict_order_block_kind(self) -> None:
        series = _series_with_a_bearish_engulfing_pair_and_a_real_bos()
        archived = daily_key_levels(series, redefined=False)
        redefined = daily_key_levels(series, redefined=True)
        assert all(level.kind == "ict_order_block" for level in archived)
        assert all(level.kind == "ict_order_block" for level in redefined)

    def test_dispatch_reaches_the_archived_detector_when_not_redefined(self, monkeypatch) -> None:
        """Sanity check the WIRING, not either detector's own domain logic
        (already covered by their own test suites): `redefined=False`
        must call `primitives.ict_order_block.detect_ict_order_blocks`
        and never `composite.ict_order_block.detect_order_blocks`."""
        import experimental.order_block_redefinition_backtest as module

        calls = []
        monkeypatch.setattr(
            module, "detect_ict_order_blocks", lambda series: calls.append("archived") or []
        )
        monkeypatch.setattr(
            module, "detect_order_blocks", lambda series: calls.append("redefined") or []
        )

        module.daily_key_levels(_series_with_a_bearish_engulfing_pair_and_a_real_bos(), redefined=False)
        assert calls == ["archived"]

    def test_dispatch_reaches_the_redefined_detector_when_redefined(self, monkeypatch) -> None:
        import experimental.order_block_redefinition_backtest as module

        calls = []
        monkeypatch.setattr(
            module, "detect_ict_order_blocks", lambda series: calls.append("archived") or []
        )
        monkeypatch.setattr(
            module, "detect_order_blocks", lambda series: calls.append("redefined") or []
        )

        module.daily_key_levels(_series_with_a_bearish_engulfing_pair_and_a_real_bos(), redefined=True)
        assert calls == ["redefined"]


class TestTradeStats:
    def test_empty_reports_zero_not_an_error(self) -> None:
        stats = trade_stats([])
        assert stats == {"trades": 0, "closed": 0, "win_rate": 0.0, "avg_r": 0.0, "total_r": 0.0}

    def test_counts_wins_losses_and_r_over_closed_trades_only(self) -> None:
        trades = [
            _FakeTrade("win", 2.0),
            _FakeTrade("loss", -1.0),
            _FakeTrade("open", None),
        ]
        stats = trade_stats(trades)
        assert stats["trades"] == 3
        assert stats["closed"] == 2
        assert stats["win_rate"] == 0.5
        assert stats["avg_r"] == 0.5
        assert stats["total_r"] == 1.0
