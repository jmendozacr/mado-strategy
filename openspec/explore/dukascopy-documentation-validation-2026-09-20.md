# Dukascopy documentation validation

Official Dukascopy documentation does not establish a complete, historical, versioned closure authority for the inclusive 2022-08-08 through 2026-08-19 window. Dukascopy remains a viable candidate for a separately approved experiment and a later empirical access probe, but documentation alone cannot activate the archived calendar-aware gap contract or preserve the frozen Exness three-instrument estimand.

## Verdict

| Question | Documentation-only result | Consequence |
|---|---|---|
| Can a broker-native FX pair replace `DOLLAR.IDX/USD`? | No neutral replacement is documented. `USDJPY` and `USDCHF` are FX pairs, while `DOLLAR.IDX/USD` is a US Dollar Index Basket CFD. | Any FX-pair substitution is a new experiment. |
| Can `DOLLAR.IDX/USD` replace Exness `DXYm` directly? | Not as an identity-preserving substitution. Dukascopy documents the current instrument class, but not equivalence to Exness `DXYm`. | A Dukascopy three-instrument run is a new provider/instrument experiment. |
| Can the run use only EURUSD and GBPUSD? | Not under the frozen pooled three-instrument protocol. | A two-instrument run requires a new preregistration, estimand, lineage, baseline, and approval. |
| Is historical export free? | Yes. The official export page describes the Historical Data Export tool as free. | Cost is not the blocker. Access and licensing still need to be respected. |
| Does `getOfflineTimeDomains` prove complete historical closures? | No. It returns instrument-scoped offline intervals described as weekend intervals, but exposes no schedule version, revision date, provenance, completeness flag, or holiday guarantee. | Treat it as a server response to retain and test, not as a self-authenticating historical calendar. |
| Does Dukascopy publish a complete, versioned closure history? | No such official facility was found. The public Trading Breaks Calendar is mutable, not guaranteed, and subject to change. Dated news notices are isolated records. | Documentation-only validation is a no-go for calendar activation. |
| Are repeated requests guaranteed reproducible? | No official byte-level or row-level stability guarantee was found. | Reproducibility must be tested empirically and raw responses retained with hashes. |

## Why instrument identity matters

Charters 8-10 make time and instrument class part of the strategy definition:

- Forex uses the 9 PM, 1 AM, and 5 AM four-hour candles: 9 PM is the Asia reference range, while 1 AM and 5 AM are the named CRT setups.
- Indices use the corresponding 2 AM and 6 AM candles.
- The setup depends on session placement, preceding ranges, higher-timeframe context, and M15 confirmation.

Changing an index-like dollar basket to an FX pair therefore changes more than a ticker. It changes the instrument class and may change the strategy clock, session behavior, population of observations, and pooled estimand. A statistical protocol cannot preserve those properties by renaming a symbol.

## Official evidence

### Historical access and restrictions

| Claim | Classification | Official support | Limitation |
|---|---|---|---|
| Historical Data Export is free and supports CSV data from tick to monthly timeframes. | Verified | [Historical Data Export](https://www.dukascopy.com/swiss/english/marketwatch/historical/) | The public page does not document a service-level guarantee or immutable dataset version. |
| Historical Data Manager requires login to the demo or live JForex system. | Verified | [Historical Data Export FAQ](https://www.dukascopy.com/swiss/english/marketwatch/historical/) | This statement applies to the JForex route. The documentation does not clearly state that the separate web exporter requires login. |
| A standard JForex demo account is advertised as free for 14 days. | Verified | [JForex demo account](https://www.dukascopy.com/swiss/english/forex/demo-fx-account/) | Registration requests personal details and account creation remains outside this validation. |
| Demo historical data comes from the live environment, while demo real-time ticks come from a separate demo environment. | Verified | [Historical data overview](https://www.dukascopy.com/wiki/en/development/strategy-api/historical-data/overview-historical-data/) | This does not guarantee that later retrievals are immutable. |
| JForex API access is licensed for personal, non-commercial use unless a supplementary agreement covers other use. | Verified | [JForex API Terms of Use](https://www.dukascopy.com/swiss/docs/api/index.php) | The terms also allow availability to be limited and the content to be changed or discontinued. Legal applicability to the intended use requires user review. |

The public export page embeds demo registration and states that opening a demo expresses consent to possible contact and group sharing of account information. No account was opened and no access assumption was tested.

### `getOfflineTimeDomains` semantics

The official Javadoc reviewed for this validation is JForex API 2.13.99.

| Behavior | Verified documentation |
|---|---|
| Preferred signature | `getOfflineTimeDomains(long from, long to, Instrument instrument)`; the two-argument overload is deprecated. |
| Return value | A `Set<ITimeDomain>` ordered ascending by time. |
| Documented meaning | Offline intervals, repeatedly described as "offline (weekend)" intervals. |
| Range overlap | If `from` falls inside an offline period, that period is the first result; if `to` falls inside one, that period is the last result. |
| Instrument scope | The non-deprecated overload takes the instrument being checked. |
| Interval shape | `ITimeDomain` exposes only `getStart()` and `getEnd()`. |
| Related point check | `isOfflineTime(long, Instrument)` also describes an offline weekend period. |

Sources: [IDataService Javadoc](https://www.dukascopy.com/client/javadoc3/com/dukascopy/api/IDataService.html), [ITimeDomain Javadoc](https://www.dukascopy.com/client/javadoc3/com/dukascopy/api/ITimeDomain.html), and [Market Hours example](https://www.dukascopy.com/wiki/en/development/strategy-api/instruments/market-hours/).

The documentation does not define:

- whether every historical holiday, early close, late open, maintenance interval, or exceptional closure is included;
- an as-of date, schedule version, revision identifier, or changelog for returned intervals;
- a completeness guarantee for a requested historical window;
- provenance linking an interval to a published notice;
- precise endpoint inclusivity. The official example uses strict comparisons (`time > start && time < end`), but `ITimeDomain` itself documents only start and end accessors;
- behavior when an instrument did not exist or was unavailable for part of the requested window;
- stability of old responses after corrections or server updates.

These omissions prevent treating the method as a complete, versioned historical authority without an empirical probe and retained output.

### Published closure schedules

Dukascopy's [Trading Breaks Calendar](https://www.dukascopy.com/swiss/english/marketwatch/trading-breaks-calendar/) publishes special holiday hours in GMT. The same page says those hours are believed accurate but not guaranteed and may change. It does not expose an official historical version selector or immutable schedule identifier.

Dated official news posts can corroborate individual events, such as the [2023 Christmas and New Year notice](https://www.dukascopy.com/swiss/english/about/ournews/market-closures-on-christmas-and-new-year-dbl202761) and the [9 January 2025 US closure notice](https://www.dukascopy.com/swiss/english/about/ournews/us-market-closure-on-9th-of-january-2025). Those notices refer readers to the mutable calendar and do not form a complete instrument-by-instrument schedule for the validation window.

Result: official documentation proves that Dukascopy publishes current special-hours information and some dated notices. It does not prove completeness, effective-period continuity, or versioned retention from 2022-08-08 through 2026-08-19.

### Instrument identity and documented availability

| Instrument | Official identity | Current documentation status | Historical-window status |
|---|---|---|---|
| EURUSD | FX currency pair | Predefined `Instrument.EURUSD` | Not verified without querying first-available data and the requested interval. |
| GBPUSD | FX currency pair | Predefined `Instrument.GBPUSD` | Not verified without querying first-available data and the requested interval. |
| USDJPY | FX currency pair | Predefined `Instrument.USDJPY` | Candidate only; not a dollar-index substitute and historical coverage is unverified. |
| USDCHF | FX currency pair | Predefined `Instrument.USDCHF` | Candidate only; not a dollar-index substitute and historical coverage is unverified. |
| `DOLLAR.IDX/USD` | US Dollar Index Basket CFD | Listed in Dukascopy's current index-CFD range | Equivalence to Exness `DXYm` and full historical coverage are unverified. |

Sources: [Instrument Javadoc](https://www.dukascopy.com/client/javadoc3/com/dukascopy/api/Instrument.html) and [Dukascopy CFD indices](https://www.dukascopy.com/swiss/english/cfd/range-of-markets/cfd-indices/).

The Javadoc also provides `getTimeOfFirstTick(Instrument)` and `getTimeOfFirstCandle(Instrument, Period)`. Those methods offer a future empirical availability check, but documentation of the methods is not evidence that every target instrument covers the required window.

## Reproducibility assessment

JForex can read historical bars from local cache and download missing history from the server. Requests can therefore be specified precisely by instrument, period, offer side, filter, timezone/day-start choice, and UTC range. Sources: [History bars](https://www.dukascopy.com/wiki/en/development/strategy-api/historical-data/history-bars/) and [Historical data overview](https://www.dukascopy.com/wiki/en/development/strategy-api/historical-data/overview-historical-data/).

That supports a reproducibility test, not a reproducibility guarantee. The API terms describe content as continuously developed, as-is, and without guarantees of accuracy, completeness, reliability, or availability. They also reserve the right to change or discontinue content. No official snapshot identifier, dataset release, content digest, or historical revision log was found.

A later approved probe would need to retain, for each request:

- JForex and API versions;
- demo or live environment and account class;
- server properties and instrument identity returned at runtime;
- instrument, offer side, period, filters, timezone, and day-start settings;
- exact inclusive request window and observed boundary behavior;
- raw output bytes, row count, first/last timestamps, and SHA-256;
- offline-domain output separately from price data;
- a second cold-cache request and a later repeated request for byte- and row-level comparison.

No such probe was performed in this validation.

## Decision matrix

| Option | Preserves the frozen experiment? | Calendar-evidence burden | Scientific tradeoff | Status |
|---|---:|---|---|---|
| Dukascopy EURUSD + GBPUSD + `DOLLAR.IDX/USD` | No | Must establish all three identities, historical availability, closure completeness, and cross-broker non-equivalence handling. | Retains a dollar-basket role but changes provider and instrument identity. | Possible only as a new experiment. |
| Dukascopy EURUSD + GBPUSD only | No | Avoids the index-CFD calendar, but both FX histories and closures still require validation. | Changes the pooled three-instrument estimand to two instruments and may alter power and heterogeneity. | Possible only as a new experiment. |
| Dukascopy EURUSD + GBPUSD + USDJPY or USDCHF | No | All three FX calendars still require validation. | Replaces a dollar basket with a bilateral pair and introduces a new quote-currency exposure. | Possible only as a new experiment with explicit rationale. |
| Preserve the frozen Exness experiment | Yes | Still requires complete Exness historical evidence. | Preserves lineage and estimand but remains blocked. | Current fail-closed state. |

## Evidence still missing

- A documented or empirically retained response proving which offline intervals Dukascopy returns for each target instrument across the full inclusive window.
- Proof that returned intervals include exceptional holidays, early closes, late opens, and maintenance, rather than ordinary weekends only.
- Historical availability boundaries for EURUSD, GBPUSD, `DOLLAR.IDX/USD`, USDJPY, and USDCHF in the relevant environment.
- An official version or provenance mechanism for closure schedules, or an approved retention method that compensates for its absence.
- Repeated-request evidence showing whether identical requests produce identical rows and bytes.
- A verified mapping between Dukascopy `DOLLAR.IDX/USD` and Exness `DXYm`; no official source currently establishes one.
- A legal/use decision confirming that the intended research and artifact retention fit the JForex API terms.

## Decisions requiring approval

1. Whether to keep the frozen Exness experiment blocked or authorize planning a separate Dukascopy experiment.
2. If a new experiment is desired, whether its population is:
   - EURUSD, GBPUSD, and `DOLLAR.IDX/USD`;
   - EURUSD and GBPUSD only; or
   - EURUSD, GBPUSD, and a preregistered FX pair such as USDJPY or USDCHF.
3. Whether to authorize a later access probe that may require a 14-day demo account and historical-data retrieval.
4. Whether the intended use is personal and non-commercial under the published API terms, or needs separate licensing review.

Until those approvals are given, no account should be opened, no data should be downloaded, and no protocol, baseline, dataset identity, or production behavior should change.

## Scope and controls

This validation used repository documents and official Dukascopy/JForex sources accessed on 2026-09-20. The Javadoc reviewed is JForex API 2.13.99; mutable pages reflect only their state on the retrieval date. The validation did not create an account, download market data, contact Dukascopy or Exness, send an external message, or modify code, datasets, statistical protocols, baselines, or instrument identities.
