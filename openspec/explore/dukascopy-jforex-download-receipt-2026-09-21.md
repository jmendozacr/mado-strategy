# Dukascopy JForex download receipt

This receipt records the first approved full-window descriptive download. The raw CSV files remain outside the repository at their original JForex location. No strategy statistics or production changes were performed.

## Request parameters

| Field | Value |
|-------|-------|
| Instruments | `EURUSD`, `GBPUSD` |
| JForex labels | `EUR/USD`, `GBP/USD` |
| Date window | `2022.08.08 00:00:00` through `2026.08.19 23:59:00` |
| Interval | `1 Min` |
| Offer side | `Bid` |
| Account | JForex demo |
| Download date | 2026-09-21 |

## Retrieved files

| Instrument | Original path | Size (bytes) | Lines | SHA-256 |
|------------|---------------|--------------|-------|---------|
| EURUSD | `D:\Josué\Documents\dukascopy-original-2026-09-21\EURUSD_1 Min_Bid_2022.08.08_2026.08.19.csv` | 88,625,458 | 1,509,416 | `F43EC0BE4CD09F5BE0D0B957C9EC87E8E9544C22760A6ACF9C2BB677BD2832E6` |
| GBPUSD | `D:\Josué\Documents\dukascopy-original-2026-09-21\GBPUSD_1 Min_Bid_2022.08.08_2026.08.19.csv` | 88,122,339 | 1,509,416 | `520D5B8391BB8485199ECBE812756937D8FAD6DDB3889EE4EB8128D34809A77A` |

## Observed format and boundaries

- Header for both files: `Time (EET),Open,High,Low,Close,Volume`.
- First row for both files: `2022.08.08 00:00:00`.
- Last row for both files: `2026.08.19 23:59:00`.
- Each file contains 1,509,415 one-minute rows plus the header.
- The provider labels the timestamps `EET`; no UTC conversion has been applied.
- Dukascopy's `JFTimeZone.EET` documentation defines EET as UTC+2 in standard time and UTC+3 in daylight time. The JForex preferences documentation states that EET is the default day-start zone for Forex instruments. Any later UTC mapping must therefore be DST-aware and must preserve the original EET strings.

## Interpretation

The JForex manager produced complete-looking one-minute files for both selected instruments and the requested boundaries. This establishes retrieval and file-format coverage for the selected request, not closure completeness, holiday semantics, or reproducibility. Missing rows, zero volume, and offline intervals still require separate analysis under the strict fail-closed rules.

## Repeatability result

A second download with the same instruments, dates, interval, offer side, and EET settings completed on 2026-09-21. The second files in `D:\Josué\Documents` matched the preserved originals byte-for-byte:

- EURUSD: `F43EC0BE4CD09F5BE0D0B957C9EC87E8E9544C22760A6ACF9C2BB677BD2832E6`.
- GBPUSD: `520D5B8391BB8485199ECBE812756937D8FAD6DDB3889EE4EB8128D34809A77A`.

This passes repeatability for this request, account mode, client state, and retrieval date. It does not establish immutable snapshots or complete historical closure authority.

## Initial descriptive continuity scan

Both files were scanned without changing their contents or calculating strategy statistics:

- 0 malformed rows and 0 duplicate timestamps in each file.
- 1,509,199 consecutive one-minute transitions in each file.
- 215 non-one-minute transitions in each file, with identical transition frequencies: 192 transitions of 2,881 minutes (ordinary weekend gaps), 8 of 2,821 minutes and 8 of 2,941 minutes (daylight-offset transitions), plus seven longer holiday/year-boundary patterns.
- Zero-volume rows: 14,745 in EURUSD and 8,461 in GBPUSD.

These are observations about the exported series, not broker-closure classifications. Weekend, daylight-offset, holiday, and zero-volume behavior still require EET-aware interpretation and comparison against the approved closure-evidence sources.

The seven non-weekend/non-daylight candidate boundaries observed in both files were:

- `2023.12.22 23:58:00` → `2023.12.25 01:00:00`;
- `2023.12.25 09:58:00` → `2023.12.26 00:01:00`;
- `2023.12.29 23:59:00` → `2024.01.02 00:00:00`;
- `2024.12.25 09:59:00` → `2024.12.26 00:00:00`;
- `2024.12.31 23:59:00` → `2025.01.02 00:00:00`;
- `2025.12.25 09:58:00` → `2025.12.26 00:00:00`;
- `2025.12.31 23:58:00` → `2026.01.02 00:00:00`.

These candidate boundaries require source-by-source corroboration; their calendar names are intentionally not inferred here.

## Controls

- Raw files remain in the external `dukascopy-original-2026-09-21` folder and are not staged or copied into the repository. The folder move changed path only; verified sizes and hashes are unchanged.
- No `Ask` files were requested.
- No strategy performance, hypothesis test, baseline update, or production change was performed.
- The files must be repeated under the approved reproducibility procedure before any descriptive closure verdict.

## Official timezone references

- `https://www.dukascopy.com/client/javadoc3/com/dukascopy/api/JFTimeZone.html`
- `https://www.dukascopy.com/wiki/en/manuals/jforex4-desktop/preferences/`

## Offline-domain probe receipt (2026-09-22)

| Field | Value |
|-------|-------|
| JForex desktop | `4.8.18` |
| JForex API | `4.8.13` |
| Probe source | `D:\Josué\Documents\DukascopyOfflineDomainsProbeV2.java` |
| Probe SHA-256 | `ED7CC4EFEDA5AA3DC532FD2D49463D8E971DE82B600F8F8FCB446C982F79AFA0` |
| Source lines | `68` |
| API range | `2022-08-08T00:00:00Z` through `2026-08-20T00:00:00Z` |

The probe returned `COUNT=215` for both `EUR/USD` and `GBP/USD`. The returned special domains were identical for both instruments: Christmas intervals on 2023-12-25, 2024-12-25, and 2025-12-25, plus year-end intervals spanning 2023/2024, 2024/2025, and 2025/2026. The capture is broker/API evidence of returned offline domains, not proof of a complete immutable closure calendar.
