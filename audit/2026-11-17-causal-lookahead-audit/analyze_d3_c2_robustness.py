"""D3/C2 2015+ robustness audit (read-only). Does not rerun any backtest,
does not touch detector/scanner/docs, does not modify any historical
CSV/script. Inputs: trades_d3_c2_2015plus_run2.csv, funnel_2015plus_run2.csv,
year_breakdown_2015plus_run2.csv (all already-exported, unmodified).

Phases implemented here (design: see results-d3-c2-robustness-2015plus.md):
  1. Corrected funnel interpretation (pair-level vs. per-model fields).
  2. Execution-cost sensitivity (additional penalty scenarios).
  3. Temporal robustness + leave-one-year-out.
  4. Block bootstrap (monthly/quarterly) with a fixed seed.
  5. Simultaneous-exposure / correlation analysis.
  6. Ambiguous/gap-filled sensitivity.
  7. Out-of-sample validity review (documentation, not computed).
"""
import csv
import json
import random
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta

PAIRS = ("EURUSD", "USDCAD", "AUDUSD")
LABEL = "2015plus_run2"
OUT_PREFIX = "robustness"
SEED = 20261119  # fixed seed, documented -- date this audit was authorized

with open(f"trades_d3_c2_{LABEL}.csv", newline="", encoding="utf-8") as f:
    TRADES = list(csv.DictReader(f))
with open(f"funnel_{LABEL}.csv", newline="", encoding="utf-8") as f:
    FUNNEL = list(csv.DictReader(f))


def r_of(row):
    return float(row["r_multiple"]) if row["r_multiple"] != "" else 0.0


def is_closed(row):
    return row["outcome"] in ("win", "loss")


def closed(rows):
    return [r for r in rows if is_closed(r)]


def exit_dt(row):
    return datetime.fromisoformat(row["exit_timestamp_broker"]) if row["exit_timestamp_broker"] else None


def entry_dt(row):
    return datetime.fromisoformat(row["entry_timestamp_broker"]) if row["entry_timestamp_broker"] else None


def profit_factor(rows):
    gains = sum(r_of(r) for r in rows if r["outcome"] == "win")
    losses = -sum(r_of(r) for r in rows if r["outcome"] == "loss")
    return gains / losses if losses > 0 else float("inf")


def expectancy(rows):
    c = closed(rows)
    return sum(r_of(r) for r in c) / len(c) if c else None


def total_r(rows):
    return sum(r_of(r) for r in closed(rows))


def max_dd_chronological(rows):
    pts = sorted(((exit_dt(r), r_of(r)) for r in rows if exit_dt(r)), key=lambda p: p[0])
    equity = peak = max_dd = 0.0
    series = []
    for ts, r in pts:
        equity += r
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
        series.append((ts, equity, max_dd))
    return max_dd, series


def write_csv(path, columns, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        for r in rows:
            w.writerow(r)


# ===========================================================================
# PHASE 1 -- corrected funnel interpretation
# ===========================================================================

def phase1_funnel():
    print("\n" + "=" * 100)
    print("PHASE 1 -- corrected funnel interpretation")
    print("=" * 100)

    pair_rows = defaultdict(list)
    for f in FUNNEL:
        pair_rows[f["pair"]].append(f)

    corrected_rows = []
    for pair in PAIRS:
        frows = pair_rows[pair]
        # candidates_built/filled/never_filled/skipped_no_placement are PAIR-LEVEL
        # aggregates computed once per (pair,arm) by process_arm, then (bug) merged
        # identically into BOTH the "1am" and "9am" funnel rows. Summing across
        # model rows (as the original results-d3-c2-2015plus.md report did)
        # silently doubles them. Take it from exactly ONE row (they are identical
        # by construction) instead of summing.
        pop_candidates_built = int(frows[0]["candidates_built"])
        pop_never_filled = int(frows[0]["never_filled"])
        pop_filled = int(frows[0]["filled"])
        pop_skipped = int(frows[0]["skipped_no_placement"])
        assert all(int(fr["candidates_built"]) == pop_candidates_built for fr in frows), \
            f"{pair}: candidates_built differs across model rows -- duplication assumption is WRONG, stop"
        assert all(int(fr["never_filled"]) == pop_never_filled for fr in frows)
        assert all(int(fr["filled"]) == pop_filled for fr in frows)

        # Genuinely per-model fields (never duplicated -- each model has its own
        # FunnelCounters instance in run_d1_d2_d3.py, confirmed by code reading).
        per_model = {}
        for fr in frows:
            per_model[fr["model"]] = {
                "windows_considered": int(fr["windows_considered"]),
                "triggers_with_key_level": int(fr["triggers_with_key_level"]),
                "model1_confirmed": int(fr["model1_confirmed"]),
            }

        # Exact, verifiable per-model trade counts -- reconstructed directly from
        # trades_d3_c2_2015plus_run2.csv (ground truth, one row per real trade,
        # "model" column set per-trade at signal-assembly time, never duplicated).
        pair_trades = [r for r in TRADES if r["pair"] == pair]
        for model in ("1am", "9am"):
            mrows = [r for r in pair_trades if r["model"] == model]
            per_model[model]["filled_verified"] = len(mrows)
            per_model[model]["closed_verified"] = len(closed(mrows))
            per_model[model]["open_verified"] = sum(1 for r in mrows if r["outcome"] == "open")

        filled_sum_check = per_model["1am"]["filled_verified"] + per_model["9am"]["filled_verified"]
        print(f"\n{pair}:")
        print(f"  Pair-level (from funnel row, taken once -- NOT summed across model rows):")
        print(f"    Modelo #1 CONFIRMED (candidatos de señal, antes de construir orden): "
              f"{per_model['1am']['model1_confirmed']} (1am) + {per_model['9am']['model1_confirmed']} (9am) "
              f"= {per_model['1am']['model1_confirmed'] + per_model['9am']['model1_confirmed']} (esto SI es "
              f"correctamente per-modelo, no duplicado)")
        print(f"    Candidatos de poblacion (tras SL/TP/R:R, pair-level, NO desglosable por modelo sin "
              f"re-ejecutar la generacion de señales -- fuera de alcance): {pop_candidates_built}")
        print(f"    Nunca llenados (pair-level, misma limitacion): {pop_never_filled}")
        print(f"    Candidatos descartados entre CONFIRMED y poblacion "
              f"({per_model['1am']['model1_confirmed'] + per_model['9am']['model1_confirmed']} - {pop_candidates_built}): "
              f"{per_model['1am']['model1_confirmed'] + per_model['9am']['model1_confirmed'] - pop_candidates_built}")
        print(f"    Ejecutadas (filled, pair-level de funnel.csv): {pop_filled} -- verificado contra trades.csv: "
              f"{filled_sum_check} ({'OK' if filled_sum_check == pop_filled else 'MISMATCH'})")
        print(f"  Per-modelo (verificado directamente desde trades CSV, identificadores reales, no dividido):")
        for model in ("1am", "9am"):
            pm = per_model[model]
            print(f"    {model}: windows_considered={pm['windows_considered']} "
                  f"triggers_with_key_level={pm['triggers_with_key_level']} "
                  f"model1_confirmed={pm['model1_confirmed']} "
                  f"filled(trades)={pm['filled_verified']} closed={pm['closed_verified']} open={pm['open_verified']}")

        corrected_rows.append({
            "pair": pair, "model1_confirmed_1am": per_model["1am"]["model1_confirmed"],
            "model1_confirmed_9am": per_model["9am"]["model1_confirmed"],
            "population_candidates_built_PAIR_LEVEL": pop_candidates_built,
            "never_filled_PAIR_LEVEL": pop_never_filled,
            "filled_PAIR_LEVEL": pop_filled,
            "filled_1am_verified": per_model["1am"]["filled_verified"],
            "filled_9am_verified": per_model["9am"]["filled_verified"],
            "filled_sum_check_matches_pair_level": filled_sum_check == pop_filled,
            "closed_1am": per_model["1am"]["closed_verified"], "closed_9am": per_model["9am"]["closed_verified"],
            "open_1am": per_model["1am"]["open_verified"], "open_9am": per_model["9am"]["open_verified"],
        })

    write_csv(f"{OUT_PREFIX}_funnel_corrected.csv", list(corrected_rows[0].keys()), corrected_rows)
    print(f"\nWritten: {OUT_PREFIX}_funnel_corrected.csv")

    # Data-integrity checks the user explicitly asked for (beyond final trades).
    print("\n-- Data integrity checks (not just final trades) --")
    key_counts = Counter((r["pair"], r["signal_id"]) for r in TRADES)
    dupes = {k: v for k, v in key_counts.items() if v > 1}
    print(f"  (pair, signal_id) collisions: {len(dupes)}")
    stable_counts = Counter(r["stable_id"] for r in TRADES)
    dupe_stable = {k: v for k, v in stable_counts.items() if v > 1}
    print(f"  stable_id collisions: {len(dupe_stable)}")
    bad_order = 0
    for r in TRADES:
        act = datetime.fromisoformat(r["activation_instant_ts"])
        m1 = datetime.fromisoformat(r["model1_available_ts"])
        placed = datetime.fromisoformat(r["order_placed_ts"])
        e, x = entry_dt(r), exit_dt(r)
        if not (act <= m1 <= placed):
            bad_order += 1
        if e and placed > e:
            bad_order += 1
        if e and x and e > x:
            bad_order += 1
    print(f"  Timestamp-order violations (activation<=model1<=placed<=entry<=exit): {bad_order}")
    bad_dir = sum(1 for r in TRADES if r["signal_id"].split("-")[2] != r["direction"])
    print(f"  signal_id-vs-row direction mismatches: {bad_dir}")
    return corrected_rows


# ===========================================================================
# PHASE 2 -- execution-cost sensitivity (additional R penalty, not a refill)
# ===========================================================================

PENALTY_SCENARIOS = (0.00, 0.01, 0.025, 0.04, 0.05, 0.10)


def phase2_cost_sensitivity():
    print("\n" + "=" * 100)
    print("PHASE 2 -- execution-cost sensitivity (ADDITIONAL penalty on top of already-realized R)")
    print("=" * 100)
    print("This is an ARITHMETIC sensitivity on existing closed trades (subtract a flat R per trade), "
          "NOT a re-simulation of fills under different spread/slippage assumptions. The scenarios are "
          "stress levels to test, not claimed real broker spreads.")

    rows_out = []
    for pair in PAIRS + ("COMBINED",):
        pair_rows = TRADES if pair == "COMBINED" else [r for r in TRADES if r["pair"] == pair]
        c = closed(pair_rows)
        n = len(c)
        if n == 0:
            continue
        print(f"\n{pair} (n_closed={n}):")
        current_expectancy = sum(r_of(r) for r in c) / n
        for penalty in PENALTY_SCENARIOS:
            adj_total = sum(r_of(r) - penalty for r in c)
            adj_exp = adj_total / n
            row = {"pair": pair, "penalty_r": penalty, "n_closed": n,
                   "total_r": round(adj_total, 4), "expectancy": round(adj_exp, 5)}
            for model in ("1am", "9am"):
                mc = closed([r for r in pair_rows if r["model"] == model])
                if mc:
                    mt = sum(r_of(r) - penalty for r in mc)
                    row[f"total_r_{model}"] = round(mt, 4)
                    row[f"expectancy_{model}"] = round(mt / len(mc), 5)
                else:
                    row[f"total_r_{model}"] = None
                    row[f"expectancy_{model}"] = None
            rows_out.append(row)
            print(f"  +{penalty:.3f}R/trade: total_r={adj_total:+9.3f}  expectancy={adj_exp:+.5f}  "
                  f"(1am total_r={row['total_r_1am']}, 9am total_r={row['total_r_9am']})")
        max_sustainable = max(current_expectancy, 0.0)
        print(f"  Max ADDITIONAL penalty before expectancy<=0: {max_sustainable:.5f} R/trade "
              f"(current expectancy={current_expectancy:+.5f})" if current_expectancy > 0 else
              f"  Already at/below zero expectancy before any additional penalty (current={current_expectancy:+.5f})")

    write_csv("robustness_cost_sensitivity.csv",
              ["pair", "penalty_r", "n_closed", "total_r", "expectancy", "total_r_1am", "expectancy_1am",
               "total_r_9am", "expectancy_9am"], rows_out)
    print("\nWritten: robustness_cost_sensitivity.csv")
    return rows_out


# ===========================================================================
# PHASE 3 -- temporal robustness + leave-one-year-out
# ===========================================================================

def year_of(row):
    d = exit_dt(row)
    return d.year if d else None


def phase3_temporal():
    print("\n" + "=" * 100)
    print("PHASE 3 -- temporal robustness")
    print("=" * 100)

    years = list(range(2015, 2027))
    year_rows = []
    for pair in PAIRS + ("COMBINED",):
        pair_rows = TRADES if pair == "COMBINED" else [r for r in TRADES if r["pair"] == pair]
        for model in ("1am", "9am", "ALL"):
            mrows = pair_rows if model == "ALL" else [r for r in pair_rows if r["model"] == model]
            c = closed(mrows)
            by_year = defaultdict(list)
            for r in c:
                by_year[year_of(r)].append(r)
            for yr in years:
                yr_rows = by_year.get(yr, [])
                if not yr_rows:
                    continue
                yt = sum(r_of(r) for r in yr_rows)
                wins = sum(1 for r in yr_rows if r["outcome"] == "win")
                year_rows.append({
                    "pair": pair, "model": model, "year": yr, "trades": len(yr_rows),
                    "win_rate": round(wins / len(yr_rows), 4), "total_r": round(yt, 4),
                    "expectancy": round(yt / len(yr_rows), 5),
                })
    write_csv("robustness_year_breakdown.csv",
              ["pair", "model", "year", "trades", "win_rate", "total_r", "expectancy"], year_rows)
    print("Written: robustness_year_breakdown.csv")

    print("\n-- Per pair (ALL models combined): positive/negative years, top/bottom 3, half-period split --")
    half_split_rows = []
    for pair in PAIRS + ("COMBINED",):
        pair_rows = TRADES if pair == "COMBINED" else [r for r in TRADES if r["pair"] == pair]
        c = closed(pair_rows)
        by_year = defaultdict(list)
        for r in c:
            by_year[year_of(r)].append(r)
        yearly_totals = sorted(((yr, sum(r_of(r) for r in rows)) for yr, rows in by_year.items()))
        pos_years = sum(1 for _, t in yearly_totals if t > 0)
        neg_years = sum(1 for _, t in yearly_totals if t < 0)
        zero_years = sum(1 for _, t in yearly_totals if t == 0)
        grand_total = sum(t for _, t in yearly_totals)
        by_abs = sorted(yearly_totals, key=lambda p: -abs(p[1]))
        top3 = by_abs[:3]
        bot3 = sorted(yearly_totals, key=lambda p: p[1])[:3]
        first_half = [r for r in c if year_of(r) <= 2020]
        second_half = [r for r in c if year_of(r) >= 2021]
        fh_total, sh_total = total_r(first_half), total_r(second_half)
        fh_exp = expectancy(first_half)
        sh_exp = expectancy(second_half)
        print(f"\n{pair}: {pos_years} positive years, {neg_years} negative years, {zero_years} flat, "
              f"grand_total={grand_total:+.3f}")
        print(f"  Top-3 |contribution|: {[(y, round(t,2)) for y,t in top3]} "
              f"sum={sum(t for _,t in top3):+.3f} ({100*sum(t for _,t in top3)/grand_total:+.1f}% of total, if total!=0)" if grand_total else "")
        print(f"  Bottom-3 (most negative): {[(y, round(t,2)) for y,t in bot3]}")
        print(f"  2015-2020: n={len(first_half)} total_r={fh_total:+.3f} expectancy={fh_exp}")
        print(f"  2021-2026: n={len(second_half)} total_r={sh_total:+.3f} expectancy={sh_exp}")
        half_split_rows.append({
            "pair": pair, "positive_years": pos_years, "negative_years": neg_years,
            "grand_total_r": round(grand_total, 4),
            "top3_years": str([y for y, _ in top3]), "top3_sum_r": round(sum(t for _, t in top3), 4),
            "bottom3_years": str([y for y, _ in bot3]), "bottom3_sum_r": round(sum(t for _, t in bot3), 4),
            "n_2015_2020": len(first_half), "total_r_2015_2020": round(fh_total, 4), "expectancy_2015_2020": fh_exp,
            "n_2021_2026": len(second_half), "total_r_2021_2026": round(sh_total, 4), "expectancy_2021_2026": sh_exp,
        })
    write_csv("robustness_half_period_split.csv", list(half_split_rows[0].keys()), half_split_rows)
    print("\nWritten: robustness_half_period_split.csv")

    # Chronological drawdown evolution
    dd_summary = []
    for pair in PAIRS + ("COMBINED",):
        pair_rows = TRADES if pair == "COMBINED" else [r for r in TRADES if r["pair"] == pair]
        c = closed(pair_rows)
        max_dd, series = max_dd_chronological(c)
        dd_summary.append({"pair": pair, "max_drawdown_r": round(max_dd, 4), "n_points": len(series)})
        print(f"{pair}: max chronological drawdown = {max_dd:.4f} R over {len(series)} closed trades")
    write_csv("robustness_drawdown_summary.csv", ["pair", "max_drawdown_r", "n_points"], dd_summary)

    return year_rows


def phase3_leave_one_year_out():
    print("\n" + "=" * 100)
    print("PHASE 3b -- leave-one-year-out (systematic, all years 2015-2026)")
    print("=" * 100)
    years = list(range(2015, 2027))
    loyo_rows = []
    for pair in PAIRS + ("COMBINED",):
        pair_rows = TRADES if pair == "COMBINED" else [r for r in TRADES if r["pair"] == pair]
        c = closed(pair_rows)
        full_total = total_r(c)
        full_exp = expectancy(c)
        for yr in years:
            remaining = [r for r in c if year_of(r) != yr]
            removed = [r for r in c if year_of(r) == yr]
            if not removed:
                continue
            rem_total = total_r(remaining)
            rem_exp = expectancy(remaining)
            loyo_rows.append({
                "pair": pair, "excluded_year": yr, "n_removed": len(removed),
                "removed_year_total_r": round(sum(r_of(r) for r in removed), 4),
                "remaining_n": len(remaining), "remaining_total_r": round(rem_total, 4),
                "remaining_expectancy": round(rem_exp, 5) if rem_exp is not None else None,
                "full_total_r": round(full_total, 4), "sign_flips": (full_total > 0) != (rem_total > 0),
            })
    write_csv("robustness_leave_one_year_out.csv",
              ["pair", "excluded_year", "n_removed", "removed_year_total_r", "remaining_n",
               "remaining_total_r", "remaining_expectancy", "full_total_r", "sign_flips"], loyo_rows)
    print("Written: robustness_leave_one_year_out.csv")

    print("\n-- Sign flips (removing one year changes the SIGN of the pair's total_r) --")
    for r in loyo_rows:
        if r["sign_flips"]:
            print(f"  {r['pair']} without {r['excluded_year']}: full={r['full_total_r']:+.3f} -> "
                  f"remaining={r['remaining_total_r']:+.3f}")

    print("\n-- Highlighted cases (requested specifically, shown among the systematic results above) --")
    highlights = [("USDCAD", 2016), ("AUDUSD", 2017), ("AUDUSD", 2024), ("EURUSD", 2020)]
    for pair, yr in highlights:
        match = next((r for r in loyo_rows if r["pair"] == pair and r["excluded_year"] == yr), None)
        if match:
            print(f"  {pair} sin {yr}: full_total_r={match['full_total_r']:+.3f} -> "
                  f"remaining_total_r={match['remaining_total_r']:+.3f} "
                  f"(removed {match['n_removed']} trades contributing {match['removed_year_total_r']:+.3f}R)")
    return loyo_rows


# ===========================================================================
# PHASE 4 -- block bootstrap (monthly / quarterly), fixed seed
# ===========================================================================

N_RESAMPLES = 5000


def period_key(dt, granularity):
    if granularity == "monthly":
        return (dt.year, dt.month)
    quarter = (dt.month - 1) // 3 + 1
    return (dt.year, quarter)


def build_blocks(rows, granularity):
    """rows: closed trades (any mix of pairs, for COMBINED). Groups by exit
    calendar period -- for COMBINED this naturally keeps temporally-related
    trades from DIFFERENT pairs together in the same block, since the key is
    the calendar period alone, not pair+period."""
    blocks = defaultdict(list)
    for r in rows:
        d = exit_dt(r)
        if d is None:
            continue
        blocks[period_key(d, granularity)].append(r)
    return blocks


def block_bootstrap(rows, granularity, n_resamples, seed):
    blocks = build_blocks(rows, granularity)
    block_list = list(blocks.values())
    n_blocks = len(block_list)
    rng = random.Random(seed)
    total_rs, expectancies = [], []
    for _ in range(n_resamples):
        drawn = [block_list[rng.randrange(n_blocks)] for _ in range(n_blocks)]
        sample = [r for block in drawn for r in block]
        n = len(sample)
        if n == 0:
            continue
        tr = sum(r_of(r) for r in sample)
        total_rs.append(tr)
        expectancies.append(tr / n)
    return n_blocks, total_rs, expectancies


def percentile(sorted_vals, p):
    if not sorted_vals:
        return None
    idx = min(len(sorted_vals) - 1, max(0, int(round(p * (len(sorted_vals) - 1)))))
    return sorted_vals[idx]


def phase4_bootstrap():
    print("\n" + "=" * 100)
    print(f"PHASE 4 -- block bootstrap, seed={SEED}, n_resamples={N_RESAMPLES}")
    print("=" * 100)
    print("Resamples CALENDAR BLOCKS (monthly/quarterly) with replacement, not individual trades --"
          " trades are plausibly correlated within a short calendar window (shared market regime,"
          " overlapping active signals), so an i.i.d. single-trade bootstrap would understate real"
          " uncertainty and is NOT used as primary evidence here.")

    rows_out = []
    for pair in PAIRS + ("COMBINED",):
        pair_rows = closed(TRADES if pair == "COMBINED" else [r for r in TRADES if r["pair"] == pair])
        for granularity in ("monthly", "quarterly"):
            n_blocks, total_rs, expectancies = block_bootstrap(pair_rows, granularity, N_RESAMPLES, SEED)
            total_rs.sort()
            expectancies.sort()
            p_exp_le_zero = sum(1 for e in expectancies if e <= 0) / len(expectancies) if expectancies else None
            tr_lo, tr_hi = percentile(total_rs, 0.025), percentile(total_rs, 0.975)
            exp_lo, exp_hi = percentile(expectancies, 0.025), percentile(expectancies, 0.975)
            observed_total_r = total_r(pair_rows)
            observed_exp = expectancy(pair_rows)
            print(f"\n{pair} ({granularity}, {n_blocks} blocks available, n_closed={len(pair_rows)}):")
            print(f"  Observed: total_r={observed_total_r:+.3f} expectancy={observed_exp:+.5f}")
            print(f"  Bootstrap 95% CI: total_r=[{tr_lo:+.3f}, {tr_hi:+.3f}]  "
                  f"expectancy=[{exp_lo:+.5f}, {exp_hi:+.5f}]")
            print(f"  P(expectancy <= 0 under resampling) = {p_exp_le_zero:.4f}")
            rows_out.append({
                "pair": pair, "granularity": granularity, "n_blocks": n_blocks, "n_closed": len(pair_rows),
                "observed_total_r": round(observed_total_r, 4), "observed_expectancy": round(observed_exp, 5),
                "boot_total_r_p2_5": round(tr_lo, 4), "boot_total_r_p97_5": round(tr_hi, 4),
                "boot_expectancy_p2_5": round(exp_lo, 5), "boot_expectancy_p97_5": round(exp_hi, 5),
                "p_expectancy_le_zero": round(p_exp_le_zero, 4),
            })
    write_csv("robustness_bootstrap.csv", list(rows_out[0].keys()), rows_out)
    print("\nWritten: robustness_bootstrap.csv")
    print("\nLIMITATIONS (explicit): monthly blocks give ~132-144 available blocks per series, quarterly "
          "~44-48 -- both are SMALL numbers of effectively-independent units for a block bootstrap; tail "
          "percentiles with this few blocks are necessarily imprecise. The procedure assumes blocks are "
          "exchangeable across calendar time (no trend/regime assumed), which may not hold -- this is a "
          "DESCRIPTIVE measure of sampling variability under the historical block distribution, not proof "
          "of future profitability or a formal hypothesis test.")
    return rows_out


# ===========================================================================
# PHASE 5 -- simultaneous exposure / correlation across pairs
# ===========================================================================

def build_intervals():
    """One interval per FILLED trade (entry_timestamp_broker -> exit, or the
    dataset's last known timestamp for still-open trades -- a conservative,
    explicitly-flagged cap, not a real resolution date)."""
    last_ts = max(
        (exit_dt(r) for r in TRADES if exit_dt(r)), default=None
    )
    intervals = []
    open_capped = 0
    for r in TRADES:
        e = entry_dt(r)
        if e is None:
            continue
        x = exit_dt(r)
        if x is None:
            x = last_ts
            open_capped += 1
        if x < e:
            continue  # defensive; should not happen, checked in phase 1
        intervals.append({"pair": r["pair"], "entry": e, "exit": x, "outcome": r["outcome"],
                           "r": r_of(r), "signal_id": r["signal_id"]})
    return intervals, open_capped


def max_concurrent(intervals):
    events = []
    for iv in intervals:
        events.append((iv["entry"], 1))
        events.append((iv["exit"], -1))
    events.sort(key=lambda e: (e[0], -e[1]))  # opens before closes at the same instant
    cur = peak = 0
    for _, delta in events:
        cur += delta
        peak = max(peak, cur)
    return peak


def overlaps(a, b):
    return a["entry"] < b["exit"] and b["entry"] < a["exit"]


def phase5_exposure():
    print("\n" + "=" * 100)
    print("PHASE 5 -- simultaneous exposure / correlation across pairs")
    print("=" * 100)
    intervals, open_capped = build_intervals()
    print(f"Built {len(intervals)} trade intervals ({open_capped} still-open trades capped at the "
          f"dataset's last known timestamp -- their TRUE exposure duration is unknown, flagged explicitly).")

    per_pair_max = {}
    for pair in PAIRS:
        pair_ivs = [iv for iv in intervals if iv["pair"] == pair]
        per_pair_max[pair] = max_concurrent(pair_ivs)
        print(f"  Max concurrent exposure WITHIN {pair} (both models together): {per_pair_max[pair]}")
    combined_max = max_concurrent(intervals)
    print(f"  Max concurrent exposure COMBINED (all 3 pairs together): {combined_max}")

    # Pairwise overlap frequency.
    print("\n-- Pairwise overlap frequency --")
    overlap_rows = []
    pair_names = PAIRS
    for i, pa in enumerate(pair_names):
        for pb in pair_names[i + 1:]:
            ivs_a = [iv for iv in intervals if iv["pair"] == pa]
            ivs_b = [iv for iv in intervals if iv["pair"] == pb]
            # Sort b by entry for a light sweep rather than full O(n*m) -- counts
            # stay small enough here (a few hundred to ~1300 per pair) that a
            # straightforward double loop is fine and easiest to verify by eye.
            overlap_count_a = sum(1 for a in ivs_a if any(overlaps(a, b) for b in ivs_b))
            overlap_count_b = sum(1 for b in ivs_b if any(overlaps(a, b) for a in ivs_a))
            both_loss = sum(1 for a in ivs_a for b in ivs_b
                             if overlaps(a, b) and a["outcome"] == "loss" and b["outcome"] == "loss")
            freq_a = overlap_count_a / len(ivs_a) if ivs_a else 0.0
            freq_b = overlap_count_b / len(ivs_b) if ivs_b else 0.0
            print(f"  {pa}-{pb}: {overlap_count_a}/{len(ivs_a)} ({freq_a:.1%}) of {pa} trades overlap some "
                  f"{pb} trade; {overlap_count_b}/{len(ivs_b)} ({freq_b:.1%}) of {pb} trades overlap some "
                  f"{pa} trade; co-occurring BOTH-loss overlapping pairs: {both_loss}")
            overlap_rows.append({"pair_a": pa, "pair_b": pb, "a_trades": len(ivs_a), "b_trades": len(ivs_b),
                                  "a_overlapping": overlap_count_a, "a_overlap_freq": round(freq_a, 4),
                                  "b_overlapping": overlap_count_b, "b_overlap_freq": round(freq_b, 4),
                                  "both_loss_overlaps": both_loss})
    write_csv("robustness_pairwise_overlap.csv",
              ["pair_a", "pair_b", "a_trades", "b_trades", "a_overlapping", "a_overlap_freq",
               "b_overlapping", "b_overlap_freq", "both_loss_overlaps"], overlap_rows)

    # Monthly simultaneous-loss periods: months where 2+ pairs each have a
    # negative net R for that month (a simpler, calendar-level proxy for
    # "multiple pairs losing at the same time" than exact tick-level overlap).
    monthly_pair_r = defaultdict(lambda: defaultdict(float))
    for r in closed(TRADES):
        d = exit_dt(r)
        monthly_pair_r[(d.year, d.month)][r["pair"]] += r_of(r)
    simultaneous_loss_months = []
    for ym, pair_r in sorted(monthly_pair_r.items()):
        losing_pairs = [p for p, v in pair_r.items() if v < 0]
        if len(losing_pairs) >= 2:
            simultaneous_loss_months.append({"year": ym[0], "month": ym[1],
                                              "losing_pairs": ",".join(losing_pairs),
                                              **{f"r_{p}": round(pair_r.get(p, 0.0), 3) for p in PAIRS}})
    write_csv("robustness_simultaneous_loss_months.csv",
              ["year", "month", "losing_pairs"] + [f"r_{p}" for p in PAIRS], simultaneous_loss_months)
    print(f"\nMonths where >=2 pairs both had a net negative R: {len(simultaneous_loss_months)} "
          f"of {len(monthly_pair_r)} months with any closed trade.")
    print("Written: robustness_pairwise_overlap.csv, robustness_simultaneous_loss_months.csv")

    print("\n-- Limitations on treating sum(R) as a real portfolio curve (explicit, not glossed over) --")
    limitations = [
        "Each pair's R is normalized to ITS OWN risk unit (its own stop-loss distance) -- 1R in EURUSD and "
        "1R in AUDUSD are not the same account-currency amount unless position sizing is set so that they are, "
        "which this backtest never modeled (no position sizing, no account equity, no margin).",
        f"Concurrent exposure reaches {combined_max} simultaneously open trades combined -- summing R across "
        "genuinely concurrent trades assumes independent, fully-collateralized risk per trade, which is not how "
        "a real margined account behaves under simultaneous drawdown.",
        "No correlation-adjusted position sizing, no margin calls, no broker-imposed exposure limits are modeled.",
        f"{open_capped} trades are still open at the end of the available data -- their eventual R is unknown, "
        "and the combined curve already includes their entry without a real exit.",
    ]
    for lim in limitations:
        print(f"  - {lim}")
    return {"per_pair_max": per_pair_max, "combined_max": combined_max, "open_capped": open_capped}


# ===========================================================================
# PHASE 6 -- ambiguous_bar / gap_filled sensitivity
# ===========================================================================

def _is_true(value):
    return str(value).strip().lower() == "true"


def phase6_ambiguous_fills():
    print("\n" + "=" * 100)
    print("PHASE 6 -- ambiguous_bar / gap_filled sensitivity")
    print("=" * 100)
    rows_out = []
    for pair in PAIRS + ("COMBINED",):
        pair_rows = closed(TRADES if pair == "COMBINED" else [r for r in TRADES if r["pair"] == pair])
        ambiguous = [r for r in pair_rows if _is_true(r["ambiguous_bar"])]
        gap_filled = [r for r in pair_rows if _is_true(r["gap_filled"])]
        either = [r for r in pair_rows if _is_true(r["ambiguous_bar"]) or _is_true(r["gap_filled"])]
        clean = [r for r in pair_rows if r not in either]
        full_total = total_r(pair_rows)
        clean_total = total_r(clean)
        full_exp = expectancy(pair_rows)
        clean_exp = expectancy(clean)
        print(f"\n{pair} (n_closed={len(pair_rows)}):")
        print(f"  ambiguous_bar=True: {len(ambiguous)} trades, R contributed={sum(r_of(r) for r in ambiguous):+.3f}")
        print(f"  gap_filled=True: {len(gap_filled)} trades, R contributed={sum(r_of(r) for r in gap_filled):+.3f}")
        print(f"  either flag: {len(either)} trades ({100*len(either)/len(pair_rows):.1f}% of closed trades)")
        print(f"  Full: total_r={full_total:+.3f} expectancy={full_exp:+.5f}")
        print(f"  Excluding either flag (sensitivity only, NOT a claim these trades are invalid): "
              f"n={len(clean)} total_r={clean_total:+.3f} expectancy={clean_exp:+.5f}  "
              f"(delta={clean_total - full_total:+.3f}R)")
        rows_out.append({
            "pair": pair, "n_closed": len(pair_rows),
            "ambiguous_bar_count": len(ambiguous), "ambiguous_bar_r": round(sum(r_of(r) for r in ambiguous), 4),
            "gap_filled_count": len(gap_filled), "gap_filled_r": round(sum(r_of(r) for r in gap_filled), 4),
            "either_flag_count": len(either), "either_flag_pct": round(100 * len(either) / len(pair_rows), 2),
            "full_total_r": round(full_total, 4), "full_expectancy": round(full_exp, 5),
            "excl_flagged_total_r": round(clean_total, 4), "excl_flagged_expectancy": round(clean_exp, 5),
            "delta_r": round(clean_total - full_total, 4),
        })
    write_csv("robustness_ambiguous_fill_sensitivity.csv", list(rows_out[0].keys()), rows_out)
    print("\nWritten: robustness_ambiguous_fill_sensitivity.csv")
    print("\nNote: `_fill_sides`/`_resolve_exits` (unmodified) already apply a documented, conservative "
          "convention for these cases -- this phase only measures sensitivity, it does NOT modify the "
          "simulation engine or substitute its results.")
    return rows_out


if __name__ == "__main__":
    phase1_funnel()
    phase2_cost_sensitivity()
    phase3_temporal()
    phase3_leave_one_year_out()
    phase4_bootstrap()
    phase5_exposure()
    phase6_ambiguous_fills()
