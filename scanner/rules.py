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


def filter_new_alerts(symbol, candidates, reaction_by_signal_id, m15_series, already_alerted_ids):
    """`candidates`: backtest.population.Stage6Population.candidates (real
    selection already applied -- confirmed, aligned, has a Key Level).
    `reaction_by_signal_id`: signal_id -> AlignedSignal.key_level_reaction.
    Returns new alert dicts (symbol, signal_id, direction, entry_price,
    stop_loss, take_profit, anchor_ts), oldest first."""
    alerts = []
    for c in candidates:
        if c.signal_id in already_alerted_ids:
            continue
        if reaction_by_signal_id.get(c.signal_id) != "reject_close_inside":
            continue
        anchor_ts = m15_series.candles[c.anchor_index].timestamp
        if not _in_session(anchor_ts):
            continue
        alerts.append({
            "signal_id": c.signal_id, "symbol": symbol, "direction": c.direction,
            "entry_price": c.entry_price, "stop_loss": c.stop_loss, "take_profit": c.take_profit,
            "anchor_ts": anchor_ts,
        })
    alerts.sort(key=lambda a: a["anchor_ts"])
    return alerts
