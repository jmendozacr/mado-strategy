# Proposal + Spec: Backtest Two-Stage (Partial) Exit Model

> M light pipeline — merged propose+spec artefact (one signature). Identical content persisted to `proposal.md` and `spec.md`.

## Intent

This session measured the current single-fixed-TP backtest engine against real EURUSDm/GBPUSDm/DXYm data: 23-27% winrate, no measurable confluence-gate edge. Mado's actual, self-reported ~75%-winrate method is not single-TP — charter-2 [00:18:46] and charter-3 [00:09:44]/[00:13:55] both state the exit is "100% del rango **o** parciales en el 50% (Equilibrium)": a partial exit at the CRT range midpoint, remainder riding to the existing full-range target. The current engine has no notion of this — every trade is a binary full-TP-or-full-SL outcome, which means today's 23-27% number is measuring the WRONG model, not necessarily a wrong methodology. This change implements the real two-stage model so the winrate/R comparison this project needs is measuring what Mado actually does.

## Scope (in/out)

```yaml
in_scope:
  - Two-stage exit: partial at the midpoint between the trade's own entry price and take-profit target (REVISED — see REQ-68; previously described here as the H4 CRT range's own midpoint, but REQ-70's property test found that formula violates the ordering invariant on 6.7-12.6% of real candidates across the 3-instrument corpus), default 50% of position size, remainder riding to the existing full-range target/stop (unchanged, REQ-32/44).
  - Blended R-multiple for a partial-then-remainder trade: fraction-weighted sum of two independently-resolved legs, both measured against the ORIGINAL entry/stop (no re-basing) — consistent with breakeven-after-partial being out of scope.
  - Extended trades.csv/metrics_summary fields disclosing the partial leg explicitly (no silent folding into the existing r_multiple column).
  - Partial-price ordering safety guarantee (property-tested), so a malformed partial (worse than entry/stop) fails loudly instead of silently corrupting a trade's numbers.
  - `--partial-fraction` CLI override (mirrors the existing REQ-51 BacktestConfig-flag pattern); `0.0` reproduces today's single-TP behavior exactly, giving a built-in comparability lever.
  - Comparable real-data run (EURUSDm, GBPUSDm, DXYm) producing a winrate/R number for the two-stage model, directly comparable to today's single-TP numbers.
out_of_scope:
  - Trailing stops / breakeven-after-partial (stop stays at its original level for leg 2).
  - More than one partial level.
  - Full equity-curve/drawdown tracking.
  - Confluence-gate/Key Level crediting logic changes.
  - Lot-size/position-sizing realism beyond the simple fraction abstraction (`partial_fraction`).
  - A separate enable/disable toggle for the feature — `partial_fraction=0.0` already covers "off".
```

### Scope Admission

| Item | Admission | Destination |
|---|---|---|
| Two-stage exit mechanism (midpoint level, third sweep, SL-wins-ties extension) | product-guarantee | REQ-68 |
| Blended R-multiple + proportional cost allocation | product-guarantee | REQ-69 |
| Partial-price ordering guarantee (property test) | safety-guarantee — required to make the two-stage exit safe (explore's open question #3) | REQ-70 |
| trades.csv trailing columns + metrics_summary partial-exit count | product-guarantee (disclosure, per triage's explicit "no silent folding" scope item) | REQ-45, REQ-49 (MODIFIED) |
| `--partial-fraction` CLI flag, default 0.5 | product-guarantee | REQ-51 (MODIFIED) |
| `Trade` gains 4 optional partial-leg fields; outcome still win/loss/open | product-guarantee | REQ-38 (MODIFIED) |
| Real-data comparison run | test-evidence | Success Criteria (not a REQ) |
| Position-sizing realism, trailing stops, 2nd partial level | reject / follow-up | Out of Scope |

## Capabilities

### New Capabilities
None — this extends the existing backtest domains; no new bounded context is introduced.

### Modified Capabilities
- `backtest-simulation`: trade resolution gains a second, partial exit leg (REQ-68), a blended R-multiple with proportional cost allocation (REQ-69), a partial-price ordering guarantee (REQ-70), and extended `Trade` fields (REQ-38).
- `backtest-metrics` / `cli-output-filtering`: `trades.csv` gains 4 trailing disclosure columns (REQ-45) and `metrics_summary` gains a partial-exit count line (REQ-49); `BacktestConfig` CLI overrides gain a 6th flag (REQ-51).

## Approach

`backtest/levels.py` gains a `partial_price(entry_price, take_profit) -> float` function — `(entry_price + take_profit) / 2`, the midpoint between the trade's own entry and its target (REVISED — see REQ-68; an earlier shape, `partial_price(htf_context, direction) -> float` computing `(htf_context.high + htf_context.low) / 2`, is superseded because REQ-70's property test found it violates the ordering invariant on real data). This is a signature change from the function's original shape — callers pass `entry_price`/`take_profit` instead of `htf_context`; `sdd-design` must formalize the new call site at `backtest/simulate.py::_build_candidate` (currently `pp = _partial_price(tagged.htf_context, signal.direction)`). `backtest/simulate.py`'s `_resolve_exits` gains a third `two_heap_sweep` pass (`_partial_sides()`, mirroring `_tp_sides()`'s same-side monotonic geometry) alongside the existing SL/TP passes, all still eligible at `fill_index + 1` (REQ-37, unchanged). `_resolve_trade` extends its fixed-order resolution: SL winning at-or-before the partial index (REQ-33's existing pessimistic tie-break, now generalized to "SL wins ties against whichever level would otherwise resolve first") collapses to today's single-leg outcome exactly — no partial recorded. Otherwise, leg 1 closes at the partial price (or gap-open, reusing `_exit_gap_beyond`/REQ-34 unchanged), and leg 2 re-resolves the SAME original stop/target from `partial_index + 1` onward via the existing SL/TP sweep results, sliced to indices after the partial. `net_r_multiple` (REQ-48) is called per leg unchanged; `_resolve_trade` blends the two per REQ-69. `BacktestConfig.partial_fraction: float = 0.5` is the only new config field — no separate enable/disable flag, since `0.0` already collapses to today's exact behavior (verified by REQ-68.5/REQ-51.4 as a byte-identical regression check). `viz/trades_table.py`'s `_TRADES_HEADER` grows by 4 trailing columns, matching the append-only precedent `detections.csv`'s `key_level_source` column already established. `take_profit()` (REQ-32/44) and `min_risk_reward` (REQ-35, `2.0` default) are NOT touched — both are already correct per the real strategy.

The partial-price ordering guarantee (REQ-70) is a property test over the real 3-instrument corpus, not a new runtime exclusion bucket. Running it against the original H4-range-midpoint formula found real violations — 6.7% (EURUSDm), 8.4% (GBPUSDm), 12.6% (DXYm) of RR-floor-surviving candidates, not a rare edge case — so the formula itself was corrected (REQ-68) rather than adding a defensive branch around a known-broken derivation. The corrected `(entry_price + take_profit) / 2` formula satisfies REQ-70's invariant BY CONSTRUCTION, since `entry_price` and `take_profit` are already correctly ordered by REQ-35's existing R:R floor — the property test is expected to now pass with zero violations, and stays in place as a regression guard rather than a discovery tool.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `detector/backtest/levels.py` | Modified | `partial_price()` derivation; `net_r_multiple` reused per-leg (REQ-68/69) |
| `detector/backtest/simulate.py` | Modified | third sweep pass, two-stage `_resolve_trade`, `Trade` gains 4 fields (REQ-68/38) |
| `detector/backtest/metrics.py` | Modified | `metrics_summary` disclosure gains partial-exit count (REQ-49) |
| `detector/core/config.py` | Modified | `BacktestConfig.partial_fraction: float = 0.5` (REQ-51) |
| `detector/viz/trades_table.py` | Modified | `trades.csv` header 13 → 17 columns (REQ-45) |
| `detector/cli.py` | Modified | `--partial-fraction` flag wiring + validation (REQ-51) |
| `detector/primitives/crt_range.py` | Unaffected | No longer read by `partial_price()` (REVISED — now derives from `entry_price`/`take_profit`, not the HTF range; REQ-68). `take_profit()` (REQ-32/44) still reads it, unchanged. |
| `detector/tests/test_backtest_*`, `test_cli_backtest_e2e.py`, `test_viz.py` | Modified | new TDD coverage per REQ-68/69/70 scenarios |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Combining two independently-resolved legs into one net trade result has no existing sibling in this codebase | Medium | REQ-68 fully specifies the resolution order, reusing REQ-33's pessimistic-tie precedent as the template rather than inventing new ambiguity rules |
| `Trade`/`trades.csv` schema change is a downstream contract change (REQ-38/45), not purely additive | Medium | Both are append-only (new trailing fields/columns), and REQ-38.3/REQ-45.5 pin that a non-partial trade's new fields stay `None`/blank — no regression for the majority case |
| Blended-R convention (fraction-weighted, non-rebased legs) is a real modeling decision that determines the headline winrate/R number this change exists to produce | Medium | Resolved explicitly in REQ-69 rather than left to `sdd-design`; matches industry-standard "let winners run" partial-model convention, and is the scope-consistent default given breakeven-after-partial is out of scope |
| Ordering invariant (`stop < entry < partial_price < target`, direction-adjusted) not previously guaranteed structurally | Low (was realized: REQ-70's property test measured 6.7-12.6% real violations under the original H4-range-midpoint formula, prompting REQ-68's revision) | REQ-68's corrected `(entry_price + take_profit) / 2` formula satisfies the invariant BY CONSTRUCTION via REQ-35's existing R:R floor; REQ-70's property test now guards against regression rather than discovering violations |

## Rollback Plan

This is a Python CLI over local CSV files — no deployed service, no database, no running users, no migrations. All changes are either purely additive (new `Trade`/CSV fields, new `BacktestConfig` field, new CLI flag) or internal to `_resolve_trade`'s resolution order (no persisted state). Rollback is a plain `git revert` of the change's commit(s): `detections.csv`, `trades.csv`, and `overlay.png` are all regenerated artefacts recreated fresh on the next run, so there is no partial-state risk and nothing external depends on the old behavior mid-flight. Validation: re-run the existing test suite (`uv run pytest`) and `uv run lint-imports` post-revert — both green confirms the revert is complete. No data is lost by reverting: the real-data evidence produced by this change (winrate/R comparison numbers) is captured in the change's evidence file independently of the code.

## Dependencies

None.

## Success Criteria

- [ ] All REQ-68, REQ-69, REQ-70, REQ-38, REQ-45, REQ-49, REQ-51 scenarios pass.
- [ ] `uv run lint-imports` passes (layering respected — no new cross-layer import).
- [ ] REQ-68.5/REQ-51.4 regression check: a `--partial-fraction 0.0` run produces trade-for-trade, r_multiple-for-r_multiple byte-identical output to the pre-this-change single-TP engine on the same input.
- [ ] REQ-70's property test passes against the real EURUSDm/GBPUSDm/DXYm corpus with zero violations.
- [ ] Real-data run completes on EURUSDm/GBPUSDm/DXYm producing a winrate/R number for the two-stage model at `partial_fraction=0.5` (default), directly comparable to this session's single-TP baseline (23-27% winrate).

## Requirements

**Spec version**: V3 (REQ-45/REQ-49/REQ-51 MODIFIED blocks repaired — full original requirement + all original scenarios restored ahead of each edit, per `sdd-archive`'s `destructive-sync-rejected` halt; REQ-38's already-correct block used as template. REQ-68's V2 formula revision is unchanged by this correction.)
**Status**: signed (2026-09-04; V3 correction is mechanical — no new product decision, same sign-off stands)

### REQ-68 (NEW): Two-stage (partial) exit detection and resolution
For every trade candidate reaching the exit-resolution stage (REQ-37), the system MUST additionally compute `partial_price = (entry_price + take_profit) / 2` — the midpoint between the trade's OWN entry price and its OWN take-profit target (REQ-32/44), not any HTF-range-level derivation. (Previously: `partial_price = (htf_context.high + htf_context.low) / 2`, the H4 range's own midpoint — REVISED after REQ-70's property test found this violates the ordering invariant on 6.7% (EURUSDm), 8.4% (GBPUSDm), and 12.6% (DXYm) of real RR-floor-surviving trade candidates across the 3-instrument corpus — not a rare edge case. Root cause: the H4 range's midpoint has no structural relationship to the LTF trade's own entry/stop, which are anchored to LTF-local swing structure.) Because `entry_price` and `take_profit` are already correctly ordered for every candidate reaching this stage (REQ-35's R:R floor requires a positive-reward configuration), the revised formula guarantees `entry_price` strictly between `stop_loss` and `partial_price`, and `partial_price` strictly between `entry_price` and `take_profit` (direction-adjusted) BY CONSTRUCTION — REQ-70's ordering invariant (unchanged by this revision) now holds structurally rather than incidentally. Starting the sweep at `fill_index + 1` (unchanged), the system searches for the first index touching `partial_price` alongside the existing SL and TP searches. WHEN the stop-loss level would resolve at or before the partial level (SL wins ties, extending REQ-33's existing pessimistic precedent to this third level), the trade resolves as a SINGLE-LEG outcome exactly as it did before this change — no partial leg is recorded. OTHERWISE (the partial level resolves strictly before the stop-loss), leg 1 closes at `partial_price` (or the gap-open price per REQ-34's existing rule, applied identically to this level) at that index, and a second leg resolves the SAME, UNCHANGED original stop-loss and take-profit — never moved or re-based — starting at the partial's resolving index + 1, using REQ-33's existing SL-vs-TP pessimistic tie-break unmodified for leg 2's own resolution. `BacktestConfig.partial_fraction` (REQ-51) sets the position-size fraction closing at leg 1; `partial_fraction=0.0` MUST make leg 1 never eligible to fire, collapsing every trade to the exact single-leg resolution this codebase produced before this change.
- **REQ-68.1** (happy, two-leg win-then-win): GIVEN a candidate whose partial level resolves at index 50 (before SL) and whose remainder then resolves at the original take-profit at index 80, WHEN resolved, THEN leg 1 closes at `partial_price` (index 50), leg 2 closes at `take_profit` (index 80), and both leg exits are recorded.
- **REQ-68.2** (happy, two-leg win-then-loss): GIVEN the same partial firing at index 50, but the remainder then resolves at the ORIGINAL stop-loss at index 90 (not moved), WHEN resolved, THEN leg 2 closes at `stop_loss` — the stop was never re-based after the partial fired.
- **REQ-68.3** (edge, SL wins the tie — no partial): GIVEN a candle in which stop-loss and the partial level would resolve at the same index, or stop-loss resolves at an earlier index than the partial, WHEN resolved, THEN the trade resolves as a single-leg loss at the stop-loss price — no partial leg is recorded, matching this codebase's exact pre-this-change behavior for that candidate.
- **REQ-68.4** (edge, gap-through partial): GIVEN the resolving candle's open price already lies beyond `partial_price`, WHEN leg 1 is resolved, THEN it fills at the candle's actual open price, not at `partial_price` itself (REQ-34, applied identically).
- **REQ-68.5** (edge, `partial_fraction=0.0` regression): GIVEN `BacktestConfig.partial_fraction=0.0`, WHEN any candidate is resolved, THEN the resulting `Trade` (outcome, exit_index, exit_price, r_multiple) is byte-identical to resolving the SAME candidate with this change's code entirely absent.
- **REQ-68.6** (edge, never touched): GIVEN neither SL, TP, nor the partial level is ever touched by series end, WHEN resolved, THEN the trade remains `outcome="open"` with no partial leg recorded (mirrors REQ-38.1).

### REQ-69 (NEW): Blended R-multiple and proportional cost allocation
WHEN a trade resolves with a partial leg (REQ-68), the system MUST compute the trade's `r_multiple` as `partial_fraction * R_leg1 + (1 - partial_fraction) * R_leg2`, where `R_leg1` and `R_leg2` are each computed via the existing `net_r_multiple` formula (REQ-48), BOTH measured against the trade's ORIGINAL, unchanged `entry_price` and `stop_loss` — leg 2's risk is never re-based to a moved or breakeven stop, consistent with trailing-stops/breakeven-after-partial being explicitly out of scope. `trading_cost_price` (REQ-48) MUST be allocated proportionally across the two legs — `partial_fraction * trading_cost_price` netted from leg 1, the remainder from leg 2 — so the TOTAL cost netted across both legs equals exactly `trading_cost_price`, never double-counted and never dropped.
- **REQ-69.1** (happy): GIVEN `partial_fraction=0.5`, `R_leg1=+1.5` (partial always profitable when it fires, since it only fires after price has moved favorably), `R_leg2=-1.0`, WHEN blended, THEN `r_multiple = 0.5*1.5 + 0.5*(-1.0) = 0.25`.
- **REQ-69.2** (edge, cost-default neutrality): GIVEN the default `trading_cost_price=0.0`, WHEN a two-leg trade's blended `r_multiple` is computed, THEN it is bit-identical to a zero-cost computation, regardless of `partial_fraction`.
- **REQ-69.3** (edge, single-leg trade unaffected): GIVEN a trade that resolves single-leg (REQ-68.3, SL wins the tie, or no partial ever configured), WHEN `r_multiple` is computed, THEN it uses the existing REQ-48 formula EXACTLY as before this change — no blending, full `trading_cost_price` applied once.

### REQ-70 (NEW): Partial-price ordering guarantee
For every trade candidate that survives the R:R floor filter (REQ-35), the system MUST guarantee `partial_price` (REQ-68) lies strictly between `entry_price` and `take_profit` on the favorable side of the trade, and strictly on the favorable side of `stop_loss` — i.e., a partial exit is never priced worse than holding to the stop, and never behind entry. This MUST be verified by an explicit property test run against the real 3-instrument corpus (EURUSDm, GBPUSDm, DXYm), not assumed. If the property is ever falsified for a real candidate, the test MUST fail explicitly, naming the offending candidate — the resolution logic MUST NOT silently emit a nonsensical partial.
- **REQ-70.1** (property test): GIVEN every real trade candidate surviving REQ-35's floor across the 3-instrument corpus, WHEN direction-adjusted ordering is checked, THEN `stop_loss` is strictly worse than `entry_price`, which is strictly worse than `partial_price`, which is strictly worse than `take_profit`, for every single candidate.
- **REQ-70.2** (edge, loud failure): GIVEN a hypothetical candidate constructed to violate this ordering, WHEN the property test runs against it, THEN it fails explicitly identifying that candidate — never silently excluded or skipped.

### REQ-38 (MODIFIED — reopens signed REQ-38): Trade terminal states gain partial-leg disclosure fields

**Original REQ-38**: "Every simulated trade MUST resolve to EXACTLY one of three terminal states: `win`, `loss`, or `open` (neither SL nor TP touched by series end). An `open` trade MUST have `exit_index=None`, `exit_price=None`, `r_multiple=None`, `ambiguous_bar=False`, `gap_filled=False`."

**MODIFIED REQ-38**: The three terminal states remain the ONLY three — REQ-68's two-stage resolution does not add a fourth state; a two-leg trade still resolves to `win` or `loss` based on the SIGN of its `r_multiple` (REQ-69's blended figure when a partial fired, REQ-48's unmodified figure otherwise). `Trade` gains four new fields disclosing the partial leg: `partial_exit_index: int | None`, `partial_exit_price: float | None`, `partial_r_multiple: float | None`, `partial_gap_filled: bool` — ALL `None`/`False` when no partial fired, including every `open` trade and every single-leg `win`/`loss` trade.
- **REQ-38.1** (unchanged, open trade): GIVEN a trade whose SL, TP, and partial level are never touched, WHEN simulation ends, THEN `outcome="open"`, all exit fields (including the 4 new partial fields) are `None`/`False`.
- **REQ-38.2** (NEW, blended sign determines outcome): GIVEN a two-leg trade whose blended `r_multiple` (REQ-69) is `+0.25`, WHEN resolved, THEN `outcome="win"` — the same sign rule REQ-38's original text already applied to a single figure now applies to the blended one.
- **REQ-38.3** (NEW, no-partial fields stay empty): GIVEN a single-leg trade (REQ-68.3's SL-wins-tie case, or `partial_fraction=0.0`), WHEN resolved, THEN all four new partial-leg fields are `None`/`False`.

### REQ-45 (MODIFIED — reopens signed REQ-45): `trades.csv` gains 4 trailing partial-disclosure columns

**Original REQ-45**: "The system MUST accept a `--backtest` boolean flag, composable with the existing `--from-date`/`--to-date`/`--session`/`--types` filter chain. WHEN `--backtest` is supplied, the system MUST write `trades.csv` with exactly these 13 columns in this order: `signal_id, anchor_timestamp, entry_timestamp, direction, entry_price, stop_loss, take_profit, exit_timestamp, exit_price, outcome, r_multiple, ambiguous_bar, gap_filled`. WHEN `--backtest` is supplied, `detections.csv` gains a trailing `signal_id` column (REQ-41) and no other change; `overlay.png` is unaffected. WHEN `--backtest` is NOT supplied, the system MUST reproduce today's exact byte-for-byte output for both `detections.csv` and `overlay.png` — no carve-out applies."
- **REQ-45.1** (happy, regression): GIVEN `--session ny-killzone --backtest`, WHEN the run completes, THEN trades are filtered accordingly AND `overlay.png` is byte-identical to an equivalent non-backtest run.
- **REQ-45.2** (edge, contract): GIVEN any `--backtest` run producing at least one trade, WHEN `trades.csv` is inspected, THEN its header is exactly the 13 columns above in that order, and `entry_timestamp` is the timestamp of the candle at `fill_index` (REQ-50).
- **REQ-45.3** (edge, byte-for-byte without carve-out): GIVEN a detector run WITHOUT `--backtest`, WHEN `detections.csv` and `overlay.png` are inspected, THEN both are byte-for-byte identical to the equivalent pre-backtest-feature output, with no `signal_id` column present in `detections.csv`.

**MODIFIED REQ-45**: The `--backtest` flag, its filter-chain composability, the `detections.csv`/`overlay.png` carve-out-free behavior, and the byte-for-byte non-backtest guarantee all remain unchanged. `trades.csv` gains 4 trailing columns — 17 total: the 13 above plus `partial_exit_timestamp, partial_exit_price, partial_r_multiple, partial_gap_filled` (append-only, mirroring `detections.csv`'s own `key_level_source` trailing-column precedent, REQ-24). Cells are blank/`False` for a trade with no partial leg (REQ-38.3). (Previously: header was exactly 13 columns, with no partial-leg disclosure.)
- **REQ-45.1** (unchanged, happy, regression): GIVEN `--session ny-killzone --backtest`, WHEN the run completes, THEN trades are filtered accordingly AND `overlay.png` is byte-identical to an equivalent non-backtest run.
- **REQ-45.2** (UPDATED — column count 13→17 to match this change's own edit; edge, contract): GIVEN any `--backtest` run producing at least one trade, WHEN `trades.csv` is inspected, THEN its header is exactly the 17 columns above in that order, and `entry_timestamp` is the timestamp of the candle at `fill_index` (REQ-50).
- **REQ-45.3** (unchanged, edge, byte-for-byte without carve-out): GIVEN a detector run WITHOUT `--backtest`, WHEN `detections.csv` and `overlay.png` are inspected, THEN both are byte-for-byte identical to the equivalent pre-backtest-feature output, with no `signal_id` column present in `detections.csv`.
- **REQ-45.4** (NEW, contract): GIVEN any `--backtest` run, WHEN `trades.csv` is inspected, THEN its header is exactly the 17 columns above, in that order.
- **REQ-45.5** (NEW, disclosure): GIVEN a trade whose partial leg fired, WHEN its `trades.csv` row is inspected, THEN its 4 trailing cells are populated; GIVEN a trade with no partial leg, THEN those same 4 cells are blank/`False`.

### REQ-49 (MODIFIED — reopens signed REQ-49): Aggregate profitability disclosure gains partial-exit count

**Original REQ-49**: "`metrics_summary` MUST report an aggregate profitability figure alongside per-trade metrics: the AVERAGE `r_multiple` across all CLOSED trades, AND the TOTAL R (sum) — both `None`/"n/a" when zero trades have closed. Both figures MUST be accompanied by an explicit note that they assume unlimited capital with no cap on concurrently open positions. `metrics_summary` MUST also disclose the count of trades still `open` at series end as its own explicit line."
- **REQ-49.1** (happy): GIVEN 3 closed trades with r_multiples `+2, +2, -1`, WHEN aggregate profitability is computed, THEN `average_r_multiple=1.0` and `total_r=3.0`.
- **REQ-49.2** (edge, no substitution): GIVEN zero closed trades, WHEN aggregate profitability is computed, THEN both figures are "n/a" — never `0.0`.
- **REQ-49.3** (edge, disclosure wording): GIVEN 5 closed trades averaging `1.0`, WHEN `metrics_summary` is written, THEN it states the average "over 5 closed trades" plus the unlimited-capital note.
- **REQ-49.4** (edge): GIVEN a run in which 7 trades remain `open` at series end, WHEN `metrics_summary` is written, THEN it includes an explicit "open trades: 7" line.

**MODIFIED REQ-49**: The average/total-R figures, the unlimited-capital note, and the open-trades count line all remain unchanged. `metrics_summary` MUST additionally disclose the count of trades whose partial leg fired (REQ-68), as its own explicit line, distinct from the open-trades count. (Previously: no partial-exit count line.)
- **REQ-49.1** (unchanged, happy): GIVEN 3 closed trades with r_multiples `+2, +2, -1`, WHEN aggregate profitability is computed, THEN `average_r_multiple=1.0` and `total_r=3.0`.
- **REQ-49.2** (unchanged, edge, no substitution): GIVEN zero closed trades, WHEN aggregate profitability is computed, THEN both figures are "n/a" — never `0.0`.
- **REQ-49.3** (unchanged, edge, disclosure wording): GIVEN 5 closed trades averaging `1.0`, WHEN `metrics_summary` is written, THEN it states the average "over 5 closed trades" plus the unlimited-capital note.
- **REQ-49.4** (unchanged, edge): GIVEN a run in which 7 trades remain `open` at series end, WHEN `metrics_summary` is written, THEN it includes an explicit "open trades: 7" line.
- **REQ-49.5** (NEW): GIVEN a run in which 4 trades fired a partial exit, WHEN `metrics_summary` is written, THEN it includes an explicit "partial exits: 4" line.

### REQ-51 (MODIFIED — reopens signed REQ-51): BacktestConfig CLI overrides gain a 6th flag

**Original REQ-51**: "The system MUST accept 5 CLI flags, each overriding exactly one `BacktestConfig` field when `--backtest` is used, falling back to that field's default when the flag is omitted: `--sl-buffer` (REQ-31's `sl_buffer_price`, default `0.0002`, a raw price-unit offset, never a pip count), `--min-rr` (REQ-35's `min_risk_reward`), `--trading-cost` (REQ-48's `trading_cost_price`), `--kill-zone-gated` (REQ-36's gate, boolean), `--max-fill-wait` (REQ-50's `max_fill_wait`). 1:1 flag-to-field mapping — no new configuration abstraction beyond it."
- **REQ-51.1** (happy): GIVEN `--backtest --min-rr 3.0`, WHEN a run executes, THEN `excluded_rr_floor` is computed against `3.0`, not the `2.0` default, and downstream trade counts differ measurably from an equivalent run using the `2.0` default on the same input.
- **REQ-51.2** (edge): GIVEN `--backtest` with none of the 5 override flags supplied, WHEN a run executes, THEN all 5 fields use `BacktestConfig`'s defaults, producing output identical to a run with all 5 flags set explicitly to those same default values.
- **REQ-51.3** (edge): GIVEN `--backtest` invoked with an override flag value that violates that flag's constraint — `--max-fill-wait` set to zero or negative, or `--sl-buffer`, `--min-rr`, or `--trading-cost` set to a negative value — WHEN the run starts, THEN the system MUST reject with exit 1, naming the offending flag and the constraint it violates.

**MODIFIED REQ-51**: The system now accepts 6 CLI flags — the original 5 above (unchanged: `--sl-buffer`, `--min-rr`, `--trading-cost`, `--kill-zone-gated`, `--max-fill-wait`, each still 1:1 to its `BacktestConfig` field with the same defaults) plus a 6th, `--partial-fraction`, overriding `BacktestConfig.partial_fraction` (REQ-68, default `0.5`), valid range `[0.0, 1.0)` — `1.0` is rejected as degenerate (no remainder leg would exist). Still a strict 1:1 flag-to-field mapping — no new configuration abstraction beyond it. (Previously: 5 flags, no `--partial-fraction`.)
- **REQ-51.1** (unchanged, happy): GIVEN `--backtest --min-rr 3.0`, WHEN a run executes, THEN `excluded_rr_floor` is computed against `3.0`, not the `2.0` default, and downstream trade counts differ measurably from an equivalent run using the `2.0` default on the same input.
- **REQ-51.2** (UPDATED — flag/field count 5→6 to match this change's own edit; edge): GIVEN `--backtest` with none of the 6 override flags supplied, WHEN a run executes, THEN all 6 fields use `BacktestConfig`'s defaults, producing output identical to a run with all 6 flags set explicitly to those same default values.
- **REQ-51.3** (unchanged, edge): GIVEN `--backtest` invoked with an override flag value that violates that flag's constraint — `--max-fill-wait` set to zero or negative, or `--sl-buffer`, `--min-rr`, or `--trading-cost` set to a negative value — WHEN the run starts, THEN the system MUST reject with exit 1, naming the offending flag and the constraint it violates.
- **REQ-51.4** (NEW, happy, comparability escape hatch): GIVEN `--backtest --partial-fraction 0.0`, WHEN a run executes, THEN it reproduces, trade-for-trade, the exact single-TP outcomes and r_multiples this codebase produced before this change (REQ-68.5).
- **REQ-51.5** (NEW, edge, validation): GIVEN `--partial-fraction` supplied with a negative value or a value `>= 1.0`, WHEN the run starts, THEN the system MUST reject with exit 1, naming the flag and the constraint violated (mirrors REQ-51.3's existing pattern).
