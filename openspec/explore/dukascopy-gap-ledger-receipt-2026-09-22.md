# Dukascopy gap-ledger receipt

This receipt records the streaming gap scan over the retained EURUSD and GBPUSD JForex exports. The raw CSV files and generated ledger remain outside the repository.

## Artifacts

| Artifact | External reference | SHA-256 |
|---|---|---|
| Offline-domain receipt | `D:\Josué\Documents\DukascopyOfflineDomainsProbeV2-normalized.json` | `4ec765f25b49b16b02d45e12a0ffcd69edbd24b0cb98e3607ffefeeed5c4c9ba` |
| Retained gap ledger v1 | `D:\Josué\Documents\Dukascopy-gap-ledger-2026-09-22.json` | `d9026e3a1dbcd4a4cad0e826ebe814f95fd5c6f2aeb625393996d780931860f5` |
| Schema-upgraded gap ledger v2 | `D:\Josué\Documents\Dukascopy-gap-ledger-2026-09-22-v2.json` | `85755a70045f7b121278c5a8009aa5de623e96eaba9c371862d44f541bfb398d` |

The v2 ledger has `dukascopy-gap-ledger/v2` schema and preserves a `derived_from` reference to the v1 path and hash. It adds `date_eet`, `setup`, `cause`, and `source_evidence` deterministically from the retained v1 ledger, the retained run manifest, and the normalized offline-domain receipt. This is a schema migration, not a second CSV scan.

## Scan results

| Strategy identity | Rows | Gaps | Explained | Unresolved | Zero-volume rows |
|---|---:|---:|---:|---:|---:|
| `DUKASCOPY_EURUSD` | 1,509,415 | 215 | 215 | 0 | 14,745 |
| `DUKASCOPY_GBPUSD` | 1,509,415 | 215 | 215 | 0 | 8,461 |

The two files share the same gap count and the same retained offline-domain set. The scan validated the exact JForex header, monotonic timestamps, and finite numeric fields while reading each CSV in streaming mode.

## Christmas and year-boundary candidates

The seven candidates are the EURUSD closure spanning Christmas Day in 2022, the Christmas closures in 2023–2025, and the three year-boundary closures in 2023/24–2025/26. This definition does not treat every December or January weekend as a candidate. Every listed gap is fully covered by the indexed `EUR/USD` domain in the retained receipt.

| EET date | Interval start UTC | Interval end UTC | Receipt domain | Covering domain |
|---|---|---|---|---|
| `2022-12-24` | `2022-12-23T22:00:00Z` | `2022-12-25T22:00:00Z` | `EUR/USD#20` | `2022-12-23T22:00:00Z->2022-12-25T22:00:00Z` |
| `2023-12-25` | `2023-12-25T07:59:00Z` | `2023-12-25T22:01:00Z` | `EUR/USD#73` | `2023-12-25T07:59:00Z->2023-12-25T22:01:00Z` |
| `2023-12-30` | `2023-12-29T22:00:00Z` | `2024-01-01T22:00:00Z` | `EUR/USD#74` | `2023-12-29T22:00:00Z->2024-01-01T22:00:00Z` |
| `2024-12-25` | `2024-12-25T08:00:00Z` | `2024-12-25T22:00:00Z` | `EUR/USD#126` | `2024-12-25T08:00:00Z->2024-12-25T22:00:00Z` |
| `2025-01-01` | `2024-12-31T22:00:00Z` | `2025-01-01T22:00:00Z` | `EUR/USD#128` | `2024-12-31T22:00:00Z->2025-01-01T22:00:00Z` |
| `2025-12-25` | `2025-12-25T07:59:00Z` | `2025-12-25T22:00:00Z` | `EUR/USD#180` | `2025-12-25T07:59:00Z->2025-12-25T22:00:00Z` |
| `2025-12-31` | `2025-12-31T21:59:00Z` | `2026-01-01T22:00:00Z` | `EUR/USD#182` | `2025-12-31T21:59:00Z->2026-01-01T22:00:00Z` |

### One-minute offset treatment

The receipt reports one-minute boundary offsets in three candidates: `EUR/USD#73` ends at `22:01Z`, while `EUR/USD#180` and `EUR/USD#182` start at `07:59Z` and `21:59Z`, respectively. These are retained exactly as returned; no calendar normalization is applied. The fail-closed rule accepts a domain only when its recorded UTC interval fully covers the raw-series gap.

## Interpretation boundary

All observed missing-minute intervals were fully covered by the retained `getOfflineTimeDomains` output, so no raw-series gap was excluded by the approved fail-closed rule. This does not convert the API output into a complete immutable closure calendar. Zero-volume rows were preserved and counted separately; they were not used as closure evidence.

The first and last UTC timestamps are `2022-08-07T21:00:00Z` and `2026-08-19T20:59:00Z`, respectively, because the source timestamps are EET-labelled and the conversion is DST-aware.
