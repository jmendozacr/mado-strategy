"""Research-only command: run the canonical two-pair Dukascopy backtest and
publish deterministic, replayable evidence.

Not imported by any production module.

Derived-root layout: six pre-aggregated CSVs named
``{strategy_instrument}_{M15|H4|D1}.csv`` with header
``timestamp_utc,open,high,low,close,volume`` (timestamp_utc is UTC ISO-8601
with a trailing ``Z``, as written by ``research.streaming.write_aggregated_csv``).
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import hashlib
import io
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

from core.config import BacktestConfig, DetectorConfig
from runner.serialization import canonical_json, manifest_sha256, to_json_value

from research.dukascopy_eurusd_gbpusd.adapter import OHLCVBar
from research.dukascopy_eurusd_gbpusd.manifest import RunManifest, deserialize_manifest
from research.dukascopy_eurusd_gbpusd.seam import (
    APPROVED_STRATEGY_INSTRUMENTS,
    ohlcvbar_to_series,
    run_instrument_seam,
)

# Ordered pairs — evidence and receipt always publish EURUSD before GBPUSD.
ORDERED_PAIRS: tuple[str, ...] = ("DUKASCOPY_EURUSD", "DUKASCOPY_GBPUSD")
assert set(ORDERED_PAIRS) == APPROVED_STRATEGY_INSTRUMENTS

# External derived-artifact timeframe labels -> internal detector-core minutes.
_DERIVED_TIMEFRAME_MINUTES: dict[str, int] = {"M15": 15, "H4": 240, "D1": 1440}

_DERIVED_CSV_HEADER = ("timestamp_utc", "open", "high", "low", "close", "volume")

_EXPECTED_DERIVED_ARTIFACTS: frozenset[str] = frozenset(
    f"{instrument}_{tf_label}.csv"
    for instrument in ORDERED_PAIRS
    for tf_label in _DERIVED_TIMEFRAME_MINUTES
)


class BacktestError(Exception):
    """Any validation, execution, destination, or publication failure."""


def _sha256_hex(value: str) -> str:
    if not re.fullmatch(r"[0-9a-fA-F]{64}", value):
        raise argparse.ArgumentTypeError(f"must be a 64-character hex SHA-256 digest, got {value!r}")
    return value.lower()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m research.dukascopy_eurusd_gbpusd.backtest"
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--expected-manifest-sha256", required=True, type=_sha256_hex)
    parser.add_argument("--derived-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--eurusd-cost", required=True, type=float)
    parser.add_argument("--gbpusd-cost", required=True, type=float)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        _run(args)
    except Exception as exc:  # noqa: BLE001 — command boundary: report, never crash
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def _run(args: argparse.Namespace) -> None:
    costs = {"DUKASCOPY_EURUSD": args.eurusd_cost, "DUKASCOPY_GBPUSD": args.gbpusd_cost}
    for instrument, cost in costs.items():
        if cost < 0:
            raise BacktestError(f"cost for {instrument} must be non-negative, got {cost}")

    output_dir: Path = args.output_dir
    if output_dir.exists():
        raise BacktestError(f"output directory already exists: {output_dir}")

    manifest_bytes = args.manifest.read_bytes()
    raw_manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    if raw_manifest_sha256 != args.expected_manifest_sha256:
        raise BacktestError(
            f"manifest identity mismatch: expected {args.expected_manifest_sha256},"
            f" got {raw_manifest_sha256}"
        )
    manifest = deserialize_manifest(manifest_bytes.decode("utf-8"))
    canonical_manifest_sha256 = manifest_sha256(manifest)
    _validate_manifest_identity(manifest)
    bars_by_artifact, derived_hashes = _load_and_validate_derived_files(args.derived_root, manifest)

    candidate_cutoff = _parse_manifest_instant(manifest.candidate_cutoff_end_utc)
    outcome_followup = _parse_manifest_instant(manifest.outcome_followup_end_utc)

    per_instrument: dict[str, dict] = {}
    trade_payloads: dict[str, bytes] = {}

    for instrument in ORDERED_PAIRS:
        series_by_tf = {
            tf_label: ohlcvbar_to_series(bars_by_artifact[f"{instrument}_{tf_label}.csv"], instrument, minutes)
            for tf_label, minutes in _DERIVED_TIMEFRAME_MINUTES.items()
        }
        ltf, htf, daily = series_by_tf["M15"], series_by_tf["H4"], series_by_tf["D1"]

        config = _config_for_cost(costs[instrument])
        result = run_instrument_seam(
            ltf, htf, daily, config, candidate_cutoff, outcome_followup, manifest=manifest
        )

        trades_payload = {
            "instrument": instrument,
            "trades": [to_json_value(trade) for trade in result.trades],
        }
        data = canonical_json(trades_payload)
        trade_payloads[instrument] = data
        per_instrument[instrument] = {
            "candidate_count": result.candidate_count,
            "candidate_fingerprint": result.candidate_fingerprint,
            "reconciliation": to_json_value(result.reconciliation),
            "trades_file": f"{instrument}_trades.json",
            "trades_sha256": hashlib.sha256(data).hexdigest(),
        }

    receipt = _build_receipt(
        manifest=manifest,
        raw_manifest_sha256=raw_manifest_sha256,
        expected_manifest_sha256=args.expected_manifest_sha256,
        canonical_manifest_sha256=canonical_manifest_sha256,
        costs=costs,
        derived_hashes=derived_hashes,
        per_instrument=per_instrument,
    )
    receipt_bytes = canonical_json(receipt)

    _publish(output_dir, trade_payloads, receipt_bytes)


def _parse_manifest_instant(value: str) -> datetime:
    """Reverse ``_require_utc_instant``'s ``isoformat(timespec='seconds') + 'Z'``."""
    return datetime.fromisoformat(value[:-1])


def _config_for_cost(cost: float) -> DetectorConfig:
    base = DetectorConfig()
    return dataclasses.replace(
        base, backtest=dataclasses.replace(base.backtest, trading_cost_price=cost)
    )


def _validate_manifest_identity(manifest: RunManifest) -> None:
    """The manifest's declared derived-artifact set must include exactly the
    six expected CSVs. Additional non-CSV provenance entries (e.g. a retained
    exclusion-gap-ledger hash) are permitted; an undeclared derived CSV is not."""
    declared = set(dict(manifest.output_hashes))
    missing = _EXPECTED_DERIVED_ARTIFACTS - declared
    if missing:
        raise BacktestError(
            f"manifest output_hashes missing required derived artifact(s): {sorted(missing)}"
        )
    unexpected_csv = {name for name in declared - _EXPECTED_DERIVED_ARTIFACTS if name.lower().endswith(".csv")}
    if unexpected_csv:
        raise BacktestError(
            f"manifest output_hashes declares unexpected derived CSV(s): {sorted(unexpected_csv)}"
        )


def _parse_derived_csv(data: bytes, path: Path) -> list[OHLCVBar]:
    reader = csv.reader(io.StringIO(data.decode("utf-8")))
    try:
        header = tuple(column.strip() for column in next(reader))
    except StopIteration as exc:
        raise BacktestError(f"empty derived CSV: {path}") from exc
    if header != _DERIVED_CSV_HEADER:
        raise BacktestError(
            f"unexpected derived CSV header in {path}: expected {_DERIVED_CSV_HEADER}, got {header}"
        )
    bars: list[OHLCVBar] = []
    for row in reader:
        if not row:
            continue
        ts_str, open_, high, low, close, volume = row
        timestamp = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        bars.append(
            OHLCVBar(
                timestamp=timestamp,
                open=float(open_),
                high=float(high),
                low=float(low),
                close=float(close),
                volume=float(volume),
            )
        )
    return bars


def _load_and_validate_derived_files(
    derived_root: Path, manifest: RunManifest
) -> tuple[dict[str, list[OHLCVBar]], dict[str, str]]:
    """Reads, hashes, and parses every expected derived CSV exactly once —
    coverage, hash, and row-count are all validated before any candidate is
    simulated (REQ-01.3)."""
    declared_hashes = dict(manifest.output_hashes)
    missing = sorted(name for name in _EXPECTED_DERIVED_ARTIFACTS if not (derived_root / name).is_file())
    if missing:
        raise BacktestError(f"missing derived file(s): {missing}")

    bars_by_artifact: dict[str, list[OHLCVBar]] = {}
    hashes: dict[str, str] = {}
    for name in sorted(_EXPECTED_DERIVED_ARTIFACTS):
        path = derived_root / name
        data = path.read_bytes()
        actual_hash = hashlib.sha256(data).hexdigest()
        if actual_hash != declared_hashes[name]:
            raise BacktestError(
                f"derived file hash mismatch for {name}:"
                f" manifest declares {declared_hashes[name]}, got {actual_hash}"
            )
        bars = _parse_derived_csv(data, path)
        if not bars:
            raise BacktestError(f"derived file has no data rows: {name}")
        hashes[name] = actual_hash
        bars_by_artifact[name] = bars
    return bars_by_artifact, hashes


def _argv_template(eurusd_cost: float, gbpusd_cost: float, expected_manifest_sha256: str) -> list[str]:
    return [
        "uv", "run", "--project", "detector",
        "python", "-m", "research.dukascopy_eurusd_gbpusd.backtest",
        "--manifest", "${MANIFEST}",
        "--expected-manifest-sha256", expected_manifest_sha256,
        "--derived-root", "${DERIVED_ROOT}",
        "--output-dir", "${OUTPUT_DIR}",
        "--eurusd-cost", repr(eurusd_cost),
        "--gbpusd-cost", repr(gbpusd_cost),
    ]


def _build_receipt(
    *,
    manifest: RunManifest,
    raw_manifest_sha256: str,
    expected_manifest_sha256: str,
    canonical_manifest_sha256: str,
    costs: dict[str, float],
    derived_hashes: dict[str, str],
    per_instrument: dict[str, dict],
) -> dict:
    default_backtest = BacktestConfig()
    return {
        "schema_version": 2,
        "pairs": list(ORDERED_PAIRS),
        "manifest_sha256": raw_manifest_sha256,
        "expected_manifest_sha256": expected_manifest_sha256,
        "canonical_manifest_sha256": canonical_manifest_sha256,
        "sources": [
            {
                "strategy_instrument": entry.strategy_instrument,
                "provider_instrument": entry.provider_instrument,
                "source_path": entry.source_path,
                "source_sha256": entry.source_sha256,
            }
            for entry in manifest.inputs
        ],
        "derived_sha256": derived_hashes,
        "costs": costs,
        "backtest_config": {
            "sl_buffer_atr_multiple": default_backtest.sl_buffer_atr_multiple,
            "min_risk_reward": default_backtest.min_risk_reward,
            "kill_zone_gated": default_backtest.kill_zone_gated,
            "max_fill_wait": default_backtest.max_fill_wait,
            "partial_fraction": default_backtest.partial_fraction,
        },
        "instruments": per_instrument,
        "replay": {
            "argv_template": _argv_template(
                costs["DUKASCOPY_EURUSD"], costs["DUKASCOPY_GBPUSD"], expected_manifest_sha256
            )
        },
    }


def _verify_staging_members(staging: Path, members: dict[str, bytes]) -> None:
    """The single discrete pre-rename gate: exactly the required members,
    each byte-identical to what the receipt already claims for it."""
    actual_names = {p.name for p in staging.iterdir()}
    if actual_names != set(members):
        raise BacktestError(
            f"staging directory members changed before publish:"
            f" expected {sorted(members)}, got {sorted(actual_names)}"
        )
    for name, data in members.items():
        if (staging / name).read_bytes() != data:
            raise BacktestError(f"staging file changed before publish: {name}")


def _publish(output_dir: Path, trade_payloads: dict[str, bytes], receipt_bytes: bytes) -> None:
    if output_dir.exists():
        raise BacktestError(f"output directory already exists: {output_dir}")

    members = {f"{instrument}_trades.json": data for instrument, data in trade_payloads.items()}
    members["receipt.json"] = receipt_bytes

    parent = output_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = parent / f".staging-{output_dir.name}-{os.getpid()}-{time.monotonic_ns()}"
    staging.mkdir()
    try:
        for name, data in members.items():
            (staging / name).write_bytes(data)
        _verify_staging_members(staging, members)
        if output_dir.exists():
            raise BacktestError(f"output directory already exists: {output_dir}")
        os.replace(staging, output_dir)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise


if __name__ == "__main__":
    sys.exit(main())
