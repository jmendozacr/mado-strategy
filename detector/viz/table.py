import csv

from alignment.htf_ltf import AlignedSignal
from composite.mss import MSSEvent
from core.candle import OHLCSeries
from entries.model1 import Model1Signal
from primitives.crt_range import CRTRange
from primitives.fvg import FVG
from primitives.swing import SwingPoint

_HEADER = ["timestamp", "type", "direction", "price_high", "price_low", "status", "aligned"]


def write_detections_csv(
    series: OHLCSeries,
    output_path: str,
    swings: list[SwingPoint] | None = None,
    fvgs: list[FVG] | None = None,
    crt_ranges: list[CRTRange] | None = None,
    mss_events: list[MSSEvent] | None = None,
    model1_signals: list[Model1Signal] | None = None,
    aligned_signals: list[AlignedSignal] | None = None,
) -> None:
    rows = []
    for swing in swings or []:
        rows.append(_row(series, swing.index, "swing", swing.kind, swing.price, swing.price, "", ""))
    for fvg in fvgs or []:
        rows.append(_row(series, fvg.start_index, "fvg", fvg.direction, fvg.top, fvg.bottom, fvg.fill_status, ""))
    for crt_range in crt_ranges or []:
        rows.append(
            _row(series, crt_range.start_index, "crt_range", "", crt_range.high, crt_range.low, crt_range.resolution, "")
        )
    for event in mss_events or []:
        rows.append(
            _row(series, event.index, "mss", event.direction, event.broken_swing.price, event.broken_swing.price, "", "")
        )

    if aligned_signals is not None:
        for tagged in aligned_signals:
            rows.append(_model1_row(series, tagged.ltf_signal, tagged.aligned))
    else:
        for signal in model1_signals or []:
            rows.append(_model1_row(series, signal, ""))

    rows.sort(key=lambda row: row[0])

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(_HEADER)
        writer.writerows(rows)


def _model1_row(series: OHLCSeries, signal: Model1Signal, aligned: str) -> list:
    return _row(
        series, signal.anchor_index, "model1", signal.direction,
        signal.entry_price, signal.entry_price, signal.status.value, aligned,
    )


def _row(series: OHLCSeries, index: int, type_: str, direction: str, price_high: float, price_low: float, status: str, aligned: str) -> list:
    return [series.candles[index].timestamp.isoformat(), type_, direction, price_high, price_low, status, aligned]
