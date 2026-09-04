import random
from datetime import datetime, timedelta

from fixtures.synthetic import CandleSeriesBuilder
from matplotlib.collections import LineCollection, PatchCollection, PathCollection

from alignment.htf_ltf import AlignedSignal
from composite.mss import MSSEvent, detect_mss_events
from core.candle import Candle, OHLCSeries
from core.config import DetectorConfig
from core.results import DetectionStatus
from entries.model1 import Model1Signal, detect_model1_signals
from primitives.crt_range import CRTRange, detect_crt_ranges
from primitives.fvg import FVG, detect_fvgs
from primitives.swing import SwingPoint, detect_swings
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


def _wick_segment_count(ax):
    """Isolates the candle-wick LineCollection from the mix of collections
    an axes can hold (MSS/model1 markers, CRT-range brackets, model1 entry
    lines) — wicks are the only collection drawn in _WICK_COLOR ("black")
    at linewidth 1 (Perf: wicks are now one batched LineCollection, not N
    individual Line2D objects — see apply-progress).
    """
    for collection in ax.collections:
        widths = collection.get_linewidths()
        colors = collection.get_edgecolors()
        if len(widths) and widths[0] == 1 and len(colors) and tuple(colors[0]) == (0.0, 0.0, 0.0, 1.0):
            return len(collection.get_segments())
    return 0


def test_no_index_range_plots_every_candle(tmp_path):
    """Bug 3 (a): with no index_range (the CLI's no-date-filter case),
    behavior is unchanged — every candle in the series is plotted.
    """
    series = _series()
    output_path = tmp_path / "overlay.png"

    fig = render_chart(series, [], str(output_path))

    assert _wick_segment_count(fig.axes[0]) == len(series.candles)


def test_ltf_index_range_plots_only_candles_within_window(tmp_path):
    """Bug 3 (b): a windowed ltf_index_range plots only the candles inside
    it, for chart legibility, without altering detection inputs elsewhere.
    """
    series = _series()  # 3 candles: indices 0, 1, 2
    output_path = tmp_path / "overlay.png"

    fig = render_chart(series, [], str(output_path), ltf_index_range=(1, 2))

    assert _wick_segment_count(fig.axes[0]) == 2


def test_htf_index_range_plots_only_candles_within_window(tmp_path):
    """Same windowing applied to the HTF panel in pair mode."""
    htf_series = (
        CandleSeriesBuilder()
        .candle(open=1.0, high=1.0030, low=0.9980, close=1.0010)
        .candle(open=1.0010, high=1.0040, low=0.9990, close=1.0020)
        .candle(open=1.0020, high=1.0050, low=1.0000, close=1.0030)
        .build()
    )
    output_path = tmp_path / "overlay.png"

    fig = render_chart(
        _series(), [], str(output_path), htf_series=htf_series, htf_index_range=(0, 1)
    )

    assert _wick_segment_count(fig.axes[0]) == 2


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
    # Only PathCollection (scatter markers) count as "marker points" — a
    # LineCollection/PatchCollection (candle wicks/bodies, FVG rectangles)
    # also reports a spurious default single offset via get_offsets().
    swing_marker_points = sum(
        len(c.get_offsets()) for c in ax.collections if isinstance(c, PathCollection)
    )
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
    # Perf: FVG rectangles are batched into a single PatchCollection rather
    # than added individually via ax.add_patch(), so they no longer appear
    # in ax.patches — count paths in the collection instead.
    fvg_collections = [c for c in ax.collections if isinstance(c, PatchCollection)]
    assert len(fvg_collections) == 1
    assert len(fvg_collections[0].get_paths()) == len(fvgs)


def test_render_chart_crt_ranges_draw_brackets_without_per_instance_labels(tmp_path):
    """Bug 2 (chart legibility): per-instance CRT-range text labels are
    dropped entirely — at real-data density (thousands of overlapping
    detections) they stacked into unreadable text blobs. The bracket lines
    (2 dashed lines per range, high+low) still convey the detection
    visually and stay in the legend, matching the "CRT Range" entry.
    """
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
    assert len(ax.texts) == 0
    crt_range_collections = [
        c for c in ax.collections
        if tuple(c.get_edgecolors()[0]) == (0.5019607843137255, 0.0, 0.5019607843137255, 1.0)
    ]
    assert len(crt_range_collections) == 1
    assert len(crt_range_collections[0].get_segments()) == 2 * len(crt_ranges)


def test_render_chart_adds_one_small_marker_per_mss_event(tmp_path):
    """Bug 2 (chart legibility): MSS switched from a full-height dashed
    vline (at real density — ~2,715 events over ~6,200 candles — this
    created solid horizontal striping obscuring candlesticks) to a small
    triangle marker at the broken swing's price level, matching the visual
    weight of the existing Swing triangle markers. No more full-height
    dashed vlines for MSS.
    """
    mss_events = [
        MSSEvent(
            index=1,
            direction="bullish",
            broken_swing=SwingPoint(index=0, price=1.0005, kind="high"),
        )
    ]
    output_path = tmp_path / "overlay.png"

    fig = render_chart(_series(), [], str(output_path), mss_events=mss_events)

    ax = fig.axes[0]
    # Perf: markers are batched into one scatter() call per direction, so a
    # single collection can hold multiple events — sum offsets across the
    # MSS-colored (darkorange) collections instead of counting one
    # collection per event.
    mss_marker_points = sum(
        len(c.get_offsets()) for c in ax.collections
        if len(c.get_facecolors()) and tuple(c.get_facecolors()[0]) == (1.0, 0.5490196078431373, 0.0, 1.0)
    )
    assert mss_marker_points == len(mss_events)
    dashed_vlines = [
        line
        for line in ax.get_lines()
        if line.get_linestyle() == "--" and len(set(line.get_xdata())) == 1
    ]
    assert dashed_vlines == []


def test_render_chart_adds_one_arrow_and_entry_line_per_model1_signal(tmp_path):
    model1_signals = [
        Model1Signal(
            anchor_index=1,
            direction="bullish",
            purge_target=0.9990,
            confirmation_type="purge_engulf",
            entry_type="wick",
            entry_price=0.9995,
            retest_index=2,
            status=DetectionStatus.CONFIRMED,
            confirmation_index=2,
            origin_index=0,
        )
    ]
    output_path = tmp_path / "overlay.png"

    fig = render_chart(_series(), [], str(output_path), model1_signals=model1_signals)

    ax = fig.axes[0]
    arrow_points = sum(
        len(c.get_offsets()) for c in ax.collections if isinstance(c, PathCollection)
    )
    assert arrow_points == len(model1_signals)
    # Perf: entry lines are now one batched LineCollection (navy, solid)
    # instead of one Line2D per signal.
    entry_line_collections = [
        c for c in ax.collections
        if hasattr(c, "get_segments")
        and len(c.get_edgecolors())
        and tuple(c.get_edgecolors()[0]) == (0.0, 0.0, 0.5019607843137255, 1.0)
    ]
    assert len(entry_line_collections) == 1
    assert len(entry_line_collections[0].get_segments()) == len(model1_signals)


def test_render_chart_colors_model1_marker_border_by_alignment_state(tmp_path):
    """REQ-23: alignment=border color (green/gray/dashed-gray per the 3
    ADR-05 states) — pair-mode markers are colored by `aligned`, one per
    AlignedSignal, instead of the plain single-color single-series style.
    """
    aligned_signals = [
        AlignedSignal(
            ltf_signal=Model1Signal(
                anchor_index=1,
                direction="bullish",
                purge_target=0.9990,
                confirmation_type="purge_engulf",
                entry_type="wick",
                entry_price=0.9995,
                retest_index=2,
                status=DetectionStatus.CONFIRMED,
                confirmation_index=2,
                origin_index=0,
            ),
            htf_context=None,
            aligned="aligned",
        )
    ]
    output_path = tmp_path / "overlay.png"

    fig = render_chart(_series(), [], str(output_path), aligned_signals=aligned_signals)

    ax = fig.axes[0]
    # Perf: markers are batched by (direction, aligned-state) group, but
    # with exactly 1 signal there's still exactly 1 scatter (PathCollection)
    # marker — filtered from the LineCollection entry line, which also
    # reports 1 default offset (isinstance, not offset-count, disambiguates
    # the two collection types).
    markers = [c for c in ax.collections if isinstance(c, PathCollection)]
    assert len(markers) == 1
    edge_colors = markers[0].get_edgecolors()
    assert len(edge_colors) == 1
    # green RGBA
    assert tuple(edge_colors[0]) == (0.0, 0.5019607843137255, 0.0, 1.0)


def test_render_chart_autoscales_axes_to_cover_all_plotted_data(tmp_path):
    """Perf fix (found via profiling, flagged as a deviation in
    apply-progress): matplotlib recomputes the full axis autoscale on
    every single scatter()/plot()/add_patch() call by default — an
    accidental O(artists) per call that dominated real-data runtime
    (~73% of one measured full-pipeline run). Autoscale is disabled during
    the per-artist plotting loop and computed once at the end instead; this
    pins that the final view still correctly bounds every plotted artist
    type (candle wicks, FVG rectangles, swing scatter points), exactly as
    the old per-call autoscaling would have produced.
    """
    series = (
        CandleSeriesBuilder()
        .candle(open=1.0, high=1.0005, low=0.9995, close=1.0)
        .candle(open=1.0, high=1.0020, low=0.9990, close=1.0)
        .candle(open=1.0, high=1.0010, low=0.9985, close=1.0)
        .build()
    )
    swings = [SwingPoint(index=1, price=1.0020, kind="high")]
    fvgs = [
        FVG(
            start_index=0, end_index=2, top=1.0020, bottom=1.0010,
            direction="bullish", fill_status="open",
        )
    ]
    output_path = tmp_path / "overlay.png"

    fig = render_chart(series, swings, str(output_path), fvgs=fvgs)

    ax = fig.axes[0]
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    assert xlim[0] <= 0 and xlim[1] >= 2
    assert ylim[0] <= 0.9985 and ylim[1] >= 1.0020


def _large_realistic_series(size: int = 600, seed: int = 3) -> OHLCSeries:
    """Same generator shape as test_performance.py's differential fixture —
    a realistic, overlap-heavy random-walk series large enough to exercise
    every rendering batch (candles/crt_ranges/fvgs/mss/model1) with real,
    varied, boundary-touching detections instead of a handful of hand-built
    ones.
    """
    rng = random.Random(seed)
    candles = []
    price = 1.1000
    for i in range(size):
        open_ = price
        close = open_ + rng.uniform(-0.0015, 0.0015)
        high = max(open_, close) + rng.uniform(0.0, 0.0008)
        low = min(open_, close) - rng.uniform(0.0, 0.0008)
        candles.append(
            Candle(
                timestamp=datetime(2026, 1, 1) + timedelta(minutes=5 * i),
                open=open_, high=high, low=low, close=close,
            )
        )
        price = close
    return OHLCSeries(candles=tuple(candles), instrument="EURUSD", timeframe="5M")


def test_batched_rendering_matches_per_item_geometry_on_a_large_realistic_series(tmp_path):
    """Perf fix differential test: candles/crt_ranges/fvgs/mss/model1 were
    each rewritten from one matplotlib call per item to a single batched
    LineCollection/PatchCollection/grouped-scatter (see apply-progress —
    real-scale render was the actual bottleneck, not detection). This pins
    the batched output against geometry computed independently, straight
    from the detection objects (an oracle, not chart.py's own internals),
    on a 600-candle fixture with real overlapping FVGs/CRT ranges/MSS/
    Model-1 signals — proving the batching didn't drop, duplicate, or
    misplace/miscolor a single mark.
    """
    series = _large_realistic_series()
    config = DetectorConfig()
    swings = detect_swings(series, config.swing)
    fvgs = detect_fvgs(series, config.fvg)
    crt_ranges = detect_crt_ranges(series, config.crt_range)
    mss_events = detect_mss_events(series, config.mss)
    model1_signals = detect_model1_signals(series, config.crt_range, config.fvg, config.model1)

    # Sanity: the fixture actually exercises every batched code path.
    assert len(fvgs) > 20 and len(crt_ranges) > 20 and len(mss_events) > 20 and len(model1_signals) > 5

    output_path = tmp_path / "overlay.png"
    fig = render_chart(
        series, swings, str(output_path),
        fvgs=fvgs, crt_ranges=crt_ranges, mss_events=mss_events, model1_signals=model1_signals,
    )
    ax = fig.axes[0]

    # --- candles: one wick + one body LineCollection, oracle built
    # directly from series.candles, independent of _plot_candles' own
    # numpy array construction ---
    wick_collection = next(
        c for c in ax.collections
        if isinstance(c, LineCollection) and c.get_linewidths()[0] == 1
        and tuple(c.get_edgecolors()[0]) == (0.0, 0.0, 0.0, 1.0)
    )
    wick_segments = wick_collection.get_segments()
    assert len(wick_segments) == len(series.candles)
    for i, candle in enumerate(series.candles):
        expected = {(float(i), candle.low), (float(i), candle.high)}
        actual = {tuple(point) for point in wick_segments[i]}
        assert actual == expected

    body_collection = next(
        c for c in ax.collections
        if isinstance(c, LineCollection) and c.get_linewidths()[0] == 4
    )
    body_segments = body_collection.get_segments()
    assert len(body_segments) == len(series.candles)
    for i, candle in enumerate(series.candles):
        expected = {(float(i), candle.open), (float(i), candle.close)}
        actual = {tuple(point) for point in body_segments[i]}
        assert actual == expected

    # --- CRT ranges: 2 segments per range (High + Low bracket) ---
    crt_collection = next(
        c for c in ax.collections
        if isinstance(c, LineCollection)
        and tuple(c.get_edgecolors()[0]) == (0.5019607843137255, 0.0, 0.5019607843137255, 1.0)
    )
    expected_crt_segments = set()
    for r in crt_ranges:
        expected_crt_segments.add(((float(r.start_index), r.high), (float(r.end_index), r.high)))
        expected_crt_segments.add(((float(r.start_index), r.low), (float(r.end_index), r.low)))
    actual_crt_segments = {tuple(tuple(p) for p in seg) for seg in crt_collection.get_segments()}
    assert len(crt_collection.get_segments()) == 2 * len(crt_ranges)
    assert actual_crt_segments == expected_crt_segments

    # --- FVGs: one rectangle path per FVG, in a single PatchCollection ---
    fvg_collection = next(c for c in ax.collections if isinstance(c, PatchCollection))
    assert len(fvg_collection.get_paths()) == len(fvgs)

    # --- MSS: total marker points split correctly by direction ---
    mss_paths = [c for c in ax.collections if isinstance(c, PathCollection) and c.get_paths()]
    darkorange = (1.0, 0.5490196078431373, 0.0, 1.0)
    mss_total = sum(
        len(c.get_offsets()) for c in mss_paths
        if tuple(c.get_facecolors()[0]) == darkorange
    )
    assert mss_total == len(mss_events)

    # --- Model-1: total marker points + entry-line segment coordinates ---
    navy = (0.0, 0.0, 0.5019607843137255, 1.0)
    model1_marker_total = sum(
        len(c.get_offsets()) for c in mss_paths
        if tuple(c.get_facecolors()[0]) == navy
    )
    assert model1_marker_total == len(model1_signals)

    entry_line_collection = next(
        c for c in ax.collections
        if isinstance(c, LineCollection) and c.get_linewidths()[0] == 1
        and tuple(c.get_edgecolors()[0]) == navy
    )
    entry_segments = entry_line_collection.get_segments()
    assert len(entry_segments) == len(model1_signals)
    for signal, segment in zip(model1_signals, entry_segments):
        line_end = (
            signal.retest_index if signal.retest_index is not None else signal.anchor_index + 1
        )
        expected = {(float(signal.anchor_index), signal.entry_price), (float(line_end), signal.entry_price)}
        actual = {tuple(point) for point in segment}
        assert actual == expected


def test_render_chart_pair_mode_produces_two_stacked_panels(tmp_path):
    """Design 4.6: 2-panel stacked HTF-top/LTF-bottom in pair mode."""
    htf_series = (
        CandleSeriesBuilder()
        .candle(open=1.0, high=1.0030, low=0.9980, close=1.0010)
        .candle(open=1.0010, high=1.0040, low=0.9990, close=1.0020)
        .build()
    )
    output_path = tmp_path / "overlay.png"

    fig = render_chart(_series(), [], str(output_path), htf_series=htf_series)

    assert len(fig.axes) == 2
