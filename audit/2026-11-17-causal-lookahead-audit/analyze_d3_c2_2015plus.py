"""Analysis of the D3/C2 2015-01-01+ historical run (trades_d3_c2_2015plus_run2.csv,
funnel_2015plus_run2.csv, year_breakdown_2015plus_run2.csv). Read-only --
does not rerun anything. Reconciles CSV-derived R against the runner's
own printed aggregates, and reports every metric requested: funnel
stages, win rate, total R / expectancy, profit factor, max drawdown
(chronological), per-model (1AM/9AM) breakdown, per-year breakdown,
%-trades-per-year and profit concentration, win/loss distribution, and
the already-configured (not invented) execution-cost impact.
"""
import csv
from collections import defaultdict
from datetime import datetime

LABEL = "2015plus_run2"
PAIRS = ("EURUSD", "USDCAD", "AUDUSD")

# Same trading_cost_price DetectorConfig/SYMBOL_CONFIG already applies inside
# _resolve_exits -- read directly from the production config, not invented.
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "detector"))
from experimental.htf_trigger_1am_9am_backtest import SYMBOL_CONFIG  # noqa: E402

with open(f"trades_d3_c2_{LABEL}.csv", newline="", encoding="utf-8") as f:
    all_rows = list(csv.DictReader(f))
with open(f"funnel_{LABEL}.csv", newline="", encoding="utf-8") as f:
    funnel_rows = list(csv.DictReader(f))


def r_of(row):
    return float(row["r_multiple"]) if row["r_multiple"] != "" else 0.0


def closed(rows):
    return [r for r in rows if r["outcome"] in ("win", "loss")]


def profit_factor(rows):
    gains = sum(r_of(r) for r in rows if r["outcome"] == "win")
    losses = -sum(r_of(r) for r in rows if r["outcome"] == "loss")
    return gains / losses if losses > 0 else float("inf")


def max_drawdown_chronological(rows):
    """Chronological by exit_timestamp_broker (the actual resolution
    order), not by signal/entry order."""
    pts = sorted(
        ((datetime.fromisoformat(r["exit_timestamp_broker"]), r_of(r)) for r in rows if r["exit_timestamp_broker"]),
        key=lambda p: p[0],
    )
    equity = peak = max_dd = 0.0
    for _, r in pts:
        equity += r
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return max_dd


def year_of(row):
    return datetime.fromisoformat(row["exit_timestamp_broker"]).year if row["exit_timestamp_broker"] else None


def execution_cost_impact_r(rows):
    """trading_cost_price is already baked into every row's r_multiple
    (via _resolve_exits, unmodified). This recomputes its aggregate R
    impact analytically from entry_price/stop_loss already in the CSV
    (cost_in_r = trading_cost_price / risk_per_unit), using the REAL,
    already-configured per-symbol cost -- never an invented spread or
    slippage figure."""
    total_cost_r = 0.0
    for r in rows:
        cfg = SYMBOL_CONFIG[r["pair"]]
        risk = abs(float(r["entry_price"]) - float(r["stop_loss"]))
        if risk > 0:
            total_cost_r += cfg.trading_cost_price / risk
    return total_cost_r


print("=" * 100)
print("RECONCILIATION: sum(r_multiple) from CSV vs. runner's printed total_r aggregate")
print("=" * 100)
runner_printed_total_r = {"EURUSD": -0.2525, "USDCAD": 51.1780, "AUDUSD": 27.6775}
for pair in PAIRS:
    rows = [r for r in all_rows if r["pair"] == pair]
    csv_total_r = sum(r_of(r) for r in closed(rows))
    printed = runner_printed_total_r[pair]
    diff = abs(csv_total_r - printed)
    print(f"{pair}: CSV sum(r_multiple)={csv_total_r:.4f}  runner printed={printed:.4f}  diff={diff:.6f}  "
          f"{'OK' if diff < 0.001 else 'MISMATCH'}")

for pair in PAIRS:
    rows = [r for r in all_rows if r["pair"] == pair]
    c = closed(rows)
    opens = [r for r in rows if r["outcome"] == "open"]
    wins = [r for r in c if r["outcome"] == "win"]
    losses = [r for r in c if r["outcome"] == "loss"]
    total_r = sum(r_of(r) for r in c)
    frows = [f for f in funnel_rows if f["pair"] == pair]
    htf_triggers = sum(int(f["triggers_with_key_level"]) for f in frows)
    model1_confirmed = sum(int(f["model1_confirmed"]) for f in frows)
    candidates_built = sum(int(f["candidates_built"]) for f in frows)
    never_filled = sum(int(f["never_filled"]) for f in frows)

    print("\n" + "=" * 100)
    print(f"{pair} -- D3/C2, 2015-01-01 to latest available")
    print("=" * 100)
    print(f"Funnel: HTF triggers+KeyLevel={htf_triggers}  Model-1 CONFIRMED={model1_confirmed}  "
          f"population candidates={candidates_built}  filled(=trades)={len(rows)}  "
          f"never_filled(pending, no fill)={never_filled}  open(pending, still running)={len(opens)}  "
          f"closed={len(c)}")
    print(f"Win rate (closed): {len(wins)}/{len(c)} = {len(wins)/len(c):.4f}" if c else "no closed trades")
    print(f"Total R (closed): {total_r:+.4f}   Expectancy per closed trade: {total_r/len(c):+.4f} R" if c else "")
    print(f"Profit factor: {profit_factor(c):.4f}")
    print(f"Max drawdown (R, chronological by exit): {max_drawdown_chronological(c):.4f}")
    exec_cost_r = execution_cost_impact_r(rows)
    print(f"Execution cost already applied (SYMBOL_CONFIG.trading_cost_price={SYMBOL_CONFIG[pair].trading_cost_price}, "
          f"baked into r_multiple via _resolve_exits): aggregate cost impact across all {len(rows)} trades "
          f"~= {exec_cost_r:.4f} R total ({exec_cost_r/len(rows):.5f} R/trade avg)")

    print("\n  -- Per model --")
    for model in ("1am", "9am"):
        mc = closed([r for r in rows if r["model"] == model])
        mrows = [r for r in rows if r["model"] == model]
        mwins = [r for r in mc if r["outcome"] == "win"]
        mtotal = sum(r_of(r) for r in mc)
        print(f"  {model}: trades={len(mrows)} closed={len(mc)} wr={len(mwins)/len(mc):.4f} "
              f"total_r={mtotal:+.4f} expectancy={mtotal/len(mc):+.4f} pf={profit_factor(mc):.4f}" if mc else f"  {model}: no closed trades")

    print("\n  -- Per year (closed trades, by exit date) --")
    by_year = defaultdict(list)
    for r in c:
        by_year[year_of(r)].append(r)
    for year in sorted(by_year):
        yr = by_year[year]
        ywins = [r for r in yr if r["outcome"] == "win"]
        ytotal = sum(r_of(r) for r in yr)
        pct_of_total = 100 * len(yr) / len(c)
        print(f"    {year}: trades={len(yr):3d} ({pct_of_total:5.1f}% of all closed) wr={len(ywins)/len(yr):.4f} "
              f"total_r={ytotal:+8.3f}")

    print("\n  -- Profit concentration (years sorted by |total_r| contribution) --")
    year_totals = sorted(((yr, sum(r_of(r) for r in rows)) for yr, rows in by_year.items()),
                          key=lambda p: -abs(p[1]))
    cum = 0.0
    for yr, yt in year_totals:
        cum += yt
        print(f"    {yr}: total_r={yt:+8.3f}  cumulative={cum:+8.3f}  "
              f"({100*yt/total_r if total_r else 0:+6.1f}% of grand total_r)")

    print("\n  -- Win/loss R distribution (closed trades) --")
    import statistics
    win_rs = [r_of(r) for r in wins]
    loss_rs = [r_of(r) for r in losses]
    if win_rs:
        print(f"    Wins: n={len(win_rs)} mean={statistics.mean(win_rs):+.3f} "
              f"median={statistics.median(win_rs):+.3f} min={min(win_rs):+.3f} max={max(win_rs):+.3f}")
    if loss_rs:
        print(f"    Losses: n={len(loss_rs)} mean={statistics.mean(loss_rs):+.3f} "
              f"median={statistics.median(loss_rs):+.3f} min={min(loss_rs):+.3f} max={max(loss_rs):+.3f}")
