"""Deliverables: funnel by close-position group, original-outcome
comparison by group, and timeline/causal-availability flags.

Reuses, read-only: `extract.from_causal_lookahead_audit.extract` (the
real ledger, for ORIGINAL trade outcomes -- entry_ts/exit_ts/r_multiple/
outcome, never a resimulated value) from the sibling
`research/loss-pattern-discovery` lab, and that lab's own block-
bootstrap percentile helper (`stats.early_stop_hypothesis._percentile_ci`)
for the uncertainty on the primary mean-R difference. The block-
resampling unit here is (symbol, NY trading date) -- not that lab's own
ISO-week block -- because this protocol's own clustering concern is
signals sharing a current H4 candle (which always share the same NY
date), stated explicitly in `docs/01-protocol.md`.
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

LAB_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = LAB_ROOT.parent.parent
DETECTOR_ROOT = REPO_ROOT / "detector"
LPD_ROOT = REPO_ROOT / "research" / "loss-pattern-discovery"
for _path in (LAB_ROOT, DETECTOR_ROOT, LPD_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from extract.from_causal_lookahead_audit import extract as extract_ledger  # noqa: E402
from schema.events import Outcome  # noqa: E402
from stats.early_stop_hypothesis import N_RESAMPLES, PRIMARY_CI_LEVEL, SEED, _percentile_ci  # noqa: E402

_NY = ZoneInfo("America/New_York")
_UTC = ZoneInfo("UTC")
SYMBOLS = ("EURUSD", "USDCAD", "AUDUSD")
CLOSE_GROUPS = ("INSIDE", "OUTSIDE", "EXACT_BOUNDARY", "MISSING_OR_INCOMPLETE")


def load_classifications() -> dict[str, dict]:
    """Merges the 3 per-symbol artifacts. Raises explicitly if any is
    missing -- never silently proceeds on a partial population."""
    merged = {}
    missing = []
    for symbol in SYMBOLS:
        path = LAB_ROOT / "artifacts" / f"raza_9am_classification_{symbol}.json"
        if not path.exists():
            missing.append(symbol)
            continue
        merged[symbol] = json.loads(path.read_text(encoding="utf-8"))
    if missing:
        raise FileNotFoundError(f"missing classification artifacts for {missing}")
    return merged


def _ny_date(ts: datetime):
    return ts.replace(tzinfo=_UTC).astimezone(_NY).date()


def build_trigger_table(data: dict) -> list[dict]:
    """One row per (symbol, stable_id) trigger -- the unit of
    observation (protocol section 'Unit of observation')."""
    rows = []
    for symbol, payload in data.items():
        confirmed = set(payload["confirmed_sids"])
        candidate = set(payload["candidate_sids"])
        filled = set(payload["filled_sids"])
        executed = payload["executed"]
        for sid, c in payload["classifications"].items():
            rows.append({
                "symbol": symbol, "stable_id": sid, "direction": c["direction"],
                "current_open_ts": datetime.fromisoformat(c["current_open_ts"]),
                "h4_close_available_ts": datetime.fromisoformat(c["h4_close_available_ts"]),
                "close_position": c["close_position"], "sweep_side": c["sweep_side"],
                "raza_direction": c["raza_direction"],
                "is_confirmed": sid in confirmed, "is_candidate": sid in candidate,
                "is_filled": sid in filled, "is_executed": sid in executed,
            })
    return rows


def distinct_candle_and_signal_counts(rows: list[dict]) -> dict:
    """Requirement: show BOTH signal counts and distinct candle counts,
    since one H4 candle can produce up to 2 signals (one per
    direction)."""
    candles = {(r["symbol"], r["current_open_ts"]) for r in rows}
    return {"n_signals": len(rows), "n_distinct_candles": len(candles)}


def funnel_by_group(rows: list[dict]) -> dict:
    out = {}
    for group in CLOSE_GROUPS:
        sub = [r for r in rows if r["close_position"] == group]
        out[group] = {
            "n_signals": len(sub),
            "n_distinct_candles": len({(r["symbol"], r["current_open_ts"]) for r in sub}),
            "confirmed": sum(r["is_confirmed"] for r in sub),
            "candidate": sum(r["is_candidate"] for r in sub),
            "filled": sum(r["is_filled"] for r in sub),
        }
    totals = distinct_candle_and_signal_counts(rows)
    out["TOTAL"] = {
        "n_signals": totals["n_signals"], "n_distinct_candles": totals["n_distinct_candles"],
        "confirmed": sum(r["is_confirmed"] for r in rows),
        "candidate": sum(r["is_candidate"] for r in rows),
        "filled": sum(r["is_filled"] for r in rows),
    }
    return out


def sweep_side_breakdown(rows: list[dict]) -> dict:
    return dict(Counter(r["sweep_side"] for r in rows))


def join_executed_outcomes(rows: list[dict]) -> list[dict]:
    """Joins filled/executed signals to the REAL ledger by `stable_id`
    -- the ORIGINAL execution record (entry/stop/target/cost/RR rules
    unchanged), never a resimulated outcome. Reports, per executed
    trigger: outcome, r_multiple, entry_ts, exit_ts, whether exit_ts is
    before/at/after the H4 close-availability instant (13:00 NY same
    day), with exact ties marked indeterminate."""
    ledger = extract_ledger(REPO_ROOT)
    ledger_by_id = {r.identification.event_id: r for r in ledger}

    joined = []
    for r in rows:
        if not r["is_executed"]:
            continue
        led = ledger_by_id.get(r["stable_id"])
        if led is None:
            joined.append({**r, "ledger_match": False})
            continue
        op = led.operation
        close_ts = r["h4_close_available_ts"]
        exit_ts = op.exit_ts
        if op.outcome is Outcome.OPEN or exit_ts is None:
            ordering = "OPEN_NO_EXIT_YET"
        elif exit_ts < close_ts:
            ordering = "OUTCOME_KNOWN_BEFORE_1300"
        elif exit_ts > close_ts:
            ordering = "OUTCOME_KNOWN_AFTER_1300"
        else:
            ordering = "ORDERING_INDETERMINATE"
        joined.append({
            **r, "ledger_match": True, "outcome": op.outcome.value, "r_multiple": op.r_multiple,
            "entry_ts": op.entry_ts.isoformat() if op.entry_ts else None,
            "exit_ts": exit_ts.isoformat() if exit_ts else None,
            "outcome_vs_1300": ordering,
        })
    return joined


def order_placement_vs_h4_close(rows: list[dict]) -> dict:
    """The decisive timeline check: is the ORIGINAL order ever placed
    AFTER the current H4 candle's own close becomes available? The 9AM
    confirmation window is itself 09:00-13:00 NY -- the SAME span as
    the current candle -- so this checks whether that window's own
    deadline ever extends past the candle's own close, which would be
    required for a prospective "wait for the close" entry rule to even
    be representable under the EXISTING window design."""
    ledger = extract_ledger(REPO_ROOT)
    by_sid = {r["stable_id"]: r for r in rows}
    before = after = tie = missing = 0
    for rec in ledger:
        if rec.identification.session_label != "9am":
            continue
        r = by_sid.get(rec.identification.event_id)
        order_ts = rec.features_pre_entry.order_placed_ts
        if r is None or order_ts is None:
            missing += 1
            continue
        close_ts = r["h4_close_available_ts"]
        if order_ts < close_ts:
            before += 1
        elif order_ts > close_ts:
            after += 1
        else:
            tie += 1
    return {
        "order_placed_before_1300": before, "order_placed_after_1300": after,
        "order_placed_exactly_at_1300": tie, "missing": missing,
        "total": before + after + tie + missing,
    }


def outcome_stats_by_group(joined: list[dict], instrument: str | None = None) -> dict:
    out = {}
    for group in CLOSE_GROUPS:
        sub = [
            j for j in joined if j["close_position"] == group and j["outcome"] != Outcome.OPEN.value
            and (instrument is None or j["symbol"] == instrument)
        ]
        rs = [j["r_multiple"] for j in sub if j["r_multiple"] is not None]
        wins = [j["outcome"] == Outcome.WIN.value for j in sub]
        out[group] = {
            "n": len(sub), "n_open_excluded": sum(
                1 for j in joined if j["close_position"] == group and j["outcome"] == Outcome.OPEN.value
                and (instrument is None or j["symbol"] == instrument)
            ),
            "mean_r": (sum(rs) / len(rs)) if rs else None,
            "win_rate": (sum(wins) / len(wins)) if wins else None,
        }
    return out


def _block_key(j: dict) -> tuple:
    return (j["symbol"], _ny_date(j["current_open_ts"]))


def _group_by_block(rows: list[tuple[float, tuple]]) -> list[list[float]]:
    blocks: dict = {}
    for value, key in rows:
        blocks.setdefault(key, []).append(value)
    return list(blocks.values())


def _resample_mean(blocks: list[list[float]], rng: random.Random) -> float:
    if not blocks:
        return float("nan")
    chosen = [blocks[rng.randrange(len(blocks))] for _ in range(len(blocks))]
    pooled = [v for block in chosen for v in block]
    return sum(pooled) / len(pooled) if pooled else float("nan")


def mean_r_difference_ci(joined: list[dict], group_a: str, group_b: str) -> dict:
    """Block bootstrap on the (group_a - group_b) mean-R difference,
    clustering by (symbol, NY trading date) -- signals sharing a
    current H4 candle always share this same block."""
    def _rows_for(group):
        return [
            (j["r_multiple"], _block_key(j))
            for j in joined
            if j["close_position"] == group and j["outcome"] != Outcome.OPEN.value and j["r_multiple"] is not None
        ]

    rows_a, rows_b = _rows_for(group_a), _rows_for(group_b)
    if not rows_a or not rows_b:
        return {"n_a": len(rows_a), "n_b": len(rows_b), "insufficient_support": True}

    mean_a = sum(v for v, _ in rows_a) / len(rows_a)
    mean_b = sum(v for v, _ in rows_b) / len(rows_b)
    diff_point = mean_a - mean_b

    rng = random.Random(SEED)
    blocks_a = _group_by_block(rows_a)
    blocks_b = _group_by_block(rows_b)
    diffs = [_resample_mean(blocks_a, rng) - _resample_mean(blocks_b, rng) for _ in range(N_RESAMPLES)]
    ci_low, ci_high = _percentile_ci(diffs, PRIMARY_CI_LEVEL)
    return {
        "n_a": len(rows_a), "n_b": len(rows_b), "mean_a": mean_a, "mean_b": mean_b,
        "diff_a_minus_b": diff_point, "ci_low": ci_low, "ci_high": ci_high, "ci_level": PRIMARY_CI_LEVEL,
        "insufficient_support": False,
    }


def run() -> dict:
    data = load_classifications()
    rows = build_trigger_table(data)
    joined = join_executed_outcomes(rows)

    return {
        "overall": distinct_candle_and_signal_counts(rows),
        "funnel_by_group": funnel_by_group(rows),
        "sweep_side_breakdown": sweep_side_breakdown(rows),
        "outcome_by_group_pooled": outcome_stats_by_group(joined),
        "outcome_by_group_by_instrument": {s: outcome_stats_by_group(joined, s) for s in SYMBOLS},
        "mean_r_diff_inside_vs_outside": mean_r_difference_ci(joined, "INSIDE", "OUTSIDE"),
        "n_ledger_mismatches": sum(1 for j in joined if not j.get("ledger_match", True)),
        "n_ordering_indeterminate": sum(1 for j in joined if j.get("outcome_vs_1300") == "ORDERING_INDETERMINATE"),
        "ordering_breakdown": dict(Counter(j.get("outcome_vs_1300") for j in joined if j.get("ledger_match"))),
        "order_placement_vs_h4_close": order_placement_vs_h4_close(rows),
    }


def main() -> dict:
    result = run()
    artifacts_dir = LAB_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    (artifacts_dir / "raza_9am_funnel_and_outcome_report.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8",
    )
    print(json.dumps(result, indent=2, default=str))
    return result


if __name__ == "__main__":
    main()
