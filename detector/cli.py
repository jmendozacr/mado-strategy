"""CLI entry point — single-series mode (S-000). Pair mode, date/type
filters, and the detections.csv table land in later slices (S-005/S-006).
"""

import argparse
import sys
from pathlib import Path

from core.config import DetectorConfig
from ingestion.loader import LoadError, load_mt5_csv
from primitives.swing import detect_swings
from viz.chart import render_chart


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m detector.cli")
    parser.add_argument("--csv", required=True, help="Path to the MT5-exported OHLC CSV")
    parser.add_argument("--symbol", required=True, help="Instrument identity, e.g. EURUSD")
    parser.add_argument("--output-dir", required=True, help="Directory for overlay.png")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    try:
        series = load_mt5_csv(args.csv, symbol=args.symbol)
    except LoadError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    config = DetectorConfig()
    swings = detect_swings(series, config.swing)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    render_chart(series, swings, str(output_dir / "overlay.png"))

    return 0


if __name__ == "__main__":
    sys.exit(main())
