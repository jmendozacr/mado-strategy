"""Phase 8 Unit D: read-only diagnostic adapter reconstructing the
per-model split of `candidates_built`/`filled`/`never_filled`/
`skipped_no_placement` -- the four fields `funnel_2015plus_run2.csv`
stores identically duplicated across each pair's 1am/9am rows, because
`run_c1_c2.process_arm()` computes them ONCE for both models' POOLED
candidates per (symbol, arm) and merges the same dict into both funnel
rows (`audit/.../run_d1_d2_d3.py`: `**c.to_dict(), **pop_stats`). No
candidate-level file is persisted anywhere, so this split cannot be
recovered by reading existing CSVs alone -- see
docs/56-funnel-provenance-audit.md for the full citation trail.

Reuses, byte-for-byte UNMODIFIED (never reimplemented, never re-tuned):
`run_d1_d2_d3.run_d_c2` (signal generation, pinned to D3/C2:
`anchor_source="new"`, `windows_9am="new"`), `backtest.population.
build_stage6_population`, `causal_intrabar.fill_pass_c`. The ONLY new
code here is bookkeeping: recomputing `fill_pass_c`'s own eligible/
skipped/never-filled partition using the EXACT SAME boolean condition
it uses internally, so each candidate's bucket can be tagged with the
`model_by_sig` mapping `run_d_c2`'s own records already carry --
`fill_pass_c` itself is never called twice with different logic, and
its returned aggregate counts are cross-checked against this
reconstruction's own tally as a correctness gate (see
`verify_against_pooled_counts`).

Writes ONLY to this lab's `artifacts/` directory. Never writes to, or
re-runs anything that writes to, `audit/2026-11-17-causal-lookahead-audit/`.
"""
from __future__ import annotations

import bisect
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = LAB_ROOT.parent.parent
DETECTOR_ROOT = REPO_ROOT / "detector"
AUDIT_ROOT = REPO_ROOT / "audit" / "2026-11-17-causal-lookahead-audit"
for _path in (LAB_ROOT, DETECTOR_ROOT, AUDIT_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import causal_intrabar as ci  # noqa: E402
import run_c1_c2 as base  # noqa: E402
from backtest.population import build_stage6_population  # noqa: E402
from backtest.simulate import _resolve_exits  # noqa: E402
from core.config import DetectorConfig  # noqa: E402
from experimental.htf_trigger_1am_9am_backtest import SYMBOL_CONFIG, _find_csv  # noqa: E402
from ingestion.loader import load_mt5_csv  # noqa: E402
from ingestion.pairing import load_pair  # noqa: E402
from primitives.swing import detect_swings  # noqa: E402
from causal_lib import build_key_levels  # noqa: E402
from run_d1_d2_d3 import run_d_c2  # noqa: E402

import config as lab_config  # noqa: E402
from behavior.post_stop_metrics import compute_atr_at_event  # noqa: E402
from control.sampling import period_bucket  # noqa: E402
from extract.model1_rejection_diagnostics import run_d_c2_instrumented, _window_open_ts_from_stable_id  # noqa: E402
from extract.stage6_attrition_diagnostics import (  # noqa: E402
    build_stage6_population_instrumented, verify_population_cuts_are_zero,
)
from stats.bootstrap import median, quantiles  # noqa: E402

PERIOD_BUCKETS = ("2015-2017", "2018-2020", "2021-2023", "2024-2026")


def _load_symbol_data(symbol: str):
    """Same 3 calls as `run_c1_c2.load_symbol_data` -- `_find_csv`,
    `load_pair`, `load_mt5_csv`, unmodified -- but resolving the data
    directory via this lab's own `config.resolve_data_dir()` instead of
    `run_c1_c2.py`'s own hardcoded `DATA_DIR` (which is relative to
    WHERE THAT FILE PHYSICALLY LIVES ON DISK, i.e. this worktree's own
    checked-out `audit/` copy, which has no `data/` next to it --
    `data/` is gitignored and only exists in the main worktree). Never a
    second data-loading implementation, only a different directory
    lookup for the exact same read."""
    data_dir = str(lab_config.resolve_data_dir())
    h4_csv = _find_csv(data_dir, symbol, "H4")
    m15_csv = _find_csv(data_dir, symbol, "M15")
    d1_csv = _find_csv(data_dir, symbol, "D1")
    h4, m15 = load_pair(htf_csv=h4_csv, htf_symbol=symbol, ltf_csv=m15_csv, ltf_symbol=symbol)
    daily = load_mt5_csv(d1_csv, symbol=symbol)
    return h4, m15, daily

SYMBOLS = ("EURUSD", "USDCAD", "AUDUSD")
ANCHOR_SOURCE = "new"   # D3's own value -- never D1/D2's "old"
WINDOWS_9AM = "new"     # D3's own value -- never D1's "old"
ARM_NAME = "d3_c2"      # must match the arm_name encoded in the real ledger's "arm" column
START_DATE = datetime(2015, 1, 1)  # the user's own standing scope decision, same as the original run


@dataclass(frozen=True)
class ModelFunnelSplit:
    candidates_built: int
    filled: int
    never_filled: int
    skipped_no_placement: int


def _eligible_and_skipped(candidates, candles, m15_timestamps, order_placed_by_sig, confirmation_idx_by_sig):
    """Mirrors `causal_intrabar.fill_pass_c`'s own eligibility partition
    EXACTLY (same boolean condition, same bisect call) -- never a
    different rule -- but returns which CANDIDATES fall into `eligible`
    vs. `skipped`, which `fill_pass_c` itself computes and discards
    (it only returns the skipped COUNT, not the member list)."""
    first_fillable: dict[str, int] = {}
    for sid, ts in order_placed_by_sig.items():
        idx = bisect.bisect_left(m15_timestamps, ts)
        if idx < len(candles):
            assert idx > confirmation_idx_by_sig[sid]
        first_fillable[sid] = idx
    eligible = [c for c in candidates if first_fillable.get(c.signal_id, len(candles)) < len(candles)]
    skipped = [c for c in candidates if first_fillable.get(c.signal_id, len(candles)) >= len(candles)]
    return eligible, skipped


def _numeric(values: list[float]) -> dict:
    clean = [v for v in values if v is not None]
    if not clean:
        return {"n": 0, "median": None, "quantiles": {}}
    return {"n": len(clean), "median": median(clean), "quantiles": quantiles(clean)}


def _covariates_for_group(candidates, m15, order_placed_by_sig) -> dict:
    """`atr_at_order_placement`/`planned_risk_atr_at_order_placement` --
    deliberately NOT `atr_m15_at_entry`/`risk_atr` (Phase 4/5): those are
    computed at `entry_ts`, which never-filled candidates do not have.
    Both are computed here using ONLY bars closed strictly before
    `order_placed_ts` (`compute_atr_at_event`, Phase 3's own causal
    boundary, unmodified) -- never a future, fictitious entry."""
    atr_values = []
    planned_risk_atr_values = []
    for c in candidates:
        order_placed_ts = order_placed_by_sig.get(c.signal_id)
        if order_placed_ts is None:
            continue
        atr = compute_atr_at_event(m15, order_placed_ts)
        atr_values.append(atr)
        risk_price = abs(c.entry_price - c.stop_loss)
        planned_risk_atr_values.append(risk_price / atr if atr else None)
    return {
        "atr_at_order_placement": _numeric(atr_values),
        "planned_risk_atr_at_order_placement": _numeric(planned_risk_atr_values),
    }


def reconstruct_for_symbol(symbol: str) -> dict:
    h4, m15, daily = _load_symbol_data(symbol)
    config = DetectorConfig(backtest=SYMBOL_CONFIG[symbol])
    m15_timestamps = [c.timestamp for c in m15.candles]
    swings = detect_swings(m15, config.swing)
    key_levels = build_key_levels(h4, daily, config.fvg)

    records_with_ids, counters, rejection_diagnostics = run_d_c2_instrumented(
        symbol, h4, m15, daily, config, m15_timestamps, key_levels,
        WINDOWS_9AM, ARM_NAME, start_date=START_DATE,
    )
    aligned_records = [(rec, sid) for rec, sid in records_with_ids if rec.aligned is not None]
    aligned_signals = [rec.aligned for rec, _sid in aligned_records]
    model_by_sig = {rec.aligned.ltf_signal.signal_id: rec.model_name for rec, _sid in aligned_records}
    stable_by_sig = {rec.aligned.ltf_signal.signal_id: sid for rec, sid in aligned_records}
    order_placed_by_sig = {rec.aligned.ltf_signal.signal_id: rec.order_placed_ts for rec, _sid in aligned_records}
    confirmation_idx_by_sig = {
        rec.aligned.ltf_signal.signal_id: rec.confirmation_index for rec, _sid in aligned_records
    }

    population, removed_by_model = build_stage6_population_instrumented(
        aligned_signals, m15, config, swings=swings, model_by_sig=model_by_sig,
    )
    population_cuts_check = verify_population_cuts_are_zero(population)
    eligible, skipped = _eligible_and_skipped(
        population.candidates, m15.candles, m15_timestamps, order_placed_by_sig, confirmation_idx_by_sig,
    )
    filled, never_filled_count, skipped_count = ci.fill_pass_c(
        population.candidates, m15.candles, m15_timestamps, config.backtest.max_fill_wait,
        order_placed_by_sig, confirmation_idx_by_sig,
    )
    filled_sig_ids = {c.signal_id for c, _ in filled}
    never_filled_candidates = [c for c in eligible if c.signal_id not in filled_sig_ids]

    candidates_by_model = Counter(model_by_sig.get(c.signal_id, "unknown") for c in population.candidates)
    filled_by_model = Counter(model_by_sig.get(c.signal_id, "unknown") for c, _ in filled)
    never_filled_by_model = Counter(model_by_sig.get(c.signal_id, "unknown") for c in never_filled_candidates)
    skipped_by_model = Counter(model_by_sig.get(c.signal_id, "unknown") for c in skipped)

    splits = {
        model: ModelFunnelSplit(
            candidates_built=candidates_by_model.get(model, 0),
            filled=filled_by_model.get(model, 0),
            never_filled=never_filled_by_model.get(model, 0),
            skipped_no_placement=skipped_by_model.get(model, 0),
        )
        for model in ("1am", "9am")
    }
    pooled_check = {
        "candidates_built": len(population.candidates), "filled": len(filled),
        "never_filled": never_filled_count, "skipped_no_placement": skipped_count,
    }

    filled_candidates_by_model = {m: [] for m in ("1am", "9am")}
    for c, _fill_index in filled:
        model = model_by_sig.get(c.signal_id)
        if model in filled_candidates_by_model:
            filled_candidates_by_model[model].append(c)
    never_filled_by_model_list = {m: [] for m in ("1am", "9am")}
    for c in never_filled_candidates:
        model = model_by_sig.get(c.signal_id)
        if model in never_filled_by_model_list:
            never_filled_by_model_list[model].append(c)

    covariates = {
        model: {
            "filled": _covariates_for_group(filled_candidates_by_model[model], m15, order_placed_by_sig),
            "never_filled": _covariates_for_group(never_filled_by_model_list[model], m15, order_placed_by_sig),
        }
        for model in ("1am", "9am")
    }

    # Unit A: event-level identity. `_resolve_exits` is the SAME real,
    # unmodified function `run_c1_c2.process_arm` calls -- reused here so
    # the final `Trade.signal_id`/`entry_index`/`entry_price` reconciled
    # against the real ledger are produced by the identical code path,
    # never recomputed a different way.
    trades = _resolve_exits(
        filled, m15.candles, config.backtest.trading_cost_price, config.backtest.partial_fraction,
        breakeven_after_partial=config.backtest.breakeven_after_partial,
    )
    reconstructed_identities = {
        stable_by_sig.get(t.signal_id, t.signal_id): {
            "signal_id": t.signal_id, "pair": symbol, "model": model_by_sig.get(t.signal_id, "unknown"),
            "direction": t.direction, "entry_index": t.entry_index, "entry_price": t.entry_price,
        }
        for t in trades
    }

    # Unit B/C: Model-1 rejection taxonomy, by model, with the anchor probe.
    rejection_taxonomy_by_model = {m: Counter() for m in ("1am", "9am")}
    anchor_probe_by_model = {m: Counter() for m in ("1am", "9am")}
    for diag in rejection_diagnostics.values():
        if diag.model_name not in rejection_taxonomy_by_model:
            continue
        rejection_taxonomy_by_model[diag.model_name][diag.category] += 1
        if diag.anchor_probe is not None:
            key = "anchor_found_but_chain_exhausted" if diag.anchor_probe else "zero_anchors_ever"
            anchor_probe_by_model[diag.model_name][key] += 1

    # Period bucketing (all triggers with a Key Level, confirmed or not) --
    # `window_open_ts` recovered from each record's own `stable_trigger_id`,
    # the same value the real loop built it from, never guessed.
    triggers_by_model_period = {m: Counter() for m in ("1am", "9am")}
    confirmed_by_model_period = {m: Counter() for m in ("1am", "9am")}
    for record, sid in records_with_ids:
        if record.model_name not in triggers_by_model_period:
            continue
        bucket = period_bucket(_window_open_ts_from_stable_id(sid))
        triggers_by_model_period[record.model_name][bucket] += 1
        if record.aligned is not None:
            confirmed_by_model_period[record.model_name][bucket] += 1

    return {
        "splits": splits, "pooled_check": pooled_check,
        "counters_by_model": {m: counters[m].to_dict() for m in ("1am", "9am")},
        "covariates": covariates,
        "population_cuts_check": population_cuts_check,
        "stage6_removed_by_model": removed_by_model,
        "reconstructed_identities": reconstructed_identities,
        "rejection_taxonomy_by_model": {m: dict(c) for m, c in rejection_taxonomy_by_model.items()},
        "anchor_probe_by_model": {m: dict(c) for m, c in anchor_probe_by_model.items()},
        "triggers_by_model_period": {m: dict(c) for m, c in triggers_by_model_period.items()},
        "confirmed_by_model_period": {m: dict(c) for m, c in confirmed_by_model_period.items()},
    }


def verify_against_pooled_counts(result: dict) -> dict:
    """Cross-check: summing this reconstruction's own per-model buckets
    must reproduce `fill_pass_c`'s own pooled return values EXACTLY --
    the reconstruction never silently drops or double-counts a
    candidate relative to the original, unmodified function."""
    splits = result["splits"]
    summed = {
        "candidates_built": sum(s.candidates_built for s in splits.values()),
        "filled": sum(s.filled for s in splits.values()),
        "never_filled": sum(s.never_filled for s in splits.values()),
        "skipped_no_placement": sum(s.skipped_no_placement for s in splits.values()),
    }
    return {"summed_from_split": summed, "pooled_from_fill_pass_c": result["pooled_check"],
            "matches": summed == result["pooled_check"]}


def verify_sweep_and_trigger_invariants(counters_by_model: dict) -> dict:
    """Two invariants `FunnelCounters`' own construction guarantees, never
    assumed without checking (requirement 5, two-direction triggers never
    double-counted against a different unit): (1) the four mutually-
    exclusive sweep categories sum to exactly `windows_considered` --
    `record_sweep` assigns exactly one category per window; (2)
    `model1_confirmed` plus every `zero_signal_reason_categories` count
    sums to exactly `triggers_with_key_level` -- every (window, direction)
    trigger resolves to exactly one of those two outcomes, never both,
    never neither."""
    out = {}
    for model, counters in counters_by_model.items():
        sweep_sum = (
            counters["swept_bearish_only"] + counters["swept_bullish_only"]
            + counters["swept_both"] + counters["swept_neither"]
        )
        reason_sum = counters["model1_confirmed"] + sum(counters["zero_signal_reason_categories"].values())
        out[model] = {
            "sweep_sum": sweep_sum, "windows_considered": counters["windows_considered"],
            "sweep_invariant_holds": sweep_sum == counters["windows_considered"],
            "reason_sum": reason_sum, "triggers_with_key_level": counters["triggers_with_key_level"],
            "trigger_invariant_holds": reason_sum == counters["triggers_with_key_level"],
        }
    return out


def run() -> dict:
    out = {}
    all_identities: dict[str, dict] = {}
    for symbol in SYMBOLS:
        result = reconstruct_for_symbol(symbol)
        verification = verify_against_pooled_counts(result)
        all_identities.update(result["reconstructed_identities"])
        out[symbol] = {
            "splits": {m: s.__dict__ for m, s in result["splits"].items()},
            "pooled_check": result["pooled_check"],
            "counters_by_model": result["counters_by_model"],
            "covariates": result["covariates"],
            "verification": verification,
            "sweep_and_trigger_invariants": verify_sweep_and_trigger_invariants(result["counters_by_model"]),
            "population_cuts_check": result["population_cuts_check"],
            "stage6_removed_by_model": result["stage6_removed_by_model"],
            "rejection_taxonomy_by_model": result["rejection_taxonomy_by_model"],
            "anchor_probe_by_model": result["anchor_probe_by_model"],
            "triggers_by_model_period": result["triggers_by_model_period"],
            "confirmed_by_model_period": result["confirmed_by_model_period"],
        }
    out["_reconstructed_identities"] = all_identities
    return out


def main() -> dict:
    import json

    result = run()
    artifacts_dir = LAB_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    (artifacts_dir / "phase8_funnel_reconstruction.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(
        {s: result[s]["verification"] for s in result if s != "_reconstructed_identities"},
        indent=2, default=str,
    ))
    return result


if __name__ == "__main__":
    main()
