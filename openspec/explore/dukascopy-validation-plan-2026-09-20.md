# Dukascopy validation plan

Dukascopy is suitable for a separately preregistered validation experiment, but it is not yet an authoritative replacement for the historical Exness closure schedule.

## Decisions

| Question | Decision | Reason |
|---|---|---|
| Replace `DOLLAR.IDX/USD`? | Possible, but only as a new experiment | `DOLLAR.IDX/USD` is a Dukascopy CFD index and is not proven equivalent to Exness `DXYm`. Replacing it with a currency pair changes the instrument identity and the frozen three-instrument estimand. |
| Best low-change option | Run EURUSD and GBPUSD only | This removes the unresolved index equivalence, but requires reopening the statistical protocol and accepting a two-instrument estimand. |
| Best three-instrument FX option | Evaluate USDJPY or USDCHF | Both are broker-native FX pairs, but neither is a dollar-index substitute; the choice must be preregistered with a rationale. |
| Data cost | Historical export is advertised as free | Access still requires a demo/live JForex login; the demo account is advertised as 14 days. |
| Licensing | Personal, non-commercial use only by default | Commercial or non-personal use requires supplementary permission under the API terms. |

## Evidence already established

- JForex exposes historical ticks and bars by time interval, with data read from local cache or downloaded from Dukascopy servers.
- `IDataService` exposes offline time domains, but the official documentation describes them as market-offline/weekend intervals. It does not establish a versioned, complete historical holiday calendar.
- Dukascopy publishes `DOLLAR.IDX/USD` as a US Dollar Index Basket CFD.
- Historical data on demo is documented as LIVE historical data; demo realtime ticks are a separate environment.
- Platform timezone and day-start settings affect candle boundaries and must be recorded.

## Blocking checks before any real-data run

1. Confirm server-returned identities and availability for EURUSD, GBPUSD, and the selected replacement instrument.
2. Confirm the API behavior and scope of `getOfflineTimeDomains` for the full 2022-08-08 through 2026-08-19 window.
3. Determine whether special holidays and early closes are represented, or only ordinary weekend closures.
4. Record API/platform version, endpoint, account environment, timezone, day-start, offer side, period, and inclusive UTC range.
5. Repeat the same request to test row-level and byte-level reproducibility.
6. Retain raw responses and hashes before any transformation.

## Explicit non-decisions

- No instrument replacement is authorized yet.
- No code, protocol, baseline, or dataset identity is changed by this document.
- Exness remains paused; no request is sent and no real data is downloaded.

## Primary sources

- [JForex historical data overview](https://www.dukascopy.com/wiki/en/development/strategy-api/historical-data/overview-historical-data/)
- [JForex history bars](https://www.dukascopy.com/wiki/en/development/strategy-api/historical-data/history-bars/)
- [JForex market hours](https://www.dukascopy.com/wiki/en/development/strategy-api/instruments/market-hours/)
- [IDataService Javadocs](https://www.dukascopy.com/client/javadoc3/com/dukascopy/api/IDataService.html)
- [Dukascopy index instruments](https://www.dukascopy.com/swiss/deutsch/cfd/range-of-markets/cfd-indices/)
- [Historical Data Export](https://www.dukascopy.com/swiss/english/marketwatch/historical/)
- [Dukascopy API terms](https://www.dukascopy.com/swiss/docs/api/index.php)
