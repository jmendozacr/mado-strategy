import pytest

from research.dukascopy_eurusd_gbpusd.manifest import (
    APPROVED_STRATEGY_INSTRUMENTS,
    APPROVED_TIMEFRAME_LABELS,
    InputManifestEntry,
    RunManifest,
    build_manifest,
    deserialize_manifest,
    serialize_manifest,
)

# Synthetic SHA-256 digests: 64 lowercase hex characters each.
_SHA_A = "a" * 64
_SHA_B = "b" * 64
_SHA_C = "c" * 64
_SHA_D = "d" * 64

_EURUSD_ENTRY = InputManifestEntry(
    strategy_instrument="DUKASCOPY_EURUSD",
    provider_instrument="EURUSD",
    source_path="/ext/eurusd.csv",
    source_sha256=_SHA_A,
)
_GBPUSD_ENTRY = InputManifestEntry(
    strategy_instrument="DUKASCOPY_GBPUSD",
    provider_instrument="GBPUSD",
    source_path="/ext/gbpusd.csv",
    source_sha256=_SHA_B,
)

_BASE = dict(
    run_id="run-2026-09-22-001",
    population_start="2022-08-08",
    population_end="2026-08-19",
    inputs=[_EURUSD_ENTRY, _GBPUSD_ENTRY],
    timezone_label="EET",
    dst_rule="Europe/Helsinki",
    day_start_config="00:00:00 EET",
    offer_side="Bid",
    timeframe_set={"D1", "H4", "M15"},
    offline_domain_receipt_hash=_SHA_C,
    offline_domain_receipt_reference="openspec/explore/offline-domains-receipt.json",
    protocol_references=["openspec/explore/dukascopy-experiment-proposal-2026-09-20.md"],
    design_reference="openspec/explore/dukascopy-research-adapter-design-2026-09-22.md",
    adapter_source_reference="research/dukascopy_eurusd_gbpusd/adapter.py",
    output_hashes={"eurusd_d1.parquet": _SHA_D},
    exclusion_ledger_reference="runs/run-2026-09-22-001/exclusion-ledger.json",
)


def _build(**overrides: object) -> RunManifest:
    return build_manifest(**{**_BASE, **overrides})


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_build_manifest_happy_path() -> None:
    m = _build()
    assert m.run_id == "run-2026-09-22-001"
    assert m.population_start == "2022-08-08"
    assert m.population_end == "2026-08-19"
    assert m.timezone_label == "EET"
    assert m.dst_rule == "Europe/Helsinki"
    assert m.offer_side == "Bid"
    assert set(m.timeframe_set) == {"D1", "H4", "M15"}


def test_manifest_records_both_strategy_identities() -> None:
    m = _build()
    assert {e.strategy_instrument for e in m.inputs} == {
        "DUKASCOPY_EURUSD",
        "DUKASCOPY_GBPUSD",
    }


def test_manifest_records_provider_labels() -> None:
    m = _build()
    assert {e.provider_instrument for e in m.inputs} == {"EURUSD", "GBPUSD"}


def test_manifest_records_source_paths_and_sha256() -> None:
    m = _build()
    by_strategy = {e.strategy_instrument: e for e in m.inputs}
    assert by_strategy["DUKASCOPY_EURUSD"].source_path == "/ext/eurusd.csv"
    assert by_strategy["DUKASCOPY_EURUSD"].source_sha256 == _SHA_A
    assert by_strategy["DUKASCOPY_GBPUSD"].source_path == "/ext/gbpusd.csv"
    assert by_strategy["DUKASCOPY_GBPUSD"].source_sha256 == _SHA_B


def test_manifest_records_offline_domain_receipt() -> None:
    m = _build()
    assert m.offline_domain_receipt_hash == _SHA_C
    assert m.offline_domain_receipt_reference == "openspec/explore/offline-domains-receipt.json"


def test_manifest_records_protocol_and_design_references() -> None:
    m = _build()
    assert "openspec/explore/dukascopy-experiment-proposal-2026-09-20.md" in m.protocol_references
    assert m.design_reference == "openspec/explore/dukascopy-research-adapter-design-2026-09-22.md"
    assert m.adapter_source_reference == "research/dukascopy_eurusd_gbpusd/adapter.py"


def test_manifest_records_output_hashes() -> None:
    m = _build()
    assert ("eurusd_d1.parquet", _SHA_D) in m.output_hashes


def test_manifest_records_exclusion_ledger_reference() -> None:
    m = _build()
    assert m.exclusion_ledger_reference == "runs/run-2026-09-22-001/exclusion-ledger.json"


# ---------------------------------------------------------------------------
# Identity rejection
# ---------------------------------------------------------------------------

def test_manifest_rejects_unknown_strategy_instrument() -> None:
    bad = InputManifestEntry(
        strategy_instrument="UNKNOWN_INSTRUMENT",
        provider_instrument="EURUSD",
        source_path="/ext/eurusd.csv",
        source_sha256=_SHA_A,
    )
    with pytest.raises(ValueError, match="not in approved set"):
        _build(inputs=[bad, _GBPUSD_ENTRY])


def test_manifest_rejects_mismatched_provider_strategy_pair() -> None:
    # EURUSD provider must map to DUKASCOPY_EURUSD, not DUKASCOPY_GBPUSD.
    bad = InputManifestEntry(
        strategy_instrument="DUKASCOPY_GBPUSD",
        provider_instrument="EURUSD",
        source_path="/ext/eurusd.csv",
        source_sha256=_SHA_A,
    )
    with pytest.raises(ValueError, match="maps to strategy_instrument"):
        _build(inputs=[bad, _GBPUSD_ENTRY])


def test_manifest_requires_both_instruments() -> None:
    with pytest.raises(ValueError, match="missing"):
        _build(inputs=[_EURUSD_ENTRY])


def test_manifest_rejects_empty_inputs() -> None:
    with pytest.raises(ValueError, match="inputs must not be empty"):
        _build(inputs=[])


def test_manifest_rejects_duplicate_strategy_instrument() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        _build(inputs=[_EURUSD_ENTRY, _EURUSD_ENTRY, _GBPUSD_ENTRY])


# ---------------------------------------------------------------------------
# Offer side / timezone / DST rule
# ---------------------------------------------------------------------------

def test_manifest_rejects_wrong_offer_side() -> None:
    with pytest.raises(ValueError, match="offer_side"):
        _build(offer_side="Ask")


def test_manifest_rejects_wrong_timezone_label() -> None:
    with pytest.raises(ValueError, match="timezone_label"):
        _build(timezone_label="UTC")


def test_manifest_rejects_wrong_dst_rule() -> None:
    with pytest.raises(ValueError, match="dst_rule"):
        _build(dst_rule="Europe/London")


def test_manifest_rejects_empty_day_start_config() -> None:
    with pytest.raises(ValueError, match="day_start_config"):
        _build(day_start_config="")


# ---------------------------------------------------------------------------
# Hash validation
# ---------------------------------------------------------------------------

def test_manifest_rejects_malformed_source_sha256() -> None:
    bad = InputManifestEntry(
        strategy_instrument="DUKASCOPY_EURUSD",
        provider_instrument="EURUSD",
        source_path="/ext/eurusd.csv",
        source_sha256="not-a-valid-hash",
    )
    with pytest.raises(ValueError, match="SHA-256"):
        _build(inputs=[bad, _GBPUSD_ENTRY])


def test_manifest_accepts_and_normalizes_uppercase_source_sha256() -> None:
    upper_entry = InputManifestEntry(
        strategy_instrument="DUKASCOPY_EURUSD",
        provider_instrument="EURUSD",
        source_path="/ext/eurusd.csv",
        source_sha256="A" * 64,
    )
    m = _build(inputs=[upper_entry, _GBPUSD_ENTRY])
    by_strategy = {e.strategy_instrument: e for e in m.inputs}
    assert by_strategy["DUKASCOPY_EURUSD"].source_sha256 == "a" * 64


def test_manifest_accepts_and_normalizes_uppercase_receipt_hash() -> None:
    m = _build(offline_domain_receipt_hash="C" * 64)
    assert m.offline_domain_receipt_hash == "c" * 64


def test_manifest_accepts_and_normalizes_uppercase_output_hash() -> None:
    m = _build(output_hashes={"eurusd_d1.parquet": "D" * 64})
    assert dict(m.output_hashes)["eurusd_d1.parquet"] == "d" * 64


def test_manifest_accepts_and_normalizes_mixed_case_sha256() -> None:
    mixed = "aAbBcCdDeEfF" + "0" * 52  # 64 chars, mixed case
    m = _build(offline_domain_receipt_hash=mixed)
    assert m.offline_domain_receipt_hash == mixed.lower()


def test_manifest_rejects_short_source_sha256() -> None:
    bad = InputManifestEntry(
        strategy_instrument="DUKASCOPY_EURUSD",
        provider_instrument="EURUSD",
        source_path="/ext/eurusd.csv",
        source_sha256="abc123",
    )
    with pytest.raises(ValueError, match="SHA-256"):
        _build(inputs=[bad, _GBPUSD_ENTRY])


def test_manifest_rejects_malformed_receipt_hash() -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        _build(offline_domain_receipt_hash="tooshort")


def test_manifest_rejects_malformed_output_hash() -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        _build(output_hashes={"eurusd_d1.parquet": "bad"})


# ---------------------------------------------------------------------------
# Run ID and population dates
# ---------------------------------------------------------------------------

def test_manifest_rejects_empty_run_id() -> None:
    with pytest.raises(ValueError, match="run_id"):
        _build(run_id="")


def test_manifest_rejects_invalid_population_start() -> None:
    with pytest.raises(ValueError, match="population_start"):
        _build(population_start="not-a-date")


def test_manifest_rejects_invalid_population_end() -> None:
    with pytest.raises(ValueError, match="population_end"):
        _build(population_end="2026/08/19")


def test_manifest_rejects_population_end_before_start() -> None:
    with pytest.raises(ValueError, match="population_start"):
        _build(population_start="2026-08-19", population_end="2022-08-08")


def test_manifest_same_start_and_end_accepted() -> None:
    m = _build(population_start="2024-01-15", population_end="2024-01-15")
    assert m.population_start == m.population_end


# ---------------------------------------------------------------------------
# Timeframe set
# ---------------------------------------------------------------------------

def test_manifest_rejects_incomplete_timeframe_set() -> None:
    with pytest.raises(ValueError, match="timeframe_set"):
        _build(timeframe_set={"D1", "H4"})


def test_manifest_rejects_extra_timeframe() -> None:
    with pytest.raises(ValueError, match="timeframe_set"):
        _build(timeframe_set={"D1", "H4", "M15", "M5"})


def test_manifest_rejects_empty_timeframe_set() -> None:
    with pytest.raises(ValueError, match="timeframe_set"):
        _build(timeframe_set=set())


# ---------------------------------------------------------------------------
# Required reference fields
# ---------------------------------------------------------------------------

def test_manifest_rejects_empty_protocol_references() -> None:
    with pytest.raises(ValueError, match="protocol_references"):
        _build(protocol_references=[])


def test_manifest_rejects_empty_design_reference() -> None:
    with pytest.raises(ValueError, match="design_reference"):
        _build(design_reference="")


def test_manifest_rejects_empty_adapter_source_reference() -> None:
    with pytest.raises(ValueError, match="adapter_source_reference"):
        _build(adapter_source_reference="")


def test_manifest_rejects_empty_offline_domain_receipt_reference() -> None:
    with pytest.raises(ValueError, match="offline_domain_receipt_reference"):
        _build(offline_domain_receipt_reference="")


def test_manifest_rejects_empty_exclusion_ledger_reference() -> None:
    with pytest.raises(ValueError, match="exclusion_ledger_reference"):
        _build(exclusion_ledger_reference="")


def test_manifest_rejects_empty_output_hashes() -> None:
    with pytest.raises(ValueError, match="output_hashes"):
        _build(output_hashes={})


def test_manifest_rejects_empty_source_path() -> None:
    bad = InputManifestEntry(
        strategy_instrument="DUKASCOPY_EURUSD",
        provider_instrument="EURUSD",
        source_path="",
        source_sha256=_SHA_A,
    )
    with pytest.raises(ValueError, match="source_path"):
        _build(inputs=[bad, _GBPUSD_ENTRY])


# ---------------------------------------------------------------------------
# Deterministic ordering
# ---------------------------------------------------------------------------

def test_timeframe_set_stored_sorted() -> None:
    m = _build()
    assert list(m.timeframe_set) == sorted(m.timeframe_set)


def test_output_hashes_stored_sorted_by_name() -> None:
    m = _build(
        output_hashes={
            "z_file.parquet": _SHA_D,
            "a_file.parquet": _SHA_C,
        }
    )
    names = [pair[0] for pair in m.output_hashes]
    assert names == sorted(names)


def test_inputs_sorted_by_strategy_instrument_regardless_of_caller_order() -> None:
    # Pass GBPUSD first, then EURUSD — stored order must be alphabetical.
    m = _build(inputs=[_GBPUSD_ENTRY, _EURUSD_ENTRY])
    stored = [e.strategy_instrument for e in m.inputs]
    assert stored == sorted(stored)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def test_serialization_is_stable() -> None:
    m = _build()
    assert serialize_manifest(m) == serialize_manifest(m)


def test_same_inputs_produce_identical_json() -> None:
    m1 = _build()
    m2 = _build()
    assert serialize_manifest(m1) == serialize_manifest(m2)


def test_serialization_stable_under_input_reorder() -> None:
    # Input order [EUR, GBP] vs [GBP, EUR] must produce byte-identical JSON.
    m1 = _build(inputs=[_EURUSD_ENTRY, _GBPUSD_ENTRY])
    m2 = _build(inputs=[_GBPUSD_ENTRY, _EURUSD_ENTRY])
    assert serialize_manifest(m1) == serialize_manifest(m2)


def test_serialization_does_not_contain_runtime_fields() -> None:
    text = serialize_manifest(_build())
    assert "created_at" not in text
    assert '"timestamp"' not in text
    assert "generated_at" not in text


def test_serialization_contains_all_manifest_fields() -> None:
    text = serialize_manifest(_build())
    for field in (
        "run_id",
        "population_start",
        "population_end",
        "inputs",
        "timezone_label",
        "dst_rule",
        "day_start_config",
        "offer_side",
        "timeframe_set",
        "offline_domain_receipt_hash",
        "offline_domain_receipt_reference",
        "protocol_references",
        "design_reference",
        "adapter_source_reference",
        "output_hashes",
        "exclusion_ledger_reference",
    ):
        assert f'"{field}"' in text, f"missing field in JSON: {field}"


def test_manifest_round_trips_through_json() -> None:
    m = _build()
    restored = deserialize_manifest(serialize_manifest(m))
    assert m == restored


def test_deserialized_manifest_is_fully_validated() -> None:
    # Tamper with the serialized JSON to sneak in a bad offer_side.
    import json

    m = _build()
    d = json.loads(serialize_manifest(m))
    d["offer_side"] = "Ask"
    with pytest.raises(ValueError, match="offer_side"):
        deserialize_manifest(json.dumps(d))


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_approved_strategy_instruments_constant() -> None:
    assert APPROVED_STRATEGY_INSTRUMENTS == {"DUKASCOPY_EURUSD", "DUKASCOPY_GBPUSD"}


def test_approved_timeframe_labels_constant() -> None:
    assert APPROVED_TIMEFRAME_LABELS == {"D1", "H4", "M15"}
