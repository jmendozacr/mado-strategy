"""Section 3/4 report: funnel, reconciliation, primary paired net-R
metric, decomposition, and block-bootstrap uncertainty for the
13:00-exact-confirmation population. Protocol: `docs/07`.
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter
from datetime import date
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

from raza_extract.thirteen_oclock_experiment import reconcile_baseline_against_ledger  # noqa: E402

SYMBOLS = ("EURUSD", "USDCAD", "AUDUSD")
SEED = 20261126
N_RESAMPLES = 2000
CI_LEVEL = 0.95


def load_rows() -> dict[str, dict]:
    merged = {}
    missing = []
    for symbol in SYMBOLS:
        path = LAB_ROOT / "artifacts" / f"raza_thirteen_oclock_{symbol}.json"
        if not path.exists():
            missing.append(symbol)
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        merged.update(data["rows"])
    if missing:
        raise FileNotFoundError(f"missing thirteen-oclock artifacts for {missing}")
    return merged


def funnel_by_arm(rows: dict) -> dict:
    out = {}
    for arm in ("baseline", "variant"):
        candidate = sum(1 for r in rows.values() if r[arm]["is_candidate"])
        filled = sum(1 for r in rows.values() if r[arm]["is_filled"])
        closed = sum(1 for r in rows.values() if r[arm]["outcome"] in ("win", "loss"))
        open_ = sum(1 for r in rows.values() if r[arm]["outcome"] == "open")
        out[arm] = {
            "confirmed": len(rows), "candidate": candidate, "filled": filled,
            "closed": closed, "open": open_, "skipped_or_unfilled": len(rows) - filled,
        }
    return out


def sweep_and_close_breakdown(rows: dict) -> dict:
    return {
        "close_position": dict(Counter(r["close_position"] for r in rows.values())),
        "sweep_side": dict(Counter(r["sweep_side"] for r in rows.values())),
        "inside_single_sided": sum(
            1 for r in rows.values() if r["close_position"] == "INSIDE" and r["sweep_side"] in ("HIGH_ONLY", "LOW_ONLY")
        ),
        "inside_double_sweep": sum(
            1 for r in rows.values() if r["close_position"] == "INSIDE" and r["sweep_side"] == "BOTH"
        ),
    }


def _signal_r(arm: dict) -> tuple[float, bool]:
    """Returns (r_for_primary_metric, is_censored). Open trades are
    censored (excluded from the primary sum, never assigned 0 or any
    invented value); everything else that never closed contributes 0."""
    if arm["outcome"] == "open":
        return 0.0, True
    if arm["outcome"] in ("win", "loss") and arm["r_multiple"] is not None:
        return arm["r_multiple"], False
    return 0.0, False


def decomposition(rows: dict) -> dict:
    counts = Counter()
    for r in rows.values():
        b, b_cens = _signal_r(r["baseline"])
        v, v_cens = _signal_r(r["variant"])
        if b_cens or v_cens:
            if b_cens and not v_cens:
                counts["NO_LONGER_CENSORED"] += 1
            elif v_cens and not b_cens:
                counts["NEWLY_CENSORED"] += 1
            else:
                counts["BOTH_CENSORED"] += 1
            continue
        if r["baseline"]["outcome"] is None and r["variant"]["outcome"] is None:
            counts["BOTH_ZERO"] += 1
        elif r["baseline"]["outcome"] == r["variant"]["outcome"] and abs(b - v) < 1e-9:
            counts["UNAFFECTED"] += 1
        elif r["baseline"]["outcome"] == "loss" and r["variant"]["outcome"] != "loss":
            counts["LOSS_AVOIDED"] += 1
        elif r["baseline"]["outcome"] == "win" and r["variant"]["outcome"] != "win":
            counts["GAIN_FORGONE"] += 1
        else:
            counts["OTHER"] += 1
    return dict(counts)


def primary_metric(rows: dict, instrument: str | None = None) -> dict:
    non_censored = []
    n_censored_baseline = n_censored_variant = 0
    for r in rows.values():
        if instrument is not None and r["symbol"] != instrument:
            continue
        b, b_cens = _signal_r(r["baseline"])
        v, v_cens = _signal_r(r["variant"])
        if b_cens:
            n_censored_baseline += 1
        if v_cens:
            n_censored_variant += 1
        if b_cens or v_cens:
            continue
        non_censored.append((b, v))

    n = len(non_censored)
    if n == 0:
        return {"n": 0, "insufficient_support": True}
    mean_baseline = sum(b for b, _ in non_censored) / n
    mean_variant = sum(v for _, v in non_censored) / n
    diff = mean_variant - mean_baseline
    total_baseline = sum(b for b, _ in non_censored)
    total_variant = sum(v for _, v in non_censored)
    n_closed_baseline = sum(1 for b, _ in non_censored if b != 0.0)
    n_closed_variant = sum(1 for _, v in non_censored if v != 0.0)
    return {
        "n": n,
        "n_censored_baseline": n_censored_baseline, "n_censored_variant": n_censored_variant,
        "mean_r_baseline": mean_baseline, "mean_r_variant": mean_variant,
        "diff_variant_minus_baseline": diff,
        "total_r_baseline": total_baseline, "total_r_variant": total_variant,
        "mean_r_per_closed_baseline": (total_baseline / n_closed_baseline) if n_closed_baseline else None,
        "mean_r_per_closed_variant": (total_variant / n_closed_variant) if n_closed_variant else None,
        "n_closed_baseline": n_closed_baseline, "n_closed_variant": n_closed_variant,
        "insufficient_support": False,
    }


def _ny_date_block_key(row: dict) -> date:
    return date.fromisoformat(row["ny_date"])


def bootstrap_ci(rows: dict) -> dict:
    """Blocks are whole NY trading dates, pooled across all three
    instruments together -- per `docs/07`'s own explicit instruction,
    never resampled per instrument."""
    pairs_by_block: dict = {}
    for r in rows.values():
        b, b_cens = _signal_r(r["baseline"])
        v, v_cens = _signal_r(r["variant"])
        if b_cens or v_cens:
            continue
        pairs_by_block.setdefault(_ny_date_block_key(r), []).append((b, v))

    blocks = list(pairs_by_block.values())
    if not blocks:
        return {"ci_low": None, "ci_high": None, "n_blocks": 0}

    def _mean_diff(chosen_blocks):
        pooled = [pair for block in chosen_blocks for pair in block]
        if not pooled:
            return float("nan")
        return sum(v - b for b, v in pooled) / len(pooled)

    rng = random.Random(SEED)
    diffs = []
    for _ in range(N_RESAMPLES):
        chosen = [blocks[rng.randrange(len(blocks))] for _ in range(len(blocks))]
        diffs.append(_mean_diff(chosen))
    diffs = sorted(d for d in diffs if d == d)
    n = len(diffs)
    alpha = (1 - CI_LEVEL) / 2
    lo = diffs[max(int(alpha * n), 0)]
    hi = diffs[min(int((1 - alpha) * n), n - 1)]
    return {"ci_low": lo, "ci_high": hi, "ci_level": CI_LEVEL, "n_blocks": len(blocks), "n_resamples": N_RESAMPLES}


def run() -> dict:
    rows = load_rows()
    recon = reconcile_baseline_against_ledger(rows)
    unique_dates = {r["ny_date"] for r in rows.values()}

    return {
        "n_population": len(rows),
        "n_unique_ny_dates": len(unique_dates),
        "reconciliation": recon,
        "funnel_by_arm": funnel_by_arm(rows),
        "sweep_and_close_breakdown": sweep_and_close_breakdown(rows),
        "decomposition": decomposition(rows),
        "primary_metric_pooled": primary_metric(rows),
        "primary_metric_by_instrument": {s: primary_metric(rows, s) for s in SYMBOLS},
        "bootstrap_ci": bootstrap_ci(rows),
        "n_population_by_instrument": dict(Counter(r["symbol"] for r in rows.values())),
    }


def main() -> dict:
    result = run()
    artifacts_dir = LAB_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    (artifacts_dir / "raza_thirteen_oclock_report.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8",
    )
    print(json.dumps(result, indent=2, default=str))
    return result


if __name__ == "__main__":
    main()
