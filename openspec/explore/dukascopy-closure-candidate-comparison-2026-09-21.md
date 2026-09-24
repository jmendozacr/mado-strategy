# Dukascopy closure-candidate comparison

This note compares candidate timestamp boundaries observed in the EURUSD and GBPUSD JForex exports with official Dukascopy notices. It is descriptive evidence only; it does not activate the calendar-aware gap contract or classify exact closure minutes.

## Conservative classification

| Export candidates | Official source | Classification |
|-------------------|-----------------|----------------|
| 2023 Christmas/New Year boundaries | Dukascopy notice published 2023-12-22 warns of low liquidity and market closures throughout Christmas/New Year, particularly 25 December | Broad holiday corroboration; exact EET boundaries remain unverified. |
| 2024 Christmas/New Year boundaries | Dukascopy notice published 2024-12-20 warns of low liquidity and market closures throughout Christmas/New Year, particularly 25 December | Broad holiday corroboration; exact EET boundaries remain unverified. |
| 2025 Christmas/New Year boundaries | Dukascopy notice published 2025-12-19 warns of low liquidity and market closures throughout Christmas/New Year | Broad holiday corroboration; exact EET boundaries remain unverified. |

The seven candidate blocks in the download receipt therefore remain candidates, not confirmed exact closures. The notices corroborate the relevant holiday periods but defer detailed schedules to the Trading Breaks Calendar.

## Independent review disposition

Claude Code independently reviewed this comparison and returned **APPROVED WITH CAVEATS**. The evidence chain is coherent and the scope preserves the Forex-clock knowledge in Charters 8–10, but the following items remain prerequisites for a sufficient closure-evidence verdict:

- Explicitly assess zero-volume rows, or record why they are excluded from the closure-evidence burden.
- Check whether non-Christmas holidays appear as unexplained non-contiguous gaps and record the empirical result.
- Treat the EET conversion as DST-aware: EET is UTC+2 in standard time and UTC+3 during daylight time. Retain the original EET labels and the converted GMT/UTC representation together.

## Why exact confirmation is still open

- The Trading Breaks Calendar publishes special schedules in GMT, while the CSV timestamps are labeled EET; the comparison must apply the correct seasonal offset for each date.
- The calendar page says its holiday hours are believed accurate but not guaranteed and may change.
- The dated notices do not provide a versioned historical snapshot of every minute boundary.
- `getOfflineTimeDomains` output has not yet been captured for either instrument.

## API semantics confirmed

The official JForex `IDataService` Javadoc defines `getOfflineTimeDomains(long from, long to, Instrument instrument)` as returning ascending offline **weekend** `ITimeDomain` intervals within the requested bounds. If either bound falls inside an offline interval, that interval is included at the corresponding edge. The older overload without `Instrument` is deprecated. The documentation does not describe this method as a versioned holiday calendar or guarantee its historical completeness.

## Empirical `getOfflineTimeDomains` capture

On 2026-09-22, the temporary JForex probe queried `2022-08-08T00:00:00Z` through `2026-08-20T00:00:00Z` for both instruments. Each returned `COUNT=215`. The returned sets were identical, including these non-standard weekend-domain intervals:

| Interval (UTC) | Duration | Interpretation for this review |
|----------------|---------:|--------------------------------|
| 2023-12-25 07:59 → 22:01 | 14 h | Christmas special domain; exact closure meaning still requires external schedule corroboration. |
| 2023-12-29 22:00 → 2024-01-01 22:00 | 72 h | Year-end extension over the regular weekend. |
| 2024-12-25 08:00 → 22:00 | 14 h | Christmas special domain; exact closure meaning still requires external schedule corroboration. |
| 2024-12-31 22:00 → 2025-01-01 22:00 | 24 h | New Year special domain. |
| 2025-12-25 07:59 → 22:00 | 14 h | Christmas special domain; exact closure meaning still requires external schedule corroboration. |
| 2025-12-31 21:59 → 2026-01-01 22:00 | 24 h | New Year special domain. |

This is strong broker/API evidence that the historical service exposes special holiday intervals in addition to regular weekends. It is not, by itself, proof of a complete, immutable, versioned closure schedule, and the one-minute boundary differences remain part of the evidence to reconcile.

The empirical result also exposes a semantic limitation: four of the six special domains fall on weekday holiday dates even though the Javadoc describes the method as returning “offline (weekend)” intervals. The method therefore returns useful broker/API availability domains, but its output must remain evidence rather than an authoritative closure-calendar contract.

## Empirical caveat checks

The descriptive scan of the two JForex files found zero-volume rows, so volume cannot be used as a closure label:

| Instrument | Zero-volume rows | Dates containing zero-volume rows | Notable concentration |
|------------|-----------------:|----------------------------------:|------------------------|
| EURUSD | 14,745 | 986 | 1,320–1,439 rows per day on 2024-12-02 through 2024-12-06; this is an unexplained data-quality concentration, not a closure classification. |
| GBPUSD | 8,461 | 992 | Highest daily counts occur on Christmas dates and other holiday-like dates, but the rows remain observations rather than proof of closure. |

The timestamp-continuity scan found no additional non-weekend, non-daylight-offset missing blocks beyond the seven candidate blocks already listed in the download receipt. That result narrows the next check; it does not establish that the candidate blocks are official closures, and zero-volume observations on other dates still require reconciliation.

## Official sources

- 2023 notice: `https://www.dukascopy.com/swiss/english/about/ournews/market-closures-on-christmas-and-new-year-dbl202761`
- 2024 notice: `https://www.dukascopy.com/swiss/english/about/ournews/market-closures-during-x-mas-and-new-year-dbl203022`
- 2025 notice: `https://www.dukascopy.com/swiss/english/about/ournews/market-closures-during-x-mas-and-new-year-dbl203256`
- Trading Breaks Calendar: `https://www.dukascopy.com/swiss/english/marketwatch/trading-breaks-calendar/`

## Next evidence required

1. Capture the relevant Trading Breaks Calendar schedules with retrieval date and raw page evidence.
2. Convert GMT schedule boundaries to the CSV's EET labels with DST-aware rules while retaining both representations.
3. Capture `getOfflineTimeDomains` for EURUSD and GBPUSD over the same window.
4. Reconcile any unexplained discrepancy as insufficient evidence under the fail-closed policy.
5. Include zero-volume rows and non-Christmas holiday gaps in the reconciliation record before declaring the closure evidence sufficient.
6. Preserve the exact probe source, a content hash, and the JForex platform/API version with the capture receipt before relying on the result downstream.
