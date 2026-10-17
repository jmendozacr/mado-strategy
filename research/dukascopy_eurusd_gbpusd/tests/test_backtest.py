"""Synthetic two-pair command tests for the Dukascopy research backtest.

All tests use in-memory/temp-filesystem fixtures only — no real Dukascopy
CSVs, no network. No production modules are modified.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backtest.simulate import ReconciliationReport, Trade
from research.dukascopy_eurusd_gbpusd.backtest import ORDERED_PAIRS, main
from research.dukascopy_eurusd_gbpusd.manifest import (
    InputManifestEntry,
    build_manifest,
    deserialize_manifest,
    serialize_manifest,
)
from research.dukascopy_eurusd_gbpusd.seam import SeamInstrumentResult
from runner.serialization import manifest_sha256

_UTC = timezone.utc
_ZERO_HASH = "0" * 64

_TF_SPACING: dict[str, timedelta] = {
    "M15": timedelta(minutes=15),
    "H4": timedelta(hours=4),
    "D1": timedelta(days=1),
}
_TF_ROWS: dict[str, int] = {"M15": 60, "H4": 30, "D1": 20}


def _write_derived_csv(path: Path, tf_label: str) -> None:
    base = datetime(2023, 1, 2, tzinfo=_UTC)
    step = _TF_SPACING[tf_label]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["timestamp_utc", "open", "high", "low", "close", "volume"])
        for i in range(_TF_ROWS[tf_label]):
            ts = (base + i * step).isoformat().replace("+00:00", "Z")
            writer.writerow([ts, "1.1000", "1.1000", "1.1000", "1.1000", "1.0"])


def _write_empty_derived_csv(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["timestamp_utc", "open", "high", "low", "close", "volume"])


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_derived_root(derived_root: Path) -> dict[str, str]:
    """Writes all six derived CSVs and returns their real sha256 hashes,
    keyed by filename — the shape `build_manifest`'s `output_hashes` needs."""
    derived_root.mkdir(parents=True)
    hashes: dict[str, str] = {}
    for instrument in ORDERED_PAIRS:
        for tf_label in _TF_SPACING:
            path = derived_root / f"{instrument}_{tf_label}.csv"
            _write_derived_csv(path, tf_label)
            hashes[path.name] = _sha256(path)
    return hashes


def _write_manifest(manifest_path: Path, output_hashes: dict[str, str]) -> str:
    """Returns the manifest file's raw SHA-256 — the value `--expected-manifest-sha256`
    must match. The CLI validates raw file bytes, not the parsed/canonicalized form;
    see `manifest_sha256` (imported above) for the separate canonical identity."""
    manifest = build_manifest(
        run_id="test-run-001",
        population_start="2023-01-01",
        population_end="2023-06-01",
        candidate_cutoff_end_utc="2030-01-01T00:00:00Z",
        outcome_followup_end_utc="2030-12-31T00:00:00Z",
        inputs=[
            InputManifestEntry(
                strategy_instrument="DUKASCOPY_EURUSD",
                provider_instrument="EURUSD",
                source_path="/external/EURUSD.csv",
                source_sha256=_ZERO_HASH,
            ),
            InputManifestEntry(
                strategy_instrument="DUKASCOPY_GBPUSD",
                provider_instrument="GBPUSD",
                source_path="/external/GBPUSD.csv",
                source_sha256=_ZERO_HASH,
            ),
        ],
        timezone_label="EET",
        dst_rule="Europe/Helsinki",
        day_start_config="00:00:00 EET",
        offer_side="Bid",
        timeframe_set={"D1", "H4", "M15"},
        offline_domain_receipt_hash=_ZERO_HASH,
        offline_domain_receipt_reference="/external/offline-domains.json",
        protocol_references=["/external/protocol.md"],
        design_reference="openspec/changes/dukascopy-backtest-readiness/design.md",
        adapter_source_reference="research/dukascopy_eurusd_gbpusd/adapter.py",
        output_hashes=output_hashes,
        exclusion_ledger_reference="/external/exclusion-ledger.json",
    )
    manifest_path.write_text(serialize_manifest(manifest), encoding="utf-8")
    return hashlib.sha256(manifest_path.read_bytes()).hexdigest()


def _prepare_run(root: Path) -> tuple[Path, Path, str]:
    """Derived root + manifest, both valid, both under `root`. Returns
    (manifest_path, derived_root, expected_manifest_sha256)."""
    derived_root = root / "derived"
    output_hashes = _write_derived_root(derived_root)
    manifest_path = root / "manifest.json"
    expected_hash = _write_manifest(manifest_path, output_hashes)
    return manifest_path, derived_root, expected_hash


def _run_args(
    manifest_path: Path, derived_root: Path, output_dir: Path, expected_manifest_sha256: str, **cost_overrides
) -> list[str]:
    costs = {"--eurusd-cost": "0.0001", "--gbpusd-cost": "0.00015"}
    costs.update(cost_overrides)
    args = [
        "--manifest", str(manifest_path),
        "--expected-manifest-sha256", expected_manifest_sha256,
        "--derived-root", str(derived_root),
        "--output-dir", str(output_dir),
    ]
    for flag, value in costs.items():
        args += [flag, value]
    return args


def _loss_trade(signal_id: str) -> Trade:
    return Trade(
        signal_id=signal_id,
        anchor_index=0,
        direction="bullish",
        entry_index=1,
        entry_price=1.1000,
        stop_loss=1.0950,
        take_profit=1.1100,
        exit_index=2,
        exit_price=1.0950,
        outcome="loss",
        r_multiple=-1.0,
        ambiguous_bar=False,
        gap_filled=False,
        partial_exit_index=None,
        partial_exit_price=None,
        partial_r_multiple=None,
        partial_gap_filled=False,
    )


def _reconciliation_for_one_loss() -> ReconciliationReport:
    return ReconciliationReport(
        signals_considered=1,
        trades_opened=1,
        excluded_no_crt_range=0,
        excluded_unaligned=0,
        excluded_never_confirmed=0,
        excluded_no_key_level=0,
        excluded_duplicate=0,
        excluded_kill_zone=0,
        excluded_rr_floor=0,
        excluded_never_filled=0,
    )


def _staging_leftovers(output_dir: Path) -> list[Path]:
    return list(output_dir.parent.glob(".staging-*"))


# ---------------------------------------------------------------------------
# Happy path: flat series, no signals, both pairs published
# ---------------------------------------------------------------------------


def test_backtest_command_publishes_ordered_two_pair_evidence(tmp_path: Path):
    manifest_path, derived_root, expected_hash = _prepare_run(tmp_path)
    output_dir = tmp_path / "run-output"

    exit_code = main(_run_args(manifest_path, derived_root, output_dir, expected_hash))

    assert exit_code == 0
    assert (output_dir / "DUKASCOPY_EURUSD_trades.json").is_file()
    assert (output_dir / "DUKASCOPY_GBPUSD_trades.json").is_file()
    receipt = json.loads((output_dir / "receipt.json").read_text(encoding="utf-8"))

    assert receipt["pairs"] == ["DUKASCOPY_EURUSD", "DUKASCOPY_GBPUSD"]
    assert set(receipt["instruments"]) == {"DUKASCOPY_EURUSD", "DUKASCOPY_GBPUSD"}
    assert receipt["costs"] == {"DUKASCOPY_EURUSD": 0.0001, "DUKASCOPY_GBPUSD": 0.00015}
    assert receipt["manifest_sha256"] == expected_hash
    assert receipt["expected_manifest_sha256"] == expected_hash


def test_backtest_command_receipt_distinguishes_raw_and_canonical_manifest_hash(tmp_path: Path):
    """The receipt must expose the raw manifest-file hash (what the CLI
    actually validates) and the parsed/canonicalized hash as separate,
    distinguishable fields — never conflate the two."""
    manifest_path, derived_root, raw_hash = _prepare_run(tmp_path)
    canonical_hash = manifest_sha256(deserialize_manifest(manifest_path.read_text(encoding="utf-8")))
    assert raw_hash != canonical_hash  # sanity: pretty-printed file vs. compact canonical form
    output_dir = tmp_path / "run-output"

    exit_code = main(_run_args(manifest_path, derived_root, output_dir, raw_hash))

    assert exit_code == 0
    receipt = json.loads((output_dir / "receipt.json").read_text(encoding="utf-8"))
    assert receipt["schema_version"] == 2
    assert receipt["manifest_sha256"] == raw_hash
    assert receipt["expected_manifest_sha256"] == raw_hash
    assert receipt["canonical_manifest_sha256"] == canonical_hash


def test_backtest_command_argv_template_is_portable(tmp_path: Path):
    """replay.argv_template must contain only the three stable tokens — no
    runtime paths, staging names, timestamps, or cwd leak into it."""
    manifest_path, derived_root, expected_hash = _prepare_run(tmp_path)
    output_dir = tmp_path / "run-output"

    main(_run_args(manifest_path, derived_root, output_dir, expected_hash))
    receipt = json.loads((output_dir / "receipt.json").read_text(encoding="utf-8"))
    argv_template = receipt["replay"]["argv_template"]

    assert "${MANIFEST}" in argv_template
    assert "${DERIVED_ROOT}" in argv_template
    assert "${OUTPUT_DIR}" in argv_template
    assert expected_hash in argv_template  # literal, not tokenized — no new path token
    joined = " ".join(argv_template)
    assert str(tmp_path) not in joined


# ---------------------------------------------------------------------------
# REQ-01.4: an unprofitable result still exits successfully
# ---------------------------------------------------------------------------


def test_backtest_command_succeeds_with_unprofitable_trades(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    manifest_path, derived_root, expected_hash = _prepare_run(tmp_path)
    output_dir = tmp_path / "run-output"

    def fake_run_instrument_seam(ltf, htf, daily, config, cutoff, followup, *, manifest=None):
        return SeamInstrumentResult(
            observations=(),
            candidate_count=1,
            candidate_fingerprint="a" * 64,
            trades=(_loss_trade(f"{ltf.instrument}-s0"),),
            reconciliation=_reconciliation_for_one_loss(),
        )

    monkeypatch.setattr(
        "research.dukascopy_eurusd_gbpusd.backtest.run_instrument_seam",
        fake_run_instrument_seam,
    )

    exit_code = main(_run_args(manifest_path, derived_root, output_dir, expected_hash))

    assert exit_code == 0
    eurusd_trades = json.loads((output_dir / "DUKASCOPY_EURUSD_trades.json").read_text(encoding="utf-8"))
    assert eurusd_trades["trades"][0]["outcome"] == "loss"
    receipt = json.loads((output_dir / "receipt.json").read_text(encoding="utf-8"))
    assert receipt["instruments"]["DUKASCOPY_EURUSD"]["reconciliation"]["trades_opened"] == 1


# ---------------------------------------------------------------------------
# REQ-01.3: invalid or incomplete evidence sources are rejected pre-simulation
# ---------------------------------------------------------------------------


def test_backtest_command_rejects_derived_file_hash_mismatch(tmp_path: Path):
    manifest_path, derived_root, expected_hash = _prepare_run(tmp_path)
    tampered = derived_root / "DUKASCOPY_EURUSD_M15.csv"
    with tampered.open("a", encoding="utf-8") as f:
        f.write("2099-01-01T00:00:00Z,1.0,1.0,1.0,1.0,1.0\n")
    output_dir = tmp_path / "run-output"

    exit_code = main(_run_args(manifest_path, derived_root, output_dir, expected_hash))

    assert exit_code == 1
    assert not output_dir.exists()
    assert _staging_leftovers(output_dir) == []


# ---------------------------------------------------------------------------
# --expected-manifest-sha256 is mandatory identity
# ---------------------------------------------------------------------------


def test_backtest_command_rejects_wrong_expected_manifest_sha256(tmp_path: Path):
    """A well-formed but wrong hash is rejected before any derived file is
    even opened."""
    manifest_path, derived_root, expected_hash = _prepare_run(tmp_path)
    output_dir = tmp_path / "run-output"
    wrong_hash = ("1" if expected_hash[0] == "0" else "0") + expected_hash[1:]

    exit_code = main(_run_args(manifest_path, derived_root, output_dir, wrong_hash))

    assert exit_code == 1
    assert not output_dir.exists()
    assert _staging_leftovers(output_dir) == []


def test_backtest_command_rejects_reformatted_manifest_against_raw_hash(tmp_path: Path):
    """Regression test: a manifest that parses to an identical `RunManifest`
    but is serialized with different raw bytes (compact vs. pretty-printed
    JSON) must still be rejected against the original raw-file hash — the
    identity check is on raw bytes, not the parsed/canonicalized content."""
    manifest_path, derived_root, raw_hash = _prepare_run(tmp_path)
    original_text = manifest_path.read_text(encoding="utf-8")
    reformatted = json.dumps(json.loads(original_text), sort_keys=True, separators=(",", ":"))
    assert reformatted != original_text  # sanity: genuinely different raw bytes
    # Sanity: still semantically equivalent — reformatting alone must not
    # change the parsed manifest's canonical identity.
    assert manifest_sha256(deserialize_manifest(original_text)) == manifest_sha256(
        deserialize_manifest(reformatted)
    )
    manifest_path.write_text(reformatted, encoding="utf-8")
    output_dir = tmp_path / "run-output"

    exit_code = main(_run_args(manifest_path, derived_root, output_dir, raw_hash))

    assert exit_code == 1
    assert not output_dir.exists()
    assert _staging_leftovers(output_dir) == []


def test_backtest_command_invalid_expected_manifest_sha256_format_exits_2():
    with pytest.raises(SystemExit) as exc_info:
        main([
            "--manifest", "x", "--expected-manifest-sha256", "not-a-valid-hash",
            "--derived-root", "y", "--output-dir", "z",
            "--eurusd-cost", "0.0", "--gbpusd-cost", "0.0",
        ])
    assert exc_info.value.code == 2


def test_backtest_command_missing_expected_manifest_sha256_exits_2(tmp_path: Path):
    manifest_path, derived_root, _ = _prepare_run(tmp_path)
    output_dir = tmp_path / "run-output"

    with pytest.raises(SystemExit) as exc_info:
        main([
            "--manifest", str(manifest_path), "--derived-root", str(derived_root),
            "--output-dir", str(output_dir), "--eurusd-cost", "0.0001", "--gbpusd-cost", "0.00015",
        ])
    assert exc_info.value.code == 2


def test_backtest_command_rejects_manifest_declaring_an_extra_artifact(tmp_path: Path):
    """An untracked 7th derived-CSV entry: the per-artifact hash loop iterates
    only the expected 6 and would never see it, so this isolates the
    manifest's own identity check. Additional derived CSVs stay rejected even
    though additional non-CSV provenance entries are now permitted (see
    `test_backtest_command_accepts_additional_non_csv_provenance_hash`)."""
    derived_root = tmp_path / "derived"
    output_hashes = _write_derived_root(derived_root)
    output_hashes["DUKASCOPY_EURUSD_H1.csv"] = _ZERO_HASH
    manifest_path = tmp_path / "manifest.json"
    expected_hash = _write_manifest(manifest_path, output_hashes)
    output_dir = tmp_path / "run-output"

    exit_code = main(_run_args(manifest_path, derived_root, output_dir, expected_hash))

    assert exit_code == 1
    assert not output_dir.exists()


def test_backtest_command_rejects_manifest_declaring_an_extra_artifact_uppercase_extension(
    tmp_path: Path,
):
    """The extra-CSV guard must be case-insensitive on the file extension —
    an untracked 7th entry named with `.CSV` must be rejected exactly like
    the lowercase `.csv` case, not silently accepted as non-CSV provenance."""
    derived_root = tmp_path / "derived"
    output_hashes = _write_derived_root(derived_root)
    output_hashes["DUKASCOPY_EURUSD_H1.CSV"] = _ZERO_HASH
    manifest_path = tmp_path / "manifest.json"
    expected_hash = _write_manifest(manifest_path, output_hashes)
    output_dir = tmp_path / "run-output"

    exit_code = main(_run_args(manifest_path, derived_root, output_dir, expected_hash))

    assert exit_code == 1
    assert not output_dir.exists()
    assert _staging_leftovers(output_dir) == []


def test_backtest_command_accepts_additional_non_csv_provenance_hash(tmp_path: Path):
    """A retained non-CSV provenance entry (e.g. an exclusion-gap-ledger JSON
    hash) declared alongside the six required derived CSVs must not be
    rejected — only undeclared derived CSVs are refused."""
    derived_root = tmp_path / "derived"
    output_hashes = _write_derived_root(derived_root)
    output_hashes["Dukascopy-gap-ledger-2026-09-22.json"] = _ZERO_HASH
    manifest_path = tmp_path / "manifest.json"
    expected_hash = _write_manifest(manifest_path, output_hashes)
    output_dir = tmp_path / "run-output"

    exit_code = main(_run_args(manifest_path, derived_root, output_dir, expected_hash))

    assert exit_code == 0
    assert (output_dir / "receipt.json").is_file()


def test_backtest_command_rejects_incomplete_manifest_output_hashes(tmp_path: Path):
    derived_root = tmp_path / "derived"
    output_hashes = _write_derived_root(derived_root)
    del output_hashes["DUKASCOPY_GBPUSD_D1.csv"]
    manifest_path = tmp_path / "manifest.json"
    expected_hash = _write_manifest(manifest_path, output_hashes)
    output_dir = tmp_path / "run-output"

    exit_code = main(_run_args(manifest_path, derived_root, output_dir, expected_hash))

    assert exit_code == 1
    assert not output_dir.exists()


def test_backtest_command_rejects_incomplete_derived_coverage(tmp_path: Path):
    manifest_path, derived_root, expected_hash = _prepare_run(tmp_path)
    (derived_root / "DUKASCOPY_GBPUSD_H4.csv").unlink()
    output_dir = tmp_path / "run-output"

    exit_code = main(_run_args(manifest_path, derived_root, output_dir, expected_hash))

    assert exit_code == 1
    assert not output_dir.exists()


def test_backtest_command_rejects_empty_derived_file(tmp_path: Path):
    derived_root = tmp_path / "derived"
    output_hashes = _write_derived_root(derived_root)
    empty_path = derived_root / "DUKASCOPY_EURUSD_D1.csv"
    _write_empty_derived_csv(empty_path)
    output_hashes[empty_path.name] = _sha256(empty_path)
    manifest_path = tmp_path / "manifest.json"
    expected_hash = _write_manifest(manifest_path, output_hashes)
    output_dir = tmp_path / "run-output"

    exit_code = main(_run_args(manifest_path, derived_root, output_dir, expected_hash))

    assert exit_code == 1
    assert not output_dir.exists()


def test_backtest_command_rejects_negative_cost(tmp_path: Path):
    manifest_path, derived_root, expected_hash = _prepare_run(tmp_path)
    output_dir = tmp_path / "run-output"

    exit_code = main(
        _run_args(manifest_path, derived_root, output_dir, expected_hash, **{"--eurusd-cost": "-0.0001"})
    )

    assert exit_code == 1
    assert not output_dir.exists()


def test_backtest_command_argparse_missing_required_flag_exits_2():
    with pytest.raises(SystemExit) as exc_info:
        main(["--manifest", "x", "--derived-root", "y", "--output-dir", "z", "--eurusd-cost", "0.0"])
    assert exc_info.value.code == 2


# ---------------------------------------------------------------------------
# Destination already exists — never overwritten
# ---------------------------------------------------------------------------


def test_backtest_command_rejects_existing_destination(tmp_path: Path):
    manifest_path, derived_root, expected_hash = _prepare_run(tmp_path)
    output_dir = tmp_path / "run-output"
    output_dir.mkdir()
    (output_dir / "marker.txt").write_text("preexisting", encoding="utf-8")

    exit_code = main(_run_args(manifest_path, derived_root, output_dir, expected_hash))

    assert exit_code == 1
    assert (output_dir / "marker.txt").read_text(encoding="utf-8") == "preexisting"


# ---------------------------------------------------------------------------
# Injected failures leave no mixed or partial evidence
# ---------------------------------------------------------------------------


def test_backtest_command_execution_failure_leaves_no_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    manifest_path, derived_root, expected_hash = _prepare_run(tmp_path)
    output_dir = tmp_path / "run-output"

    def failing_on_second_pair(ltf, htf, daily, config, cutoff, followup, *, manifest=None):
        if ltf.instrument == "DUKASCOPY_GBPUSD":
            raise RuntimeError("injected execution failure")
        return SeamInstrumentResult(
            observations=(), candidate_count=0, candidate_fingerprint="a" * 64,
            trades=(), reconciliation=_reconciliation_for_one_loss(),
        )

    monkeypatch.setattr(
        "research.dukascopy_eurusd_gbpusd.backtest.run_instrument_seam",
        failing_on_second_pair,
    )

    exit_code = main(_run_args(manifest_path, derived_root, output_dir, expected_hash))

    assert exit_code == 1
    assert not output_dir.exists()
    assert _staging_leftovers(output_dir) == []


def test_backtest_command_write_failure_leaves_no_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    manifest_path, derived_root, expected_hash = _prepare_run(tmp_path)
    output_dir = tmp_path / "run-output"

    original_write_bytes = Path.write_bytes
    calls = {"count": 0}

    def flaky_write_bytes(self, data):
        calls["count"] += 1
        if calls["count"] == 2:
            raise OSError("injected write failure")
        return original_write_bytes(self, data)

    monkeypatch.setattr(Path, "write_bytes", flaky_write_bytes)

    exit_code = main(_run_args(manifest_path, derived_root, output_dir, expected_hash))

    assert exit_code == 1
    assert not output_dir.exists()
    assert _staging_leftovers(output_dir) == []


def test_backtest_command_rename_failure_leaves_no_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    manifest_path, derived_root, expected_hash = _prepare_run(tmp_path)
    output_dir = tmp_path / "run-output"

    def failing_replace(src, dst):
        raise OSError("injected rename failure")

    monkeypatch.setattr(os, "replace", failing_replace)

    exit_code = main(_run_args(manifest_path, derived_root, output_dir, expected_hash))

    assert exit_code == 1
    assert not output_dir.exists()
    assert _staging_leftovers(output_dir) == []


def test_backtest_command_rechecks_destination_immediately_before_rename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A destination created concurrently, after the initial absence check
    but before the rename, must still never be touched — whether the pre-
    rename recheck or the rename call itself is what refuses it."""
    import research.dukascopy_eurusd_gbpusd.backtest as backtest_module

    manifest_path, derived_root, expected_hash = _prepare_run(tmp_path)
    output_dir = tmp_path / "run-output"
    original_verify = backtest_module._verify_staging_members

    def verify_then_race(staging, members):
        original_verify(staging, members)
        output_dir.mkdir()
        (output_dir / "marker.txt").write_text("concurrent writer", encoding="utf-8")

    monkeypatch.setattr(backtest_module, "_verify_staging_members", verify_then_race)

    exit_code = main(_run_args(manifest_path, derived_root, output_dir, expected_hash))

    assert exit_code == 1
    assert (output_dir / "marker.txt").read_text(encoding="utf-8") == "concurrent writer"
    assert _staging_leftovers(output_dir) == []


# ---------------------------------------------------------------------------
# REQ-01.2: identical replay across two independent local directories
# ---------------------------------------------------------------------------


def test_backtest_command_replay_is_byte_identical_across_directories(tmp_path: Path):
    manifest_a, derived_a, expected_hash_a = _prepare_run(tmp_path / "site-a")
    manifest_b, derived_b, expected_hash_b = _prepare_run(tmp_path / "elsewhere" / "site-b")
    output_a = tmp_path / "site-a" / "out"
    output_b = tmp_path / "elsewhere" / "site-b-out"

    # same content, different local paths -> same manifest_sha256
    assert expected_hash_a == expected_hash_b

    exit_a = main(_run_args(manifest_a, derived_a, output_a, expected_hash_a))
    exit_b = main(_run_args(manifest_b, derived_b, output_b, expected_hash_b))

    assert exit_a == 0
    assert exit_b == 0
    assert (output_a / "receipt.json").read_bytes() == (output_b / "receipt.json").read_bytes()
    for instrument in ORDERED_PAIRS:
        name = f"{instrument}_trades.json"
        assert (output_a / name).read_bytes() == (output_b / name).read_bytes()
