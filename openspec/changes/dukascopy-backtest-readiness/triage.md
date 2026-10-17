# Triage: Dukascopy Backtest Readiness

**Classification**: L  
**Decided at**: 2026-09-25  
**Change name**: `dukascopy-backtest-readiness`

## Problem & Scope

> Obtain a reproducible EURUSD/GBPUSD backtest that can credibly inform a later shadow-mode and demo-account decision, without relying on misleading historical metrics.

```yaml
scope:
  in_scope:
    - Use the already-integrated bounded Dukascopy EURUSD/GBPUSD experiment as the canonical evidence seam.
    - Correct the two named canonical backtest-reporting defects.
    - Execute and preserve one reproducible two-pair run.
  out_of_scope:
    - Shadow mode, broker integration, and demo execution.
    - New strategy rules, 05:00 profiles, and Key-Level expansion.
```

## Criteria Evaluation

| Criterion | Evidence | Score |
|---|---|---|
| Files affected | ~11 adopted research files plus canonical reports, tests, and receipts | L |
| Lines | ~400 adopted changes plus corrections/evidence | M |
| Contexts | Research ingress/run seam; canonical simulation/reporting | L |
| New patterns | Bounded external-data run and reproducibility receipt | L |
| Test types | Existing pytest plus reproducibility/run evidence | M |
| Precedent | Existing research-only seam; no reduction for adoption/run contract | none |

### Overrides Triggered

None. This is research evidence, not order execution or financial-transaction logic.

**Final classification**: L — a single decision-critical outcome requires branch adoption, canonical metric integrity, and an auditable run.

## Recommended Path

- Phase: full Planner with Council.
- Skills: `sdd-explore` → `sdd-propose` → `sdd-spec` → `sdd-design` → `sdd-slice`.
- Slice maximum: 7; target 3 vertical slices.

## Risks Flagged at Triage

- Manifest validation must be unavoidable before outcome-producing execution.
- Fix reporting semantics at their canonical owner, not as Dukascopy-only post-processing.
- The first run is descriptive evidence, never a profitability threshold.

## Halt?

No.

## Notes for Next Phase

Preserve the research-only boundary: production detector modules must not import the Dukascopy adapter.
