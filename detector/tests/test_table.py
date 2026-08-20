"""REQ-24: detections.csv companion table — one row per detection object,
columns timestamp,type,direction,price_high,price_low,status,aligned.
"""

import csv

from fixtures.synthetic import CandleSeriesBuilder

from alignment.htf_ltf import AlignedSignal
from composite.mss import MSSEvent
from core.results import DetectionStatus
from entries.model1 import Model1Signal
from primitives.crt_range import CRTRange
from primitives.fvg import FVG
from primitives.swing import SwingPoint
from viz.table import write_detections_csv

_HEADER = ["timestamp", "type", "direction", "price_high", "price_low", "status", "aligned"]


def _series():
    return (
        CandleSeriesBuilder()
        .candle(open=1.0, high=1.0005, low=0.9995, close=1.0)
        .candle(open=1.0, high=1.0020, low=0.9995, close=1.0)
        .candle(open=1.0, high=1.0010, low=0.9995, close=1.0)
        .build()
    )


def _read(path):
    with open(path, newline="") as f:
        return list(csv.reader(f))


def test_zero_detections_emits_header_only_csv(tmp_path):
    output_path = tmp_path / "detections.csv"

    write_detections_csv(_series(), str(output_path))

    assert _read(output_path) == [_HEADER]


def test_one_row_per_swing(tmp_path):
    swings = [SwingPoint(index=1, price=1.0020, kind="high")]
    output_path = tmp_path / "detections.csv"

    write_detections_csv(_series(), str(output_path), swings=swings)

    rows = _read(output_path)
    assert rows[0] == _HEADER
    assert len(rows) == 2
    assert rows[1][1] == "swing"
    assert rows[1][2] == "high"
    assert rows[1][3] == "1.002"
    assert rows[1][4] == "1.002"


def test_one_row_per_fvg_with_direction_and_status(tmp_path):
    fvgs = [
        FVG(start_index=0, end_index=2, top=1.0020, bottom=1.0010, direction="bullish", fill_status="open")
    ]
    output_path = tmp_path / "detections.csv"

    write_detections_csv(_series(), str(output_path), fvgs=fvgs)

    rows = _read(output_path)
    assert rows[1][1] == "fvg"
    assert rows[1][2] == "bullish"
    assert rows[1][3] == "1.002"
    assert rows[1][4] == "1.001"
    assert rows[1][5] == "open"


def test_one_row_per_crt_range(tmp_path):
    crt_ranges = [
        CRTRange(
            model="3-candle", high=1.0020, low=0.9995, start_index=0,
            end_index=2, resolution="true_break", resolved_at_index=2,
        )
    ]
    output_path = tmp_path / "detections.csv"

    write_detections_csv(_series(), str(output_path), crt_ranges=crt_ranges)

    rows = _read(output_path)
    assert rows[1][1] == "crt_range"
    assert rows[1][3] == "1.002"
    assert rows[1][4] == "0.9995"
    assert rows[1][5] == "true_break"


def test_one_row_per_mss_event(tmp_path):
    mss_events = [
        MSSEvent(index=1, direction="bullish", broken_swing=SwingPoint(index=0, price=1.0005, kind="high"))
    ]
    output_path = tmp_path / "detections.csv"

    write_detections_csv(_series(), str(output_path), mss_events=mss_events)

    rows = _read(output_path)
    assert rows[1][1] == "mss"
    assert rows[1][2] == "bullish"
    assert rows[1][3] == "1.0005"


def test_one_row_per_model1_signal_single_series_leaves_aligned_blank(tmp_path):
    model1_signals = [
        Model1Signal(
            anchor_index=1, direction="bullish", purge_target=0.9990,
            confirmation_type="purge_engulf", entry_type="wick", entry_price=0.9995,
            retest_index=2, status=DetectionStatus.CONFIRMED,
        )
    ]
    output_path = tmp_path / "detections.csv"

    write_detections_csv(_series(), str(output_path), model1_signals=model1_signals)

    rows = _read(output_path)
    assert rows[1][1] == "model1"
    assert rows[1][2] == "bullish"
    assert rows[1][5] == "confirmed"
    assert rows[1][6] == ""


def test_aligned_signals_populate_aligned_column_and_replace_plain_model1(tmp_path):
    aligned_signals = [
        AlignedSignal(
            ltf_signal=Model1Signal(
                anchor_index=1, direction="bullish", purge_target=0.9990,
                confirmation_type="purge_engulf", entry_type="wick", entry_price=0.9995,
                retest_index=2, status=DetectionStatus.PENDING,
            ),
            htf_context=None,
            aligned="aligned",
        )
    ]
    output_path = tmp_path / "detections.csv"

    write_detections_csv(_series(), str(output_path), aligned_signals=aligned_signals)

    rows = _read(output_path)
    assert len(rows) == 2
    assert rows[1][1] == "model1"
    assert rows[1][5] == "pending"
    assert rows[1][6] == "aligned"


def test_rows_are_sorted_by_timestamp(tmp_path):
    swings = [
        SwingPoint(index=2, price=1.0010, kind="high"),
        SwingPoint(index=1, price=1.0020, kind="low"),
    ]
    output_path = tmp_path / "detections.csv"

    write_detections_csv(_series(), str(output_path), swings=swings)

    rows = _read(output_path)
    assert rows[1][0] < rows[2][0]
