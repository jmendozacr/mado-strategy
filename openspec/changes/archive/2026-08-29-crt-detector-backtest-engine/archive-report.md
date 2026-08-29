# Archive Report: crt-detector-backtest-engine

**Archived at**: 2026-08-29T00:00:00Z
**Verify verdict**: pass-with-followups
**Spec version archived**: V10 (signed)

## Summary

Archived the CRT backtest simulation engine — a candle-by-candle trade lifecycle simulator (entry fill, SL, TP) over v1's Model-1 signals, giving the trader an honest, non-survivorship-biased win-rate/R-multiple read instead of an unvalidated signal stream. Synced 23 new REQ-IDs (REQ-30 through REQ-52) into main at `openspec/specs/detector/spec.md` — all ADDED, no MODIFIED/REMOVED. 193/193 tests passing after judgment-day's fix batches; import-linter clean. Judgment-day (2 rounds) APPROVED. Steward reckoning ran the tool on real 100k-candle EURUSD data and confirmed all 7 north-star criteria — `delivered`, human-ratified as complete. 13 followups synced to `openspec/pending-changes.md`.

## Specs Synced

| Domain | Type | REQs Added | REQs Modified | REQs Removed |
|---|---|---|---|---|
| `backtest-simulation` (new) | New | 15 | 0 | 0 |
| `backtest-metrics` (new) | New | 2 | 0 | 0 |
| `signal-traceability` (new) | New | 2 | 0 | 0 |
| `model1-entry-detection` (extended) | Delta | 2 | 0 | 0 |
| `cli-output-filtering` (extended) | Delta | 2 | 0 | 0 |

Main spec now at `openspec/specs/detector/spec.md` (V5, 52 REQ-IDs total across both archived changes).

## Archive Location

`openspec/changes/archive/2026-08-29-crt-detector-backtest-engine/` — this change ran in engram-only mode for its planning artefacts (no `openspec/changes/crt-detector-backtest-engine/` folder existed to move); this folder was created fresh, reconstructed from the change's engram observations.

## Lessons Learned Persisted

1. **A "see revision history" elision becomes permanently unretrievable when only the latest revision is fetchable** — two Plan Verify judges hit a wall on ~14 REQ-IDs and 3 ADRs elided that way; fixed by reproducing full text on every revision, splitting into per-domain keys once size risked repeating the same truncation. (type: pattern)
2. **A foresight gate that checks whether a config constant coincides with a computed value used elsewhere can catch a headline-metric defect before any code exists** — the SL model would have made "risk" a constant 2 pips for 96% of trades, silently turning the change's own R-multiple output into a measurement of that constant rather than the methodology. (type: pattern)
3. **Never trust an interrupted async agent call's implicit completion state** — a slice's apply work landed correctly on disk but the call itself surfaced as failed before its persistence step ran; only an independent from-scratch re-verification (re-run tests, re-read every touched file, re-check every acceptance criterion) confirmed it was actually done. (type: discovery)
4. **A disclosed default is not automatically a legible one** — the frictionless-cost default was labeled honestly and the override mechanism worked correctly, but a reader still had to independently run a cost sweep to see the realistic (near-breakeven) number; disclosure without a realistic-case default can still mislead by omission of effort, not of fact. (type: discovery)

## ADRs

### Promoted to Project-Level
Human confirmed all 5. Promoted as ADR-007 through ADR-011 at `project/architectural-decisions` (engram #321, registry updated in place):
- **ADR-007** (was ADR-01): `backtest` as a new lint-enforced layer above `alignment` — establishes the precedent for how this project's pipeline grows a new layer; directly reusable for a future phase-3 (live alerts) addition.
- **ADR-008** (was ADR-02): Ambiguity resolved by fixed ORDERING of sweep passes rather than special-casing — a reusable technique for any future exit/position simulation logic (the planned `crt-detector-backtest-partial-exits` change will extend this directly).
- **ADR-009** (was ADR-03): Every population cut lands in exactly one of N mutually-exclusive, precedence-ordered buckets, with a sum invariant — a reusable reporting discipline for any future filtering/exclusion pipeline in this project.
- **ADR-010** (was ADR-04): Deduplication key + stage ordering (dedup before rule cuts, so downstream counts describe distinct candidates) — reusable wherever overlapping-candidate inflation recurs.
- **ADR-011** (was ADR-05): Simulation-local price levels computed independently of, and decoupled from, detection-output fields — the fix for this change's own foresight-caught defect; worth codifying as a standing principle (a value a detector emits for display and a value a downstream consumer needs for arithmetic should not be silently assumed identical).

### Recommended but Not Yet Promoted
None — all 5 promoted above.

## Followups Registered

13 followups (already registered at engram `project/pending-changes`, obs #303 — synced here, not re-registered):

| Description | Type | Size | Origin |
|---|---|---|---|
| "never confirmed" bucket label wrong for PENDING+no-retest signals (~5,800 at real scale) | data-quality | S | judgment-day + reckoning priority bump |
| Intra-fill-candle stop-outs undisclosed | disclosure-gap | XS | judgment-day round 2 |
| `risk == 0` ZeroDivisionError reachable at library boundary | robustness | XS | judgment-day round 1/2 |
| `_fixed_decimal` misreports values below ~5e-11 | rendering-nit | XS | judgment-day |
| REQ-34.1 spec scenario arithmetically impossible as written | spec-text | XS | judgment-day |
| REQ-52.2 premise factually false (relocated, not removed) | spec-text | S | judgment-day |
| Backtest population read from pre-filter snapshot, structurally fragile | design-debt | S | judgment-day |
| `invert_bullish` flag hard to read | style | XS | judgment-day (2 judges corroborated) |
| 5 CLI error tests assert exit code only, not message (= verify F-03) | test-gap | XS | verify-final |
| `include_signal_id` threaded through 7 call sites | style | XS | judgment-day |
| Import grouping inconsistent in 3 new files | style | XS | judgment-day |
| 4 minor test-coverage gaps (order-independence, sum-invariant, REQ-45.1, fixture scope) | test-gap | S | judgment-day |
| Frictionless default reads optimistic vs. real cost (human: leave as-is) | ux-nice-to-have | XS | reckoning |

## Final State

- **Spec status**: signed (V10, archived)
- **Main specs updated for**: `detector` (5 domain sections, 23 REQ-IDs added)
- **Tests**: 193/193 passing (post judgment-day)
- **Import-linter**: clean (1 kept, 0 broken)
- **REQ coverage**: 23/23 REQ-IDs tested, 64/67 sub-scenarios fully compliant (3 partial — behaviour confirmed correct at runtime, test coverage gap only)
- **Lessons in project memory**: 4 added
- **ADRs in project memory**: 5 promoted (ADR-007..011, human-confirmed)
- **Pending changes in project memory**: 13 synced (already registered, not duplicated)

## Pre-PR Audit Notes

Not run as a separate pass this archive — judgment-day's 2-round adversarial review already covered this ground against the same signed spec and full diff (Round 1: 7 fix-now items applied, each RED-verified via mutation before GREEN; Round 2: 0 confirmed CRITICAL/real-WARNING findings, 2 further Suspect-only findings deliberately deferred to followups by user decision — APPROVED). No additional pre-PR audit pass added beyond that.

## Artefacts Persisted

| Artefact | Location |
|---|---|
| Archive report | `openspec/changes/archive/2026-08-29-crt-detector-backtest-engine/archive-report.md` + engram `sdd/crt-detector-backtest-engine/archive-report` |
| Main spec | `openspec/specs/detector/spec.md` (V5, extended with 23 new REQ-IDs) |
| Lessons learned | engram `project/lessons-learned` (4 new entries) |
| Pending changes | `openspec/pending-changes.md` (13 entries synced) |

---

**Archive sealed**: 2026-08-29
**Next step**: Orchestrator to surface ADR promotion recommendations to human for confirmation, then continue cycle (next planned change: `crt-detector-backtest-partial-exits`).
