# Dukascopy derived-intermediate manifest receipt

The deterministic M15, H4, and D1 intermediates were generated from the retained EURUSD and GBPUSD one-minute Bid exports using the research adapter's EET/DST rules. All generated files remain outside the repository.

## Pre-registered configuration

These values are derived from the signed preregistration and adapter contract; they do not depend on external files.

| Field | Value | Authority |
|---|---|---|
| Population start | `2022-08-08` | Signed preregistration |
| Population end | `2026-08-19` | Signed preregistration |
| Timezone label | `EET` | `adapter.EXPECTED_TIMEZONE_LABEL` |
| DST rule | `Europe/Helsinki` | `manifest.REQUIRED_DST_RULE` |
| Day-start config | `00:00:00 EET` | Adapter bucket boundary; midnight wall-clock in Helsinki |
| Offer side | `Bid` | `adapter.EXPECTED_OFFER_SIDE` |
| Timeframe set | `D1`, `H4`, `M15` | `manifest.APPROVED_TIMEFRAME_LABELS` |
| Candidate cutoff end UTC | `2026-08-19T00:00:00Z` | Retained run manifest |
| Outcome follow-up end UTC | `2026-08-19T20:30:00Z` | Retained run manifest |

## Source CSV hashes

The values below were read from the retained run manifest at the external run root. The CSV files remain outside the repository.

| Strategy instrument | External source path | Source SHA-256 |
|---|---|---|
| `DUKASCOPY_EURUSD` | `D:\Josué\Documents\dukascopy-original-2026-09-21\EURUSD_1 Min_Bid_2022.08.08_2026.08.19.csv` | `f43ec0be4cd09f5be0d0b957c9ec87e8e9544c22760a6acf9c2bb677bd2832e6` |
| `DUKASCOPY_GBPUSD` | `D:\Josué\Documents\dukascopy-original-2026-09-21\GBPUSD_1 Min_Bid_2022.08.08_2026.08.19.csv` | `520d5b8391bb8485199ecbe812756937d8fad6ddb3889ee4eb8128d34809a77a` |

## Manifest

| Field | Value |
|---|---|
| Run ID | `dukascopy-eurusd-gbpusd-2026-09-22-001` |
| External run root | `D:\Josué\Documents\dukascopy-run-2026-09-22` |
| Run manifest | `D:\Josué\Documents\dukascopy-run-2026-09-22\run-manifest.json` |
| Manifest SHA-256 (raw file bytes) | `e3c2caafb0a181a167a79d514fc9542886634643f4a543b3fbbd9367c75b745c` |
| Offline-domain receipt SHA-256 | `4ec765f25b49b16b02d45e12a0ffcd69edbd24b0cb98e3607ffefeeed5c4c9ba` |
| Gap-ledger v1 SHA-256 | `d9026e3a1dbcd4a4cad0e826ebe814f95fd5c6f2aeb625393996d780931860f5` |
| Gap-ledger v2 SHA-256 | `85755a70045f7b121278c5a8009aa5de623e96eaba9c371862d44f541bfb398d` |
| Candidate admission cutoff | `2026-08-19T00:00:00Z` |
| Outcome follow-up cutoff | `2026-08-19T20:30:00Z` |
| Source revision | `c37f5bc` |

## Derived outputs

| Output | Rows | SHA-256 |
|---|---:|---|
| `DUKASCOPY_EURUSD_M15.csv` | 100,628 | `490d20cb96a9b01cce24440d402113166238065855db6b65bbd670076bf4d474` |
| `DUKASCOPY_EURUSD_H4.csv` | 6,306 | `746b766e2c29df8e4c61b447b6366b1c52c18a87ab9caa1e202bb2ec8d2c9b41` |
| `DUKASCOPY_EURUSD_D1.csv` | 1,065 | `501f4040b592a960f04f35a0ceaaa26c3cea62ccf8e870ae5f579f0393312010` |
| `DUKASCOPY_GBPUSD_M15.csv` | 100,628 | `e9db3907b0e8630adddd03f733e554c29ce59ee33ce3bebd9606de2598f6bcce` |
| `DUKASCOPY_GBPUSD_H4.csv` | 6,306 | `5f5407ad47e07e82e4235b9a7ef603d2b8972146f2c14105740bb9d0b856c302` |
| `DUKASCOPY_GBPUSD_D1.csv` | 1,065 | `f55db9dd8ce4fccf0d2aff1aef4f8ce03740cc37f858a693319731774adb8b5e` |

The manifest was deserialized successfully through the research manifest validator. No detector signals, outcomes, statistical estimates, baselines, or production files were changed.

## Replay verification

The versioned streaming aggregation runner regenerated all six outputs into a separate external replay directory. Every replayed CSV matched the corresponding manifest SHA-256 exactly. The runner's focused synthetic tests and the full research test suite passed before this replay.
