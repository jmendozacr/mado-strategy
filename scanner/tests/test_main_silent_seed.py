"""Regression test for the real incident this session: a fresh state must
never blast the whole lookback window as Telegram alerts. run_once(...,
silent=True) must mark candidates as seen WITHOUT sending any message.

Updated for odd/tasks/scanner-1am-9am-diversified.md T3: the detection
call path is now causal.htf_trigger.find_1am_9am_aligned_signals (not
cli._detect_all) -- mocked here the same way _detect_all used to be, since
this test is about state/Telegram behavior, not detection correctness
(that's covered by detector/tests/test_htf_trigger_aligned_signals.py).
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "detector"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.candle import Candle, OHLCSeries  # noqa: E402

import main  # noqa: E402


class _FakeAlignedSignal:
    def __init__(self, signal_id, status):
        self.ltf_signal = _FakeLtfSignal(signal_id, status)
        self.aligned = "aligned"
        self.key_level = _FakeKeyLevel()
        self.key_level_reaction = "reject_close_inside"
        self.htf_context = None


class _FakeKeyLevel:
    kind = "fvg"


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
    return OHLCSeries(candles=candles, instrument="EURUSD", timeframe="15M"), DetectionStatus


def _fake_candidate(signal_id):
    from backtest.candidate import Candidate  # noqa: E402
    return Candidate(
        signal_id=signal_id, anchor_index=0, origin_index=0, direction="bullish", entry_type="wick",
        retest_index=1, entry_price=1.1005, stop_loss=1.0990, take_profit=1.1050, partial_price=1.10275,
    )


def test_silent_run_never_sends_telegram_but_marks_state(monkeypatch):
    m15, DetectionStatus = _m15_series()
    aligned_signal = _FakeAlignedSignal("sig-1", DetectionStatus.CONFIRMED)
    results = [(aligned_signal, "9am")]

    sent_messages = []
    monkeypatch.setattr(main.telegram_notify, "send_message", lambda text: sent_messages.append(text))
    monkeypatch.setattr(main.mt5_feed, "fetch_series", lambda symbol, tf, count: m15)
    monkeypatch.setattr(main.news_calendar, "fetch_this_week_events", lambda: [])
    monkeypatch.setattr(main, "_build_key_levels", lambda *a, **k: [])
    monkeypatch.setattr(main, "find_1am_9am_aligned_signals", lambda *a, **k: results)
    monkeypatch.setattr(main, "build_stage6_population", lambda *a, **k: type("P", (), {
        "candidates": [_fake_candidate("sig-1")],
    }))
    monkeypatch.setattr(main, "SYMBOLS", ("EURUSD",))

    empty_state = {"alerted_ids": [], "daily_counts": {}}
    result_state = main.run_once(empty_state, silent=True)

    assert sent_messages == []
    assert len(result_state["alerted_ids"]) == 1
    assert result_state["alerted_ids"][0].startswith("EURUSD|")


def test_non_silent_run_sends_telegram_with_model_and_key_level_in_the_message(monkeypatch):
    m15, DetectionStatus = _m15_series()
    aligned_signal = _FakeAlignedSignal("sig-1", DetectionStatus.CONFIRMED)
    results = [(aligned_signal, "1am")]

    sent_messages = []
    monkeypatch.setattr(main.telegram_notify, "send_message", lambda text: sent_messages.append(text))
    monkeypatch.setattr(main.mt5_feed, "fetch_series", lambda symbol, tf, count: m15)
    monkeypatch.setattr(main.news_calendar, "fetch_this_week_events", lambda: [])
    monkeypatch.setattr(main.news_calendar, "is_near_high_impact_news", lambda *a, **k: False)
    monkeypatch.setattr(main, "_build_key_levels", lambda *a, **k: [])
    monkeypatch.setattr(main, "find_1am_9am_aligned_signals", lambda *a, **k: results)
    monkeypatch.setattr(main, "build_stage6_population", lambda *a, **k: type("P", (), {
        "candidates": [_fake_candidate("sig-1")],
    }))
    monkeypatch.setattr(main, "SYMBOLS", ("EURUSD",))
    monkeypatch.setattr(main, "AUTO_EXECUTE", False)

    empty_state = {"alerted_ids": [], "daily_counts": {}}
    main.run_once(empty_state, silent=False)

    assert len(sent_messages) == 1
    assert "1AM" in sent_messages[0]
    assert "reject_close_inside" in sent_messages[0]
    assert "fvg" in sent_messages[0]


def _patched_for_execution(monkeypatch, m15, results):
    monkeypatch.setattr(main.telegram_notify, "send_message", lambda text: None)
    monkeypatch.setattr(main.mt5_feed, "fetch_series", lambda symbol, tf, count: m15)
    monkeypatch.setattr(main.news_calendar, "fetch_this_week_events", lambda: [])
    monkeypatch.setattr(main.news_calendar, "is_near_high_impact_news", lambda *a, **k: False)
    monkeypatch.setattr(main, "_build_key_levels", lambda *a, **k: [])
    monkeypatch.setattr(main, "find_1am_9am_aligned_signals", lambda *a, **k: results)
    monkeypatch.setattr(main, "build_stage6_population", lambda *a, **k: type("P", (), {
        "candidates": [_fake_candidate("sig-1")],
    }))
    monkeypatch.setattr(main, "SYMBOLS", ("EURUSD",))


def test_silent_seed_never_places_an_order_even_if_auto_execute_is_on(monkeypatch):
    """S5/T3: silent=True is backfill seeding, never live trading -- a
    pre-existing historical candidate must never become a real order just
    because AUTO_EXECUTE happens to be on."""
    m15, DetectionStatus = _m15_series()
    _patched_for_execution(monkeypatch, m15, [(_FakeAlignedSignal("sig-1", DetectionStatus.CONFIRMED), "1am")])
    monkeypatch.setattr(main, "AUTO_EXECUTE", True)

    order_calls = []
    monkeypatch.setattr(main.mt5_feed, "send_pending_order", lambda *a, **k: order_calls.append((a, k)))

    main.run_once({"alerted_ids": [], "daily_counts": {}}, silent=True)
    assert order_calls == []


def test_auto_execute_true_places_a_pending_order_with_the_calculated_lot(monkeypatch):
    m15, DetectionStatus = _m15_series()
    _patched_for_execution(monkeypatch, m15, [(_FakeAlignedSignal("sig-1", DetectionStatus.CONFIRMED), "1am")])
    monkeypatch.setattr(main, "AUTO_EXECUTE", True)

    monkeypatch.setattr(main.mt5_feed, "symbol_trade_specs", lambda symbol: {
        "tick_value": 1.0, "tick_size": 0.00001, "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01,
    })
    monkeypatch.setattr(main.mt5_feed, "current_price", lambda symbol, direction: 1.1010)

    order_calls = []

    class _FakeResult:
        retcode = 10009  # TRADE_RETCODE_DONE

    monkeypatch.setattr(main.mt5_feed, "send_pending_order", lambda *a, **k: (order_calls.append((a, k)), _FakeResult())[1])
    monkeypatch.setattr(main.mt5_feed, "order_succeeded", lambda result: result.retcode == 10009)

    main.run_once({"alerted_ids": [], "daily_counts": {}}, silent=False)

    assert len(order_calls) == 1
    args, kwargs = order_calls[0]
    assert args[0] == "EURUSD"  # symbol
    # entry=1.1005, stop=1.0990 (the fixture Candidate) -> stop_distance=0.0015 ->
    # 150 ticks * $1/tick = $150/lot; risk_amount = main.INITIAL_BALANCE (10000) * 1% = $100;
    # raw_lots = 100/150 = 0.6666... -> floored to the 0.01 step = 0.66.
    assert kwargs["volume"] == 0.66


def test_lot_below_minimum_skips_the_order_without_crashing(monkeypatch):
    """Risk is always INITIAL_BALANCE*RISK_PCT now (fixed, non-compounding
    -- never the live account balance), so "below minimum" has to be
    triggered via the symbol's own specs here, not via a tiny balance."""
    m15, DetectionStatus = _m15_series()
    _patched_for_execution(monkeypatch, m15, [(_FakeAlignedSignal("sig-1", DetectionStatus.CONFIRMED), "1am")])
    monkeypatch.setattr(main, "AUTO_EXECUTE", True)

    monkeypatch.setattr(main.mt5_feed, "symbol_trade_specs", lambda symbol: {
        "tick_value": 1.0, "tick_size": 0.00001, "volume_min": 1.0, "volume_max": 100.0, "volume_step": 0.01,
    })  # volume_min raised to 1.0 lot -- the real target (0.66) rounds below it
    monkeypatch.setattr(main.mt5_feed, "current_price", lambda symbol, direction: 1.1010)

    order_calls = []
    monkeypatch.setattr(main.mt5_feed, "send_pending_order", lambda *a, **k: order_calls.append((a, k)))

    main.run_once({"alerted_ids": [], "daily_counts": {}}, silent=False)
    assert order_calls == []


def test_order_send_exception_is_logged_not_raised(monkeypatch):
    """S6: one symbol's execution failure must never crash the poll."""
    m15, DetectionStatus = _m15_series()
    _patched_for_execution(monkeypatch, m15, [(_FakeAlignedSignal("sig-1", DetectionStatus.CONFIRMED), "1am")])
    monkeypatch.setattr(main, "AUTO_EXECUTE", True)

    monkeypatch.setattr(main.mt5_feed, "symbol_trade_specs", lambda symbol: {
        "tick_value": 1.0, "tick_size": 0.00001, "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01,
    })
    monkeypatch.setattr(main.mt5_feed, "current_price", lambda symbol, direction: 1.1010)

    def _boom(*a, **k):
        raise main.mt5_feed.MT5ConnectionError("terminal disconnected")
    monkeypatch.setattr(main.mt5_feed, "send_pending_order", _boom)

    # Must not raise.
    result_state = main.run_once({"alerted_ids": [], "daily_counts": {}}, silent=False)
    assert len(result_state["alerted_ids"]) == 1  # the alert itself still went through
