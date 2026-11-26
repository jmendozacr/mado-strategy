"""Section 3/4 experiment: among 9AM Model-1 confirmations whose own
`model1_available_ts` equals the current H4 candle's own close-
availability instant EXACTLY (not merely "before" -- see
`docs/05-correction-2026-11-26.md`), compare the BASELINE arm (the
real, unmodified D3/C2 rules) against a VARIANT arm that additionally
requires the final H4 close to sit strictly inside the 05:00-09:00
reference range before a candidate is ever built.

Reuses, read-only, byte-for-byte unmodified: `run_d_c2_instrumented`
(for the authoritative confirmed-signal population),
`backtest.population.build_stage6_population`, `causal_intrabar.
fill_pass_c`, `backtest.simulate._resolve_exits`. The variant arm is
built by restricting the INPUT aligned-signal list to the
close-position == INSIDE subset BEFORE calling these same functions --
never a different rule, never a re-tuned parameter. `docs/06-thirteen-
oclock-protocol.md` is this unit's own pre-registered protocol,
committed before any outcome below was computed.
"""
from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

LAB_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = LAB_ROOT.parent.parent
DETECTOR_ROOT = REPO_ROOT / "detector"
AUDIT_ROOT = REPO_ROOT / "audit" / "2026-11-17-causal-lookahead-audit"
LPD_ROOT = REPO_ROOT / "research" / "loss-pattern-discovery"
for _path in (LAB_ROOT, DETECTOR_ROOT, AUDIT_ROOT, LPD_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import causal_intrabar as ci  # noqa: E402
from backtest.population import build_stage6_population  # noqa: E402
from backtest.simulate import _resolve_exits  # noqa: E402
from causal_lib import build_key_levels  # noqa: E402
from core.config import DetectorConfig  # noqa: E402
from experimental.htf_trigger_1am_9am_backtest import SYMBOL_CONFIG  # noqa: E402
from primitives.swing import detect_swings  # noqa: E402

from extract.funnel_reconstruction import ARM_NAME, START_DATE, WINDOWS_9AM, _load_symbol_data  # noqa: E402
from extract.from_causal_lookahead_audit import extract as extract_ledger  # noqa: E402
from extract.model1_rejection_diagnostics import (  # noqa: E402
    _window_open_ts_from_stable_id, run_d_c2_instrumented,
)

from raza_extract.reference_candle_classification import classify_one  # noqa: E402

_NY = ZoneInfo("America/New_York")
_UTC = ZoneInfo("UTC")
H4_DURATION = timedelta(hours=4)


def _run_arm(aligned_signals, m15, config, swings, order_placed_by_sig, confirmation_idx_by_sig):
    """One call sequence, reused identically for both arms: the SAME
    `build_stage6_population`/`fill_pass_c`/`_resolve_exits` the real
    pipeline uses, applied to whatever `aligned_signals` subset is
    passed in -- the input set is the only thing that ever differs
    between baseline and variant."""
    population = build_stage6_population(aligned_signals, m15, config, swings=swings)
    candidate_sig_ids = {c.signal_id for c in population.candidates}
    filled, _never_filled, _skipped = ci.fill_pass_c(
        population.candidates, m15.candles,
        [c.timestamp for c in m15.candles], config.backtest.max_fill_wait,
        order_placed_by_sig, confirmation_idx_by_sig,
    )
    filled_sig_ids = {c.signal_id for c, _fi in filled}
    trades = _resolve_exits(
        filled, m15.candles, config.backtest.trading_cost_price, config.backtest.partial_fraction,
        breakeven_after_partial=config.backtest.breakeven_after_partial,
    )
    trade_by_sig_id = {t.signal_id: t for t in trades}
    return candidate_sig_ids, filled_sig_ids, trade_by_sig_id


def _ny_date(ts):
    return ts.replace(tzinfo=_UTC).astimezone(_NY).date()


def build_experiment_for_symbol(symbol: str, start_date=START_DATE, end_date=None) -> dict:
    h4, m15, daily = _load_symbol_data(symbol)
    config = DetectorConfig(backtest=SYMBOL_CONFIG[symbol])
    m15_timestamps = [c.timestamp for c in m15.candles]
    swings = detect_swings(m15, config.swing)
    key_levels = build_key_levels(h4, daily, config.fvg)

    records_with_ids, _counters, _diag = run_d_c2_instrumented(
        symbol, h4, m15, daily, config, m15_timestamps, key_levels,
        WINDOWS_9AM, ARM_NAME, start_date=start_date, end_date=end_date,
    )
    confirmed = [(r, sid) for r, sid in records_with_ids if r.model_name == "9am" and r.aligned is not None]

    classifications = {}
    for record, sid in confirmed:
        current_open_ts = _window_open_ts_from_stable_id(sid)
        classifications[sid] = classify_one(
            symbol, record.direction, sid, current_open_ts, m15_timestamps, m15.candles,
        )

    pop = [
        (r, sid) for r, sid in confirmed
        if r.model1_available_ts == classifications[sid].h4_close_available_ts
    ]

    pop_stable_by_sig = {r.aligned.ltf_signal.signal_id: sid for r, sid in pop}
    pop_aligned = [r.aligned for r, _sid in pop]
    order_placed_by_sig = {r.aligned.ltf_signal.signal_id: r.order_placed_ts for r, _sid in pop}
    confirmation_idx_by_sig = {r.aligned.ltf_signal.signal_id: r.confirmation_index for r, _sid in pop}

    baseline_candidates, baseline_filled, baseline_trades = _run_arm(
        pop_aligned, m15, config, swings, order_placed_by_sig, confirmation_idx_by_sig,
    )

    variant_aligned = [
        r.aligned for r, sid in pop if classifications[sid].close_position == "INSIDE"
    ]
    variant_candidates, variant_filled, variant_trades = _run_arm(
        variant_aligned, m15, config, swings, order_placed_by_sig, confirmation_idx_by_sig,
    )

    rows = {}
    for record, sid in pop:
        sig_id = record.aligned.ltf_signal.signal_id
        c = classifications[sid]
        b_trade = baseline_trades.get(sig_id)
        v_trade = variant_trades.get(sig_id)
        rows[sid] = {
            "symbol": symbol,
            "direction": record.direction,
            "close_position": c.close_position,
            "sweep_side": c.sweep_side,
            "ny_date": _ny_date(c.current_open_ts).isoformat(),
            "baseline": {
                "is_candidate": sig_id in baseline_candidates,
                "is_filled": sig_id in baseline_filled,
                "outcome": b_trade.outcome if b_trade else None,
                "r_multiple": b_trade.r_multiple if b_trade else None,
            },
            "variant": {
                "is_candidate": sig_id in variant_candidates,
                "is_filled": sig_id in variant_filled,
                "outcome": v_trade.outcome if v_trade else None,
                "r_multiple": v_trade.r_multiple if v_trade else None,
            },
        }

    return {"symbol": symbol, "n_population": len(pop), "rows": rows}


def reconcile_baseline_against_ledger(rows: dict) -> dict:
    """Requirement: every baseline-executed signal in this restricted
    population must match the real ledger's own record exactly, since
    restricting the input set to `build_stage6_population`/`fill_pass_c`
    never changes any individual candidate's own resolution (each item
    in `two_heap_sweep` resolves independently of which other items
    share the run) -- verified here empirically, not assumed."""
    ledger = extract_ledger(REPO_ROOT)
    ledger_by_id = {r.identification.event_id: r for r in ledger}

    matched, mismatched, missing_from_ledger = 0, [], []
    for sid, row in rows.items():
        baseline = row["baseline"]
        if not baseline["is_filled"]:
            continue
        led = ledger_by_id.get(sid)
        if led is None:
            missing_from_ledger.append(sid)
            continue
        led_outcome = led.operation.outcome.value
        led_r = led.operation.r_multiple
        if led_outcome != baseline["outcome"] or (
            led_r is not None and baseline["r_multiple"] is not None
            and abs(led_r - baseline["r_multiple"]) > 1e-6
        ):
            mismatched.append(sid)
        else:
            matched += 1
    return {
        "n_matched": matched, "n_mismatched": len(mismatched), "mismatched_sids": mismatched,
        "n_missing_from_ledger": len(missing_from_ledger), "missing_sids": missing_from_ledger,
        "fully_reconciled": not mismatched and not missing_from_ledger,
    }
