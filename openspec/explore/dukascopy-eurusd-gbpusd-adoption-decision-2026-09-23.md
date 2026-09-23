# Dukascopy EURUSD + GBPUSD adoption decision

## Decision

Adopt Dukascopy as the preferred source for the separate EURUSD + GBPUSD personal-research experiment documented on this branch.

## Rationale

Compared with the unavailable historical-closure evidence for the earlier experiment, the retained Dukascopy evidence package provides:

- JForex `getOfflineTimeDomains` receipts for both approved instruments;
- a fail-closed ledger in which all 430 observed minute gaps are covered by retained offline domains;
- explicit weekend, Christmas, and year-end intervals;
- hashed raw and derived artifacts; and
- byte-identical outcome replay under the frozen two-instrument protocol.

This adoption is based on stronger closure and continuity evidence, not on a claim that Dukascopy's schedule is an immutable or versioned historical calendar.

## Scope and non-effects

- The adopted experiment is limited to `DUKASCOPY_EURUSD` and `DUKASCOPY_GBPUSD`.
- It is a separately defined research population, not a replacement for the original three-instrument experiment.
- `DOLLAR.IDX/USD` remains unresolved and is not substituted.
- The original production code, datasets, baselines, statistical protocols, and instrument identities are unchanged.
- Exness remains paused; this decision authorizes no broker contact, account creation, data download, or external message.
- The outcome remains exploratory rather than confirmatory.

## Evidence references

- `openspec/explore/dukascopy-offline-domains-receipt-2026-09-22.md`
- `openspec/explore/dukascopy-gap-ledger-receipt-2026-09-22.md`
- `openspec/explore/dukascopy-outcome-receipt-2026-09-23.md`
- `openspec/explore/dukascopy-eurusd-gbpusd-experiment-preregistration-2026-09-22.md`
- `docs/charter-8.md`, `docs/charter-9.md`, and `docs/charter-10.md`
