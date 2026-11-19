"""Orchestrates experiments D1/D2/D3 -- design-causal-anchor-source.md's
"Cierre de diseño -- ronda 3", conditionally approved in the review of
commit 86a1e58 (corrections applied before this file was written).

Shares every config-agnostic piece of run_c1_c2.py/causal_intrabar.py
(FunnelCounters, stable_trigger_id, process_arm, year_breakdown, the
CSV-writing helpers, load_symbol_data) by importing that module
directly -- the only NEW orchestration logic is run_d_c1/run_d_c2,
generalizing run_c1/run_c2 to accept (anchor_source, windows_9am)
instead of being hardcoded to "old anchor + old windows" (= C1/C2).

D1 = new anchor source, old 9AM/1AM windows -- causal diagnostic,
isolates Modificación 1's effect alone.
D2 = old (resolution-gated) anchor source, new 9AM windows -- labeled
DIAGNOSTIC NON-CAUSAL. Its R must NEVER be used as profitability
evidence -- it exists only to isolate Modificación 2's (window-
widening) effect, in isolation from Modificación 1, while still
carrying the old mechanism's look-ahead dependency this whole audit
has been correcting.
D3 = new anchor source + new 9AM windows -- represents the AGREED 9AM
operative design (design S19), not a third equally-weighted variant.
D1/D2 are diagnostic tools to attribute effects; D3 is the candidate
implementation.

1AM's windows are never touched in any config (design S19 S5). C1/C2
(run_c1_c2.py, causal_intrabar.py) are not modified -- their own CSVs
stay untouched, immutable historical references. Nothing under
detector/scanner/docs is touched.
"""
from __future__ import annotations

import os
import sys
from datetime import timedelta

AUDIT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(AUDIT_DIR, "..", ".."))
DETECTOR_DIR = os.path.join(REPO_ROOT, "detector")
DATA_DIR = os.path.join(REPO_ROOT, "data")
OUT_DIR = AUDIT_DIR

sys.path.insert(0, DETECTOR_DIR)
sys.path.insert(0, AUDIT_DIR)

from core.config import DetectorConfig  # noqa: E402
from experimental.htf_trigger_1am_9am_backtest import SYMBOL_CONFIG  # noqa: E402
from primitives.crt_range import detect_crt_ranges  # noqa: E402
from primitives.swing import detect_swings  # noqa: E402

import causal_anchor_v2 as ca  # noqa: E402
import causal_intrabar as ci  # noqa: E402
import run_c1_c2 as base  # noqa: E402
from causal_lib import build_key_levels  # noqa: E402

SYMBOLS = ("EURUSD", "USDCAD", "AUDUSD")

CONFIGS = {
    # name: (anchor_source, windows_9am, causal_label)
    "d1": ("new", "old", "causal diagnostic -- anchor-source effect alone"),
    "d2": ("old", "new", "DIAGNOSTIC NON-CAUSAL -- do not use its R as profitability evidence"),
    "d3": ("new", "new", "agreed 9AM operative design"),
}


def run_d_c1(symbol, h4, m15, daily, config, m15_timestamps, ltf_ranges, swings, key_levels,
             anchor_source, windows_9am, arm_name, start_date=None, end_date=None):
    """Mirrors `run_c1_c2.run_c1`'s loop exactly (broker H4 grid) --
    the anchor mechanism and the 9AM window boundaries are chosen by
    `anchor_source`/`windows_9am` instead of being hardcoded, so
    D1/D2/D3 share this ONE function instead of three copies."""
    counters = {"1am": base.FunnelCounters(), "9am": base.FunnelCounters()}
    records: list = []
    for model, model_name in ((ci.MODEL_1AM, "1am"), (ci.MODEL_9AM, "9am")):
        c = counters[model_name]
        confirm_fn = ca.new_confirm_fn() if anchor_source == "new" else ca.old_confirm_fn(ltf_ranges)
        if model_name == "9am" and windows_9am == "new":
            window_start_fn, window_end_fn = ca.new_9am_window_fns()
        else:
            window_start_fn, window_end_fn = ca.old_window_fns(model)

        for i in range(1, len(h4.candles)):
            if h4.candles[i].timestamp.hour != model.trigger_utc_hour or h4.candles[i].timestamp.minute != 0:
                continue
            window_open_ts = h4.candles[i].timestamp
            if start_date is not None and window_open_ts < start_date:
                continue
            if end_date is not None and window_open_ts > end_date:
                continue
            reference = ci.complete_feeder_candle_broker(h4, i - 1)
            activation_start_ts = ca.activation_window_open_ts(window_open_ts, model_name, windows_9am)
            activation_close_ts = ca.activation_window_close_ts(window_open_ts, model_name, windows_9am)
            c.windows_considered += 1
            outcomes = ci.detect_sweep_and_key_level(
                m15_timestamps, m15.candles, reference, activation_start_ts, activation_close_ts, key_levels, h4
            )
            c.record_sweep(outcomes)
            for direction, outcome in outcomes.items():
                if outcome.trigger is None:
                    continue
                c.triggers_with_key_level += 1
                record = ca.build_causal_signal_v2(
                    model_name, outcome.trigger, window_open_ts, m15, config.model1, reference,
                    window_start_fn, window_end_fn, confirm_fn,
                )
                if record.aligned is not None:
                    c.model1_confirmed += 1
                else:
                    c.zero_signal_reasons[base._categorize_reason(record.zero_signal_reason)] += 1
                sid = base.stable_trigger_id(symbol, arm_name, model_name, window_open_ts, direction)
                records.append((record, sid))
    return records, counters


def run_d_c2(symbol, h4, m15, daily, config, m15_timestamps, ltf_ranges, swings, key_levels,
             anchor_source, windows_9am, arm_name, start_date=None, end_date=None):
    """Mirrors `run_c1_c2.run_c2`'s loop exactly (NY-anchored feeder
    grid) -- same generalization as `run_d_c1` above."""
    counters = {"1am": base.FunnelCounters(), "9am": base.FunnelCounters()}
    records: list = []
    first_day, last_day = m15.candles[0].timestamp.date(), m15.candles[-1].timestamp.date()
    one_day = timedelta(days=1)

    for model, model_name in ((ci.MODEL_1AM, "1am"), (ci.MODEL_9AM, "9am")):
        c = counters[model_name]
        confirm_fn = ca.new_confirm_fn() if anchor_source == "new" else ca.old_confirm_fn(ltf_ranges)
        if model_name == "9am" and windows_9am == "new":
            window_start_fn, window_end_fn = ca.new_9am_window_fns()
        else:
            window_start_fn, window_end_fn = ca.old_window_fns(model)

        ref_hour = ci.REFERENCE_HOUR_NY[model_name]
        cur_hour = ci.CURRENT_HOUR_NY[model_name]
        ref_prev_day = ci.REFERENCE_IS_PREVIOUS_DAY[model_name]
        day = first_day
        while day <= last_day:
            current_open_ts = ci.ny_anchored_open_utc(day, cur_hour)
            ref_day = (day - one_day) if ref_prev_day else day
            ref_open_ts = ci.ny_anchored_open_utc(ref_day, ref_hour)
            day += one_day

            if start_date is not None and current_open_ts < start_date:
                continue
            if end_date is not None and current_open_ts > end_date:
                continue

            reference = ci.complete_feeder_candle_ny(m15_timestamps, m15.candles, ref_open_ts)
            if reference is None:
                c.reference_incomplete_skipped += 1
                continue
            c.windows_considered += 1
            activation_start_ts = ca.activation_window_open_ts(current_open_ts, model_name, windows_9am)
            activation_close_ts = ca.activation_window_close_ts(current_open_ts, model_name, windows_9am)
            outcomes = ci.detect_sweep_and_key_level(
                m15_timestamps, m15.candles, reference, activation_start_ts, activation_close_ts, key_levels, h4
            )
            c.record_sweep(outcomes)
            for direction, outcome in outcomes.items():
                if outcome.trigger is None:
                    continue
                c.triggers_with_key_level += 1
                record = ca.build_causal_signal_v2(
                    model_name, outcome.trigger, current_open_ts, m15, config.model1, reference,
                    window_start_fn, window_end_fn, confirm_fn,
                )
                if record.aligned is not None:
                    c.model1_confirmed += 1
                else:
                    c.zero_signal_reasons[base._categorize_reason(record.zero_signal_reason)] += 1
                sid = base.stable_trigger_id(symbol, arm_name, model_name, current_open_ts, direction)
                records.append((record, sid))
    return records, counters


RUN_FN_BY_GRID = {"c1": run_d_c1, "c2": run_d_c2}


def build_arg_parser():
    import argparse
    parser = argparse.ArgumentParser(
        description="Run experiments D1/D2/D3 over a configurable trigger-window date range. "
                     "Defaults to 2015-01-01+ (the user's standing scope decision) -- for a small "
                     "smoke test, pass an explicit short --start-date/--end-date pair. The loaded "
                     "series and shared detection always use the FULL available history as "
                     "warmup -- only which TRIGGER WINDOWS get walked is filtered."
    )
    parser.add_argument(
        "--start-date", default="2015-01-01",
        help="YYYY-MM-DD, inclusive. Defaults to 2015-01-01 (per the user's standing scope decision) "
             "specifically to avoid accidentally running the full 23-year history -- pass an explicit "
             "value (e.g. 2003-01-01) to override.",
    )
    parser.add_argument("--end-date", default=None, help="YYYY-MM-DD, inclusive. Default: last available date.")
    parser.add_argument("--configs", default="d1,d2,d3", help="Comma-separated subset of d1,d2,d3.")
    parser.add_argument("--grids", default="c1,c2", help="Comma-separated subset of c1,c2.")
    parser.add_argument("--symbols", default=",".join(SYMBOLS), help="Comma-separated symbols.")
    parser.add_argument(
        "--output-label", default=None,
        help="Suffix for output CSV filenames (trades_<arm>_<label>.csv) so different runs/periods "
             "never collide with each other, with the historical A/B1/B2/C1/C2 CSVs, or with the "
             "committed smoke-test CSVs. Defaults to a label derived from --start-date/--end-date.",
    )
    return parser


def main():
    args = build_arg_parser().parse_args()
    start_date = base._parse_date_arg(args.start_date)
    end_date = base._parse_date_arg(args.end_date)
    if end_date is not None:
        end_date = end_date + timedelta(hours=23, minutes=59)
    configs = [c.strip() for c in args.configs.split(",") if c.strip()]
    grids = [g.strip() for g in args.grids.split(",") if g.strip()]
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    output_label = args.output_label or f"{args.start_date or 'full'}_{args.end_date or 'latest'}"

    # Optimization (user-authorized, 2026-11-19): `ltf_ranges` (detect_crt_ranges'
    # output) is consumed ONLY by `old_confirm_fn(ltf_ranges)` inside run_d_c1/
    # run_d_c2, which is only ever called when `anchor_source == "old"` -- i.e.
    # only by D2. D1/D3 (anchor_source == "new") never touch it (confirmed by
    # grep: no other reference to `ltf_ranges` exists anywhere in this file or
    # in causal_anchor_v2.py). When no requested config is D2, skip the
    # computation entirely and pass `None` -- it is provably never dereferenced
    # on that path, so this cannot change any signal or trade for D1/D3.
    need_old_anchor = any(CONFIGS[c][0] == "old" for c in configs)

    # Accumulate across ALL symbols per arm, write once at the end --
    # mirrors run_c1_c2.py's own main() exactly (all_trade_rows[arm] +=
    # rows, written after the symbol loop). Writing inside the per-symbol
    # loop (this file's earlier bug, caught in the 2015+ USDCAD/AUDUSD run:
    # the output filename never varied by symbol, so each symbol silently
    # overwrote the previous one's CSV) would lose every earlier symbol's
    # rows for the same arm+label.
    all_trade_rows: dict[str, list] = {}
    funnel_rows: list = []
    year_rows: list = []

    for symbol in symbols:
        h4, m15, daily = base.load_symbol_data(symbol)
        config = DetectorConfig(backtest=SYMBOL_CONFIG[symbol])
        m15_timestamps = [c.timestamp for c in m15.candles]
        ltf_ranges = detect_crt_ranges(m15, config.crt_range) if need_old_anchor else None
        swings = detect_swings(m15, config.swing)
        key_levels = build_key_levels(h4, daily, config.fvg)
        ranges_desc = len(ltf_ranges) if ltf_ranges is not None else "skipped (no D2 requested)"
        print(f"{symbol}: shared detection ready ({ranges_desc} ranges, {len(swings)} swings, "
              f"{len(key_levels)} key levels)", flush=True)

        for cfg_name in configs:
            anchor_source, windows_9am, causal_label = CONFIGS[cfg_name]
            for grid in grids:
                run_fn = RUN_FN_BY_GRID[grid]
                arm_name = f"{cfg_name}_{grid}"
                records_with_ids, counters = run_fn(
                    symbol, h4, m15, daily, config, m15_timestamps, ltf_ranges, swings, key_levels,
                    anchor_source, windows_9am, arm_name, start_date=start_date, end_date=end_date,
                )
                trades, rows, pop_stats = base.process_arm(
                    symbol, arm_name, records_with_ids, h4, m15, daily, config, m15_timestamps, swings
                )
                stats = base.trade_stats(trades)
                dd = base.max_drawdown_r(trades, m15)
                print(f"{symbol} {arm_name} [{causal_label}]: "
                      f"1am={counters['1am'].to_dict()} 9am={counters['9am'].to_dict()} "
                      f"pop={pop_stats} trades={stats['trades']} closed={stats['closed']} "
                      f"wr={stats['win_rate']:.4f} total_r={stats['total_r']:.4f} max_dd={dd:.4f}",
                      flush=True)
                all_trade_rows.setdefault(arm_name, []).extend(rows)
                for model_name, c in counters.items():
                    funnel_rows.append({"pair": symbol, "arm": arm_name, "model": model_name,
                                         **c.to_dict(), **pop_stats})
                for yr in base.year_breakdown(trades, m15):
                    year_rows.append({"pair": symbol, "arm": arm_name, **yr})

    for arm_name, rows in all_trade_rows.items():
        base.write_csv(
            os.path.join(OUT_DIR, f"trades_{arm_name}_{output_label}.csv"), base.TRADE_COLUMNS, rows
        )
    if funnel_rows:
        funnel_columns = sorted({k for row in funnel_rows for k in row.keys()})
        base.write_csv(os.path.join(OUT_DIR, f"funnel_{output_label}.csv"), funnel_columns, funnel_rows)
    if year_rows:
        year_columns = sorted({k for row in year_rows for k in row.keys()})
        base.write_csv(os.path.join(OUT_DIR, f"year_breakdown_{output_label}.csv"), year_columns, year_rows)


if __name__ == "__main__":
    main()
