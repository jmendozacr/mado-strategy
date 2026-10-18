"""REQ-24: detections.csv companion table — one row per detection object,
columns timestamp,type,direction,price_high,price_low,status,aligned.
"""

import csv

from fixtures.synthetic import CandleSeriesBuilder

from alignment.htf_ltf import AlignedSignal
from composite.mss import MSSEvent
from core.key_level import KeyLevel
from core.results import DetectionStatus
from entries.model1 import Model1Signal
from primitives.crt_range import CRTRange
from primitives.fvg import FVG
from primitives.swing import SwingPoint
from viz.table import write_detections_csv

_HEADER = [
    "timestamp", "type", "direction", "price_high", "price_low", "status", "aligned",
    "key_level_source", "key_level_reaction",
]


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
            confirmation_index=2, origin_index=0,
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
                confirmation_index=2, origin_index=0,
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


def test_ict_order_block_credited_signal_writes_kind_in_key_level_source(tmp_path):
    """REQ-24.2: an aligned Model-1 signal credited to an ICTOrderBlock-
    sourced Key Level writes "ict_order_block" in key_level_source."""
    aligned_signals = [
        AlignedSignal(
            ltf_signal=Model1Signal(
                anchor_index=1, direction="bullish", purge_target=0.9990,
                confirmation_type="purge_engulf", entry_type="wick", entry_price=0.9995,
                retest_index=2, status=DetectionStatus.PENDING,
                confirmation_index=2, origin_index=0,
            ),
            htf_context=None,
            aligned="aligned",
            key_level=KeyLevel(kind="ict_order_block", top=1.01, bottom=1.00, origin_index=0),
        )
    ]
    output_path = tmp_path / "detections.csv"

    write_detections_csv(_series(), str(output_path), aligned_signals=aligned_signals)

    rows = _read(output_path)
    assert rows[1][7] == "ict_order_block"


def test_credited_signal_with_reject_close_inside_reaction_writes_it(tmp_path):
    """A credited signal whose purge candle closed back inside the CRT
    range (charter-1 [00:12:59]/charter-6 [00:03:25]) writes
    "reject_close_inside" in the new key_level_reaction column — reportable
    alongside key_level_source, not replacing it."""
    aligned_signals = [
        AlignedSignal(
            ltf_signal=Model1Signal(
                anchor_index=1, direction="bullish", purge_target=0.9990,
                confirmation_type="purge_engulf", entry_type="wick", entry_price=0.9995,
                retest_index=2, status=DetectionStatus.PENDING,
                confirmation_index=2, origin_index=0,
            ),
            htf_context=None,
            aligned="aligned",
            key_level=KeyLevel(kind="ict_order_block", top=1.01, bottom=1.00, origin_index=0),
            key_level_reaction="reject_close_inside",
        )
    ]
    output_path = tmp_path / "detections.csv"

    write_detections_csv(_series(), str(output_path), aligned_signals=aligned_signals)

    rows = _read(output_path)
    assert rows[1][7] == "ict_order_block"
    assert rows[1][8] == "reject_close_inside"


def test_credited_signal_with_continuation_reaction_writes_it(tmp_path):
    """charter-1 [00:13:45-00:14:40]/charter-2 [00:22:03]'s V-shaped
    reaction (touch, then expand straight through in the same candle)
    writes "continuation" instead."""
    aligned_signals = [
        AlignedSignal(
            ltf_signal=Model1Signal(
                anchor_index=1, direction="bullish", purge_target=0.9990,
                confirmation_type="purge_engulf", entry_type="wick", entry_price=0.9995,
                retest_index=2, status=DetectionStatus.PENDING,
                confirmation_index=2, origin_index=0,
            ),
            htf_context=None,
            aligned="aligned",
            key_level=KeyLevel(kind="fvg", top=1.01, bottom=1.00, origin_index=0),
            key_level_reaction="continuation",
        )
    ]
    output_path = tmp_path / "detections.csv"

    write_detections_csv(_series(), str(output_path), aligned_signals=aligned_signals)

    rows = _read(output_path)
    assert rows[1][8] == "continuation"


def test_non_model1_rows_leave_key_level_source_empty(tmp_path):
    """REQ-24.3: non-Model-1 rows (swing/fvg/crt_range/mss) always leave
    key_level_source and key_level_reaction empty — the concept doesn't
    apply to them."""
    swings = [SwingPoint(index=1, price=1.0020, kind="high")]
    output_path = tmp_path / "detections.csv"

    write_detections_csv(_series(), str(output_path), swings=swings)

    rows = _read(output_path)
    assert rows[1][1] == "swing"
    assert rows[1][7] == ""
    assert rows[1][8] == ""


def test_aligned_signal_with_no_key_level_leaves_key_level_source_empty(tmp_path):
    """REQ-24.3 (edge): an aligned Model-1 signal credited to no Key Level
    at all also leaves key_level_source and key_level_reaction empty."""
    aligned_signals = [
        AlignedSignal(
            ltf_signal=Model1Signal(
                anchor_index=1, direction="bullish", purge_target=0.9990,
                confirmation_type="purge_engulf", entry_type="wick", entry_price=0.9995,
                retest_index=2, status=DetectionStatus.PENDING,
                confirmation_index=2, origin_index=0,
            ),
            htf_context=None,
            aligned="aligned",
        )
    ]
    output_path = tmp_path / "detections.csv"

    write_detections_csv(_series(), str(output_path), aligned_signals=aligned_signals)

    rows = _read(output_path)
    assert rows[1][7] == ""
    assert rows[1][8] == ""


def test_include_signal_id_appends_trailing_column_to_header(tmp_path):
    """REQ-41/45: include_signal_id=True (the --backtest run) appends a
    trailing 8th signal_id column; the default False stays at 7 columns,
    matching today's byte-for-byte output."""
    output_path = tmp_path / "detections.csv"

    write_detections_csv(_series(), str(output_path), include_signal_id=True)

    assert _read(output_path) == [_HEADER + ["signal_id"]]


def test_model1_row_carries_signal_id_only_when_include_signal_id_is_true(tmp_path):
    """REQ-41.1: a model1 row carries its Model1Signal.signal_id in the
    trailing column when include_signal_id=True."""
    model1_signals = [
        Model1Signal(
            anchor_index=1, direction="bullish", purge_target=0.9990,
            confirmation_type="purge_engulf", entry_type="wick", entry_price=0.9995,
            retest_index=2, status=DetectionStatus.CONFIRMED,
            confirmation_index=2, origin_index=0,
        )
    ]
    output_path = tmp_path / "detections.csv"

    write_detections_csv(_series(), str(output_path), model1_signals=model1_signals, include_signal_id=True)

    rows = _read(output_path)
    assert rows[0] == _HEADER + ["signal_id"]
    assert rows[1][9] == "0-1-bullish-purge_engulf-wick"


def test_non_model1_rows_write_empty_signal_id_when_include_signal_id_is_true(tmp_path):
    """REQ-41: every non-model1 row type writes "" for the trailing
    signal_id column, never a real id."""
    swings = [SwingPoint(index=1, price=1.0020, kind="high")]
    output_path = tmp_path / "detections.csv"

    write_detections_csv(_series(), str(output_path), swings=swings, include_signal_id=True)

    rows = _read(output_path)
    assert rows[1][1] == "swing"
    assert rows[1][9] == ""


def test_two_signals_sharing_origin_index_but_different_confirmation_type_never_collide(tmp_path):
    """REQ-41.2: an fvg_fill-confirmed signal and a purge_engulf-confirmed
    signal sharing the same origin_index get distinct signal_id values."""
    aligned_signals = [
        AlignedSignal(
            ltf_signal=Model1Signal(
                anchor_index=1, direction="bullish", purge_target=0.9990,
                confirmation_type="purge_engulf", entry_type="wick", entry_price=0.9995,
                retest_index=2, status=DetectionStatus.CONFIRMED,
                confirmation_index=2, origin_index=40,
            ),
            htf_context=None, aligned="aligned",
        ),
        AlignedSignal(
            ltf_signal=Model1Signal(
                anchor_index=2, direction="bullish", purge_target=0.9990,
                confirmation_type="fvg_fill", entry_type="wick", entry_price=0.9995,
                retest_index=3, status=DetectionStatus.CONFIRMED,
                confirmation_index=3, origin_index=40,
            ),
            htf_context=None, aligned="aligned",
        ),
    ]
    output_path = tmp_path / "detections.csv"

    write_detections_csv(_series(), str(output_path), aligned_signals=aligned_signals, include_signal_id=True)

    rows = _read(output_path)
    signal_ids = {row[9] for row in rows[1:]}
    assert len(signal_ids) == 2


def test_rows_are_sorted_by_timestamp(tmp_path):
    swings = [
        SwingPoint(index=2, price=1.0010, kind="high"),
        SwingPoint(index=1, price=1.0020, kind="low"),
    ]
    output_path = tmp_path / "detections.csv"

    write_detections_csv(_series(), str(output_path), swings=swings)

    rows = _read(output_path)
    assert rows[1][0] < rows[2][0]
