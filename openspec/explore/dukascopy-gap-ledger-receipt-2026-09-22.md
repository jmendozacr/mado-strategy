# Dukascopy gap-ledger receipt

This receipt records the streaming gap scan over the retained EURUSD and GBPUSD JForex exports. The raw CSV files and generated ledger remain outside the repository.

## Artifacts

| Artifact | External reference | SHA-256 |
|---|---|---|
| Offline-domain receipt | `D:\Josué\Documents\DukascopyOfflineDomainsProbeV2-normalized.json` | `4ec765f25b49b16b02d45e12a0ffcd69edbd24b0cb98e3607ffefeeed5c4c9ba` |
| Gap ledger | `D:\Josué\Documents\Dukascopy-gap-ledger-2026-09-22.json` | `d9026e3a1dbcd4a4cad0e826ebe814f95fd5c6f2aeb625393996d780931860f5` |

## Scan results

| Strategy identity | Rows | Gaps | Explained | Unresolved | Zero-volume rows |
|---|---:|---:|---:|---:|---:|
| `DUKASCOPY_EURUSD` | 1,509,415 | 215 | 215 | 0 | 14,745 |
| `DUKASCOPY_GBPUSD` | 1,509,415 | 215 | 215 | 0 | 8,461 |

The two files share the same gap count and the same retained offline-domain set. The scan validated the exact JForex header, monotonic timestamps, and finite numeric fields while reading each CSV in streaming mode.

## Interpretation boundary

All observed missing-minute intervals were fully covered by the retained `getOfflineTimeDomains` output, so no raw-series gap was excluded by the approved fail-closed rule. This does not convert the API output into a complete immutable closure calendar. Zero-volume rows were preserved and counted separately; they were not used as closure evidence.

The first and last UTC timestamps are `2022-08-07T21:00:00Z` and `2026-08-19T20:59:00Z`, respectively, because the source timestamps are EET-labelled and the conversion is DST-aware.

