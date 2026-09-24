# Dukascopy empirical-probe proposal

This proposal defines the smallest future probe that could determine whether Dukascopy can supply usable historical market-closure evidence for 2022-08-08 through 2026-08-19. It does not authorize an account, a data download, a protocol change, or a production decision.

## Quick path

1. Approve the experiment population and its estimand before any account or data access.
2. Record the exact Dukascopy environment, instrument identities, request parameters, and access terms.
3. Request the same bounded evidence twice under a cold-cache or independently recorded session.
4. Compare returned offline domains, historical availability, and published closure notices against the completeness and reproducibility criteria below.
5. Make a separate go/no-go decision for any statistical experiment.

## Decisions required before access

| Decision | Available choices | Consequence |
|----------|-------------------|-------------|
| Population | **EURUSD + GBPUSD only (selected for planning)** | This is a new provider/instrument experiment. It removes the index-CFD component and changes the frozen three-instrument estimand to a two-instrument estimand. |
| Statistical status | **Descriptive data-quality probe only (selected)** | The probe will not produce strategy claims, performance estimates, or hypothesis tests. Any later statistical experiment requires a separate preregistration, estimand, baseline, power rationale, and approval. |
| Closure authority | **Strict fail-closed, multi-source comparison (selected)** | `getOfflineTimeDomains` is evidence only. Any unexplained closure or coverage gap remains insufficient; no silent “open” classification is allowed. |
| Access scope | **Minimum future access, with JForex demo only if indispensable (selected for planning)** | This does not authorize account creation or data download. Any access action requires a separate approval after the design is complete. |
| Intended use | **Personal, non-commercial research only (selected)** | No redistribution or publication of Dukascopy data or provider artefacts is planned; any broader use requires a separate licensing review. |

## Preservation of existing strategy knowledge

The probe can preserve Charters 8–10 only if it remains an evidence-acquisition exercise. It must not rewrite the CRT detector, candle windows, baselines, statistical protocol, dataset identities, or production behavior. The Forex timing documented by the charters remains the target timing contract; the probe only tests whether a candidate provider can evidence the associated market closures.

The selected two-instrument EURUSD/GBPUSD run changes the population, pooled estimand, statistical power, heterogeneity, and the preregistered instrument-order field. It therefore remains descriptive-only in this phase; any performance or hypothesis test would require a new preregistration, baseline, and approval. Because the index CFD is excluded, this proposal uses only the Forex clock defined by Charters 8–10: the 9 PM Asia reference range and the 1 AM and 5 AM named CRT setups. No index clock is inferred or applied.

## Minimum evidence package

For each selected instrument (EURUSD and GBPUSD) and the inclusive date window:

- exact instrument identifier (`EURUSD` or `GBPUSD`), instrument class, and server/environment;
- first-available and last-available timestamps returned by the selected historical request;
- the exact `getOfflineTimeDomains(from, to, instrument)` parameters and returned intervals;
- the exact history request parameters, response metadata, and raw response hash;
- retrieval timestamp, API/JForex version, account/access mode, timezone, and locale;
- a second independently recorded request with the same parameters;
- any published Dukascopy closure notices used for comparison, preserving retrieval dates and URLs.

The package must distinguish observed absence of data from a documented market closure. A repeated response is evidence of reproducibility for that request and environment, not proof that Dukascopy guarantees immutable historical snapshots.

## Acceptance criteria for the probe

| Criterion | Pass condition | Failure interpretation |
|-----------|----------------|------------------------|
| Identity | The server accepts and returns the exact selected instruments without silent substitution | Stop; identity is unresolved. |
| Coverage | The requested interval has documented availability boundaries for every selected instrument | Stop or narrow the claim; the historical window is not established. |
| Closure semantics | Offline intervals are compared with available official calendars/notices and are never treated as a complete holiday calendar by themselves | Any unexplained closure, holiday, or coverage gap keeps the result insufficient. |
| Repeatability | Repeated bounded requests match at the documented comparison level, or differences are explained | No reproducibility claim. |
| Provenance | Raw responses, hashes, versions, parameters, and access conditions are retained | Evidence is not auditable. |
| Statistical isolation | No strategy result, performance estimate, or hypothesis test is computed | No protocol contamination. |

## Closure-evidence policy

The probe uses a strict fail-closed rule. A repeated Dukascopy response can establish reproducibility for that request and environment, but it cannot by itself establish a complete historical closure schedule. The result is sufficient only for the portions of the window where coverage, offline intervals, and available official notices are mutually documented. An unexplained interval or missing historical boundary is recorded as insufficient evidence, never as an inferred open market.

## Known risks and limits

- Dukascopy's public schedules and API documentation are mutable and do not establish a historical, versioned closure authority for the whole window.
- `getOfflineTimeDomains` describes offline intervals and has boundary behavior; its official documentation does not promise completeness, holiday provenance, or immutable revisions.
- Current instrument listings do not prove historical availability throughout the requested window.
- A free public export does not remove login, demo-duration, licensing, or API-term constraints.
- Cross-broker equivalence between Dukascopy `DOLLAR.IDX/USD` and Exness `DXYm` is not established by the available official sources.

## Explicit non-actions

Until the population, statistical status, and access scope are approved, this branch will not:

- open a Dukascopy account;
- download real market data;
- alter the frozen protocol, baselines, datasets, or instrument identities;
- activate the archived calendar-aware gap contract;
- claim that Dukascopy is a complete historical closure authority.

## Approval gate

The selected population for planning is EURUSD + GBPUSD only, the selected status is a descriptive data-quality probe, the selected closure policy is strict fail-closed, the selected access scope is minimum future access with a JForex demo only if indispensable, and the selected intended use is personal, non-commercial research without redistribution or publication of provider data. Approval of this document would authorize planning only, not account creation or data acquisition.

## Sources and status

This proposal relies on the official-source documentation review recorded in `openspec/explore/dukascopy-documentation-validation-2026-09-20.md` and the existing validation plan. Sources were accessed 2026-09-20; the reviewed JForex Javadoc identifies API 2.13.99. This is a proposal, not a preregistration or a production change.
