# Exploration: Backtest Two-Stage (Partial) Exit Model (crt-detector-backtest-partial-exits)

**Triage**: M
**Persona lens**: none

## Cross-Change Lessons Consulted

- Pattern from change `crt-detector-backtest-engine` (ADR-02, engram #399): "Ambiguity resolved by fixed ORDERING of sweep passes rather than special-casing" — explicitly flagged in that archive as directly reusable for this change. Confirmed by reading `simulate.py`: exit resolution is `open-check → level-choice (SL wins ties) → gap-check`, built on three independent `two_heap_sweep` passes (fill, SL, TP), each a first-touch-index search from a fixed `eligible_at`.
- Pattern from `crt-detector-backtest-engine` (ADR-05): simulation-local price levels are computed independently of detection-output fields — relevant precedent for keeping the partial level a `levels.py`-style derivation, not a new primitive.
- Discovery `project/pending-changes` #303/#399 followup 7: backtest population is read from a pre-`_filter_by_types` snapshot in `cli.py` — a population-selection concern, orthogonal to per-trade exit resolution; does not interact with this change's per-candidate resolution logic.
- No `pattern`/`discovery`-type memory addresses blended multi-leg R-multiple computation specifically — this is new ground for this codebase.

## Affected Flows

Affected Flows: not applicable — this is a backend simulation/reporting change with no user-facing flow (CLI flags/CSV columns extend, no new interactive surface).

## Current State

`detector/backtest/simulate.py::_resolve_trade` treats every trade as a single, binary leg: after the fill pass, two `two_heap_sweep` passes (`_sl_sides`, `_tp_sides`, both starting at `fill_index + 1`, REQ-37) find the first index at which SL or TP is touched. `_resolve_trade` picks whichever resolves first (SL wins ties, REQ-33), applies the REQ-34 gap-through check, and computes one `net_r_multiple()` (`levels.py`) for the whole trade. `Trade.outcome` is a flat `Literal["win", "loss", "open"]`; `metrics.py::compute_metrics` buckets purely on that literal (`== "win"`/`"loss"`/`"open"`) and averages `r_multiple` over all non-`"open"` trades. `take_profit()` sources the full-range target from `AlignedSignal.htf_context` (HTF CRT range opposite extreme) — unchanged by this feature. No 50%/equilibrium level exists anywhere in the pipeline today; `CRTRange` exposes `high`/`low` directly, so the midpoint is a one-line derivation, not a new primitive.

Docs confirm the target model precisely: charter-2 [00:18:46] and charter-3 [00:09:44]/[00:13:55] state TP is "100% del rango **o** parciales en el 50% (Equilibrium)" — the source describes the 50% PRICE LEVEL only; it never states what FRACTION OF POSITION SIZE closes there. That fraction is a modeling decision this codebase must default, not something transcribable from the source.

## Architecture Touchpoints (A3)

No `sdd/{project}/architecture` baseline exists yet (M-triage skips baseline injection at explore); the governing structural contract is `.importlinter`'s ADR-01 layered-pipeline (`core → primitives → composite|entries → alignment → backtest → viz|cli`, `ingestion` a leaf). Confirmed by reading `.importlinter`: `backtest` sits above `alignment`, below `viz`.

| Layer/Component | Action | Why | Baseline fit |
|---|---|---|---|
| `backtest` (levels.py, simulate.py, metrics.py) | modify | new partial-level derivation, third sweep pass, blended R, outcome literal extension | aligns |
| `core` (config.py) | modify | new `BacktestConfig` field(s) for partial fraction/toggle | aligns |
| `viz` (trades_table.py) | modify | new CSV columns + metrics_summary lines disclosing the partial leg | aligns |

No new cross-layer import is introduced; all changes stay within each file's existing layer position. No `deviates` rows.

## Affected Areas

| Path | Impact | Why |
|---|---|---|
| `detector/backtest/levels.py` | Modify | add partial-level derivation (`(high+low)/2` off `htf_context`) alongside `take_profit`; `net_r_multiple` reused per-leg |
| `detector/backtest/simulate.py` | Modify | third `two_heap_sweep` pass for the partial level; `_resolve_trade`/`_resolve_exits` gain two-stage resolution + blended R; `Trade` gains partial-leg fields; `outcome` literal likely extends |
| `detector/backtest/metrics.py` | Modify | `compute_metrics`'s `== "win"`/`"loss"`/`"open"` bucketing must account for any new outcome value(s) — not listed in the task's read list but directly coupled to `Trade.outcome`, confirmed by reading it |
| `detector/core/config.py` | Modify | new `BacktestConfig` field(s): partial-exit enabled flag + fraction (position-size split), default TBD (open question) |
| `detector/viz/trades_table.py` | Modify | `trades.csv` header gains partial-leg columns (contract change, REQ-45-style); `metrics_summary.txt` gains disclosure lines |
| `detector/primitives/crt_range.py` | Read-only | confirmed `CRTRange.high`/`.low` sufficient; no new primitive needed |
| `detector/tests/test_*` (backtest/viz suites) | Modify | new TDD coverage: partial-then-TP, partial-then-SL, same-candle multi-touch, never-reaches-partial (existing single-leg case) |

## Sensitive Areas Crosscheck

No sensitive areas touched — this project's registry (`project/sensitive-areas`, obs #297) has no auth/payments/PII/deployment/migration categories; confirmed directly, no path here matches any registered category.

## Approaches

### 1. Extend the existing sweep-and-resolve pattern with a third level + two-stage resolution
**Description**: Add a `_partial_sides()` `SweepSide` pair (mirroring `_tp_sides()`, same-side monotonic geometry as TP) and a third `two_heap_sweep` pass, eligible at `fill_index + 1` like SL/TP. Extend `_resolve_trade` so: (a) if SL resolves at or before the partial level (pessimistic tie, mirroring REQ-33), the trade is a single-leg loss exactly as today, no partial recorded; (b) if the partial level resolves strictly before SL, leg 1 closes at the partial price, and a SECOND resolution search (reusing the same SL/TP sweep results, since partial and full-TP are same-side/monotonic — a candle touching TP necessarily also touches partial) determines leg 2's exit against the ORIGINAL stop/target, starting after the partial index. Blended R-multiple and a new `Trade.outcome`/schema extension surface the split result.
**Pros**: Reuses `two_heap_sweep` unchanged (ADR-02's own algorithm, no new class); keeps the existing pessimistic-tie-break precedent (REQ-33) as the template for the new SL-vs-partial tie, rather than inventing a new ambiguity rule; `take_profit`/`stop_loss` remain untouched per triage scope.
**Cons**: `_resolve_trade` genuinely grows a second decision branch (not purely additive) — the triage's own risk #3 ("combining two independent leg resolutions into one net trade result has no existing sibling") is confirmed correct by this read; `Trade`/CSV schema change is a downstream contract change for `trades_table.py`/`metrics.py`, not just additive fields.
**Effort**: Medium.
**Pattern fit**: matches existing `detector/backtest/simulate.py`'s sweep-and-resolve structure; the two-stage branch itself is new but built entirely from existing primitives (`two_heap_sweep`, `net_r_multiple`).

## Recommendation

Use Approach 1 — it is the only approach that reuses `two_heap_sweep`/ADR-02's ordering-over-special-casing technique instead of inventing a new resolution algorithm, and it lets sdd-design reuse REQ-33's pessimistic-tie-break as the direct template for the new SL-vs-partial ambiguity rather than a from-scratch design.

## Risks

- Same-candle triple-touch (SL, partial, and full-TP all within one candle's range) has no existing sibling rule — REQ-33 only resolves SL-vs-TP; sdd-design must state explicitly whether SL still wins pessimistically over BOTH other levels (recommended, consistent with REQ-33's intent) or needs its own scenario.
- `Trade.outcome`'s `Literal["win","loss","open"]` and the 13-column `trades.csv` header are consumed by `metrics.py` and downstream reports (REQ-45-style contract) — extending them is a breaking schema change to an existing, spec-locked contract, not a pure addition; design must decide the exact new literal(s)/columns.
- Real-data comparability: the triage's success criterion is a comparable EURUSDm/GBPUSDm/DXYm run producing a winrate/R number for the two-stage model — the blended-R convention chosen directly determines whether that number is meaningful; get the convention right before running it, not after (re-running is cheap, but a wrong convention would misinform the very decision — confluence-gate program pause — this change's context exists to inform).

## Open Questions

- type: technical
  question: "How should the blended R-multiple be computed for a trade that partials at the 50%-of-range level and lets the remainder ride? Candidate conventions found in real trading-system backtesting practice: (A) **fraction-weighted sum of independent leg R's** — `blended_R = fraction_closed * R_leg1 + (1 - fraction_closed) * R_leg2`, where `R_leg1 = net_r_multiple(entry, partial_price, stop, ...)` (always positive, since partial only fires when price moved favorably) and `R_leg2 = net_r_multiple(entry, leg2_exit_price, stop, ...)` computed against the SAME original entry/stop (industry-standard for 'let winners run' partial models — leg 2's R is measured from the original risk, not a re-based risk). (B) **re-based leg-2 risk** — same weighting, but leg 2's R denominator uses a moved/breakeven stop; explicitly OUT OF SCOPE per triage ('breakeven-after-partial' excluded), so (A) is the scope-consistent default. Trading-cost (REQ-48) treatment also needs a decision: apply `trading_cost_price` once per leg (two partial fills = two costs) or once per trade (current single-fill assumption)."
  why_it_matters: "This IS the change's headline output — the blended-R convention determines the winrate/R number the whole change exists to produce (context: the paused confluence-gate program decision, obs #479, is waiting on real methodology numbers). Defaulting silently here would produce a number nobody explicitly chose and reproduce the exact 'measured the wrong thing' risk this project already hit once (obs #303's counterfactual)."
- type: technical
  question: "Default partial-exit position fraction: the source material (charter-2 [00:18:46], charter-3 [00:09:44]) specifies the 50% PRICE level (equilibrium) precisely but never states what fraction of position size closes there — 50%/50% is the common real-world convention but is not sourced from any charter. What default should `BacktestConfig` ship, and should it be user-overridable via a new CLI flag (mirroring REQ-51's pattern)?"
  why_it_matters: "Silently defaulting an unsourced number changes the reported winrate/R without disclosure — the same 'disclosed but not obviously legible' failure mode flagged as a lesson in the prior archive (obs #399, lesson 4)."
- type: technical
  question: "Can the partial level (`(htf_context.high + htf_context.low) / 2`) or the stop ever land on the 'wrong side' of entry for an aligned signal (e.g., partial level below entry for a bullish trade, or stop above the partial level)? Reading `stop_loss()`/`take_profit()` suggests the purge-then-reversal invariant (entry occurs at/beyond the swept extreme, target is the OPPOSITE extreme) structurally orders `stop < entry <= htf_context.low < midpoint < htf_context.high = target` for bullish trades (mirrored for bearish) — but this was not found asserted anywhere as an explicit invariant or property test. Should design add a defensive check/property test, or is confirming the ordering already implied by `_rr_floor_cut`'s R:R filter (a candidate with `midpoint` on the wrong side would also fail R:R) sufficient?"
  why_it_matters: "If the ordering assumption is wrong for even a small subset of real signals, the two-stage resolution logic silently produces nonsensical results (e.g., a 'partial' that closes at a worse price than the stop) instead of failing loudly."

## Ready for Proposal

**Status**: partial
**Halt routing**: n/a
**Reason**: The codebase investigation is complete and one clear, precedent-fitting approach exists (Approach 1) — no architectural blocker, no sensitive-area conflict, no scope surprise. The three open questions above are real, triage-flagged design-blocking product/technical decisions (blended-R convention, default partial fraction, ordering-invariant confidence) that sdd-propose/sdd-spec must resolve explicitly rather than default silently; that is the only reason this is `partial` rather than `yes`.
**Recommended action**: Proceed to `sdd-propose`, carrying the three open questions forward verbatim into the proposal's open-decisions section (or resolved with explicit user input first, per the orchestrator's problem-gate/open-question routing) before `sdd-spec` commits to REQ-IDs.
