import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection, PatchCollection
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle

from alignment.htf_ltf import AlignedSignal
from composite.mss import MSSEvent
from core.candle import OHLCSeries
from entries.model1 import Model1Signal
from primitives.crt_range import CRTRange
from primitives.fvg import FVG
from primitives.swing import SwingPoint

_DPI = 150
_WICK_COLOR = "black"
_UP_BODY_COLOR = "seagreen"
_DOWN_BODY_COLOR = "firebrick"
_SWING_MARKER_OFFSET = 0.0005
_FVG_BULLISH_COLOR = "seagreen"
_FVG_BEARISH_COLOR = "firebrick"
_FVG_ALPHA = 0.2
_FVG_WIDTH_PAD = 0.5
_CRT_RANGE_COLOR = "purple"
_MSS_COLOR = "darkorange"
_MODEL1_COLOR = "navy"
_MODEL1_ENTRY_LINE_MIN_WIDTH = 1
_HTF_LTF_FIGSIZE = (10, 8)
_ALIGNMENT_BORDER_STYLE = {
    "aligned": ("green", "-"),
    "unaligned": ("gray", "-"),
    "insufficient_htf_data": ("gray", "--"),
}


def render_chart(
    series: OHLCSeries,
    swings: list[SwingPoint],
    output_path: str,
    fvgs: list[FVG] | None = None,
    crt_ranges: list[CRTRange] | None = None,
    mss_events: list[MSSEvent] | None = None,
    model1_signals: list[Model1Signal] | None = None,
    aligned_signals: list[AlignedSignal] | None = None,
    htf_series: OHLCSeries | None = None,
    htf_crt_ranges: list[CRTRange] | None = None,
    ltf_index_range: tuple[int, int] | None = None,
    htf_index_range: tuple[int, int] | None = None,
) -> Figure:
    """`ltf_index_range`/`htf_index_range` are DISPLAY-ONLY (Bug 3): they
    narrow which candles get drawn (e.g. from --from-date/--to-date), but
    every marker index still refers to the full, unfiltered series — so
    markers keep their correct x-position whether or not a window is set.
    """
    fvgs = fvgs or []
    crt_ranges = crt_ranges or []
    mss_events = mss_events or []
    model1_signals = model1_signals or []
    htf_crt_ranges = htf_crt_ranges or []

    if htf_series is not None:
        fig, (ax_htf, ax_ltf) = plt.subplots(2, 1, figsize=_HTF_LTF_FIGSIZE)
        ax_htf.set_autoscale_on(False)
        _plot_candles(ax_htf, htf_series, index_range=htf_index_range)
        _plot_crt_ranges(ax_htf, htf_crt_ranges)
        ax_htf.set_autoscale_on(True)
        ax_htf.autoscale_view()
        ax_htf.set_title(f"{htf_series.instrument} ({htf_series.timeframe}) — HTF")
        ax_ltf.set_title(f"{series.instrument} ({series.timeframe}) — LTF")
    else:
        fig, ax_ltf = plt.subplots()
        ax_ltf.set_title(series.instrument)

    # Perf: matplotlib recomputes the full axis autoscale on every single
    # scatter()/plot()/add_patch() call by default — an O(artists) cost per
    # call that dominates real-data runtime once thousands of markers are
    # drawn. Autoscale is disabled for the per-artist loop below and
    # computed once at the end instead (each add_* call still updates
    # ax.dataLim incrementally regardless of autoscale state, so the final
    # view is identical — only the redundant intermediate recomputes are
    # removed).
    ax_ltf.set_autoscale_on(False)
    _plot_candles(ax_ltf, series, index_range=ltf_index_range)
    _plot_swings(ax_ltf, series, swings)
    _plot_fvgs(ax_ltf, fvgs)
    _plot_crt_ranges(ax_ltf, crt_ranges)
    _plot_mss_events(ax_ltf, mss_events)
    if aligned_signals is not None:
        _plot_aligned_signals(ax_ltf, aligned_signals)
    else:
        _plot_model1_signals(ax_ltf, model1_signals)
    ax_ltf.set_autoscale_on(True)
    ax_ltf.autoscale_view()

    _add_legend(ax_ltf, swings, fvgs, crt_ranges, mss_events, model1_signals or aligned_signals)
    fig.tight_layout()
    fig.savefig(output_path, dpi=_DPI)
    return fig


def _scatter_grouped(ax, items, position_fn, groups, **scatter_kwargs) -> None:
    """Filters `items` into each `groups` predicate in turn and issues one
    batched `scatter()` call per non-empty group, instead of one per item —
    `groups` is a list of `(predicate, extra_kwargs)` pairs so a caller can
    group by a single dimension (e.g. direction -> marker) or stack a
    second dimension (e.g. direction + alignment state -> marker + edge
    style) without a different code shape for each case.
    """
    for predicate, kwargs in groups:
        group = [item for item in items if predicate(item)]
        if not group:
            continue
        xs, ys = zip(*(position_fn(item) for item in group))
        ax.scatter(xs, ys, **scatter_kwargs, **kwargs)


def _plot_mss_events(ax, mss_events: list[MSSEvent]) -> None:
    """A small triangle at the broken swing's price level, matching the
    visual weight of the existing Swing markers — replaces a full-height
    dashed vline per event, which at real-data density (thousands of MSS
    events over a few thousand candles) rendered as solid horizontal
    striping that obscured the candlesticks entirely (Bug 2).

    Perf: one `scatter()` call per direction (2 total) instead of one per
    event — at real-data density this was thousands of individual artist
    creations, the single biggest contributor (with `_plot_model1_signals`
    and `_plot_candles`) to real-scale render time (see apply-progress).
    """
    _scatter_grouped(
        ax, mss_events,
        position_fn=lambda e: (e.index, e.broken_swing.price),
        groups=[
            (lambda e, d=direction: e.direction == d, {"marker": marker})
            for marker, direction in (("^", "bullish"), ("v", "bearish"))
        ],
        color=_MSS_COLOR,
    )


def _model1_entry_line_segments(signals: list[Model1Signal]) -> list:
    return [
        [
            (signal.anchor_index, signal.entry_price),
            (
                signal.retest_index
                if signal.retest_index is not None
                else signal.anchor_index + _MODEL1_ENTRY_LINE_MIN_WIDTH,
                signal.entry_price,
            ),
        ]
        for signal in signals
    ]


def _add_entry_lines(ax, signals: list[Model1Signal]) -> None:
    ax.add_collection(
        LineCollection(
            _model1_entry_line_segments(signals),
            colors=_MODEL1_COLOR,
            linewidths=1,
            linestyles="-",
        )
    )


def _plot_model1_signals(ax, model1_signals: list[Model1Signal]) -> None:
    """Perf: markers batched into 2 `scatter()` calls (one per direction)
    and entry lines batched into a single `LineCollection`, instead of one
    `scatter()` + `plot()` pair per signal.
    """
    if not model1_signals:
        return
    _scatter_grouped(
        ax, model1_signals,
        position_fn=lambda s: (s.anchor_index, s.entry_price),
        groups=[
            (lambda s, d=direction: s.direction == d, {"marker": marker})
            for marker, direction in (("^", "bullish"), ("v", "bearish"))
        ],
        color=_MODEL1_COLOR,
    )

    _add_entry_lines(ax, model1_signals)


def _plot_aligned_signals(ax, aligned_signals: list[AlignedSignal]) -> None:
    """Same batching as `_plot_model1_signals`, grouped additionally by
    `aligned` state (marker edge color/linestyle) — at most 6 `scatter()`
    calls (2 directions x 3 states) instead of one per signal.
    """
    if not aligned_signals:
        return
    _scatter_grouped(
        ax, aligned_signals,
        position_fn=lambda t: (t.ltf_signal.anchor_index, t.ltf_signal.entry_price),
        groups=[
            (
                lambda t, d=direction, s=state: t.ltf_signal.direction == d and t.aligned == s,
                {"marker": marker, "edgecolors": border_color, "linewidths": 1.5, "linestyle": border_linestyle},
            )
            for marker, direction in (("^", "bullish"), ("v", "bearish"))
            for state, (border_color, border_linestyle) in _ALIGNMENT_BORDER_STYLE.items()
        ],
        color=_MODEL1_COLOR,
    )

    _add_entry_lines(ax, [tagged.ltf_signal for tagged in aligned_signals])


def _add_legend(
    ax,
    swings: list[SwingPoint],
    fvgs: list[FVG],
    crt_ranges: list[CRTRange],
    mss_events: list[MSSEvent],
    model1_signals: list[Model1Signal],
) -> None:
    handles = [
        Line2D([0], [0], color=_UP_BODY_COLOR, linewidth=4, label="Bullish"),
        Line2D([0], [0], color=_DOWN_BODY_COLOR, linewidth=4, label="Bearish"),
    ]
    if any(s.kind == "high" for s in swings):
        handles.append(
            Line2D([0], [0], marker="v", color="blue", linestyle="", label="Swing High")
        )
    if any(s.kind == "low" for s in swings):
        handles.append(
            Line2D([0], [0], marker="^", color="orange", linestyle="", label="Swing Low")
        )
    if fvgs:
        handles.append(
            Patch(facecolor="gray", alpha=_FVG_ALPHA, label="Fair Value Gap")
        )
    if crt_ranges:
        handles.append(
            Line2D(
                [0], [0], color=_CRT_RANGE_COLOR, linestyle="--", label="CRT Range"
            )
        )
    if mss_events:
        handles.append(
            Line2D([0], [0], marker="^", color=_MSS_COLOR, linestyle="", label="MSS")
        )
    if model1_signals:
        handles.append(
            Line2D(
                [0], [0], marker="^", color=_MODEL1_COLOR, linestyle="-", label="Model-1"
            )
        )
    ax.legend(handles=handles, loc="upper left")


def _plot_crt_ranges(ax, crt_ranges: list[CRTRange]) -> None:
    """Bracket lines only — no per-instance text label (Bug 2). At
    real-data density (thousands of overlapping detections) the labels
    stacked into unreadable text blobs; the bracket lines already convey
    the detection visually and stay legend-identifiable as "CRT Range".

    Perf: all bracket lines (2 per range: High + Low) batched into a
    single `LineCollection` instead of one `plot()` call per level — at
    real-data density this was tens of thousands of individual artist
    creations (see apply-progress).
    """
    if not crt_ranges:
        return
    segments = [
        [(crt_range.start_index, level), (crt_range.end_index, level)]
        for crt_range in crt_ranges
        for level in (crt_range.high, crt_range.low)
    ]
    ax.add_collection(
        LineCollection(segments, colors=_CRT_RANGE_COLOR, linestyles="--", linewidths=1)
    )


def _plot_fvgs(ax, fvgs: list[FVG]) -> None:
    """Perf: all FVG rectangles batched into a single `PatchCollection`
    (`match_original=True` preserves each Rectangle's own facecolor/
    edgecolor/alpha) instead of one `add_patch()` call per FVG.
    """
    if not fvgs:
        return
    patches = [
        Rectangle(
            (fvg.start_index - _FVG_WIDTH_PAD, fvg.bottom),
            width=(fvg.end_index - fvg.start_index) + 2 * _FVG_WIDTH_PAD,
            height=fvg.top - fvg.bottom,
            facecolor=_FVG_BULLISH_COLOR if fvg.direction == "bullish" else _FVG_BEARISH_COLOR,
            alpha=_FVG_ALPHA,
            edgecolor=_FVG_BULLISH_COLOR if fvg.direction == "bullish" else _FVG_BEARISH_COLOR,
        )
        for fvg in fvgs
    ]
    ax.add_collection(PatchCollection(patches, match_original=True))


def _plot_candles(ax, series: OHLCSeries, index_range: tuple[int, int] | None = None) -> None:
    """Perf (the dominant real-scale rendering cost — see apply-progress):
    wicks and bodies each batched into a single `LineCollection` built from
    numpy arrays of the OHLC values, instead of 2 individual `plot()` calls
    per candle (46,962 individual `plot()` calls measured on a real
    10,000-candle run, ~10s of a ~64s render just for this function).
    """
    start, end = index_range if index_range is not None else (0, len(series.candles) - 1)
    if start > end:
        return
    candles = series.candles[start : end + 1]
    indices = np.arange(start, end + 1)
    opens = np.array([c.open for c in candles])
    highs = np.array([c.high for c in candles])
    lows = np.array([c.low for c in candles])
    closes = np.array([c.close for c in candles])

    wick_segments = np.stack(
        [np.column_stack([indices, lows]), np.column_stack([indices, highs])], axis=1
    )
    ax.add_collection(LineCollection(wick_segments, colors=_WICK_COLOR, linewidths=1))

    body_segments = np.stack(
        [np.column_stack([indices, opens]), np.column_stack([indices, closes])], axis=1
    )
    body_colors = list(np.where(closes >= opens, _UP_BODY_COLOR, _DOWN_BODY_COLOR))
    ax.add_collection(
        LineCollection(body_segments, colors=body_colors, linewidths=4, capstyle="butt")
    )


def _plot_swings(ax, series: OHLCSeries, swings: list[SwingPoint]) -> None:
    highs = [s for s in swings if s.kind == "high"]
    lows = [s for s in swings if s.kind == "low"]

    if highs:
        ax.scatter(
            [s.index for s in highs],
            [s.price + _SWING_MARKER_OFFSET for s in highs],
            marker="v",
            color="blue",
            label="Swing High",
        )
    if lows:
        ax.scatter(
            [s.index for s in lows],
            [s.price - _SWING_MARKER_OFFSET for s in lows],
            marker="^",
            color="orange",
            label="Swing Low",
        )
