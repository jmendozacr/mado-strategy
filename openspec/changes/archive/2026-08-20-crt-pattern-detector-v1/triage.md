# Triage: CRT/ICT Pattern Detector v1

**Classification**: L
**Change name**: `crt-pattern-detector-v1`

## Problem & Scope

> Stop manually scanning Forex charts by hand to find CRT/ICT setups — the notes in `docs/charter-1..5.md` define the methodology precisely enough to encode most of it as detection rules. v1 delivers 5 of the 7 originally-named setup types (Swing, FVG, CRT range, MSS, Model-1); Order Block (ICT-conventional) and Breaker Block are deliberately deferred to a fast-follow change, ratified at the steward foresight gate.

### In Scope
- Historical OHLC ingestion (Forex: EUR/USD, GBP/USD, DXY) via MetaTrader 5 CSV export, symbol supplied explicitly via CLI flag (the MT5 export format carries no symbol column)
- Core candle/range data model shared by all detectors
- Swing High/Low detector (3-candle fractal)
- Fair Value Gap (FVG) detector (3-candle imbalance)
- Market Structure Shift (MSS) detector
- CRT range detector (3/2/Multiple-Candle models, sliding-window, CLOSE-based true/false-break resolution per charter-5's "wicks lie, closes tell the truth", only surfaced once resolved)
- Model-1 entry detector (purge + engulf-or-FVG-fill + retest) — absorbs charter-2's "Order Block" as internal anchor logic, no standalone OB detector
- HTF↔LTF timeframe alignment/tagging (paired CSV ingestion, charter-2's pairing table, conservative tail-of-data handling)
- Visual overlay (chart image, 6 distinct marker encodings) + companion detection table (CSV)
- CLI date-range and detector-type output filters
- Configurable parameters for every discretionary ICT threshold (`DetectorConfig`, Python-level defaults, no CLI/file config parsing in v1)
- Full property-based (hypothesis) no-lookahead test suite across ALL 5 detectors + alignment
- Conservative tuning philosophy (few false positives over high recall) for all discretionary detectors

### Out of Scope
- Backtest simulation / performance metrics (future change)
- Live data feed / real-time alerts (future change)
- Standalone ICT-conventional Order Block detector + Breaker Block detector (fast-follow M — pending change `crt-detector-order-block-breaker`)
- SMT Divergence detector (pending change `crt-detector-smt-divergence`)
- Rejection Block detector (pending change `crt-detector-rejection-block`)
- TSQ 5-phase sequencing (charter-4/5)
- Broker integration / order execution
- Any interactive UI (web app, dashboard) — static image + CSV table only
- Multi-symbol batch processing — single series or single HTF/LTF pair per CLI invocation
- Session/Kill-Zone time-of-day filtering logic (alignment is price/time-window against the HTF CRT range only)
- Sub-5-minute LTF timeframes (charter-2's pairing table stops at 1H→5M)
- CRT range "currently forming / live" state (v1.1 follow-up — see pending changes)

## Recommended Path
Full Planner with Council (L). Skills: `sdd-explore` → `sdd-propose` → `sdd-spec` → `sdd-design` → `sdd-slice` → plan-verify gate → `/build`.

## Personas (L)
Business Analyst, PM, QA Engineer, Architect — always for L. UX Designer / Tech Writer / Security Engineer / DBA not triggered (no interactive UI, no public API, no sensitivity override, no schema/migration).

## Note on this version
This triage was corrected mid-plan (during the plan-verify gate) after propose/design negotiated scope changes (HTF/LTF alignment added, CLI filters added, OB/Breaker deferred) that the original triage draft hadn't captured. This is the authoritative, final scope.
