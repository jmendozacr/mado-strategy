"""Pure filter over already-built backtest.candidate.Candidate objects --
never reimplements detection, alignment, or candidate construction (those
stay owned by causal.htf_trigger.find_1am_9am_aligned_signals +
build_stage6_population, called from main.py). Encodes only the ONE rule
this scanner adds on top: alert deduplication.

odd/tasks/scanner-1am-9am-diversified.md S4/S5 (replacing the old EURUSD-
only recipe): no fixed session window and no reaction-type filter here
anymore. Each FeederModel's own confirmation window
(causal.htf_trigger.confirmation_window_utc/ltf_window_indices) already
bounds which M15 candles can ever produce a Candidate at all, so a second,
independent session check in this module would just be a second place for
that boundary to silently drift out of sync with the real one. And the
validated backtest population (428 trades, 60.7% WR, +$30,345 at $10k/1%
risk -- see Engram "Combined 3-pair and 2-pair account simulation") includes
BOTH reject_close_inside and continuation reactions: filtering either out
here would alert on a different, unvalidated, worse-performing population
than the one actually backtested and approved.
"""


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
    `reaction_by_signal_id`: signal_id -> AlignedSignal.key_level_reaction,
    carried through onto the alert for display, never used to exclude one.
    Returns new alert dicts (symbol, signal_id, stable_id, direction,
    entry_price, stop_loss, take_profit, anchor_ts, key_level_reaction),
    oldest first. Dedup against `already_alerted_ids` uses stable_id, never
    signal_id."""
    alerts = []
    for c in candidates:
        anchor_ts = m15_series.candles[c.anchor_index].timestamp
        stable_id = _stable_id(symbol, anchor_ts, c.direction)
        if stable_id in already_alerted_ids:
            continue
        alerts.append({
            "signal_id": c.signal_id, "stable_id": stable_id, "symbol": symbol, "direction": c.direction,
            "entry_price": c.entry_price, "stop_loss": c.stop_loss, "take_profit": c.take_profit,
            "partial_price": c.partial_price,
            "anchor_ts": anchor_ts, "key_level_reaction": reaction_by_signal_id.get(c.signal_id),
        })
    alerts.sort(key=lambda a: a["anchor_ts"])
    return alerts
