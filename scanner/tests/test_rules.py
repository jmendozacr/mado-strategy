"""TDD tests for rules.py -- written FIRST. Candidates are hand-built
(cheap, no need to run full detection) -- filter_new_alerts is a pure
filter over already-built Candidates, never a reimplementation of
detection/selection."""
import sys
from datetime import datetime, timedelta

sys.path.insert(0, r"D:\Josué\Documents\proyectos\mado-strategy\detector")

from core.candle import Candle, OHLCSeries  # noqa: E402
from backtest.candidate import Candidate  # noqa: E402

from rules import filter_new_alerts  # noqa: E402

# London+Lunch+NY is 02:00-11:00 NY-local. In October (EDT, UTC-4), that's
# 06:00-15:00 UTC.
_IN_SESSION_UTC = datetime(2026, 10, 15, 8, 0, 0)   # 04:00 NY-local -> inside
_OUT_OF_SESSION_UTC = datetime(2026, 10, 15, 20, 0, 0)  # 16:00 NY-local -> outside


def _series_anchored_at(ts: datetime) -> OHLCSeries:
    candles = tuple(
        Candle(timestamp=ts + timedelta(minutes=15 * i), open=1.1, high=1.1005, low=1.0995, close=1.1)
        for i in range(3)
    )
    return OHLCSeries(candles=candles, instrument="EURUSDm", timeframe="M15")


def _candidate(signal_id, anchor_index=0):
    return Candidate(
        signal_id=signal_id, anchor_index=anchor_index, origin_index=0, direction="bullish",
        entry_type="wick", retest_index=1, entry_price=1.1005, stop_loss=1.0990, take_profit=1.1050,
        partial_price=1.10275,
    )


def test_reject_close_inside_in_session_not_alerted_before_is_alerted():
    m15 = _series_anchored_at(_IN_SESSION_UTC)
    candidates = [_candidate("A")]
    alerts = filter_new_alerts("EURUSDm", candidates, {"A": "reject_close_inside"}, m15, set())
    assert len(alerts) == 1
    assert alerts[0]["signal_id"] == "A"
    assert alerts[0]["symbol"] == "EURUSDm"
    assert alerts[0]["entry_price"] == 1.1005


def test_continuation_reaction_never_alerted():
    m15 = _series_anchored_at(_IN_SESSION_UTC)
    candidates = [_candidate("A")]
    alerts = filter_new_alerts("EURUSDm", candidates, {"A": "continuation"}, m15, set())
    assert alerts == []


def test_outside_session_never_alerted():
    m15 = _series_anchored_at(_OUT_OF_SESSION_UTC)
    candidates = [_candidate("A")]
    alerts = filter_new_alerts("EURUSDm", candidates, {"A": "reject_close_inside"}, m15, set())
    assert alerts == []


def test_already_alerted_signal_id_is_skipped():
    m15 = _series_anchored_at(_IN_SESSION_UTC)
    candidates = [_candidate("A")]
    alerts = filter_new_alerts("EURUSDm", candidates, {"A": "reject_close_inside"}, m15, {"A"})
    assert alerts == []


def test_multiple_candidates_only_new_qualifying_ones_returned():
    m15 = _series_anchored_at(_IN_SESSION_UTC)
    candidates = [_candidate("A"), _candidate("B"), _candidate("C")]
    reactions = {"A": "reject_close_inside", "B": "continuation", "C": "reject_close_inside"}
    alerts = filter_new_alerts("EURUSDm", candidates, reactions, m15, {"C"})
    assert {a["signal_id"] for a in alerts} == {"A"}
