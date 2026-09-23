# Dukascopy research-only adapter design

## Purpose

Provide an isolated, deterministic ingestion seam for the signed EURUSD + GBPUSD experiment without changing production modules, the frozen three-instrument manifest, or the original dataset identity.

## Boundary

Proposed location: `research/dukascopy_eurusd_gbpusd/`.

Approved experiment-local identities are `DUKASCOPY_EURUSD` and `DUKASCOPY_GBPUSD`. The raw provider labels `EURUSD` and `GBPUSD` remain separate provenance fields.

The adapter may read the two external JForex CSVs and the retained offline-domain receipt, but it must not import into or mutate `detector/`, production datasets, or archived protocol artifacts. Raw provider files remain outside the repository.

## Input contract

Each input record carries both identities:

| Field | Meaning |
|-------|---------|
| `provider_instrument` | Raw Dukascopy label: `EURUSD` or `GBPUSD`. |
| `strategy_instrument` | Experiment-local identity used by the adapter; never silently substituted for the provider label. |
| `source_path` | External absolute path recorded in the run manifest. |
| `source_sha256` | Hash verified before parsing. |
| `timezone_label` | Raw `EET` label preserved exactly. |
| `offer_side` | `Bid`. |

The parser must reject malformed rows, wrong headers, duplicate timestamps, non-finite prices, and hash drift.

## Time and aggregation contract

1. Parse the raw EET label with the official DST rule: UTC+2 standard time and UTC+3 daylight time.
2. Preserve the original EET timestamp string and derive a UTC instant for ordering and joins.
3. Do not infer a fixed offset from one date.
4. Aggregate only after the timezone conversion rule and session boundary are frozen.
5. Produce deterministic `D1`, `H4`, and `M15` strategy timeframes required by the existing outcome path.
6. Preserve raw EET labels for session interpretation, derive UTC instants for ordering, and emit an explicit day-start configuration in the experiment manifest. No implicit fixed offset is permitted.

## Closure and gap contract

- Load the retained `getOfflineTimeDomains` result as evidence, not as an authoritative calendar.
- Convert its UTC boundaries alongside the raw EET-to-UTC mapping.
- A regular weekend or special domain may explain a boundary only when the retained receipt matches the requested instrument and range.
- Any unexplained gap affecting a required setup or outcome is unresolved and fail-closed.
- Zero-volume rows remain observations; they never become closure labels automatically.
- The adapter emits an exclusion ledger rather than silently dropping affected windows.

## Output contract

The research run directory must retain:

- parsed/aggregated intermediate-file hashes;
- provider and strategy identity mapping;
- timezone and day-start configuration;
- offline-domain evidence hash and retrieval metadata;
- deterministic gap allowlist and exclusion ledger;
- adapter source commit and source hash;
- protocol and JForex receipt references.

No raw provider CSV is copied into the repository by default.

Derived intermediates and manifests use the approved external run root:
`D:\Josué\Documents\dukascopy-eurusd-gbpusd-runs\`.

The research runner may consume these normalized inputs through the existing canonical EST-B path in read-only mode. No production module imports the research adapter, and no frozen production manifest is modified.

## Test-first plan

Before implementation, add isolated tests for:

- header and identity validation;
- EET standard/DST conversion around both transitions;
- duplicate and missing-minute rejection;
- deterministic 1-minute aggregation and day-start alignment;
- weekend and special-domain matching;
- zero-volume handling;
- fail-closed unresolved gaps;
- repeated-run hashes and stable output ordering.

Tests must use synthetic fixtures only until the preflight gate authorizes a local data run. No test may weaken or edit the frozen production test suite.

## Approved design gates

1. Strategy timeframe set: `D1`, `H4`, and `M15`; day-start configuration is explicit and DST-aware.
2. Experiment-local identities: `DUKASCOPY_EURUSD` and `DUKASCOPY_GBPUSD`.
3. Derived run root: `D:\Josué\Documents\dukascopy-eurusd-gbpusd-runs\`.
4. The adapter remains research-only and has no production import path.

Status: signed design. No adapter code, statistics, production changes, or dataset mutation has occurred.
