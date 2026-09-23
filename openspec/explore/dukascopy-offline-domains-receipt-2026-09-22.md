# Dukascopy offline-domain receipt

This receipt records the complete `getOfflineTimeDomains` capture used by the EURUSD + GBPUSD research experiment. The raw console capture and normalized JSON remain outside the repository; this document records their references and hashes without copying provider data into source control.

## Capture

| Field | Value |
|---|---|
| JForex desktop | `4.8.18` |
| JForex API | `4.8.13` |
| Requested range | `2022-08-08T00:00:00Z` through `2026-08-20T00:00:00Z` |
| Instruments | `EUR/USD`, `GBP/USD` |
| Raw capture | `D:\Josué\Documents\DukascopyOfflineDomainsProbeV2-full.txt` |
| Raw capture SHA-256 | `e75b18004b652273ae992f7468e0154831f1c284a16cb1c92a4501e23a38ef7d` |
| Normalized receipt | `D:\Josué\Documents\DukascopyOfflineDomainsProbeV2-normalized.json` |
| Normalized receipt SHA-256 | `4ec765f25b49b16b02d45e12a0ffcd69edbd24b0cb98e3607ffefeeed5c4c9ba` |

## Integrity checks

- EUR/USD declared and parsed count: `215`.
- GBP/USD declared and parsed count: `215`.
- Domain indices `001` through `215` are unique for each instrument.
- The EUR/USD and GBP/USD `(start, end, duration)` domain sets are identical.
- Console ordering was reversed in the captured report; the normalized receipt is sorted by ascending UTC start timestamp.

## Interpretation boundary

The capture is broker/API evidence of returned offline domains. It is not a versioned or immutable holiday-calendar guarantee. The research ledger may use these intervals as retained closure evidence under the approved fail-closed rules, but must not infer additional closures from calendar intuition.

