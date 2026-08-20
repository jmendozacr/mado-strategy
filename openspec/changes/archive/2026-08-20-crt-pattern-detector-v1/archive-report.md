# Archive Report: crt-pattern-detector-v1

**Archived at**: 2026-08-20T14:15:00Z  
**Verify verdict**: pass-with-followups  
**Spec version archived**: V4 (signed)

## Summary

Archived the CRT/ICT pattern detector v1 — a layered pure-function pipeline encoding 5 of 7 originally-named setup types (Swing, FVG, CRT range, MSS, Model-1) from the CRT 2026 mentorship series into detection rules. Synced signed V4 spec to main at `openspec/specs/detector/spec.md`. All 105 tests passing; import-linter clean; 28/28 REQ-IDs covered. 6 non-gating audit findings registered as followups in `openspec/pending-changes.md`. Steward reckoning recorded an outcome-gap (legibility at multi-week scale) overridden by human; 5 usability followups also registered.

## Specs Synced

| Domain | Type | REQs Added | REQs Modified | REQs Removed |
|---|---|---|---|---|
| detector | New | 28 | 0 | 0 |

Main spec now at: `openspec/specs/detector/spec.md` (V4 signed, change-log annotation removed per archive protocol).

## Archive Location

Filesystem: `openspec/changes/archive/2026-08-20-crt-pattern-detector-v1/`  
Original change folder: (moved 2026-08-20, verified SRC gone / DEST present / file count preserved)

## Lessons Learned Persisted

1. **Manual acceptance at production scale surfaces bugs that unit tests cannot** — 3 separate real-MT5-data runs (100k+ rows) found O(n²) perf, chart legibility, and date-windowing bugs that 105 passing tests never caught; validates principle that small-fixture TDD is insufficient for performance-sensitive code. (type: pattern)

2. **Fixture arithmetic errors masquerade as passing tests** — overlapping-gap and min-size-threshold fixtures passed for wrong reasons; both caught only by running against correct data, illustrating non-obvious fixture mistakes. (type: discovery)

3. **Regression in bug-fix logic due to code variable naming vs. domain source** — Judgment-day Round 2 caught entry-price "fix" grounded in variable names rather than charter-2 source, silently breaking behavior. Demonstrates risk of refactoring logic divorced from domain justification. (type: pattern)

4. **Unspecified scope bullets can disable all downstream gates** — "conservative tuning / few false positives" bullet had no REQ-ID or acceptance criterion, so no gate (spec/design/slice/verify/judgment-day) could catch real-world miss. Only reckoning at realistic scale surfaced outcome-gap. (type: discovery)

5. **Confidence from small-scale validation misleads** — Performance fix validated at ~9,500 rows gave false confidence; true 100k+ dataset revealed fix incomplete. Always re-validate optimizations at actual production scale. (type: pattern)

## ADRs

### Promoted to Project-Level
None yet — orchestrator to confirm.

### Recommended but Not Yet Promoted
- **ADR-01**: Detector layering + one-way import rule — enforced by `.importlinter`; applies broadly to any layered detector work
- **ADR-02**: One typed immutable config dataclass — pattern for exposing discretionary thresholds; applies to all future detector additions
- **ADR-03**: No-lookahead / causal-detection contract — structural contract via hypothesis property tests; foundational for detector credibility
- **ADR-04**: Core data model — dataclass + tuple, pandas confined to ingestion — decouples detector API from pandas; applies to performance-critical paths
- **ADR-05**: HTF↔LTF partial-candle boundary policy — `insufficient_htf_data` distinct from `unaligned` — conservative exclusion pattern
- **ADR-06**: Instrument identity supplied explicitly via CLI, not parsed from CSV — eliminates fragile filename/price-inference parsing

## Followups Registered

| Description | Type | Size | Origin |
|---|---|---|---|
| Ingestion validation: `high<low`, OHLC out-of-range, NaN → error | design-gap | M | verify F-1 |
| Determinism/purity fitness function (hypothesis, per design.md §4.7) | design-gap | S | verify F-2 |
| CLI `--types` filtering asymmetry: HTF `htf_crt_ranges` still shown when excluded | rendering-nit | S | verify F-3 |
| Add `pairs/` to `.gitignore` (61MB untracked MT5 data) | hygiene | XS | verify F-4 |
| Commit S-005 onward + all post-acceptance passes | hygiene | S | verify F-5 |
| Document/test `_track_anchor` pre-confirmation-breach behavior | docs-gap | S | verify F-6 |
| CLI `--status` / `--aligned` filters (narrow to confirmed/HTF-aligned) | feature | M | reckoning 1 |
| Multi-week chart legibility: detect density threshold + warning | feature | M | reckoning 2 |
| Signal ID column or dedup for 764 duplicate row-groups | data-quality | S | reckoning 3 |
| Legend occlusion at day zoom (~12% candles hidden) | rendering-nit | S | reckoning 4 |
| Tick `slices.md` S-006 manual-acceptance checkbox + note | housekeeping | XS | reckoning 5 |

**Total registered**: 11 followups (6 from verify audit, 5 from steward reckoning).

## Final State

- **Spec status**: signed (V4, archived)
- **Main specs updated for**: detector (new domain)
- **Tests**: 105/105 passing (re-run at verify-final)
- **Import-linter**: clean (re-run at verify-final)
- **REQ coverage**: 28/28 REQ-IDs tested, 37/38 scenario rows compliant (1 partial: REQ-21's pre-confirmation-breach untested but defendable reading)
- **Lessons in project memory**: 5 added
- **ADRs in project memory**: 0 promoted yet (6 recommended for confirmation)
- **Pending changes in project memory**: 11 registered (6 verify findings + 5 reckoning items)

## Pre-PR Audit Notes

Verify-report's Adversarial Quality Gate ran a comprehensive pre-PR audit (6 findings) across code drift, design-promise gaps, and rendering/operational concerns. All 6 findings failed at least one of two gating filters (demonstrated failure AND outcome-blocking relevance) — none gate this archive. Findings 1-2 are design promises never delivered; 3 is a rendering consistency nit; 4 is an operational risk (data-directory commit); 5 is an operational blocker for PR (uncommitted work); 6 is an undocumented judgment call. All are correctly registered as followups rather than archive gates. No blocking Bug or MAJOR findings at the outcome-relevance level.

Steward reckoning (outcome-verdict) detected one outcome-gap: REQ-23.1's "multi-week series, all 6 types visually distinct" at realistic scale (~9 trading days, 3.48 detections/candle average) renders unreadably — legibility holds only at ~1 day zoom. Gap is scope-category (missing actionability/selectivity criterion in triage spec) rather than problem-fit; tool delivers honest detection and filterable CSV; human override confirms workflow match (window-tighter, filter-the-CSV path acceptable). 5 usability followups registered from reckoning questions 1-5.

## Artefacts Persisted

| Artefact | Location |
|---|---|
| Archive report | `openspec/changes/archive/2026-08-20-crt-pattern-detector-v1/archive-report.md` |
| Main spec | `openspec/specs/detector/spec.md` (V4 signed, new domain) |
| Lessons learned | `openspec/pending-changes.md` (5 new entries) |
| Pending changes | `openspec/pending-changes.md` (11 total entries) |

---

**Archive sealed**: 2026-08-20  
**Next step**: Orchestrator to surface ADR promotion recommendations to human for confirmation, then continue cycle.
