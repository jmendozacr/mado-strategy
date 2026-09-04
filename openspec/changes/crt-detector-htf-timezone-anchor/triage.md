# Triage: HTF Candle Construction — Real Timezone Anchor

**Classification**: L
**Work type**: bug · **Urgency**: normal
**Decided at**: 2026-08-31T21:02:00Z
**Change name**: `crt-detector-htf-timezone-anchor`

## Problem & Scope

> The detector treats every HTF (H4) candle timestamp as if it were plain UTC wall-clock time — `core/kill_zone.py`'s docstring (REQ-29) explicitly claims this was "verified against real broker data — no further broker offset". It was not: cross-checking two real FVG examples from the user's own TradingView chart (fixed to UTC-4) against our `EURUSDm`/`GBPUSDm`/`DXYm` H4 data proved the broker's server time is actually **UTC+3** (EEST, the MetaQuotes/MT5 historical default, not an edge case) — a 3-hour, structurally consistent offset, confirmed independently on two separate timestamps that both landed exactly on real H4 candle boundaries once the offset was applied. This means every H4 candle boundary in the whole pipeline (CRT range, purge detection, alignment) is built on a false timezone assumption, AND `in_ny_kill_zone`'s NY Kill Zone classification has been computing against the wrong wall-clock hour since `crt-detector-killzone-filter` shipped and archived. Empirically, re-anchoring HTF construction to real wall-clock time (tested via UTC-4/NY-local reaggregation from M15) changed `crt-detector-key-level-confluence-core`'s S-000 gate from failing 2 of 3 acceptance criteria to average-R improving across all 3 test instruments (EURUSDm, GBPUSDm, DXYm) — strong evidence this is a real, consequential defect, not a cosmetic one.

```yaml
scope:
  in_scope:
    - Fix the broker-server-time assumption at its source: HTF (and any wall-clock-sensitive) candle timestamps must be interpreted/constructed against the REAL timezone, not trusted as literal UTC
    - core/kill_zone.py::in_ny_kill_zone — correct the UTC assumption for NY Kill Zone classification
    - HTF (H4) series construction — anchor 4-hour candle boundaries to real wall-clock time (NY-local, matching how the whole CRT/ICT methodology is taught — session references, kill zones — rather than an arbitrary broker-server boundary)
    - Re-baseline any existing test (crt-pattern-detector-v1, crt-detector-backtest-engine, crt-detector-killzone-filter) whose fixtures/assertions assumed the old (wrong) timezone interpretation
    - Determine and document the actual broker server timezone rule (fixed offset vs DST-following EET/EEST) with real evidence, not assumption
  out_of_scope:
    - crt-detector-key-level-confluence-core's own remaining slices (S-001..S-006) — that sub-change stays PAUSED until this lands, then resumes against whatever HTF-construction contract this change produces
    - Program sub-changes #2 (crt-detector-ict-order-block) and #3 (crt-detector-breaker-block) — untouched
    - Any change to LTF (M15) candle boundaries — the 7-hour offset between broker-server and NY-local is an exact multiple of 15 minutes, so M15 bucket boundaries are unaffected; only timeframes not evenly divisible by the offset (H4, and by extension any coarser HTF) need re-anchoring
    - Making the broker/server offset a user-configurable parameter — YAGNI until a second broker/instrument with a different offset is actually in scope
```

## Description Received

> Surfaced by the orchestrator mid-investigation of `crt-detector-key-level-confluence-core`'s S-000 halt (REQ-60.2/.4 failing on real EURUSDm data). The user manually cross-referenced two real FVG examples from their own TradingView (FOREXCOM, fixed UTC-4) against our data; neither matched under the "broker timestamps are UTC" assumption already coded into `core/kill_zone.py`. Root cause established via direct empirical verification (real OHLC data, the actual `detect_fvgs`/pipeline functions, and an A/B backtest comparison across 3 instruments) before this triage — user explicitly agreed this deserves its own dedicated change rather than being folded into the confluence sub-change's scope.

## Criteria Evaluation

| Criterion | Evidence | Score |
|---|---|---|
| Files affected (estimated) | ~10-14: `ingestion/loader.py` or new HTF-construction module, `core/kill_zone.py`, possibly `core/config.py`, `cli.py` wiring (`--htf-csv`/`--htf-symbol` contract may change) — plus re-baselining `test_kill_zone.py`, `test_cli_e2e.py`, `test_cli_backtest_e2e.py`, `test_alignment.py`, `tests/property/test_no_lookahead.py`, `test_loader.py`, and `crt-detector-key-level-confluence-core`'s own fixtures | L |
| Lines affected (estimated) | ~800-1500 — the confluence sub-change's OWN fixture redesign (S-000.2, one file) already touched ~20 tests for a narrower change; this touches fixtures across 3 already-archived changes | L |
| Bounded contexts | 1 (`detector` is the sole code subproject) but spans every internal layer that consumes HTF/timestamp data (ingestion → core → alignment → cli → backtest) | M-L |
| New patterns | NEW — timezone-anchored candle aggregation from a finer series has no precedent in this codebase | L |
| Test types | Existing types (unit/e2e/property), but breadth of re-baselining across 3 already-shipped changes is the real cost, not new test machinery | M/L (non-discriminating) |
| Precedent | None — greenfield within this codebase | no reduction |

### Overrides Triggered

- **Cross-cutting concern, REDESIGNED (not mechanically repeated)**: how the entire pipeline interprets wall-clock time is a foundational, shared concern being corrected at its root, not a pattern copy-pasted across modules → reinforces L (would floor at M otherwise).

No sensitivity override — confirmed against `project/sensitive-areas`: no auth/payments/PII/security-boundary/deploy/migration behaviour altered (read-only CLI analysis tool over MT5 CSV exports, same as every prior change in this project).

**Final classification**: **L** — files/lines and new-pattern criteria both independently land at L; the cross-cutting-redesign override reinforces it. Blast radius into two already-archived, already-shipped changes' test suites is the dominant risk driver, not raw size alone.

## Recommended Path

- Phase: full Planner with Council
- Skills to invoke (in order): `sdd-explore` (confirm exact broker offset rule + full blast-radius inventory across archived changes — do NOT re-derive from memory, verify against real data as this session already started doing) → `sdd-propose` → `sdd-spec` → `sdd-design` → `sdd-slice` (target ≤7 slices) → `sdd-verify --mode=plan` → `/build` → `/evaluate`
- Slice maximum guardrail: 7 — prefer fewer cohesive slices

## Recommended Personas (L)

| Role | Reason |
|---|---|
| Business Analyst | Always for L |
| PM | Always for L — this also forces a scope-discipline call: does re-baselining archived changes' tests happen IN this change, or as registered followups? |
| QA Engineer | Always for L — the re-baselining risk (silently changing what "passing" means for 3 already-shipped changes) is exactly adversarial-test territory |
| Architect | Always for L — this is a foundational, cross-cutting correction; fitness-function and boundary implications are real |
| Tech Writer | CLI contract (`--htf-csv`/`--htf-symbol`) may change — clarity of the new contract matters to whoever operates this tool |

Security Engineer and DBA not triggered — no sensitivity override, no schema/migration.

## Spec Reference

spec_source: internal — no reference captured.

## Risks Flagged at Triage

- **This blast radius touches already-archived, already-shipped changes** (`crt-pattern-detector-v1`, `crt-detector-backtest-engine`, `crt-detector-killzone-filter`) — re-baselining their tests changes what "passing" meant for work already considered DONE. Architect + QA personas should treat this as a first-class concern, not incidental cleanup.
- **The exact broker-offset rule is not yet formally proven** — this session's empirical match (UTC+3, EEST) is strong (two independent timestamps landing exactly on real candle boundaries) but was derived from live investigation, not a systematic sweep. `sdd-explore` should verify it rigorously (e.g., cross-check against the well-known MT5/MetaQuotes weekly-open-gap pattern) before design commits to a specific offset or offset-detection strategy.
- **`crt-detector-key-level-confluence-core` is PAUSED, not archived, pending this change** — its S-000 code (8/9 tasks, uncommitted) references the current `--htf-csv` file-load contract; whatever this change's design produces as the new HTF-construction interface will require S-000 rework on resume.

## Halt?

No

## Notes for Next Phase

- Read `sdd/crt-detector-key-level-confluence-core/pause` (engram) and `sdd/mado-strategy/broker-timezone-discovery` (engram) for the full empirical trail already gathered this session (real OHLC cross-checks, the A/B backtest comparison, the exact offset-matching methodology) — do not re-derive from scratch, verify and extend it.
- `sdd-explore` should determine whether HTF construction should ALWAYS be derived from a finer-grained (LTF) source (eliminating the `--htf-csv`/`--htf-symbol` CLI flags and the trust-the-export assumption entirely) versus keeping a separate H4 file input but validating/correcting its timezone — this is a real architectural fork, not a detail.
