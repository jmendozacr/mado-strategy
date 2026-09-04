import csv

from alignment.htf_ltf import AlignedSignal
from composite.mss import MSSEvent
from core.candle import OHLCSeries
from entries.model1 import Model1Signal
from primitives.crt_range import CRTRange
from primitives.fvg import FVG
from primitives.swing import SwingPoint

_HEADER = ["timestamp", "type", "direction", "price_high", "price_low", "status", "aligned", "key_level_source"]
_HEADER_WITH_SIGNAL_ID = _HEADER + ["signal_id"]


def write_detections_csv(
    series: OHLCSeries,
    output_path: str,
    swings: list[SwingPoint] | None = None,
    fvgs: list[FVG] | None = None,
    crt_ranges: list[CRTRange] | None = None,
    mss_events: list[MSSEvent] | None = None,
    model1_signals: list[Model1Signal] | None = None,
    aligned_signals: list[AlignedSignal] | None = None,
    include_signal_id: bool = False,
) -> None:
    """`include_signal_id` (REQ-41/45) appends a trailing `signal_id`
    column ONLY on runs where `--backtest` was passed for this run; the
    default False preserves today's byte-for-byte 7-column output."""
    rows = []
    for swing in swings or []:
        rows.append(_row(series, swing.index, "swing", swing.kind, swing.price, swing.price, "", "", "", include_signal_id))
    for fvg in fvgs or []:
        rows.append(
            _row(
                series, fvg.start_index, "fvg", fvg.direction, fvg.top, fvg.bottom, fvg.fill_status, "", "",
                include_signal_id,
            )
        )
    for crt_range in crt_ranges or []:
        rows.append(
            _row(
                series, crt_range.start_index, "crt_range", "", crt_range.high, crt_range.low,
                crt_range.resolution, "", "", include_signal_id,
            )
        )
    for event in mss_events or []:
        rows.append(
            _row(
                series, event.index, "mss", event.direction, event.broken_swing.price, event.broken_swing.price,
                "", "", "", include_signal_id,
            )
        )

    if aligned_signals is not None:
        for tagged in aligned_signals:
            key_level_source = tagged.key_level.kind if tagged.key_level is not None else ""
            rows.append(_model1_row(series, tagged.ltf_signal, tagged.aligned, key_level_source, include_signal_id))
    else:
        for signal in model1_signals or []:
            rows.append(_model1_row(series, signal, "", "", include_signal_id))

    rows.sort(key=lambda row: row[0])

    write_csv(output_path, _HEADER_WITH_SIGNAL_ID if include_signal_id else _HEADER, rows)


def write_csv(output_path: str, header: list, rows) -> None:
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def _model1_row(
    series: OHLCSeries, signal: Model1Signal, aligned: str, key_level_source: str, include_signal_id: bool
) -> list:
    return _row(
        series, signal.anchor_index, "model1", signal.direction,
        signal.entry_price, signal.entry_price, signal.status.value, aligned,
        key_level_source, include_signal_id, signal.signal_id,
    )


def _row(
    series: OHLCSeries, index: int, type_: str, direction: str, price_high: float, price_low: float,
    status: str, aligned: str, key_level_source: str, include_signal_id: bool, signal_id: str = "",
) -> list:
    row = [
        series.candles[index].timestamp.isoformat(), type_, direction, price_high, price_low, status,
        aligned, key_level_source,
    ]
    if include_signal_id:
        row.append(signal_id)
    return row
