"""Pure filter over already-built backtest.candidate.Candidate objects --
never reimplements detection, alignment, or candidate construction (those
stay owned by build_stage6_population, called from main.py). Encodes only
the two NEW rules this scanner adds on top: the London+Lunch+NY session
window and alert deduplication.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

_UTC = ZoneInfo("UTC")
_NY = ZoneInfo("America/New_York")


def _in_session(ts: datetime) -> bool:
    local = ts.replace(tzinfo=_UTC).astimezone(_NY)
    return 2 <= local.hour < 11


def _stable_id(symbol, anchor_ts, direction):
    """Candidate.signal_id is built from INDICES into whatever series was
    passed to detection -- stable only within one call. The live scanner
    re-fetches a sliding window of the most recent N candles every poll;
    a real signal's index shifts every time a new candle rolls the window
    forward, so signal_id is NOT a safe dedup key across polls (this was
    the exact cause of a real incident: every ~15 minutes, every in-window
    historical signal's index shifted, so index-based dedup saw all of
    them as "new" again, at once). The anchor candle's own TIMESTAMP never
    shifts, so it is the dedup identity instead."""
    return f"{symbol}|{anchor_ts.isoformat()}|{direction}"


def filter_new_alerts(symbol, candidates, reaction_by_signal_id, m15_series, already_alerted_ids):
    """`candidates`: backtest.population.Stage6Population.candidates (real
    selection already applied -- confirmed, aligned, has a Key Level).
    `reaction_by_signal_id`: signal_id -> AlignedSignal.key_level_reaction.
    Returns new alert dicts (symbol, signal_id, stable_id, direction,
    entry_price, stop_loss, take_profit, anchor_ts), oldest first.
    Dedup against `already_alerted_ids` uses stable_id, never signal_id."""
    alerts = []
    for c in candidates:
        if reaction_by_signal_id.get(c.signal_id) != "reject_close_inside":
            continue
        anchor_ts = m15_series.candles[c.anchor_index].timestamp
        if not _in_session(anchor_ts):
            continue
        stable_id = _stable_id(symbol, anchor_ts, c.direction)
        if stable_id in already_alerted_ids:
            continue
        alerts.append({
            "signal_id": c.signal_id, "stable_id": stable_id, "symbol": symbol, "direction": c.direction,
            "entry_price": c.entry_price, "stop_loss": c.stop_loss, "take_profit": c.take_profit,
            "anchor_ts": anchor_ts,
        })
    alerts.sort(key=lambda a: a["anchor_ts"])
    return alerts
