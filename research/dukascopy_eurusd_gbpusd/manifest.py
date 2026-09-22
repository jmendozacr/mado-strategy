"""
Run-manifest contract for the Dukascopy EURUSD + GBPUSD research experiment.

Research-only. Not imported by any production module.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date

from research.dukascopy_eurusd_gbpusd.adapter import (
    EXPECTED_OFFER_SIDE,
    EXPECTED_TIMEZONE_LABEL,
    PROVIDER_TO_STRATEGY,
)

# Approved strategy identities for this experiment, derived from the adapter contract.
APPROVED_STRATEGY_INSTRUMENTS: frozenset[str] = frozenset(PROVIDER_TO_STRATEGY.values())

# Timeframe labels required by the outcome path (D1=1440 min, H4=240 min, M15=15 min).
APPROVED_TIMEFRAME_LABELS: frozenset[str] = frozenset({"D1", "H4", "M15"})

# Sole authoritative DST rule for the EET label: UTC+2 standard / UTC+3 daylight.
REQUIRED_DST_RULE = "Europe/Helsinki"

_HEX64_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def _require_sha256(value: str, field: str) -> str:
    """Validate that value is a 64-character hex SHA-256 digest; return it normalized to lowercase."""
    if not _HEX64_RE.match(value):
        raise ValueError(
            f"{field} must be a 64-character hex SHA-256 digest, got {value!r}"
        )
    return value.lower()


@dataclass(frozen=True)
class InputManifestEntry:
    """Provenance record for one external JForex CSV input file."""

    strategy_instrument: str  # experiment-local identity: "DUKASCOPY_EURUSD" or "DUKASCOPY_GBPUSD"
    provider_instrument: str  # raw Dukascopy label: "EURUSD" or "GBPUSD"
    source_path: str          # absolute external path; file never copied into the repo
    source_sha256: str        # 64-char lowercase hex SHA-256 of the source file


@dataclass(frozen=True)
class RunManifest:
    """
    Immutable, deterministic provenance record for one Dukascopy research run.

    All fields are validated at construction via build_manifest().  No runtime
    state (e.g. timestamps generated at construction time) is stored.
    """

    run_id: str
    population_start: str                       # ISO date YYYY-MM-DD
    population_end: str                         # ISO date YYYY-MM-DD
    inputs: tuple[InputManifestEntry, ...]
    timezone_label: str                         # must be "EET"
    dst_rule: str                               # must be "Europe/Helsinki"
    day_start_config: str                       # e.g. "00:00:00 EET"; explicit, DST-aware
    offer_side: str                             # must be "Bid"
    timeframe_set: tuple[str, ...]              # sorted; must equal {"D1", "H4", "M15"}
    offline_domain_receipt_hash: str            # 64-char hex SHA-256 of the retained receipt
    offline_domain_receipt_reference: str       # path or URL to the getOfflineTimeDomains receipt
    protocol_references: tuple[str, ...]        # at least one: proposal / pre-access docs
    design_reference: str                       # path to the signed adapter design doc
    adapter_source_reference: str               # git ref or relative path to adapter.py
    output_hashes: tuple[tuple[str, str], ...]  # sorted (artifact-name, sha256) pairs
    exclusion_ledger_reference: str             # path to the exclusion-ledger artifact


def build_manifest(
    *,
    run_id: str,
    population_start: str,
    population_end: str,
    inputs: list[InputManifestEntry],
    timezone_label: str,
    dst_rule: str,
    day_start_config: str,
    offer_side: str,
    timeframe_set: frozenset[str] | set[str],
    offline_domain_receipt_hash: str,
    offline_domain_receipt_reference: str,
    protocol_references: list[str] | tuple[str, ...],
    design_reference: str,
    adapter_source_reference: str,
    output_hashes: dict[str, str],
    exclusion_ledger_reference: str,
) -> RunManifest:
    """Validate all fields and return an immutable RunManifest.

    Raises ValueError for any validation failure: unknown strategy identity,
    wrong offer side or timezone, malformed hash, invalid date range, missing
    required field, or wrong timeframe set.
    """
    if not run_id:
        raise ValueError("run_id must not be empty")

    # Population window
    try:
        start_date = date.fromisoformat(population_start)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"invalid population_start {population_start!r}: {exc}") from exc
    try:
        end_date = date.fromisoformat(population_end)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"invalid population_end {population_end!r}: {exc}") from exc
    if start_date > end_date:
        raise ValueError(
            f"population_start {population_start!r} must not be after"
            f" population_end {population_end!r}"
        )

    # Inputs
    if not inputs:
        raise ValueError("inputs must not be empty")
    normalized_inputs: list[InputManifestEntry] = []
    covered: set[str] = set()
    for i, entry in enumerate(inputs):
        if entry.strategy_instrument not in APPROVED_STRATEGY_INSTRUMENTS:
            raise ValueError(
                f"inputs[{i}].strategy_instrument {entry.strategy_instrument!r}"
                f" not in approved set {sorted(APPROVED_STRATEGY_INSTRUMENTS)}"
            )
        # Provider/strategy pair must match the adapter's declared mapping.
        expected_strategy = PROVIDER_TO_STRATEGY.get(entry.provider_instrument)
        if expected_strategy != entry.strategy_instrument:
            raise ValueError(
                f"inputs[{i}]: provider_instrument {entry.provider_instrument!r}"
                f" maps to strategy_instrument {expected_strategy!r},"
                f" but declared {entry.strategy_instrument!r}"
            )
        if not entry.source_path:
            raise ValueError(f"inputs[{i}].source_path must not be empty")
        norm_sha = _require_sha256(entry.source_sha256, f"inputs[{i}].source_sha256")
        normalized_inputs.append(
            InputManifestEntry(
                strategy_instrument=entry.strategy_instrument,
                provider_instrument=entry.provider_instrument,
                source_path=entry.source_path,
                source_sha256=norm_sha,
            )
        )
        covered.add(entry.strategy_instrument)

    missing = APPROVED_STRATEGY_INSTRUMENTS - covered
    if missing:
        raise ValueError(
            f"inputs must cover all approved strategy instruments;"
            f" missing: {sorted(missing)}"
        )

    # Timezone and DST rule
    if timezone_label != EXPECTED_TIMEZONE_LABEL:
        raise ValueError(
            f"timezone_label must be {EXPECTED_TIMEZONE_LABEL!r}, got {timezone_label!r}"
        )
    if dst_rule != REQUIRED_DST_RULE:
        raise ValueError(
            f"dst_rule must be {REQUIRED_DST_RULE!r}, got {dst_rule!r}"
        )
    if not day_start_config:
        raise ValueError("day_start_config must not be empty")

    # Offer side
    if offer_side != EXPECTED_OFFER_SIDE:
        raise ValueError(
            f"offer_side must be {EXPECTED_OFFER_SIDE!r}, got {offer_side!r}"
        )

    # Timeframe set — must be exactly the approved triplet
    timeframe_frozen = frozenset(timeframe_set)
    if timeframe_frozen != APPROVED_TIMEFRAME_LABELS:
        raise ValueError(
            f"timeframe_set must be {sorted(APPROVED_TIMEFRAME_LABELS)},"
            f" got {sorted(timeframe_frozen)}"
        )

    # Offline-domain receipt
    offline_domain_receipt_hash = _require_sha256(offline_domain_receipt_hash, "offline_domain_receipt_hash")
    if not offline_domain_receipt_reference:
        raise ValueError("offline_domain_receipt_reference must not be empty")

    # Reference fields
    if not protocol_references:
        raise ValueError("protocol_references must contain at least one entry")
    if not design_reference:
        raise ValueError("design_reference must not be empty")
    if not adapter_source_reference:
        raise ValueError("adapter_source_reference must not be empty")

    # Output hashes
    output_hashes = {
        name: _require_sha256(digest, f"output_hashes[{name!r}]")
        for name, digest in output_hashes.items()
    }

    # Exclusion ledger
    if not exclusion_ledger_reference:
        raise ValueError("exclusion_ledger_reference must not be empty")

    return RunManifest(
        run_id=run_id,
        population_start=population_start,
        population_end=population_end,
        inputs=tuple(normalized_inputs),
        timezone_label=timezone_label,
        dst_rule=dst_rule,
        day_start_config=day_start_config,
        offer_side=offer_side,
        timeframe_set=tuple(sorted(timeframe_set)),
        offline_domain_receipt_hash=offline_domain_receipt_hash,
        offline_domain_receipt_reference=offline_domain_receipt_reference,
        protocol_references=tuple(protocol_references),
        design_reference=design_reference,
        adapter_source_reference=adapter_source_reference,
        output_hashes=tuple(sorted(output_hashes.items())),
        exclusion_ledger_reference=exclusion_ledger_reference,
    )


def serialize_manifest(manifest: RunManifest) -> str:
    """Return deterministic JSON. No runtime state is included."""
    d = {
        "run_id": manifest.run_id,
        "population_start": manifest.population_start,
        "population_end": manifest.population_end,
        "inputs": [
            {
                "strategy_instrument": e.strategy_instrument,
                "provider_instrument": e.provider_instrument,
                "source_path": e.source_path,
                "source_sha256": e.source_sha256,
            }
            for e in manifest.inputs
        ],
        "timezone_label": manifest.timezone_label,
        "dst_rule": manifest.dst_rule,
        "day_start_config": manifest.day_start_config,
        "offer_side": manifest.offer_side,
        "timeframe_set": list(manifest.timeframe_set),
        "offline_domain_receipt_hash": manifest.offline_domain_receipt_hash,
        "offline_domain_receipt_reference": manifest.offline_domain_receipt_reference,
        "protocol_references": list(manifest.protocol_references),
        "design_reference": manifest.design_reference,
        "adapter_source_reference": manifest.adapter_source_reference,
        "output_hashes": dict(manifest.output_hashes),
        "exclusion_ledger_reference": manifest.exclusion_ledger_reference,
    }
    return json.dumps(d, sort_keys=True, indent=2)


def deserialize_manifest(text: str) -> RunManifest:
    """Reconstruct a validated RunManifest from JSON produced by serialize_manifest."""
    d = json.loads(text)
    inputs = [
        InputManifestEntry(
            strategy_instrument=e["strategy_instrument"],
            provider_instrument=e["provider_instrument"],
            source_path=e["source_path"],
            source_sha256=e["source_sha256"],
        )
        for e in d["inputs"]
    ]
    return build_manifest(
        run_id=d["run_id"],
        population_start=d["population_start"],
        population_end=d["population_end"],
        inputs=inputs,
        timezone_label=d["timezone_label"],
        dst_rule=d["dst_rule"],
        day_start_config=d["day_start_config"],
        offer_side=d["offer_side"],
        timeframe_set=set(d["timeframe_set"]),
        offline_domain_receipt_hash=d["offline_domain_receipt_hash"],
        offline_domain_receipt_reference=d["offline_domain_receipt_reference"],
        protocol_references=d["protocol_references"],
        design_reference=d["design_reference"],
        adapter_source_reference=d["adapter_source_reference"],
        output_hashes=dict(d["output_hashes"]),
        exclusion_ledger_reference=d["exclusion_ledger_reference"],
    )
