"""Renders the 4 pre-declared chart examples (docs/01-protocol.md's
own chart-selection rule: first EURUSD trigger chronologically, by
`current_open_ts`, within each of INSIDE/OUTSIDE/EXACT_BOUNDARY/
DOUBLE_SWEEP_AMBIGUOUS) as PNGs in `figures/`, using matplotlib.
Read-only: reloads EURUSD's own M15 series via the sibling lab's
`_load_symbol_data`, never recomputes any detection decision.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

LAB_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = LAB_ROOT.parent.parent
DETECTOR_ROOT = REPO_ROOT / "detector"
AUDIT_ROOT = REPO_ROOT / "audit" / "2026-11-17-causal-lookahead-audit"
LPD_ROOT = REPO_ROOT / "research" / "loss-pattern-discovery"
for _path in (LAB_ROOT, DETECTOR_ROOT, AUDIT_ROOT, LPD_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import causal_intrabar as ci  # noqa: E402
from extract.funnel_reconstruction import _load_symbol_data  # noqa: E402

_NY = ZoneInfo("America/New_York")
_UTC = ZoneInfo("UTC")
M15 = timedelta(minutes=15)
H4 = timedelta(hours=4)

EXAMPLES = {
    "OUTSIDE": ("EURUSD|d3_c2|9am|2015-01-02T14:00:00|bullish", datetime(2015, 1, 2, 14, 0)),
    "INSIDE": ("EURUSD|d3_c2|9am|2015-01-07T14:00:00|bullish", datetime(2015, 1, 7, 14, 0)),
    "DOUBLE_SWEEP_AMBIGUOUS": ("EURUSD|d3_c2|9am|2015-01-29T14:00:00|bearish", datetime(2015, 1, 29, 14, 0)),
    "EXACT_BOUNDARY": ("EURUSD|d3_c2|9am|2016-09-22T13:00:00|bearish", datetime(2016, 9, 22, 13, 0)),
}


def _ref_open(cur_open: datetime) -> datetime:
    day = cur_open.replace(tzinfo=_UTC).astimezone(_NY).date()
    return ci.ny_anchored_open_utc(day, 5)


def _bucket(m15_candles, m15_timestamps, open_ts):
    import bisect
    start = bisect.bisect_left(m15_timestamps, open_ts)
    end = bisect.bisect_left(m15_timestamps, open_ts + H4)
    return m15_candles[start:end]


def render_one(label: str, stable_id: str, cur_open: datetime, m15_candles, m15_timestamps, out_dir: Path):
    ref_open = _ref_open(cur_open)
    reference = _bucket(m15_candles, m15_timestamps, ref_open)
    current = _bucket(m15_candles, m15_timestamps, cur_open)
    all_candles = list(reference) + list(current)

    fig, ax = plt.subplots(figsize=(11, 5))
    x = list(range(len(all_candles)))
    for i, c in enumerate(all_candles):
        color = "#2a9d4a" if c.close >= c.open else "#c23b2e"
        ax.vlines(i, c.low, c.high, color=color, linewidth=1)
        ax.add_patch(plt.Rectangle(
            (i - 0.3, min(c.open, c.close)), 0.6, max(abs(c.close - c.open), 1e-6),
            color=color,
        ))

    ref_high = max(c.high for c in reference)
    ref_low = min(c.low for c in reference)
    ax.axhspan(ref_low, ref_high, xmin=0, xmax=1, color="#888888", alpha=0.15)
    ax.axhline(ref_high, color="#555555", linestyle="--", linewidth=0.8)
    ax.axhline(ref_low, color="#555555", linestyle="--", linewidth=0.8)

    boundary_idx = len(reference) - 0.5
    ax.axvline(boundary_idx, color="#1a1a1a", linestyle=":", linewidth=1)
    ax.text(boundary_idx, ax.get_ylim()[1], "09:00 NY\n(observable progressively\nfrom here)",
            ha="center", va="bottom", fontsize=8)

    final_close = all_candles[-1].close
    ax.axhline(final_close, color="#1a1a1a", linestyle="-", linewidth=1, alpha=0.6)
    ax.text(len(all_candles) - 1, final_close, f"  13:00 NY close\n  (observable only at close)\n  = {final_close:.5f}",
            va="center", fontsize=8)

    ax.set_title(f"{label} — {stable_id}\nReference 05:00-09:00 NY (shaded) | Current 09:00-13:00 NY", fontsize=10)
    ax.set_xlim(-1, len(all_candles))
    ax.set_xticks([])
    fig.tight_layout()
    out_path = out_dir / f"example_{label.lower()}.png"
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    return out_path


def main():
    _h4, m15, _daily = _load_symbol_data("EURUSD")
    m15_timestamps = [c.timestamp for c in m15.candles]
    out_dir = LAB_ROOT / "figures"
    out_dir.mkdir(exist_ok=True)
    for label, (stable_id, cur_open) in EXAMPLES.items():
        path = render_one(label, stable_id, cur_open, m15.candles, m15_timestamps, out_dir)
        print(f"{label}: {path}")


if __name__ == "__main__":
    main()
