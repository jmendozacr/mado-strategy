# Lessons Learned

## 2026-09-16 — Calendar-aware gap validation

- **Require independent closure universes before accepting coverage** (discovery)
  - What: Evidence completeness must be evaluated against an independently supplied authoritative universe, never against the evidence set's own claims.
  - Why: Self-defining evidence can make partial historical coverage appear complete.
  - Where: Dataset validation and future calendar-authority changes.
  - Learned: Keep the authority boundary explicit and fail closed when the independent universe is unavailable.

- **Keep external historical truth behind a separate activation gate** (pattern)
  - What: Documentation and synthetic acceptance criteria must not activate runtime behavior or stand in for broker truth.
  - Why: Local fixtures and timestamp patterns cannot prove external historical schedules.
  - Where: External-data ingestion, preflight validation, and lineage-bound manifests.
  - Learned: Require retained original evidence, provenance, renewed lineage, and a separate authorization before changing admission behavior.
