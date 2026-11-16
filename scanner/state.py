"""Scanner state: which signal_ids have already been alerted (dedup) and
today's alert count per instrument (informational context only -- never
used to auto-suppress, per the scanner's design: the human applies the
daily-loss-stop/concurrency judgment themselves)."""
import json
from pathlib import Path

_DEFAULT_PATH = Path(__file__).parent / "state.json"


def load_state(path: Path = _DEFAULT_PATH) -> dict:
    if not path.exists():
        return {"alerted_ids": [], "daily_counts": {}, "pending_partial": {}}
    state = json.loads(path.read_text(encoding="utf-8"))
    # odd/tasks/scanner-breakeven-after-partial.md T2: the live state.json
    # predates this key -- backfill it so loading the real production
    # file never raises a KeyError.
    state.setdefault("pending_partial", {})
    return state


def save_state(state: dict, path: Path = _DEFAULT_PATH) -> None:
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def already_alerted(state: dict, signal_id: str) -> bool:
    return signal_id in state["alerted_ids"]


def record_alert(state: dict, signal_id: str, symbol: str, day: str) -> dict:
    """Returns a NEW state dict (never mutates the input) with signal_id
    marked alerted and today's count for `symbol` incremented."""
    alerted_ids = state["alerted_ids"] + [signal_id]
    daily_counts = {k: dict(v) for k, v in state["daily_counts"].items()}
    day_counts = dict(daily_counts.get(day, {}))
    day_counts[symbol] = day_counts.get(symbol, 0) + 1
    daily_counts[day] = day_counts
    return {**state, "alerted_ids": alerted_ids, "daily_counts": daily_counts}


def record_pending_partial(state: dict, ticket: str, info: dict) -> dict:
    """odd/tasks/scanner-breakeven-after-partial.md T2/T4: `ticket` is the
    MT5 position ticket (== the originating pending order's own ticket,
    confirmed by MT5's own fill behavior) a NEW trade filled into. `info`
    carries everything a later poll needs to detect the partial and act
    on it -- symbol, direction, partial_price, stop_loss (ORIGINAL, for
    the record only), take_profit, volume -- never re-fetched from MT5.
    Returns a NEW state dict, never mutates the input."""
    pending_partial = dict(state["pending_partial"])
    pending_partial[ticket] = dict(info)
    return {**state, "pending_partial": pending_partial}


def clear_pending_partial(state: dict, ticket: str) -> dict:
    """Idempotent: clearing an unknown/already-cleared ticket is a no-op,
    never an error -- a poll that retries after a partial failure must be
    safe to call this again."""
    pending_partial = {k: v for k, v in state["pending_partial"].items() if k != ticket}
    return {**state, "pending_partial": pending_partial}
