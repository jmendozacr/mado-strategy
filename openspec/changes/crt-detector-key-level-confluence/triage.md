# Triage: CRT Key Level Confluence

**Classification**: XL
**Decided at**: 2026-08-29T00:00:00Z
**Change name**: `crt-detector-key-level-confluence`

## Problem & Scope

> El pipeline de detección y backtest hoy evalúa TODA la población de setups Model-1 detectados, sin aplicar el filtro de confiabilidad que charter-1 declara como el que separa un setup real de ruido: la confluencia con un Key Level de HTF (FVG, Order Block, Breaker Block, Rejection Block, o un alto/bajo mayor). Cada win-rate/R-multiple producido hasta ahora describe una versión simplificada de la metodología. charter-1 [00:12:02]: "los setups de CRT más confiables ocurren cuando la manipulación reacciona directamente en un Key Level de temporalidad mayor".

```yaml
scope:
  in_scope:
    - Concepto unificado "KeyLevel" (5 tipos: FVG existente, Swing existente, Order Block nuevo, Breaker Block nuevo, Rejection Block nuevo)
    - Tag de confluencia Model-1 x HTF Key Level
    - Columna de confluencia en detections.csv
    - Split de métricas confluencia vs no-confluencia en --backtest
    - Absorbe pending changes `crt-detector-order-block-breaker` + `crt-detector-rejection-block` (obs #303)
  out_of_scope:
    - Partial exits / equity curve / drawdown (crt-detector-backtest-partial-exits)
    - SMT Divergence (crt-detector-smt-divergence)
    - Non-EURUSD instruments
    - CRT range "currently forming" live state
```

## Criteria Evaluation

| Criterion | Evidence | Score |
|---|---|---|
| Files affected | ~18+ (3 new primitives + unification module + alignment/htf_ltf.py + backtest metrics/levels + viz/table.py + cli.py, each with tests) | XL |
| Lines affected | ~1800-2500 (3 detector primitives ~150-200 ea + tests, unification ~100, alignment wiring ~150, backtest split ~150, viz/cli ~100) | XL |
| Bounded contexts | 5 (primitives, alignment, backtest, viz, cli) | XL |
| New patterns | multiple — 3 distinct new detectors (Order Block, Breaker Block, Rejection Block) + 1 new cross-cutting KeyLevel abstraction | XL |
| Test types | existing (pytest + hypothesis, per `primitives/fvg.py`/`primitives/swing.py` precedent) | L |
| Precedent | `primitives/fvg.py`, `primitives/swing.py` establish the pure-function detector pattern each new primitive would mirror — does not offset the overrides below (never applied when an override fires) | not applied |

### Overrides Triggered
- Spans 3+ bounded contexts (primitives, alignment, backtest, viz, cli) → forces XL decomposition
- Multiple new patterns (3 detectors + 1 unification concept) → independently clears XL size threshold

**Final classification**: XL — both the bounded-context override and size criteria land XL independently.

## Halt (Step 5)

Do NOT proceed to Step 6. Suggested decomposition (dependency order):

1. `crt-detector-order-block` — Order Block primitive + tests (parallelizable)
2. `crt-detector-breaker-block` — Breaker Block primitive + tests (parallelizable)
3. `crt-detector-rejection-block` — Rejection Block primitive + tests (parallelizable)
4. `crt-detector-key-level-confluence-core` — unifies FVG/Swing/OB/BB/RB under one KeyLevel concept + confluence tag in alignment (depends on 1-3)
5. `crt-detector-key-level-confluence-reporting` — CSV column + backtest win-rate split + CLI exposure (depends on 4)

Recommend Program Layer (`sdd-program`): sub-changes 1-3 run in parallel, 4 gates on all three, 5 gates on 4. Each of 1-3, triaged alone, likely lands M (single new primitive file + tests, mirrors `fvg.py`/`swing.py` — apply Precedent Modifier per sub-change).

## Risks Flagged

- Pending-change entries `crt-detector-order-block-breaker` and `crt-detector-rejection-block` (engram `project/pending-changes` obs #303) should be marked superseded once this program is accepted, to avoid duplicate tracking.
- "Reacts directly on a Key Level" (price-proximity tolerance) is undefined — an open technical question for sub-change 4's `sdd-explore`, not a triage decision.

## Halt?

Yes — XL. Must decompose per Step 5; orchestrator offers Program Layer to the user.
