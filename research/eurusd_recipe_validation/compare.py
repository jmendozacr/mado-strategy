"""Reproducible comparison command -- RESEARCH TOOLING, not a production
entry point.

Regenerates every committed artifact under `data/` from the raw broker CSVs
in one pass, and writes `REPORT.md` with the cross-check against the
surviving historical figures computed, never hand-typed.

    uv run --project detector python -m research.eurusd_recipe_validation.compare

Run it from the repository root. Every path defaults to this repository's
own layout, so the bare command above is the canonical invocation.
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import os
import sys
from dataclasses import dataclass

from core.config import DetectorConfig

from research.eurusd_recipe_validation import historical
from research.eurusd_recipe_validation.pipeline import VARIANTS, VariantResult, build_variant, load_series, recipe_signals
from research.eurusd_recipe_validation.sizing import RollingWindowResult, simulate_rolling_windows

DEFAULT_H4 = os.path.join("pairs", "H4", "EURUSDm_H4_202001020000_202609042000.csv")
DEFAULT_M15 = os.path.join("pairs", "M15", "EURUSDm_M15_202207260000_202609042045.csv")
DEFAULT_DAILY = os.path.join("pairs", "D1", "EURUSDm_Daily_202001020000_202609040000.csv")
DEFAULT_OUTPUT = os.path.join("research", "eurusd_recipe_validation", "data")

RISK_LEVELS: tuple[float, ...] = (0.50, 0.75, 1.00)
PHASE_1_MAX_DD_PCT = 10.0
PHASE_2_MAX_DD_PCT = 5.0
DAILY_LOSS_LIMIT_PCT = 5.0
WINDOW_DAYS = 250
DRAWDOWN_BASES: tuple[str, ...] = ("initial_balance_floor", "peak_to_trough")

# Both exit models are published because the surviving record does not pin
# one and the choice changes the conclusion -- see
# historical.RECONSTRUCTED_PARAMETERS and REPORT.md's "What reproduced".
PARTIAL_FRACTIONS: tuple[float, ...] = (0.0, 0.5)
EXIT_MODEL_LABELS: dict[float, str] = {
    0.0: "pure natural take-profit, no partial leg - what the recipe record literally describes",
    0.5: "the detector's current library default, REQ-68 - what simulate() produces today",
}


@dataclass(frozen=True)
class Run:
    partial_fraction: float
    results: tuple[VariantResult, ...]
    windows: dict[tuple[str, float, str], RollingWindowResult]


def _write_csv(path: str, header: list[str], rows) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def _write_trades(directory: str, result: VariantResult) -> None:
    _write_csv(
        os.path.join(directory, f"trades_{result.spec.key}.csv"),
        ["signal_id", "direction", "entry_time_utc", "exit_time_utc",
         "entry_index", "exit_index", "outcome", "r_multiple"],
        [
            [t.signal_id, t.direction, t.entry_time.isoformat(),
             "" if t.exit_time is None else t.exit_time.isoformat(),
             t.entry_index, "" if t.exit_index is None else t.exit_index,
             t.outcome, "" if t.r_multiple is None else f"{t.r_multiple:.6f}"]
            for t in result.trades
        ],
    )


def _write_windows(directory: str, key: str, windows: dict) -> None:
    rows = []
    for (variant_key, risk, basis), result in sorted(windows.items()):
        if variant_key != key:
            continue
        for window in result.windows:
            rows.append([
                basis, f"{risk:.2f}", f"{result.max_drawdown_pct:.1f}",
                window.start_date.isoformat(), window.end_date.isoformat(), window.trades,
                f"{window.total_r:.4f}", f"{window.worst_drawdown_r:.4f}",
                f"{window.worst_drawdown_pct:.4f}", f"{window.worst_daily_loss_pct:.4f}",
                int(window.breached_max_drawdown), int(window.breached_daily_loss),
            ])
    _write_csv(
        os.path.join(directory, f"windows_{key}.csv"),
        ["drawdown_basis", "risk_per_trade_pct", "max_drawdown_cap_pct", "window_start",
         "window_end", "trades_in_window", "total_r", "worst_drawdown_r", "worst_drawdown_pct",
         "worst_daily_loss_pct", "breached_max_drawdown", "breached_daily_loss"],
        rows,
    )


def _fmt(value, spec="%.2f", missing="n/a"):
    return missing if value is None else spec % value


def _pct(fraction):
    return "n/a" if fraction is None else f"{fraction * 100:.1f}%"


def _summary_rows(run: Run) -> list[list]:
    rows = []
    for result in run.results:
        stats = result.stats
        row = [
            run.partial_fraction, result.spec.key, result.spec.label, result.signals,
            result.trades_before_gating, stats.trades, stats.wins, stats.losses,
            _fmt(stats.win_rate, "%.4f", ""), f"{stats.total_r:.4f}", _fmt(stats.average_r, "%.4f", ""),
            f"{stats.max_drawdown_r:.4f}", _fmt(stats.calmar_ratio, "%.4f", ""),
            "" if stats.first_close is None else stats.first_close.isoformat(),
            "" if stats.last_close is None else stats.last_close.isoformat(),
        ]
        for basis in DRAWDOWN_BASES:
            for risk in RISK_LEVELS:
                window_result = run.windows[(result.spec.key, risk, basis)]
                row.append(_fmt(window_result.fail_dd_fraction, "%.5f", ""))
        for risk in RISK_LEVELS:
            window_result = run.windows[(result.spec.key, risk, DRAWDOWN_BASES[0])]
            row.append(_fmt(window_result.fail_daily_loss_fraction, "%.5f", ""))
        rows.append(row)
    return rows


def _summary_header() -> list[str]:
    header = [
        "partial_fraction", "variant", "label", "signals", "trades_before_gating", "trades",
        "wins", "losses", "win_rate", "total_r", "average_r", "max_drawdown_r", "calmar_ratio",
        "first_close", "last_close",
    ]
    for basis in DRAWDOWN_BASES:
        header += [f"fail_dd_{basis}_risk_{risk:.2f}" for risk in RISK_LEVELS]
    header += [f"fail_daily_loss_risk_{risk:.2f}" for risk in RISK_LEVELS]
    return header


def _cross_check_table(run: Run) -> list[str]:
    """Every surviving historical figure against what this reproduction
    actually produced, with the delta computed rather than asserted."""
    by_key = {result.spec.key: result for result in run.results}
    lines = [
        "| Historical figure (VERIFIED) | Value | This reproduction | Delta |",
        "| --- | --- | --- | --- |",
    ]
    for key, expected in historical.VERIFIED_TRADE_COUNTS.items():
        actual = by_key[key].stats.trades
        lines.append(
            f"| `{key}` trade count | {expected} | {actual} | "
            f"{actual - expected:+d} ({(actual - expected) / expected * 100:+.1f}%) |"
        )
    for (key, risk), expected in historical.VERIFIED_FAIL_DD_PCT.items():
        window_result = run.windows[(key, risk, "initial_balance_floor")]
        actual = window_result.fail_dd_fraction
        actual_pct = None if actual is None else actual * 100
        delta = "n/a" if actual_pct is None else f"{actual_pct - expected:+.1f} pp"
        lines.append(
            f"| `{key}` Phase-1 fail_dd @ {risk:.2f}% risk | {expected:.1f}% | "
            f"{_fmt(actual_pct, '%.1f')}% | {delta} |"
        )
    for key, expected in historical.VERIFIED_CALMAR.items():
        actual = by_key[key].stats.calmar_ratio
        delta = "n/a" if actual is None else f"{actual - expected:+.2f}"
        lines.append(f"| `{key}` Calmar ratio | {expected:.2f} | {_fmt(actual)} | {delta} |")
    return lines


def _aggregate_table(run: Run) -> list[str]:
    lines = [
        "| Variant | Trades | Win rate | Total R | Avg R / trade | Max DD (R) | Calmar |",
        "| --- | --: | --: | --: | --: | --: | --: |",
    ]
    for result in run.results:
        s = result.stats
        lines.append(
            f"| {result.spec.label} | {s.trades} | {_pct(s.win_rate)} | {s.total_r:.1f} | "
            f"{_fmt(s.average_r, '%+.3f')} | {s.max_drawdown_r:.1f} | {_fmt(s.calmar_ratio)} |"
        )
    return lines


def _windowed_table(run: Run, basis: str) -> list[str]:
    lines = [
        "| Variant | " + " | ".join(f"fail_dd @ {risk:.2f}%" for risk in RISK_LEVELS) + " |",
        "| --- | " + " | ".join("--:" for _ in RISK_LEVELS) + " |",
    ]
    for result in run.results:
        cells = [
            _pct(run.windows[(result.spec.key, risk, basis)].fail_dd_fraction) for risk in RISK_LEVELS
        ]
        lines.append(f"| {result.spec.label} | " + " | ".join(cells) + " |")
    return lines


def _parameter_table(rows, value_header: str) -> list[str]:
    lines = [f"| Parameter | {value_header} | Basis |", "| --- | --- | --- |"]
    for row in rows:
        lines.append(f"| {row.parameter} | {row.value} | {row.basis} |")
    return lines


def _baseline_safety_lines(run: Run) -> list[str]:
    """Is the unfiltered baseline really the safest variant? Computed from
    this run's own numbers rather than asserted in prose, because the answer
    depends on the exit model and the report must not claim otherwise."""
    lines = []
    for basis in DRAWDOWN_BASES:
        for risk in RISK_LEVELS:
            baseline = run.windows[(VARIANTS[0].key, risk, basis)].fail_dd_fraction or 0.0
            levers = sorted(
                (
                    (run.windows[(result.spec.key, risk, basis)].fail_dd_fraction or 0.0, result.spec.key)
                    for result in run.results[1:]
                )
            )
            best_value, best_key = levers[0]
            worst_value, worst_key = levers[-1]
            margin = (best_value - baseline) * 100
            verdict = "baseline safest" if margin >= 0 else f"`{best_key}` safer by {-margin:.1f} pp"
            lines.append(
                f"| `{basis}` | {risk:.2f}% | {_pct(baseline)} | "
                f"`{best_key}` {_pct(best_value)} | `{worst_key}` {_pct(worst_value)} | {verdict} |"
            )
    return [
        "| Drawdown basis | Risk | Baseline fail_dd | Best lever | Worst lever | Verdict |",
        "| --- | --: | --: | --- | --- | --- |",
        *lines,
    ]


def _contrast_lines(run: Run, risk: float = 0.75) -> list[str]:
    """The whole point of the exercise, computed: the lever with the BEST
    per-trade expectancy against its own rolling-window fail rate, beside
    the baseline's. If the filters really do flatter the average while
    concentrating the risk, it shows up right here."""
    baseline = run.results[0]
    best = max(run.results[1:], key=lambda r: r.stats.average_r or float("-inf"))
    basis = "initial_balance_floor"
    baseline_fail = run.windows[(baseline.spec.key, risk, basis)].fail_dd_fraction
    best_fail = run.windows[(best.spec.key, risk, basis)].fail_dd_fraction
    ratio = (
        f"{best_fail / baseline_fail:.1f}x"
        if baseline_fail and best_fail and baseline_fail > 0
        else "n/a"
    )
    return [
        f"The best per-trade expectancy among the filtered variants is `{best.spec.key}` at "
        f"{_fmt(best.stats.average_r, '%+.3f')} R per trade, against the baseline's "
        f"{_fmt(baseline.stats.average_r, '%+.3f')} R - on that number alone the filter wins. "
        f"At {risk:.2f}% risk it would have breached the static {PHASE_1_MAX_DD_PCT:.0f}% cap in "
        f"{_pct(best_fail)} of all {WINDOW_DAYS}-day windows against the baseline's "
        f"{_pct(baseline_fail)}, or {ratio} as often, on "
        f"{best.stats.trades} trades against {baseline.stats.trades}.",
    ]


def _report(runs: tuple[Run, ...], exit_labels: dict[float, str]) -> str:
    # Window counts differ slightly per variant: a variant's span runs from
    # its own first realised trade to its own last, so a filter that drops
    # the earliest or latest trades also drops a few possible start days.
    counts = [len(result.windows) for run in runs for result in run.windows.values()]
    window_range = (
        f"{min(counts)}" if min(counts) == max(counts) else f"{min(counts)}-{max(counts)}"
    )
    out: list[str] = [
        "# EURUSD recipe validation - aggregate statistics vs. rolling-window survival",
        "",
        "GENERATED FILE. Produced by "
        "`uv run --project detector python -m research.eurusd_recipe_validation.compare` "
        "from the repository root. Do not hand-edit; re-run the command instead.",
        "",
        "Read `README.md` next to this file first: it states which parameters below are "
        "VERIFIED historical facts and which are RECONSTRUCTIONS of parameters whose original "
        "values are lost. This is a REPRODUCTION of a comparison whose own data was never "
        "committed, not a replay of it.",
        "",
        "## The question",
        "",
        "Three quality-over-quantity filters were once tested against the unfiltered baseline "
        "recipe, and all three were rejected. The reason recorded at the time is the thing worth "
        "showing: on aggregate, whole-period statistics the filters looked GOOD, and on a "
        "rolling-window prop-firm survival simulation they looked WORSE. Fewer, higher-quality "
        "trades improve the average and concentrate the risk, and it is the concentration that "
        "fails an account.",
        "",
        f"Every fail_dd% below is measured over {window_range} overlapping "
        f"{WINDOW_DAYS}-day windows (the exact count varies a little per variant) - one notional "
        "account started on every possible historical day, each run against a static Phase-1 cap "
        f"of {PHASE_1_MAX_DD_PCT:.0f}% from its own initial balance.",
        "",
        "## What reproduced and what did not",
        "",
        "- **Trade counts: reproduced.** All three surviving historical counts land within 0.7% "
        "to 5.9% of this rebuild, depending on the exit model. That is close enough to confirm "
        "the signal pipeline, the session, the two account-level gates and lever B's 25-pip "
        "threshold, and close enough to PIN lever A's lost R:R value at 2.5.",
        "- **Aggregate-vs-windowed direction: reproduced, conditionally.** On the "
        "static-from-initial-balance basis with a pure natural-take-profit exit, the historical "
        "verdict holds where it matters: the baseline is the safest variant at 0.75% and 1.00% "
        "risk, and A+B is the most dangerous everywhere - A+B fails 15.9% of windows at 0.75% "
        "risk against the baseline's 4.3%, nearly four times as often. At 0.50% risk every "
        "variant is effectively safe (0.0-6.2%) and the baseline's 0.1% is one single window out "
        "of 1251, so the 0.50% row ranks noise. With the detector's current 50% partial-exit "
        "default the ordering weakens further: lever B overtakes the baseline at 0.75% risk. The "
        "exit model is load-bearing for the conclusion, so both are published below rather than "
        "one being chosen quietly.",
        "- **The `peak_to_trough` basis inverts the ranking, and should not be read as a "
        "contradiction.** It measures giving back a run-up, so it structurally punishes whichever "
        "variant made the most money - the baseline, with the most trades and the largest total "
        "R, looks worst by it. A cap that is static from the account's INITIAL balance is simply "
        "not that measurement: an account that doubled and then halved never breached a static "
        "10% floor. The basis is published for completeness because the surviving record's "
        "wording ('worst-case drawdown within any window') literally describes it, but "
        "`initial_balance_floor` is the basis that matches the rule the user confirmed.",
        "- **Absolute fail_dd% levels: NOT reproduced.** This rebuild is 7 to 19 percentage "
        "points more optimistic than the historical figures at every point of comparison. No "
        "defensible combination of the reconstructed parameters closes that gap. The lost "
        "simulator's equity model was materially harsher than anything the surviving description "
        "specifies; see README.md's 'Known unreproduced figures'.",
        "- **The Calmar contrast: NOT reproduced.** The historical record has lever B scoring "
        "BETTER than the baseline on Calmar (6.46 vs 4.35), which is precisely what made the "
        "windowed check decisive. Under the reconstructed Calmar definition the baseline scores "
        "better on both exit models. The 'aggregate flatters the filters' effect still shows up "
        "here, but in per-trade expectancy and win rate rather than in Calmar.",
        "- **The daily 5% loss limit never binds.** Across every variant, risk level and window, "
        "zero windows breached it. The stop-after-two-losses rule caps a day's exposure near 2R, "
        "so the max-drawdown cap is the only constraint that ever decides an account here.",
        "",
    ]

    for run in runs:
        out += [
            f"## Exit model: partial_fraction = {run.partial_fraction} "
            f"({exit_labels[run.partial_fraction]})",
            "",
            "### The contrast in one line",
            "",
            *_contrast_lines(run),
            "",
            "### Is the unfiltered baseline the safest variant?",
            "",
            *_baseline_safety_lines(run),
            "",
            "### Aggregate, whole-period statistics (the view that favoured the filters)",
            "",
            *_aggregate_table(run),
            "",
            f"### Rolling-window survival, Phase-1 cap {PHASE_1_MAX_DD_PCT:.0f}% static, "
            "basis `initial_balance_floor` (the user-confirmed static rule)",
            "",
            *_windowed_table(run, "initial_balance_floor"),
            "",
            f"### Rolling-window survival, Phase-1 cap {PHASE_1_MAX_DD_PCT:.0f}% static, "
            "basis `peak_to_trough` (the memory record's literal phrasing)",
            "",
            *_windowed_table(run, "peak_to_trough"),
            "",
            "### Cross-check against the surviving historical figures",
            "",
            *_cross_check_table(run),
            "",
        ]

    out += [
        "## A live/backtest mismatch found while reconstructing this",
        "",
        "Not part of the original comparison, but it surfaced from it and it affects the live "
        "scanner, so it is recorded here rather than dropped.",
        "",
        "`scanner/main.py` builds its population with a bare `DetectorConfig()`, whose "
        "`BacktestConfig.kill_zone_gated` defaults to `True`. That gate restricts candidates to "
        "the NY 07:00-11:00 kill zone inside `build_stage6_population`, which is STRICTLY "
        "NARROWER than the 02:00-11:00 London+Lunch+NY session `scanner/rules.py::_in_session` "
        "then applies. The narrower gate wins, so the live scanner's effective session is "
        "07:00-11:00 NY and its session filter changes nothing: measured on this corpus, the "
        "population is 1014 trades with that filter and 1014 without it.",
        "",
        "Consequences worth a decision:",
        "",
        "- The recipe's stated session is not the session being traded. Lever C ('NY-only "
        "narrowing'), a filter that was REJECTED, is approximately what the live scanner is "
        "already doing.",
        "- The historical baseline count of 1681 is only reachable with the gate OFF, which is "
        "why `pipeline.build_variant` forces `kill_zone_gated=False`. That makes it near-certain "
        "the original comparison also ran with it off - i.e. the comparison measured a recipe "
        "the scanner does not currently run.",
        "",
        "This research package changes nothing in `scanner/` or `detector/`. Reconciling them is "
        "a separate decision.",
        "",
        "## Parameters this reproduction did NOT have to guess",
        "",
        *_parameter_table(historical.VERIFIED_PARAMETERS, "Value (VERIFIED)"),
        "",
        "## Parameters this reproduction RECONSTRUCTED",
        "",
        "Every value in this table is a rebuild, not a recovered historical fact. Treat any "
        "number in this report that depends on one as reproduction-grade evidence, not as a "
        "replay of the original run.",
        "",
        *_parameter_table(historical.RECONSTRUCTED_PARAMETERS, "Value (RECONSTRUCTED)"),
        "",
        "## Committed data artifacts",
        "",
        "Under `data/partial_<fraction>/`:",
        "",
        "- `trades_<variant>.csv` - every trade the variant took, after both account-level gates.",
        "- `windows_<variant>.csv` - one row per rolling window per risk level per drawdown "
        "basis, carrying that window's own worst drawdown and breach flags, so every fail_dd% "
        "above can be recomputed independently from these rows alone.",
        "- `summary.csv` - every number in the tables above, machine-readable.",
        "",
    ]
    return "\n".join(out) + "\n"


def _run_variants(
    signals, m15, htf, partial_fraction: float, base_config: DetectorConfig
) -> Run:
    config = dataclasses.replace(
        base_config,
        backtest=dataclasses.replace(base_config.backtest, partial_fraction=partial_fraction),
    )
    results = tuple(build_variant(spec, signals, m15, config, htf=htf) for spec in VARIANTS)
    windows = {}
    for result in results:
        for basis in DRAWDOWN_BASES:
            for risk in RISK_LEVELS:
                windows[(result.spec.key, risk, basis)] = simulate_rolling_windows(
                    result.trades,
                    risk_per_trade_pct=risk,
                    max_drawdown_pct=PHASE_1_MAX_DD_PCT,
                    daily_loss_limit_pct=DAILY_LOSS_LIMIT_PCT,
                    window_days=WINDOW_DAYS,
                    drawdown_basis=basis,
                )
    return Run(partial_fraction=partial_fraction, results=results, windows=windows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--h4-csv", default=DEFAULT_H4)
    parser.add_argument("--m15-csv", default=DEFAULT_M15)
    parser.add_argument(
        "--daily-csv", default=DEFAULT_DAILY,
        help="pass an empty string to run without a Daily key-level tier",
    )
    parser.add_argument("--symbol", default="EURUSDm")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    print(f"loading {args.symbol} series", flush=True)
    m15, h4, daily = load_series(args.h4_csv, args.m15_csv, args.daily_csv or None, args.symbol)
    base_config = DetectorConfig()

    print("running detection and alignment once for every variant", flush=True)
    signals = recipe_signals(m15, h4, daily, base_config)
    print(f"  {len(signals)} reject_close_inside signals with a credited key level", flush=True)

    runs = []
    for partial_fraction in PARTIAL_FRACTIONS:
        print(f"resolving variants at partial_fraction={partial_fraction}", flush=True)
        run = _run_variants(signals, m15, h4, partial_fraction, base_config)
        directory = os.path.join(args.output_dir, f"partial_{partial_fraction}")
        for result in run.results:
            _write_trades(directory, result)
            _write_windows(directory, result.spec.key, run.windows)
            print(f"  {result.spec.key}: {result.stats.trades} trades", flush=True)
        _write_csv(os.path.join(directory, "summary.csv"), _summary_header(), _summary_rows(run))
        runs.append(run)

    report_path = os.path.join(args.output_dir, "REPORT.md")
    with open(report_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(_report(tuple(runs), EXIT_MODEL_LABELS))
    print(f"wrote {report_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
