import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle

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
_CRT_RANGE_LABEL_OFFSET = 0.0008
_MSS_COLOR = "darkorange"
_MODEL1_COLOR = "navy"
_MODEL1_ENTRY_LINE_MIN_WIDTH = 1


def render_chart(
    series: OHLCSeries,
    swings: list[SwingPoint],
    output_path: str,
    fvgs: list[FVG] | None = None,
    crt_ranges: list[CRTRange] | None = None,
    mss_events: list[MSSEvent] | None = None,
    model1_signals: list[Model1Signal] | None = None,
) -> Figure:
    fvgs = fvgs or []
    crt_ranges = crt_ranges or []
    mss_events = mss_events or []
    model1_signals = model1_signals or []
    fig, ax = plt.subplots()

    _plot_candles(ax, series)
    _plot_swings(ax, series, swings)
    _plot_fvgs(ax, fvgs)
    _plot_crt_ranges(ax, crt_ranges)
    _plot_mss_events(ax, mss_events)
    _plot_model1_signals(ax, model1_signals)

    ax.set_title(series.instrument)
    _add_legend(ax, swings, fvgs, crt_ranges, mss_events, model1_signals)
    fig.savefig(output_path, dpi=_DPI)
    return fig


def _plot_mss_events(ax, mss_events: list[MSSEvent]) -> None:
    for event in mss_events:
        ax.axvline(event.index, color=_MSS_COLOR, linestyle="--", linewidth=1)


def _plot_model1_signals(ax, model1_signals: list[Model1Signal]) -> None:
    for signal in model1_signals:
        marker = "^" if signal.direction == "bullish" else "v"
        ax.scatter([signal.anchor_index], [signal.entry_price], marker=marker, color=_MODEL1_COLOR)
        line_end = (
            signal.retest_index
            if signal.retest_index is not None
            else signal.anchor_index + _MODEL1_ENTRY_LINE_MIN_WIDTH
        )
        ax.plot(
            [signal.anchor_index, line_end],
            [signal.entry_price, signal.entry_price],
            color=_MODEL1_COLOR,
            linestyle="-",
            linewidth=1,
        )


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
            Line2D([0], [0], color=_MSS_COLOR, linestyle="--", label="MSS")
        )
    if model1_signals:
        handles.append(
            Line2D(
                [0], [0], marker="^", color=_MODEL1_COLOR, linestyle="-", label="Model-1"
            )
        )
    ax.legend(handles=handles, loc="upper left")


def _plot_crt_ranges(ax, crt_ranges: list[CRTRange]) -> None:
    for crt_range in crt_ranges:
        for level in (crt_range.high, crt_range.low):
            ax.plot(
                [crt_range.start_index, crt_range.end_index],
                [level, level],
                color=_CRT_RANGE_COLOR,
                linestyle="--",
                linewidth=1,
            )
        ax.text(
            crt_range.start_index,
            crt_range.high + _CRT_RANGE_LABEL_OFFSET,
            f"{crt_range.model} ({crt_range.resolution})",
            color=_CRT_RANGE_COLOR,
            fontsize=6,
        )


def _plot_fvgs(ax, fvgs: list[FVG]) -> None:
    for fvg in fvgs:
        color = _FVG_BULLISH_COLOR if fvg.direction == "bullish" else _FVG_BEARISH_COLOR
        ax.add_patch(
            Rectangle(
                (fvg.start_index - _FVG_WIDTH_PAD, fvg.bottom),
                width=(fvg.end_index - fvg.start_index) + 2 * _FVG_WIDTH_PAD,
                height=fvg.top - fvg.bottom,
                facecolor=color,
                alpha=_FVG_ALPHA,
                edgecolor=color,
            )
        )


def _plot_candles(ax, series: OHLCSeries) -> None:
    for i, candle in enumerate(series.candles):
        ax.plot([i, i], [candle.low, candle.high], color=_WICK_COLOR, linewidth=1)
        body_color = _UP_BODY_COLOR if candle.close >= candle.open else _DOWN_BODY_COLOR
        ax.plot(
            [i, i],
            [candle.open, candle.close],
            color=body_color,
            linewidth=4,
            solid_capstyle="butt",
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
