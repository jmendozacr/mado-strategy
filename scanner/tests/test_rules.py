"""TDD tests for rules.py -- written FIRST. Candidates are hand-built
(cheap, no need to run full detection) -- filter_new_alerts is a pure
filter over already-built Candidates, never a reimplementation of
detection/selection.

odd/tasks/scanner-1am-9am-diversified.md S4/S5: the 1AM/9AM recipe this
replaces the old EURUSD-only recipe with needs neither a fixed session
window (each FeederModel's own confirmation window already bounds which
M15 candles can ever produce a Candidate -- see causal.htf_trigger) nor a
reaction-type filter (the validated backtest population includes BOTH
reject_close_inside and continuation). filter_new_alerts therefore no
longer gates on either -- it only dedups and carries the reaction through
for display.

Dedup uses a TIMESTAMP-based stable_id, never Candidate.signal_id alone:
signal_id is built from indices (origin_index-anchor_index-...) into
WHATEVER series was passed to detection -- stable only within one call.
The live scanner re-fetches a SLIDING window of the most recent N candles
every poll; a real signal's index shifts every time a new candle rolls the
window forward, so signal_id is NOT stable across polls even though the
same real signal is being looked at. This is the exact bug behind the
40+-message incident: every ~15 minutes (a new M15 candle), every
in-window historical signal's index shifted, so index-based dedup saw
every one of them as "new" again, all at once. stable_id is derived from
the signal's own anchor TIMESTAMP instead, which never shifts.
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "detector"))

from core.candle import Candle, OHLCSeries  # noqa: E402
from backtest.candidate import Candidate  # noqa: E402

from rules import filter_new_alerts  # noqa: E402

_ANCHOR_UTC = datetime(2026, 10, 15, 4, 0, 0)  # arbitrary -- no session meaning anymore


def _series_anchored_at(ts: datetime, pad_before: int = 0) -> OHLCSeries:
    """`pad_before` prepends extra candles BEFORE the anchor -- simulates
    the sliding window having moved forward (more history now precedes the
    same real anchor candle), shifting its absolute index without changing
    its real timestamp."""
    start = ts - timedelta(minutes=15 * pad_before)
    candles = tuple(
        Candle(timestamp=start + timedelta(minutes=15 * i), open=1.1, high=1.1005, low=1.0995, close=1.1)
        for i in range(pad_before + 3)
    )
    return OHLCSeries(candles=candles, instrument="EURUSDm", timeframe="M15")


def _candidate(signal_id, anchor_index=0):
    return Candidate(
        signal_id=signal_id, anchor_index=anchor_index, origin_index=0, direction="bullish",
        entry_type="wick", retest_index=1, entry_price=1.1005, stop_loss=1.0990, take_profit=1.1050,
        partial_price=1.10275,
    )


def test_reject_close_inside_is_alerted_with_reaction_carried_through():
    m15 = _series_anchored_at(_ANCHOR_UTC)
    candidates = [_candidate("A")]
    alerts = filter_new_alerts("EURUSDm", candidates, {"A": "reject_close_inside"}, m15, set())
    assert len(alerts) == 1
    assert alerts[0]["signal_id"] == "A"
    assert alerts[0]["symbol"] == "EURUSDm"
    assert alerts[0]["entry_price"] == 1.1005
    assert alerts[0]["key_level_reaction"] == "reject_close_inside"
    assert alerts[0]["stable_id"] == f"EURUSDm|{_ANCHOR_UTC.isoformat()}|bullish"


def test_continuation_reaction_is_also_alerted():
    """S4: no longer dropped -- the validated backtest population includes
    continuation reactions, so the live recipe must alert on them too."""
    m15 = _series_anchored_at(_ANCHOR_UTC)
    candidates = [_candidate("A")]
    alerts = filter_new_alerts("EURUSDm", candidates, {"A": "continuation"}, m15, set())
    assert len(alerts) == 1
    assert alerts[0]["key_level_reaction"] == "continuation"


def test_already_alerted_stable_id_is_skipped():
    m15 = _series_anchored_at(_ANCHOR_UTC)
    candidates = [_candidate("A")]
    stable_id = f"EURUSDm|{_ANCHOR_UTC.isoformat()}|bullish"
    alerts = filter_new_alerts("EURUSDm", candidates, {"A": "reject_close_inside"}, m15, {stable_id})
    assert alerts == []


def test_multiple_candidates_both_reactions_pass_only_dedup_excludes():
    m15 = _series_anchored_at(_ANCHOR_UTC)  # 3 candles: index 0/1/2, each 15min apart
    candidates = [_candidate("A", anchor_index=0), _candidate("B", anchor_index=1), _candidate("C", anchor_index=2)]
    reactions = {"A": "reject_close_inside", "B": "continuation", "C": "reject_close_inside"}
    c_anchor_ts = _ANCHOR_UTC + timedelta(minutes=30)  # candle index 2
    c_stable_id = f"EURUSDm|{c_anchor_ts.isoformat()}|bullish"
    alerts = filter_new_alerts("EURUSDm", candidates, reactions, m15, {c_stable_id})
    # A and B both pass now (neither reaction type is filtered); only C is
    # excluded, by dedup -- not by its (also non-filtered) reaction.
    assert {a["signal_id"] for a in alerts} == {"A", "B"}


def test_same_real_signal_different_index_after_window_slide_is_still_deduped():
    """THE regression test for the 40+-message incident: the window slides
    forward (5 more candles now precede the same real anchor), so the SAME
    real anchor candle moves from index 0 to index 5 -- a real
    Model1Signal.signal_id (built from indices) would therefore be a
    DIFFERENT STRING on the second poll even though it's the same real
    signal. stable_id, derived from the anchor candle's own timestamp
    (never its index), must still catch the duplicate."""
    m15_first_poll = _series_anchored_at(_ANCHOR_UTC, pad_before=0)
    first_alerts = filter_new_alerts(
        "EURUSDm", [_candidate("0-0-bullish-purge_engulf-wick", anchor_index=0)],
        {"0-0-bullish-purge_engulf-wick": "reject_close_inside"}, m15_first_poll, set(),
    )
    assert len(first_alerts) == 1
    already_alerted = {first_alerts[0]["stable_id"]}

    # Window slid forward 5 candles: same real anchor, now at index 5, and
    # a real pipeline run would therefore produce a DIFFERENT signal_id
    # string here -- deliberately used below to prove dedup doesn't rely
    # on signal_id matching.
    m15_later_poll = _series_anchored_at(_ANCHOR_UTC, pad_before=5)
    later_alerts = filter_new_alerts(
        "EURUSDm", [_candidate("0-5-bullish-purge_engulf-wick", anchor_index=5)],
        {"0-5-bullish-purge_engulf-wick": "reject_close_inside"}, m15_later_poll, already_alerted,
    )
    assert later_alerts == []
