# Exploration: Evidence Acquisition Alternatives (standalone)

**Triage**: standalone
**Persona lens**: none

## Cross-Change Lessons Consulted

- Calendar-aware gap validation: external historical truth needs an independently complete authority and must fail closed when unavailable.
- Calendar-aware gap validation: synthetic fixtures and timestamp patterns prove mechanics, never broker history; activation needs retained provenance and renewed lineage.

## Affected Flows

Affected Flows: not applicable — no user-facing or runtime flow is authorised until an evidence or experiment path is chosen.

## Current State

The archived calendar design leaves the exact allowlist and blocked preflight intact; a future authority needs identity, provenance, complete coverage, and new lineage. Its evidence report leaves B3–B6 open for `Exness-MT5Trial11`: historical hours, holidays, and seasonal applicability. Wayback captures establish selected dated notices but not all three instruments across 2022-08-08 through 2026-08-19. The frozen runner requires protocol/hash consistency, nine dataset records and causal inputs, all-three validation, and one pooled statistics call; it cannot relax those constraints by configuration.

## Architecture Touchpoints (A3)

Not applicable — this investigation authorises no code or runtime-behaviour change. Any calendar activation or new experiment requires new triage and design.

## Affected Areas

| Path | Impact | Why |
|---|---|---|
| Archived calendar design and evidence reports | Read-only | Define fail-closed evidence boundary and unresolved B3–B6. |
| Statistical runner spec and Layer-3 design | Read-only | Freeze the pooled, atomic experiment contract. |
| `openspec/lessons-learned.md` | Read-only | Confirms independent-authority and provenance rules. |
| `openspec/explore/evidence-acquisition-alternatives.md` | Created | Records this decision material only. |

## Sensitive Areas Crosscheck

No sensitive areas touched. The protected authorization, preflight, and dataset/manifest paths remain unchanged.

## Approaches

### 1. Preserve user-retained artifacts and corroborate archives
**Description**: Inventory original Exness emails/notices and historical MT5 terminal, VM, or VPS artifacts without opening market datasets; retain raw `.eml`, headers, attachments, `Bases/<server>/Mail`, `News`, logs, and server/account identity with hashes. Complete Common Crawl and Wayback body extraction as corroboration.

**Pros**: Highest-yield non-provider-dependent route; can support B3–B6 provenance.
**Cons**: Existing messages cannot prove missing-notice completeness; archives lack complete server/suffix/period mapping.
**Effort**: Medium
**Pattern fit**: matches retained-byte, hash-bound evidence requirements.

### 2. Seek first-party attestation
**Description**: A future entity-correct Exness complaint/records request could obtain the strongest provider evidence; this exploration sends nothing.

**Pros**: Potentially authoritative on historical applicability.
**Cons**: No response is guaranteed; ordinary support already did not respond.
**Effort**: Low to initiate, unknown to resolve
**Pattern fit**: external dependency, not a repository substitute.

### 3. Preserve or replace the scientific scope
**Description**: If complete provider-specific evidence remains absent, close/defer this experiment as synthetic-only/no-run; if a real result is necessary, preregister a new experiment using a provider/source with complete retainable calendars.

**Pros**: Preserves honesty; a new source can be methodologically clean.
**Cons**: The new experiment changes dataset, instrument equivalence/candle construction, lineage, baseline B, authorization A, and possibly estimand.
**Effort**: Low for closeout; High for replacement
**Pattern fit**: respects frozen protocol boundaries.

## Recommendation

Use the staged strategy: first preserve/inventory user-owned artifacts; then finish Common Crawl/Wayback extraction strictly as corroboration; then choose no-run/synthetic-only closeout if Exness evidence is incomplete, or separately triage a new provider experiment if a real result is required. Do not admit sessions from weekend patterns, drop uncertain intervals, or use ICE hours as an Exness DXYm proxy.

## Risks

- Partial retained notices may look complete: require an explicit completeness claim, not inference from presence.
- Narrowing dates, dropping DXYm, per-instrument runs, or excluding uncertain intervals changes the frozen experiment and can introduce informative missingness.
- Forensic hashes, DKIM, and timestamps strengthen provenance but cannot create missing historical content.

## Open Questions

- **type**: product
  **question**: Do historical Exness emails, MT5 Mail/News folders, old terminal folders, VM/VPS backups, or PA notices still exist?
  **why_it_matters**: They are the best immediate source of original provider artifacts.
- **type**: product
  **question**: Must the claim remain specific to Exness-MT5Trial11 and the original three-instrument pooled estimand?
  **why_it_matters**: Altering it creates a new experiment.
- **type**: product
  **question**: Is a scientifically honest no-run/synthetic-only closeout acceptable, or is a new provider/new experiment required?
  **why_it_matters**: This selects the only defensible route after incomplete evidence.

## Ready for Proposal

**Status**: partial
**Reason**: Evidence inventory can begin without changing the protocol, but provider or protocol changes require the product decisions above and new triage.
**Recommended action**: Obtain answers, perform the non-data artifact inventory, then either close/defer or open a separately scoped experiment.
