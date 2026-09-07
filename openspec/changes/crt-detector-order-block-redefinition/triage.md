# Triage: ICT Order Block Redefinition (Structural / BOS-Anchored)

**Classification**: L
**Work type**: feature (redefinition of an existing, archived detector's core rule) | **Urgency**: normal
**Decided at**: 2026-09-05
**Change name**: `crt-detector-order-block-redefinition`
**Program**: `crt-detector-key-level-confluence` — reopens sub-change #2 (`crt-detector-ict-order-block`, archived 2026-09-03, spec V4) rather than extending it as a new sub-change; entangled with the NOT-YET-STARTED sub-change #3 (`crt-detector-breaker-block`) — see Architectural Risk below.

Council: this triage was authored by a single agent covering both the architect and pm lens directly (not two blind sub-personas) given the task's own instruction to execute inline; both lenses are represented in the sections below. Recommend the FULL council matrix (architect, business-analyst, pm, qa-engineer, all real independent launches) for the downstream L phases per `skills/_shared/council-matrix.md`.

## Problem & Scope

**Why now**: The program's steward reckoning on sub-change #2 returned `delivered-pending-activation` (obs #479) — the human explicitly declined to trust the 98.88-99.23% discrimination number on an ad-hoc visual review alone. That review surfaced a real concern: at least one of 3 real EURUSDm examples showed the current OB zone essentially co-located with already-trading price, no visible reactive purge-and-bounce — consistent with the current rule (any 2-candle engulfing pair) being too permissive/non-structural. The human then supplied a full, textbook ICT/SMC Order Block definition anchored in market structure, explicit that this must become "un algoritmo determinista," not a visual/subjective approximation.

```yaml
scope:
  in_scope:
    - Redefine ICTOrderBlock detection: Market Structure (Swing High/Low, HH/HL/LH/LL) -> Break of Structure (BOS, configurable close-vs-wick confirmation) -> Displacement (body-vs-ATR multiplier, configurable, spanning up to N candles) -> backward scan from displacement start for the last OPPOSING candle within a configurable lookback cap -> that candle is the Order Block
    - Configurable zone bounds: full-candle (high/low) | body (open/close) | open-to-extreme
    - Lifecycle: active -> mitigated -> invalidated, each with configurable criteria (mitigation: touch | midpoint | close-inside; invalidation: close | wick beyond zone)
    - Hard no-repaint/no-lookahead requirement across the whole chain — every structural element (pivot confirmation, BOS, OB) usable strictly incrementally, with an explicit raw-index vs first-knowable-index distinction (matches this codebase's existing pattern at SEAM-02's `origin_index` semantics and MSS's own break-index resolution, but now threaded through a materially longer pipeline)
    - Reconciling with the ALREADY-ARCHIVED, signed spec (V4, REQ-61/62/63/64/66/67, MODIFIED REQ-24/REQ-41.3) — this reopens those REQs (destructive-sync shape, per this project's established pattern for reopening signed work), not an in-place unfreeze
    - Same `kind="ict_order_block"` KeyLevel source (REPLACES the current engulfing-rule detector and its `to_key_levels` adapter, not a second parallel source) — SEAM-01/SEAM-02 contracts with `alignment`/`viz`/`backtest`/`cli` stay intended to hold, but must be re-verified against the new lifecycle's status vocabulary (`active`/`mitigated`/`invalidated` vs. today's `open`/`invalidated`) and new zone-bound math
  out_of_scope:
    - crt-detector-breaker-block (sub-change #3, not yet started) — see Architectural Risk; explore must determine whether it now shares this change's structure-break/BOS building block, but the Breaker Block detector ITSELF is not this change's scope
    - Rejection Block (project/pending-changes, deferred — no definitional source; NOT this concept)
    - The Turtle Soup + Model-1-in-zone 5th-pivot idea (project/pending-changes obs #489, explicitly rejected by Council; NOT reopened here)
    - Re-litigating whether the confluence-gate CONCEPT itself carries predictive value (see Risks — real, but a program-level question, not this change's)
```

## Criteria Evaluation

| Criterion | Evidence | Score |
|---|---|---|
| Files affected | Likely 12-16: the detector module itself (relocation candidate — `primitives/` vs `composite/`, see Architectural Risk), its config (`core/config.py::ICTOrderBlockConfig` grows from an empty marker dataclass to ~6 new configurable fields), possibly `composite/mss.py` if BOS generalizes/extends it, `core/key_level.py` (lifecycle vocabulary), `cli.py`, `viz/table.py`, `viz/chart.py`, `alignment/htf_ltf.py` (status-vocabulary and zone-bound consumers), plus new/rewritten tests for swing->BOS->displacement->backward-scan->lifecycle and the no-lookahead property test | L |
| Lines affected | The current rule is ~80 lines total (`ict_order_block.py`) implementing one geometric test. The requested chain (structure, BOS, displacement, backward scan, 3-state lifecycle with 2 configurable criteria sets) is a materially larger algorithm — closer in shape to `composite/mss.py` + `entries/model1.py` combined (~180 lines) than to `primitives/fvg.py` (128 lines), before test code | L |
| New patterns | Two genuinely new, non-precedented pieces: (1) a backward-scan-from-displacement-start algorithm — no existing detector in this codebase walks backward from a later event to anchor an earlier one; (2) a 3-state lifecycle with two independently configurable transition-criteria sets — no existing detector models more than a binary open/invalidated state. Everything else (config dataclass shape, `to_key_levels` adapter, CLI/viz wiring) is precedented | L |
| Bounded contexts | 1 (`detector`), but the reuse question below is a REAL cross-module architectural decision, not mechanical wiring | L |
| Sensitivity | None — confirmed against `project/sensitive-areas` (same conclusion as the archived sub-change #2 triage, obs #297): stateless detection-logic redefinition, no auth/payments/PII/deploy | no override |

### Architectural Risk Flagged (design-blocking — this is the change's central open question)

The three known-facts investigation this triage was asked to ground itself in found a REAL, currently-unresolved entanglement, not a mechanical reuse question:

1. **`primitives/swing.py::detect_swings`** is a plain 3-candle fractal pivot test (no config beyond a placeholder `SwingConfig`). It is lookahead-safe in the sense that a swing at index `i` cannot be confirmed before candle `i+1` is known (one-candle confirmation lag, consistent with `MSSConfig`'s incremental-safety pattern), but it does NOT classify HH/HL/LH/LL trend context — that classification is entirely new work the redefinition needs and neither `swing.py` nor anything else in the codebase currently provides.
2. **`composite/mss.py::detect_mss_events`** already detects a "decisive break of the most recent opposite-kind swing" — structurally the same SHAPE as the requested BOS step, but narrower: it only supports a close-based decisive threshold (`decisive_close_ratio`, a fraction of the swing-to-swing distance), with no wick-confirmation mode, and it does not track/emit the HH/HL/LH/LL sequence the redefinition's Market Structure step needs. It is also NOT currently wired into any KeyLevel/confluence path — `cli.py`/`viz/table.py`/`viz/chart.py` are its only real consumers today, output-only. **This is NOT the same concept as the requested BOS out of the box, but it is a compatible building block a generalization could extend** (add a wick-confirmation mode + trend-sequence tracking) rather than a from-scratch reinvention.
3. **Confirmed, not assumed**: the archived sub-change #2 (V1-V4) NEVER actually used `composite/mss.py` or any structure-break concept — its own M-triage (obs #461/#460) flagged the primitives-cannot-import-composite layering risk as design-blocking, but the eventual V1 design sidestepped it entirely by choosing a structure-FREE immediate-engulfing rule (confirmed directly in the archived design.md: "`primitives/ict_order_block.py` needs literally zero code changes for V3 — it was already series-agnostic"). **The injection-shape/reuse question was never actually answered by that change — this is genuinely the first time it must be.**
4. **The planned, not-yet-started sub-change #3 (`crt-detector-breaker-block`)** is explicitly scoped in the program plan as depending on `composite/mss.py::MSSEvent` (per charter-4 [00:07:11]) and as "extracts and reuses #2's shared detection kernel rather than duplicating it" (program.md row 3) — a kernel that, per point 3 above, does not currently exist (V4 has no shared structural kernel to extract). **If this redefinition and #3 each independently build their own BOS/structure-break logic, the program ends up with three divergent implementations of the same market-structure concept** (`composite/mss.py` as-is, this change's new BOS, and whatever #3 invents) — exactly the risk this triage's brief called out as needing reconciliation, not something explore can defer.

**Recommendation to `sdd-explore`**: resolve, before any proposal is drafted, whether BOS for this redefinition (a) generalizes/extends `composite/mss.py` in place (adding wick-confirmation mode + HH/HL/LH/LL tracking) so sub-change #3 later reuses the SAME generalized module, (b) is built as a new, separate `composite/` module the existing MSS stays untouched and #3 is redesigned to depend on the new one instead, or (c) some other reconciliation — and whether the redefined OB detector itself belongs in `primitives/` (current location, but now dependent on a `composite`-layer concept — an ADR-01 layering violation as-is per the same import-direction rule the archived M-triage already flagged) or should move to `composite/` alongside `mss.py`. This also determines whether `composite/mss.py`'s own existing consumers (`cli.py`, `viz/table.py`, `viz/chart.py`, its test suite) are touched by this change.

### Signed-Spec Reopening (destructive-sync shape, per this project's established pattern)

This change reopens `openspec/specs/detector/spec.md` REQ-61 through REQ-64, REQ-66, REQ-67 (all synced from the archived sub-change #2's V4), plus the already-MODIFIED REQ-24/REQ-41.3 (the `key_level_source` CSV column). The current REQ-61 wording ("immediate-engulfing rule") is being REPLACED by a structurally different detection rule — `sdd-spec` must treat this the same way the program's own REQ-45 and REQ-24/41.3 reopenings were handled (explicit MODIFIED blocks, not new REQs left standing alongside contradicting old ones). The `ICTOrderBlock` dataclass's own shape also changes (`status: Literal["open", "invalidated"]` -> a 3-state lifecycle; zone `top`/`bottom` derivation changes from "always candle body" to a configurable bound) — downstream consumers of that shape (`viz/chart.py`, `viz/table.py`) need re-verification, not just the KeyLevel adapter boundary.

### Program-Level Risk (surfaced for awareness, not a scope blocker)

`project/pending-changes` (obs #303) records TWO independent, real-data counterfactual measurements (2026-09-03, 2026-09-04) finding that KeyLevel-confluence crediting — under BOTH the current detection rule and a refined crediting mechanism — shows NO measurable winrate/R-multiple edge over non-credited signals, with the explicit recommendation to reconsider the confluence-gate CONCEPT before investing further sub-changes. This redefinition's own motivation is definitional correctness/trust in the mechanism (the human's explicit framing: "necesito convertir el concepto... en un algoritmo determinista"), which is a legitimate problem independent of whether it moves a discrimination or winrate number — but the program's next real decision point (proceed to #3, or reconsider confluence-gating itself) should weigh this change's real-data result against that existing flat-signal finding, not treat a more rigorous rule as automatically resolving the program's paused state.

## Recommended Path

**L — full pipeline.** Mandatory walking skeleton + SPIDR slicing via `sdd-slice` (max 7 slices, prefer fewer). Council per `skills/_shared/council-matrix.md`:
- `sdd-explore`: architect + qa-engineer (always for L) — architect specifically tasked with resolving the Architectural Risk above BEFORE any proposal; qa-engineer scoping the combinatorial test surface (BOS mode x zone-bound mode x mitigation criteria x invalidation criteria)
- `sdd-propose`/`sdd-spec`: business-analyst + pm (+ architect if the explore output confirms an architectural shift, which is likely)
- `sdd-design`: architect (+ tech-writer if the lifecycle status vocabulary change is judged a public-contract change to `detections.csv`/chart consumers)
- `sdd-verify --mode=final`: architect + qa-engineer + whichever conditional personas participated in design

No `security-engineer`/`ux-designer`/`dba` — no sensitivity override, no UI surface, no data-store layer.

**Abstraction Ladder entry**: A1 (Flow) — per the L-triage default, reinforced here since the human's own stated problem is about trusting/using the mechanism (a flow-level concern: "quiero revisar el OB de 1D y su confluencia con H4 y gatillo en 15M"), not a pure code-level ask. Descend A1 -> A2 -> A3 -> A4 through explore/design; the A3 baseline-mapping step must classify the Architectural Risk's resolution as `deviates` -> ADR if it changes `.importlinter`'s layer placement of the OB detector or extends `composite/mss.py`'s public shape.

## Priority / Debt Flags (PM lens)

- **Scope discipline**: keep this change to redefining the ONE detector (`ict_order_block`) and its lifecycle. Do not let it silently grow into building `crt-detector-breaker-block` (#3) even if explore concludes they should share a kernel — the shared kernel (if any) is this change's deliverable; the Breaker Block DETECTOR itself stays #3's job, sequenced after.
- **Do not reopen** Rejection Block or the Turtle Soup/Model-1-in-zone idea — both explicitly out of scope per `project/pending-changes`.
- **Flag to the orchestrator** (not this triage's job to execute): `openspec/changes/crt-detector-key-level-confluence/program.md` row 2 currently reads "done" for `crt-detector-ict-order-block` — once this change is triaged/planned, the program plan itself likely needs a revision-history entry noting sub-change #2's deliverable is being redefined, and row 3's dependency description ("reuses #2's shared detection kernel") needs to point at whatever this change's explore/design actually produces.
- **Real-data comparison discipline**: mirroring sub-change #2's own PM flag, keep design/slice scope to what's needed to produce a trustworthy, visually-verifiable Daily-tier OB (the human's actual ask) — avoid smuggling in production polish that doesn't serve that verification.

## Sensitivity

None. Confirmed against `project/sensitive-areas` (obs #297) — same conclusion as the archived sub-change #2's own triage; nothing about this redefinition touches auth/payments/PII/deploy.

## `ready_for_next_phase`: YES, contingent on `sdd-explore` (deep, L-depth) resolving the Architectural Risk above (BOS/structure-break reuse-vs-new-module decision, and this detector's own layer placement) BEFORE `sdd-propose`. This triage found the reuse question real and non-trivial, as instructed, but not so entangled that it should block classification — the entanglement IS the explore phase's job.
