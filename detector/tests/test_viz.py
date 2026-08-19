from fixtures.synthetic import CandleSeriesBuilder

from primitives.crt_range import CRTRange
from primitives.fvg import FVG
from primitives.swing import SwingPoint
from viz.chart import render_chart


def _series():
    return (
        CandleSeriesBuilder()
        .candle(open=1.0, high=1.0005, low=0.9995, close=1.0)
        .candle(open=1.0, high=1.0020, low=0.9995, close=1.0)
        .candle(open=1.0, high=1.0010, low=0.9995, close=1.0)
        .build()
    )


def test_render_chart_writes_a_nonempty_png_file(tmp_path):
    output_path = tmp_path / "overlay.png"

    render_chart(_series(), [], str(output_path))

    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_render_chart_always_shows_a_legend(tmp_path):
    output_path = tmp_path / "overlay.png"

    fig = render_chart(_series(), [], str(output_path))

    legend = fig.axes[0].get_legend()
    assert legend is not None
    assert len(legend.get_texts()) > 0


def test_render_chart_adds_one_marker_per_swing(tmp_path):
    swings = [SwingPoint(index=1, price=1.0020, kind="high")]
    output_path = tmp_path / "overlay.png"

    fig = render_chart(_series(), swings, str(output_path))

    ax = fig.axes[0]
    swing_marker_points = sum(len(c.get_offsets()) for c in ax.collections)
    assert swing_marker_points == len(swings)


def test_render_chart_adds_one_rectangle_per_fvg(tmp_path):
    fvgs = [
        FVG(
            start_index=0,
            end_index=2,
            top=1.0020,
            bottom=1.0010,
            direction="bullish",
            fill_status="open",
        )
    ]
    output_path = tmp_path / "overlay.png"

    fig = render_chart(_series(), [], str(output_path), fvgs=fvgs)

    ax = fig.axes[0]
    assert len(ax.patches) == len(fvgs)


def test_render_chart_adds_one_label_per_crt_range(tmp_path):
    crt_ranges = [
        CRTRange(
            model="3-candle",
            high=1.0020,
            low=0.9995,
            start_index=0,
            end_index=2,
            resolution="true_break",
            resolved_at_index=2,
        )
    ]
    output_path = tmp_path / "overlay.png"

    fig = render_chart(_series(), [], str(output_path), crt_ranges=crt_ranges)

    ax = fig.axes[0]
    assert len(ax.texts) == len(crt_ranges)
