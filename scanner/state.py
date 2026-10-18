"""Scanner state: which signal_ids have already been alerted (dedup) and
today's alert count per instrument (informational context only -- never
used to auto-suppress, per the scanner's design: the human applies the
daily-loss-stop/concurrency judgment themselves)."""
import json
from pathlib import Path

_DEFAULT_PATH = Path(__file__).parent / "state.json"


def load_state(path: Path = _DEFAULT_PATH) -> dict:
    if not path.exists():
        return {"alerted_ids": [], "daily_counts": {}}
    return json.loads(path.read_text(encoding="utf-8"))


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
    return {"alerted_ids": alerted_ids, "daily_counts": daily_counts}
