# Dukascopy pre-access checklist

This checklist prepares a future descriptive probe for EURUSD and GBPUSD over the inclusive window 2022-08-08 through 2026-08-19. It does not authorize account creation, data download, protocol changes, or production changes.

## Current gate state

| Gate | Decision | Status |
|------|----------|--------|
| Population | EURUSD + GBPUSD only | Approved for planning |
| Statistical status | Descriptive data-quality probe only | Approved |
| Closure policy | Strict fail-closed, multi-source comparison | Approved |
| Intended use | Personal, non-commercial research; no redistribution or publication | Approved for planning |
| Account creation | JForex demo only if indispensable | Not authorized |
| Historical data request | Required only after separate access approval | Not authorized |

## Pre-access invariants

- Do not alter Charters 8–10, the frozen Exness protocol, baselines, datasets, instrument identities, or production code.
- Do not treat Dukascopy as a complete historical closure authority before the probe passes its evidence criteria.
- Do not classify an unexplained interval as an open market.
- Do not compute strategy performance, estimate a new effect, or run a hypothesis test.
- Keep the Exness experiment blocked independently; Dukascopy evidence does not replace Exness evidence.

## Request plan

For each of `EURUSD` and `GBPUSD`, record before sending any request:

- exact instrument identity and instrument class;
- server/environment, account mode, JForex/API version, timezone, and locale;
- inclusive `from` and `to` timestamps for 2022-08-08 through 2026-08-19;
- exact `getOfflineTimeDomains(from, to, instrument)` parameters;
- exact historical-data request parameters and requested granularity;
- retrieval timestamp and local session identifier.

The plan must be approved as a read-only descriptive probe before any request is sent. No request may be broadened after approval without recording the change and obtaining approval again.

## Evidence to retain

For every response, retain the raw bytes where the access terms permit, plus:

- cryptographic hash of each raw response;
- response metadata and request parameters;
- returned offline intervals and boundary values;
- first-available and last-available observations for each instrument;
- client/API/JForex version and access conditions;
- retrieval timestamp and an immutable local record identifier;
- URLs and retrieval dates for any official calendar or closure notice used in comparison.

If raw-byte retention is not permitted, stop and record the restriction before proceeding; do not substitute an undocumented representation.

## Repeatability pass

Repeat the same bounded request independently for each instrument and retain both response records. Compare at the documented level:

- instrument identity;
- interval boundaries and interval count;
- historical availability boundaries;
- response metadata and hashes when byte retention is permitted.

A match supports repeatability for that request and environment only. It does not establish an immutable Dukascopy snapshot or a versioned historical calendar.

## Fail-closed decision rules

| Observation | Classification | Action |
|-------------|----------------|--------|
| Exact identity, complete requested coverage, repeated response, and corroborated official notices | Descriptively usable for the observed evidence | Preserve the evidence package; do not infer beyond it. |
| Coverage boundary missing or ambiguous | Insufficient | Stop the claim for that instrument/window. |
| Offline interval has no documented interpretation or corroboration | Insufficient | Do not classify it as open. |
| Repeated requests differ without an explanation | Non-reproducible | Stop and report the discrepancy. |
| Access terms prevent required retention or intended personal use | Access blocked | Stop before requesting or retaining data. |
| Any request would require a broader scope than approved | Out of scope | Stop and request a new approval. |

## Required authorization before execution

Execution requires a separate explicit approval that names all of the following:

1. creation or use of the required Dukascopy demo access, if indispensable;
2. the exact two-instrument request scope;
3. retention of the permitted evidence artefacts;
4. the personal, non-commercial use limitation;
5. the stop conditions and fail-closed rules in this checklist.

Until that approval is recorded, this document remains planning-only.

## Handoff

After the checklist is approved for execution, the next artefact should be an execution receipt containing the approved parameters, access decision, evidence hashes, repeatability comparison, and a descriptive verdict. It must not contain strategy-performance claims.
