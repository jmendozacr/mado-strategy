# Triage: ICT Order Block Detector

**Classification**: M
**Work type**: feature | **Urgency**: normal
**Decided at**: 2026-08-31
**Change name**: `crt-detector-ict-order-block`
**Program**: `crt-detector-key-level-confluence`, sub-change #2 of 3 (dependency order per program plan, engram `sdd/crt-detector-key-level-confluence/program` obs #413)

Council: architect + pm ran in parallel (anti-anchoring — independent reads, blind to each other), synthesized here.

## Problem & Scope

Scope fixed by the program (obs #413, row 2) — triage classifies size/path, doesn't relitigate scope:

```yaml
scope:
  in_scope:
    - New ICTOrderBlock detector in detector/primitives/, registered as a 2nd Key Level source through sub-change #1's existing adapter seam (core/key_level.py::KeyLevel, to_key_levels(...) -> list[KeyLevel] pattern already built on branch wip/crt-detector-key-level-confluence-core-s000, commit 50daee0)
    - detections.csv source-attribution column (deferred from #1 — meaningless with 1 source, meaningful with 2)
    - Named ICTOrderBlock / ict_order_block throughout to avoid colliding with Model-1's already-shipped informal "order block" (REQ-17 anchor candle)
  out_of_scope:
    - crt-detector-breaker-block (sub-change #3) — sequenced after this one, reuses this one's kernel
    - Rejection Block, Swing as Key Level sources — deferred out of the program entirely (unchanged)
    - Building a sources-registry abstraction for >2 Key Level sources (Rule of Three — plain list-concat in cli.py is enough at 2 sources; revisit at #3)
```

**Why now, out of the program's original strict dependency order**: sub-change #1's own real-data gate (S-000.9) found FVG-only confluence discriminates only 1.5-3.0% (floor 10%, obs #449) — not enough to decide accept/tighten/reconsider on one data point. #2 exists specifically to produce a second, comparable real-data number.

## Criteria Evaluation

| Criterion | Evidence | Score |
|---|---|---|
| Files affected | ~9-10: `primitives/ict_order_block.py` (new, ~100-160 lines), `tests/test_ict_order_block.py` (new), `core/key_level.py` (+1-3 lines, widen `Literal`), `core/config.py` (+new `ICTOrderBlockConfig`), `cli.py` (+15-30 lines), `viz/table.py`, `viz/chart.py`, `tests/property/test_no_lookahead.py` (+new K-constant + property test), `tests/test_cli.py`/`test_alignment.py` (mixed-source pooling) | M |
| Lines affected | ~350-550 (read against `primitives/fvg.py` 128 lines and `primitives/crt_range.py` 127 lines as the size precedent) | M |
| New patterns | Mostly precedent (the `to_key_levels` adapter shape, `KeyLevel.kind` widening, CSV/chart plumbing all follow `primitives/fvg.py` exactly — `core/key_level.py`'s own docstring already anticipates `ICTOrderBlock` as the 2nd source). Two genuinely new spots: (1) the structure-break detection concept itself, (2) the CSV source-attribution column reopening REQ-24/REQ-41.3 | M |
| Bounded contexts | 1 (`detector`), but the structure-break dependency touches a real layer-boundary risk (see below) | M |
| Sensitivity | None — confirmed against `project/sensitive-areas` (obs #297): stateless detection-logic addition, no auth/payments/PII/deploy | no override |

### Architectural Risk Flagged (design-blocking, not a footnote)

`ICTOrderBlock` detection needs a "structure break" concept. That concept already exists as `composite/mss.py::MSSEvent`, but `composite` sits ABOVE `primitives` in `.importlinter`'s layers contract — `primitives/ict_order_block.py` cannot import `composite.mss`, even for a type hint, without violating ADR-01. Well-precedented mitigation exists in this codebase (`entries/model1.py`, `alignment/htf_ltf.py` both take pre-computed HTF/structure data as injected params, computed by `cli.py` which is allowed to import every layer) — but the exact injection shape is a **design decision**, not mechanical, and `sdd-explore` must resolve it before `sdd-propose`/`sdd-spec`, not defer it.

### Domain-Definition Risk Flagged (design-blocking)

`docs/charter-1..5.md` never formally define the classical ICT Order Block detection rule — they reference it as a Key Level type and explicitly distinguish it from Model-1's own informal "order block" (charter-2.md:38-39), but the actual detection algorithm (which candle, how far back, invalidation rule) has to come from verified general ICT knowledge, not this repo's docs. Per the External Ground Truth contract: this is an `external_assumptions[]` entry — a wrong detection rule changes real backtest P&L numbers (a magnitude claim), so it cannot be left unmeasured or silently assumed. `sdd-explore` must verify this against real ICT source material (not infer from general training knowledge alone) and `sdd-spec` must get explicit user confirmation on the exact rule before design locks it in.

### CSV Schema Risk Flagged (design-blocking)

The `detections.csv` source-attribution column reopens REQ-24/REQ-41.3, which sub-change #1's *signed* spec explicitly locked at a fixed 7-column header. This needs the same explicit reopening #1 did for REQ-45 (destructive-sync, not a silent schema addition) — `sdd-spec` must handle this formally.

## Recommended Path

M light pipeline: propose+spec merged (one artefact, one signature), `sdd-slice` (max 4 slices), all phases sonnet. No Council by default at explore/design (no sensitivity override) — but `sdd-explore` (light, single pass) MUST resolve the 3 design-blocking questions above before propose, not defer them as notes.

Abstraction Ladder entry: A2 (System) — plus A1 (Flow) since this affects the user's actual backtest/signal-trust flow, same as #1.

## Priority / Debt Flags (PM lens)

- **Minimum-scope-for-the-comparison caution**: this sub-change exists to produce a second real-data number for #1's stuck calibration decision. Explore/design should keep scope to what's needed for that real-data comparison run — avoid smuggling in full production polish (extra CLI flags, chart refinements) that doesn't serve the comparison and would delay the actual decision #1 is waiting on.
- **Mandatory go/no-go checkpoint after #2's own real-data result**, before automatically proceeding to `crt-detector-breaker-block` (#3): if ICTOrderBlock confluence ALSO discriminates poorly (in the same 1-3% range as FVG), that's evidence the confluence-gate CONCEPT itself may be the problem, not any single source — a different conversation than "add a 3rd source and hope." Flag this explicitly at this sub-change's own walking-skeleton gate (mirroring #1's S-000 structure), don't wait for #3.
- Confirmed: no reintroduction of Rejection Block or Swing — scope stays exactly what the program committed to.

## Sensitivity

None. Confirmed against `project/sensitive-areas` (obs #297).

## `ready_for_next_phase`: YES, contingent on `sdd-explore` resolving the 3 design-blocking questions above (structure-break injection shape; Order Block detection rule verified against real ICT source material; REQ-24/41.3 reopening mechanics) before `sdd-propose`.

## Persona reports (full detail)

- Architect: engram obs #461, topic `sdd/crt-detector-ict-order-block/triage-architect`
- PM: engram obs #460, topic `sdd/crt-detector-ict-order-block/triage-pm-lens`
