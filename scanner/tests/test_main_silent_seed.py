"""Regression test for the real incident this session: a fresh state must
never blast the whole lookback window as Telegram alerts. run_once(...,
silent=True) must mark candidates as seen WITHOUT sending any message."""
import sys
from datetime import datetime, timedelta

sys.path.insert(0, r"D:\Josué\Documents\proyectos\mado-strategy\detector")
sys.path.insert(0, r"D:\Josué\Documents\proyectos\mado-strategy\scanner")

from core.candle import Candle, OHLCSeries  # noqa: E402

import main  # noqa: E402


class _FakeAlignedSignal:
    def __init__(self, signal_id, status):
        self.ltf_signal = _FakeLtfSignal(signal_id, status)
        self.aligned = "aligned"
        self.key_level = object()
        self.key_level_reaction = "reject_close_inside"
        self.htf_context = None


class _FakeLtfSignal:
    def __init__(self, signal_id, status):
        self.signal_id = signal_id
        self.anchor_index = 0
        self.direction = "bullish"
        self.entry_type = "wick"
        self.retest_index = 1
        self.status = status
        self.origin_index = 0


def _m15_series():
    from core.results import DetectionStatus  # noqa: E402
    candles = tuple(
        Candle(
            timestamp=datetime(2026, 10, 10, 8, 0, 0) + timedelta(minutes=15 * i),
            open=1.1, high=1.1005, low=1.0995, close=1.1,
        )
        for i in range(5)
    )
    return OHLCSeries(candles=candles, instrument="EURUSDm", timeframe="15M"), DetectionStatus


def test_silent_run_never_sends_telegram_but_marks_state(monkeypatch):
    m15, DetectionStatus = _m15_series()
    aligned_signals = [_FakeAlignedSignal("sig-1", DetectionStatus.CONFIRMED)]

    sent_messages = []
    monkeypatch.setattr(main.telegram_notify, "send_message", lambda text: sent_messages.append(text))
    monkeypatch.setattr(main.mt5_feed, "fetch_series", lambda symbol, tf, count: m15)
    monkeypatch.setattr(main.news_calendar, "fetch_this_week_events", lambda: [])
    monkeypatch.setattr(main, "_detect_all", lambda *a, **k: type("R", (), {"aligned_signals": aligned_signals}))
    monkeypatch.setattr(main, "build_stage6_population", lambda *a, **k: type("P", (), {"candidates": [
        _fake_candidate("sig-1"),
    ]}))
    monkeypatch.setattr(main, "SYMBOLS", ("EURUSDm",))

    empty_state = {"alerted_ids": [], "daily_counts": {}}
    result_state = main.run_once(empty_state, silent=True)

    assert sent_messages == []
    assert "sig-1" in result_state["alerted_ids"]


def _fake_candidate(signal_id):
    from backtest.candidate import Candidate  # noqa: E402
    return Candidate(
        signal_id=signal_id, anchor_index=0, origin_index=0, direction="bullish", entry_type="wick",
        retest_index=1, entry_price=1.1005, stop_loss=1.0990, take_profit=1.1050, partial_price=1.10275,
    )
