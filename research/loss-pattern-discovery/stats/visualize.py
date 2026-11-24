"""Deliverable visualizations: reads the already-computed
artifacts/phase2_atlas.json (never recomputes the Atlas itself) and renders
a handful of honest, CI-aware charts with matplotlib -- already a `detector`
dependency, no new dependency added.

Usage (after stats/atlas.py has been run at least once):
    uv run --project detector python research/loss-pattern-discovery/stats/visualize.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
for _path in (LAB_ROOT,):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HORIZON_ORDER = ("1h", "4h", "1d", "3d")


def _load_atlas() -> dict:
    path = LAB_ROOT / "artifacts" / "phase2_atlas.json"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found -- run stats/atlas.py first")
    return json.loads(path.read_text(encoding="utf-8"))["atlas"]


def plot_continuation_vs_reversal(atlas: dict, out_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    x = range(len(HORIZON_ORDER))
    p_cont = [atlas["overall"][h]["p_continuation"]["point_estimate"] for h in HORIZON_ORDER]
    cont_err = [
        [max(0, p - atlas["overall"][h]["p_continuation"]["ci_low"]) for h, p in zip(HORIZON_ORDER, p_cont)],
        [max(0, atlas["overall"][h]["p_continuation"]["ci_high"] - p) for h, p in zip(HORIZON_ORDER, p_cont)],
    ]
    p_rev = [atlas["overall"][h]["p_reversal"]["point_estimate"] for h in HORIZON_ORDER]
    rev_err = [
        [max(0, p - atlas["overall"][h]["p_reversal"]["ci_low"]) for h, p in zip(HORIZON_ORDER, p_rev)],
        [max(0, atlas["overall"][h]["p_reversal"]["ci_high"] - p) for h, p in zip(HORIZON_ORDER, p_rev)],
    ]
    width = 0.35
    ax.bar([i - width / 2 for i in x], p_cont, width, yerr=cont_err, capsize=3, label="Continuation")
    ax.bar([i + width / 2 for i in x], p_rev, width, yerr=rev_err, capsize=3, label="Reversal")
    ax.set_xticks(list(x))
    ax.set_xticklabels(HORIZON_ORDER)
    ax.set_ylabel("Proportion of eligible stop events (90% block-bootstrap CI)")
    ax.set_title("Continuation vs. reversal after a confirmed stop event")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "continuation_vs_reversal.png", dpi=150)
    plt.close(fig)


def plot_mae_mfe_distribution(atlas: dict, out_dir: Path, horizon: str = "1d") -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    mae = atlas["overall"][horizon]["mae_r_median"]
    mfe = atlas["overall"][horizon]["mfe_r_median"]
    labels = ["MAE (R)", "MFE (R)"]
    values = [mae["point_estimate"], mfe["point_estimate"]]
    errs = [
        [mae["point_estimate"] - mae["ci_low"], mfe["point_estimate"] - mfe["ci_low"]],
        [mae["ci_high"] - mae["point_estimate"], mfe["ci_high"] - mfe["point_estimate"]],
    ]
    ax.bar(labels, values, yerr=errs, capsize=4, color=["#b23b3b", "#2f6f4f"])
    ax.set_ylabel(f"Median, R units ({horizon} horizon, 90% CI)")
    ax.set_title(f"Post-stop MAE vs. MFE at {horizon}")
    fig.tight_layout()
    fig.savefig(out_dir / f"mae_mfe_distribution_{horizon}.png", dpi=150)
    plt.close(fig)


def plot_control_comparison(atlas: dict, out_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    x = range(len(HORIZON_ORDER))
    diffs = [
        atlas["control_comparison"][h]["p_continuation_diff_sl_minus_control"]["point_estimate"]
        for h in HORIZON_ORDER
    ]
    los = [
        atlas["control_comparison"][h]["p_continuation_diff_sl_minus_control"]["ci_low"] for h in HORIZON_ORDER
    ]
    his = [
        atlas["control_comparison"][h]["p_continuation_diff_sl_minus_control"]["ci_high"] for h in HORIZON_ORDER
    ]
    errs = [[d - lo for d, lo in zip(diffs, los)], [hi - d for d, hi in zip(diffs, his)]]
    ax.bar(list(x), diffs, yerr=errs, capsize=4, color="#3b6fb2")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(list(x))
    ax.set_xticklabels(HORIZON_ORDER)
    ax.set_ylabel("P(continuation | SL) - P(continuation | matched control)")
    ax.set_title("Difference vs. matched control (paired block bootstrap, 90% CI)")
    fig.tight_layout()
    fig.savefig(out_dir / "control_comparison_continuation.png", dpi=150)
    plt.close(fig)


def plot_by_instrument(atlas: dict, out_dir: Path, horizon: str = "1d") -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    by_instrument = atlas["by_dimension"]["instrument"][horizon]
    instruments = list(by_instrument.keys())
    values = [by_instrument[i]["mae_r_median"]["point_estimate"] for i in instruments]
    los = [by_instrument[i]["mae_r_median"]["ci_low"] for i in instruments]
    his = [by_instrument[i]["mae_r_median"]["ci_high"] for i in instruments]
    errs = [[v - lo for v, lo in zip(values, los)], [hi - v for v, hi in zip(values, his)]]
    ax.bar(instruments, values, yerr=errs, capsize=4, color="#8a5cb2")
    ax.set_ylabel(f"Median MAE, R units ({horizon} horizon, 90% CI)")
    ax.set_title("Post-stop adverse excursion by instrument")
    fig.tight_layout()
    fig.savefig(out_dir / f"by_instrument_mae_{horizon}.png", dpi=150)
    plt.close(fig)


def plot_stability_by_period(atlas: dict, out_dir: Path, horizon: str = "1d") -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    by_period = atlas["by_dimension"]["period_bucket"][horizon]
    periods = sorted(k for k in by_period.keys() if k is not None)
    values = [by_period[p]["p_continuation"]["point_estimate"] for p in periods]
    los = [by_period[p]["p_continuation"]["ci_low"] for p in periods]
    his = [by_period[p]["p_continuation"]["ci_high"] for p in periods]
    ax.plot(periods, values, marker="o", color="#b2792f")
    ax.fill_between(periods, los, his, alpha=0.2, color="#b2792f")
    ax.set_ylabel(f"P(continuation) ({horizon} horizon, 90% CI band)")
    ax.set_title("Historical stability across predeclared period buckets")
    fig.tight_layout()
    fig.savefig(out_dir / f"stability_by_period_{horizon}.png", dpi=150)
    plt.close(fig)


def main() -> None:
    atlas = _load_atlas()
    out_dir = LAB_ROOT / "artifacts" / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    plot_continuation_vs_reversal(atlas, out_dir)
    plot_mae_mfe_distribution(atlas, out_dir)
    plot_control_comparison(atlas, out_dir)
    plot_by_instrument(atlas, out_dir)
    plot_stability_by_period(atlas, out_dir)
    print(f"Figures written to {out_dir}")


if __name__ == "__main__":
    main()
