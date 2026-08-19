import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from core.candle import OHLCSeries
from primitives.swing import SwingPoint

_DPI = 150
_WICK_COLOR = "black"
_UP_BODY_COLOR = "seagreen"
_DOWN_BODY_COLOR = "firebrick"
_SWING_MARKER_OFFSET = 0.0005


def render_chart(
    series: OHLCSeries, swings: list[SwingPoint], output_path: str
) -> Figure:
    fig, ax = plt.subplots()

    _plot_candles(ax, series)
    _plot_swings(ax, series, swings)

    ax.set_title(series.instrument)
    _add_legend(ax, swings)
    fig.savefig(output_path, dpi=_DPI)
    return fig


def _add_legend(ax, swings: list[SwingPoint]) -> None:
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
    ax.legend(handles=handles, loc="upper left")


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
