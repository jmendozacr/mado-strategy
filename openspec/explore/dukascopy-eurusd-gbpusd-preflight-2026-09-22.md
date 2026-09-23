# EURUSD + GBPUSD experiment preflight

## Result

The retained Dukascopy files are present and hash-valid, but the existing frozen runner cannot execute this experiment unchanged. A research-only adapter/manifest seam is required; production code, the original three-instrument manifest, and the original baseline remain untouched.

## Data receipt verification

| Provider instrument | Local file | Bytes | SHA-256 |
|---------------------|------------|------:|---------|
| EURUSD | `D:\Josué\Documents\EURUSD_1 Min_Bid_2022.08.08_2026.08.19.csv` | 88,625,458 | `F43EC0BE4CD09F5BE0D0B957C9EC87E8E9544C22760A6ACF9C2BB677BD2832E6` |
| GBPUSD | `D:\Josué\Documents\GBPUSD_1 Min_Bid_2022.08.08_2026.08.19.csv` | 88,122,339 | `520D5B8391BB8485199ECBE812756937D8FAD6DDB3889EE4EB8128D34809A77A` |

The files remain outside the repository. No copy, conversion, or mutation was performed.

## Compatibility findings

- The existing manifest enforces the frozen `+0.20R` MEI and the original four policy IDs.
- The existing statistical specification freezes instrument order `EURUSDm`, `GBPUSDm`, `DXYm`; it is not a two-instrument Dukascopy manifest.
- Existing adapter tests and dataset records use internal identities such as `EURUSDm` and `GBPUSDm`, while the provider files are labeled `EURUSD` and `GBPUSD`. The experiment must preserve both identities as separate provenance fields; no silent rename or cross-provider equivalence is allowed.
- The Dukascopy files are 1-minute Bid exports, while the frozen real-data corpus and Layer-2 contracts reference other granularities and provider-specific dataset records. A deterministic research-only transformation and provenance record are required before any outcome run.
- `is_execution_authorized` remains false until the existing Layer-2/Layer-3 baseline conditions are satisfied. No real-data runner was invoked.

## Required next design decisions

1. Define a research-only provider adapter that preserves raw Dukascopy identity and maps to the strategy's required timeframes without editing production modules.
2. Define the exact deterministic 1-minute-to-strategy-timeframe aggregation, timezone conversion, and closure-gap allowlist before outcome construction.
3. Define how the two-instrument experiment's manifest and policy population are isolated from the frozen three-instrument manifest.
4. Record the adapter source hash and generated intermediate-file hashes before any statistics.

## Tooling note

CodeGraph was unavailable on this host (`gentle-ai codegraph` and the upstream `codegraph` command were not installed). The preflight therefore used bounded read-only text inspection as a documented fallback.

Status: preflight complete; execution blocked pending research-only adapter design. No statistics, production changes, dataset mutation, or baseline update occurred.
