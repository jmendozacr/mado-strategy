# Triage: Backtest Two-Stage (Partial) Exit Model

**Classification**: M
**Work type**: feature · **Urgency**: normal
**Decided at**: 2026-09-04
**Change name**: `crt-detector-backtest-partial-exits`

## Problem & Scope

> The user is automating Mado's discretionary CRT/ICT strategy and wants to know if a mechanical implementation can approach Mado's self-reported ~75% winrate. This session measured the current single-fixed-TP backtest engine against real data (23-27% winrate) with no measurable confluence-gate edge. Cross-checking the user's recollection against `docs/charter-2.md:148` and `docs/charter-3.md:71,84` confirmed Mado's real exit method is a two-stage model: a partial exit at 50%-of-CRT-range (equilibrium), remainder riding to the existing 100%-of-range target. The current engine has no notion of a partial exit or split-outcome trade — every trade is binary (full TP or full SL).

```yaml
scope:
  in_scope:
    - Two-stage exit: partial at CRTRange midpoint (configurable/default fraction), remainder to the existing full-range target/stop.
    - Blended R-multiple / outcome for a partial-then-remainder trade.
    - Extended CSV/report fields disclosing the partial outcome (no silent folding into the existing R column).
    - Comparable real-data run (EURUSDm, GBPUSDm, DXYm) producing a winrate/R number for the two-stage model.
  out_of_scope:
    - Trailing stops / breakeven-after-partial.
    - More than one partial level.
    - Full equity-curve/drawdown tracking.
    - Confluence-gate/Key Level crediting logic changes.
    - Lot-size/position-sizing realism beyond a simple fraction abstraction.
```

## Criteria Evaluation

| Criterion | Evidence | Score |
|---|---|---|
| Files affected (estimated) | ~7-8: `backtest/levels.py`, `backtest/simulate.py` (`Trade`, resolution loop), `core/config.py`, `viz/trades_table.py` + matching test files | L |
| Lines affected (estimated) | ~400-650 (production logic extending the per-candle scan/gap-fill pattern + TDD edge-case tests: partial-then-TP, partial-then-SL, gap through partial, same-candle multi-event) | L |
| Bounded contexts | 2 (backtest-simulation domain; viz/reporting layer) | L |
| New patterns | Variant of existing: extends the established per-candle resolution loop (`simulate.py`'s stop/target check + gap-fill), `Trade` dataclass, and `net_r_multiple` formula — not a new architecture | M |
| Test types | Existing types (unit + real-data integration run), no new test infrastructure | M |
| Precedent (before overrides) | Mirrors `detector/backtest/simulate.py`'s resolution loop and `openspec/changes/archive/2026-08-29-crt-detector-backtest-engine/design.md` (original single-TP engine design this change extends) | -1 level |

### Overrides Triggered
None. Confirmed against `project/sensitive-areas` (engram #297): no auth/payments/PII/deployment/migration in this project. No new external dependency (real MT5 CSV data already present under `pairs/{M15,H4,D1}/`). Not 3+ bounded contexts.

**Final classification**: M — size criteria trend L (files/lines/contexts) but 2/5 stay M, and a real, direct precedent (same resolution loop, dataclass, config, and report-writer this change extends) reduces the size-derived L by one level; no override reapplies a floor.

## Recommended Path

- Phase: light Planner
- Skills to invoke (in order): `sdd-explore` (light) → `sdd-propose` (merged mode: proposal + `## Requirements` with REQ-IDs/Given-When-Then, one signature) → `sdd-design` → `sdd-slice` (max 4 slices, prefer fewer)
- Slice maximum guardrail: 4

## Recommended Personas

Personas not applicable for M (no sensitivity override fired).

## Spec Reference

spec_source: internal — no reference captured

## Risks Flagged at Triage

- `Trade`'s `outcome: Literal["win", "loss", "open"]` and CSV schema are consumed downstream (`trades_table.py`, existing reports) — extending them for a split outcome is a contract change design must make explicit, not just additive fields.
- Blended R-multiple weighting (partial fraction vs. remainder) is a real modeling decision with financial-outcome consequences for the win-rate comparison this change exists to produce — treat as a design-blocking question, not an implementation default.
- Precedent is partial: the per-level check mirrors the existing loop, but combining two independent leg resolutions into one net trade result has no existing sibling — explore/design should not assume the extension is purely mechanical.

## Halt?

No

## Notes for Next Phase

`sdd-explore` should read `openspec/specs/detector/spec.md` REQ-30..52 (backtest-simulation/backtest-metrics domains) and the archived `crt-detector-backtest-engine` design's resolution-loop section before proposing the extension shape. Confirm CRTRange already exposes `high`/`low` (it does) — the 50% midpoint is a derivation, not a new primitive.
