# Proposal: CRT/ICT Pattern Detector v1

**Change**: crt-pattern-detector-v1 | **Triage**: L

## Intent

The repo owner trades using Mado's CRT/ICT methodology (`docs/charter-1..5.md`) and today identifies every setup — Swing points, Fair Value Gaps, CRT ranges, Model-1 entries — by eye, candle by candle, on every chart they review. This is slow and error-prone precisely because the methodology has many interacting rules. v1 encodes those rules as a Python detector that runs against historical OHLC and produces one marked-up chart + table per review, so the trader's job becomes reviewing machine-flagged candidates instead of scanning blind.

## Scope

See `triage.md` for the authoritative in/out-of-scope list (corrected mid-plan).

## Capabilities

### New Capabilities
- `ohlc-ingestion` — load a MetaTrader CSV export into the shared candle series model
- `htf-ltf-alignment` — correlate HTF CRT events with LTF Model-1 windows per the timeframe-pairing table
- `swing-detection`, `fvg-detection`, `crt-range-detection`, `mss-detection`, `model1-entry-detection`
- `configurable-parameters` — discretionary ICT thresholds exposed via `DetectorConfig`
- `no-lookahead-completeness` — property-based causal-detection guarantee across all detectors
- `cli-output-filtering` — date-range and detector-type output filters
- `chart-overlay-viz` — chart image + companion detection table

### Modified Capabilities
None — greenfield, no existing capabilities in this repo.

## Approach

Layered pure-function pipeline: `detector/{core,primitives,composite,entries,alignment,ingestion,viz}/`, one-way imports (`core` → `primitives` → `composite`; `entries` → `core`+`primitives` only; `alignment` → `core`+`primitives`+`entries`; `viz`/`cli` → result types only; `ingestion` → leaf). Tier 1 primitives (Swing, FVG, CRT range) depend only on `core`; Tier 2 composite (MSS) depends on Swing; Tier 3 (Model-1) depends on CRT range + FVG; Tier 4 (alignment) depends on CRT range + Model-1. Detectors with a series-end-undecided property (Model-1) return a `CONFIRMED | INVALIDATED | PENDING` three-state result, never a bare boolean.

Six ADRs formalized in `design.md`: layering + one-way-import rule, config-dataclass strategy, no-lookahead/causal-detection contract, core data model (dataclass + tuple, pandas confined to ingestion), instrument-identity-via-CLI-flag, HTF/LTF partial-coverage policy.

## Affected Areas

See `design.md` §File Changes for the exhaustive list (22 new files under `detector/`, plus `CLAUDE.md` updated to describe the new subproject).

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| False-positive propagation through the detector chain (Swing→MSS, CRT+FVG→Model-1) | Medium | Each tier independently unit-tested against stubbed upstream input |
| Undocumented threshold defaults misrepresent Mado's qualitative rules | Medium | Every default pinned + documented in `design.md` §4.4, sourced from `DetectorConfig` only (enforced by a fitness function) |
| No real-world data validation during planning (charters are prose + screenshots, not machine-readable OHLC) | Medium | Manual acceptance step added to slice S-006: run against one real MT5 export, eyeball the result, before v1 is considered done |
| No existing Python/test infra in this repo | Low | Walking-skeleton slice (S-000) establishes pytest + fixture pattern once |

## Rollback Plan

Pure new-code addition isolated to `detector/` — does not modify `docs/` or any existing repo content, no database, no deployed service. Rollback: `git revert` the merge commit(s) for this change. Validate by confirming `detector/` no longer exists and `docs/` is byte-identical to the pre-change commit. No data-loss risk.

## Dependencies

Python 3.12, `uv`. New dependencies: pandas, numpy, matplotlib, pytest, hypothesis, import-linter.

## Success Criteria

- [ ] All 5 detectors implemented as pure functions per the tiered architecture, each with a dedicated pytest suite
- [ ] No-lookahead property test (hypothesis) passes for all 5 detectors + alignment
- [ ] Import-direction fitness function passes (`.importlinter`)
- [ ] End-to-end run against a real MetaTrader CSV export produces `overlay.png` + `detections.csv`
- [ ] Manual acceptance: user runs against one real export and confirms the output looks sane
- [ ] All 6 ADRs documented
- [ ] Full test suite passes with zero failures, runnable via `cd detector && pytest`
