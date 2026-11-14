from datetime import datetime, timedelta

from core.candle import Candle, OHLCSeries
from core.key_level import KeyLevel
from experimental.breaker_block_key_level_backtest import (
    credit_counts_by_kind,
    daily_key_levels,
)


def _candle(i, o, h, l, c):
    return Candle(timestamp=datetime(2026, 1, 1) + timedelta(days=i), open=o, high=h, low=l, close=c)


def _daily_series_with_an_invalidated_model1() -> OHLCSeries:
    """Same anchor/confirm/invalidate shape as
    `tests.fixtures.synthetic.model1_invalidated_setup`, just re-timestamped
    as a Daily series: anchor @1 purges the range High, confirms @2, closes
    beyond the protected extreme @3 -> INVALIDATED -> one BreakerBlock."""
    return OHLCSeries(
        candles=(
            _candle(0, 1.1000, 1.1020, 1.0980, 1.1010),
            _candle(1, 1.1010, 1.1035, 1.1005, 1.1015),
            _candle(2, 1.1000, 1.1005, 1.0990, 1.0995),
            _candle(3, 1.0995, 1.1040, 1.0990, 1.1038),
        ),
        instrument="EURUSDm", timeframe="Daily",
    )


class TestDailyKeyLevels:
    def test_without_breaker_returns_only_order_block_kind(self) -> None:
        from core.config import DetectorConfig

        series = _daily_series_with_an_invalidated_model1()
        levels = daily_key_levels(series, DetectorConfig(), include_breaker=False)
        assert all(level.kind == "ict_order_block" for level in levels)

    def test_with_breaker_adds_the_breaker_block_kind(self) -> None:
        from core.config import DetectorConfig

        series = _daily_series_with_an_invalidated_model1()
        levels = daily_key_levels(series, DetectorConfig(), include_breaker=True)
        assert any(level.kind == "breaker_block" for level in levels)

    def test_dispatch_skips_breaker_detection_when_not_requested(self, monkeypatch) -> None:
        """Sanity check the WIRING, not the detector's own domain logic
        (covered by tests/test_breaker_block.py): `include_breaker=False`
        must never call `entries.breaker_block.detect_breaker_blocks`."""
        import experimental.breaker_block_key_level_backtest as module
        from core.config import DetectorConfig

        calls = []
        monkeypatch.setattr(
            module, "detect_breaker_blocks",
            lambda candles, signals, config: calls.append("breaker") or [],
        )

        module.daily_key_levels(_daily_series_with_an_invalidated_model1(), DetectorConfig(), include_breaker=False)
        assert calls == []

        module.daily_key_levels(_daily_series_with_an_invalidated_model1(), DetectorConfig(), include_breaker=True)
        assert calls == ["breaker"]


class TestCreditCountsByKind:
    def test_counts_by_kind_ignoring_uncredited_signals(self) -> None:
        class _FakeSignal:
            def __init__(self, key_level):
                self.key_level = key_level

        fvg = KeyLevel(kind="fvg", top=1.1, bottom=1.0, origin_index=0)
        breaker = KeyLevel(kind="breaker_block", top=1.1, bottom=1.0, origin_index=0)
        signals = [_FakeSignal(fvg), _FakeSignal(fvg), _FakeSignal(breaker), _FakeSignal(None)]

        assert credit_counts_by_kind(signals) == {"fvg": 2, "breaker_block": 1}

    def test_empty_population_reports_empty_dict(self) -> None:
        assert credit_counts_by_kind([]) == {}
